import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { RiCameraLine } from '@remixicon/react'
import ActionButton from '@/app/components/base/action-button'
import { useFile } from '../hooks'
import type { FileUpload } from '@/app/components/base/features/types'

type CameraButtonProps = {
  fileConfig: FileUpload;
  disabled?: boolean;
}

const CameraButton = ({ fileConfig, disabled }: CameraButtonProps) => {
  const { t } = useTranslation()
  const { handleLocalFileUpload } = useFile(fileConfig)

  const handleTakePhoto = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment', // Use back camera if available
        },
      })

      // Create a video element to capture the photo
      const video = document.createElement('video')
      video.srcObject = stream
      video.play()

      // Create a modal-like interface for taking the photo
      const modal = document.createElement('div')
      modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 10000;
      `

      const videoContainer = document.createElement('div')
      videoContainer.style.cssText = `
        position: relative;
        max-width: 90%;
        max-height: 70%;
        display: flex;
        flex-direction: column;
        align-items: center;
      `

      video.style.cssText = `
        max-width: 100%;
        max-height: 100%;
        border-radius: 8px;
      `

      const buttonContainer = document.createElement('div')
      buttonContainer.style.cssText = `
        margin-top: 20px;
        display: flex;
        gap: 10px;
      `

      const captureButton = document.createElement('button')
      captureButton.textContent = t('common.operation.capture')
      captureButton.style.cssText = `
        background: #155eef;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 16px;
      `

      const cancelButton = document.createElement('button')
      cancelButton.textContent = t('common.operation.cancel')
      cancelButton.style.cssText = `
        background: #6b7280;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 16px;
      `

      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')!

      const capturePhoto = () => {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        ctx.drawImage(video, 0, 0)

        canvas.toBlob(
          (blob) => {
            if (blob) {
              // Create a file from the blob
              const file = new File([blob], `photo_${Date.now()}.jpg`, {
                type: 'image/jpeg',
              })

              // Add the file to the file store using the proper handler
              handleLocalFileUpload(file)

              // Stop the camera stream
              stream.getTracks().forEach(track => track.stop())
              document.body.removeChild(modal)
            }
          },
          'image/jpeg',
          0.8,
        )
      }

      const cancelCapture = () => {
        stream.getTracks().forEach(track => track.stop())
        document.body.removeChild(modal)
      }

      captureButton.addEventListener('click', capturePhoto)
      cancelButton.addEventListener('click', cancelCapture)

      buttonContainer.appendChild(captureButton)
      buttonContainer.appendChild(cancelButton)
      videoContainer.appendChild(video)
      videoContainer.appendChild(buttonContainer)
      modal.appendChild(videoContainer)
      document.body.appendChild(modal)
    }
    catch (error) {
      console.error('Error accessing camera:', error)
    }
  }

  return (
    <ActionButton
      size="l"
      onClick={handleTakePhoto}
      disabled={disabled}
      title={t('common.fileUploader.takePhoto')}
    >
      <RiCameraLine className="h-5 w-5" />
    </ActionButton>
  )
}

export default memo(CameraButton)
