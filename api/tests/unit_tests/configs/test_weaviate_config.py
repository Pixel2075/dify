"""
Unit test to validate that WEAVIATE_BATCH_SIZE configuration is working correctly.
"""
import pytest
from unittest.mock import patch
from core.rag.datasource.vdb.weaviate.weaviate_vector import WeaviateConfig


def test_weaviate_config_default_batch_size():
    """Test that the default batch size is 50"""
    config = WeaviateConfig(endpoint="http://localhost:8080")
    assert config.batch_size == 50


def test_weaviate_config_custom_batch_size():
    """Test that custom batch size is accepted"""
    config = WeaviateConfig(endpoint="http://localhost:8080", batch_size=25)
    assert config.batch_size == 25


def test_weaviate_config_with_all_params():
    """Test that all parameters work together"""
    config = WeaviateConfig(
        endpoint="http://localhost:8080",
        api_key="test_key",
        batch_size=30
    )
    assert config.endpoint == "http://localhost:8080"
    assert config.api_key == "test_key"
    assert config.batch_size == 30


def test_weaviate_config_validation():
    """Test that batch_size must be positive"""
    # This should work
    config = WeaviateConfig(endpoint="http://localhost:8080", batch_size=1)
    assert config.batch_size == 1
    
    # Test that zero or negative values would be rejected by PositiveInt
    with pytest.raises(Exception):  # pydantic validation error
        WeaviateConfig(endpoint="http://localhost:8080", batch_size=0)
    
    with pytest.raises(Exception):  # pydantic validation error  
        WeaviateConfig(endpoint="http://localhost:8080", batch_size=-1)


def test_weaviate_config_environment_variable_integration(monkeypatch: pytest.MonkeyPatch):
    """Test that the DifyConfig picks up WEAVIATE_BATCH_SIZE from environment"""
    # Clear environment and set required variables
    monkeypatch.setenv("CONSOLE_API_URL", "https://example.com")
    monkeypatch.setenv("CONSOLE_WEB_URL", "https://example.com")
    monkeypatch.setenv("DB_USERNAME", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "postgres")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_DATABASE", "dify")
    
    # Test with custom batch size
    monkeypatch.setenv("WEAVIATE_BATCH_SIZE", "25")
    monkeypatch.setenv("WEAVIATE_ENDPOINT", "http://localhost:8080")
    
    from configs.app_config import DifyConfig
    config = DifyConfig()
    
    assert config.WEAVIATE_BATCH_SIZE == 25
    assert config.WEAVIATE_ENDPOINT == "http://localhost:8080"