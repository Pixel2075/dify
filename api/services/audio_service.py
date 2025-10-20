import io
import logging
import uuid
from collections.abc import Generator

from flask import Response, stream_with_context
from werkzeug.datastructures import FileStorage

from constants import AUDIO_EXTENSIONS
from core.model_manager import ModelManager
from core.model_runtime.entities.model_entities import ModelType
from extensions.ext_database import db
from models.enums import MessageStatus
from models.model import App, AppMode, Message
from services.errors.audio import (
    AudioTooLargeServiceError,
    NoAudioUploadedServiceError,
    ProviderNotSupportSpeechToTextServiceError,
    ProviderNotSupportTextToSpeechServiceError,
    UnsupportedAudioTypeServiceError,
)
from services.workflow_service import WorkflowService

FILE_SIZE = 30
FILE_SIZE_LIMIT = FILE_SIZE * 1024 * 1024

logger = logging.getLogger(__name__)


class AudioService:
    @classmethod
    def transcript_asr(cls, app_model: App, file: FileStorage, end_user: str | None = None):
        if app_model.mode in {AppMode.ADVANCED_CHAT, AppMode.WORKFLOW}:
            workflow = app_model.workflow
            if workflow is None:
                raise ValueError("Speech to text is not enabled")

            features_dict = workflow.features_dict
            if "speech_to_text" not in features_dict or not features_dict["speech_to_text"].get("enabled"):
                raise ValueError("Speech to text is not enabled")
        else:
            app_model_config = app_model.app_model_config
            if not app_model_config:
                raise ValueError("Speech to text is not enabled")

            if not app_model_config.speech_to_text_dict["enabled"]:
                raise ValueError("Speech to text is not enabled")

        if file is None:
            raise NoAudioUploadedServiceError()

        extension = file.mimetype
        if extension not in [f"audio/{ext}" for ext in AUDIO_EXTENSIONS]:
            raise UnsupportedAudioTypeServiceError()

        file_content = file.read()
        file_size = len(file_content)

        if file_size > FILE_SIZE_LIMIT:
            message = f"Audio size larger than {FILE_SIZE} mb"
            raise AudioTooLargeServiceError(message)

        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(
            tenant_id=app_model.tenant_id, model_type=ModelType.SPEECH2TEXT
        )
        if model_instance is None:
            raise ProviderNotSupportSpeechToTextServiceError()

        buffer = io.BytesIO(file_content)
        buffer.name = "temp.mp3"

        return {"text": model_instance.invoke_speech2text(file=buffer, user=end_user)}

    @classmethod
    def transcript_tts(
        cls,
        app_model: App,
        text: str | None = None,
        voice: str | None = None,
        end_user: str | None = None,
        message_id: str | None = None,
        is_draft: bool = False,
    ):
        from app import app

        def invoke_tts(text_content: str, app_model: App, voice: str | None = None, is_draft: bool = False):
            with app.app_context():
                if voice is None:
                    if app_model.mode in {AppMode.ADVANCED_CHAT, AppMode.WORKFLOW}:
                        if is_draft:
                            workflow = WorkflowService().get_draft_workflow(app_model=app_model)
                        else:
                            workflow = app_model.workflow
                        if (
                            workflow is None
                            or "text_to_speech" not in workflow.features_dict
                            or not workflow.features_dict["text_to_speech"].get("enabled")
                        ):
                            raise ValueError("TTS is not enabled")

                        voice = workflow.features_dict["text_to_speech"].get("voice")
                    else:
                        if not is_draft:
                            if app_model.app_model_config is None:
                                raise ValueError("AppModelConfig not found")
                            text_to_speech_dict = app_model.app_model_config.text_to_speech_dict

                            if not text_to_speech_dict.get("enabled"):
                                raise ValueError("TTS is not enabled")

                            voice = text_to_speech_dict.get("voice")

                model_manager = ModelManager()
                model_instance = model_manager.get_default_model_instance(
                    tenant_id=app_model.tenant_id, model_type=ModelType.TTS
                )
                try:
                    if not voice:
                        voices = model_instance.get_tts_voices()
                        if voices:
                            voice = voices[0].get("value")
                            if not voice:
                                raise ValueError("Sorry, no voice available.")
                        else:
                            raise ValueError("Sorry, no voice available.")

                    return model_instance.invoke_tts(
                        content_text=text_content.strip(), user=end_user, tenant_id=app_model.tenant_id, voice=voice
                    )
                except Exception as e:
                    raise e

        if message_id:
            import time
            try:
                uuid.UUID(message_id)
            except ValueError:
                logger.warning(f"Invalid message_id format: {message_id}")
                return None

            # Retry logic to handle race condition where message answer isn't saved yet
            max_retries = 5
            retry_delay = 0.5  # 500ms

            for attempt in range(max_retries):
                # Refresh session to get latest data from database
                db.session.expire_all()
                db.session.commit()  # Ensure any pending transactions are committed

                message = db.session.query(Message).where(Message.id == message_id).first()
                if message is None:
                    logger.warning(f"Message not found: {message_id}")
                    return None

                # Log the actual answer content for debugging
                answer_preview = message.answer[:100] if message.answer else "[EMPTY]"
                logger.info(f"Attempt {attempt + 1}/{max_retries}: message_id={message_id}, answer_field_length={len(message.answer)}")

                # Try to get the text content - check multiple possible sources
                text_content = None

                # First try: answer field
                if message.answer and message.answer.strip():
                    text_content = message.answer
                    logger.info(f"Using answer field for TTS, length={len(text_content)}")
                # Second try: parse message JSON for assistant response
                elif hasattr(message, 'message') and message.message:
                    try:
                        logger.info(f"Message JSON type: {type(message.message)}, content: {str(message.message)[:500]}")
                        if isinstance(message.message, list):
                            # Look for the LAST assistant role message (most recent response)
                            assistant_messages = []
                            for msg in message.message:
                                if isinstance(msg, dict):
                                    msg_role = msg.get('role', 'NO_ROLE')
                                    logger.info(f"Found message with role: {msg_role}")
                                    if msg_role == 'assistant':
                                        msg_text = msg.get('text', '') or msg.get('content', '')
                                        assistant_messages.append(msg_text)

                            # Use the LAST assistant message (most recent)
                            if assistant_messages:
                                text_content = assistant_messages[-1]
                                logger.info(f"Found {len(assistant_messages)} assistant messages, using last one with length={len(text_content)}")
                        elif isinstance(message.message, dict):
                            # If message is a dict, check if it has the text directly
                            text_content = message.message.get('text', '') or message.message.get('content', '')
                            if text_content:
                                logger.info(f"Found text in message dict, length={len(text_content)}")
                    except Exception as e:
                        logger.warning(f"Error parsing message JSON: {e}")
                else:
                    logger.warning(f"No message JSON field found or it's None/empty")

                # If we found text content, proceed with TTS
                if text_content and text_content.strip():
                    response = invoke_tts(text_content=text_content, app_model=app_model, voice=voice, is_draft=is_draft)
                    if isinstance(response, Generator):
                        return Response(stream_with_context(response), content_type="audio/mpeg")
                    return response

                # If answer is empty and we have more retries, wait and try again
                if attempt < max_retries - 1:
                    logger.info(f"Message answer empty on attempt {attempt + 1}/{max_retries}, retrying... message_id: {message_id}")
                    time.sleep(retry_delay)
                else:
                    # Last attempt and still empty
                    logger.warning(f"Message answer is empty after {attempt + 1} attempts, status: {message.status}, message_id: {message_id}")
                    return None
        else:
            if text is None:
                raise ValueError("Text is required")
            response = invoke_tts(text_content=text, app_model=app_model, voice=voice, is_draft=is_draft)
            if isinstance(response, Generator):
                return Response(stream_with_context(response), content_type="audio/mpeg")
            return response

    @classmethod
    def transcript_tts_voices(cls, tenant_id: str, language: str):
        model_manager = ModelManager()
        model_instance = model_manager.get_default_model_instance(tenant_id=tenant_id, model_type=ModelType.TTS)
        if model_instance is None:
            raise ProviderNotSupportTextToSpeechServiceError()

        try:
            return model_instance.get_tts_voices(language)
        except Exception as e:
            raise e
