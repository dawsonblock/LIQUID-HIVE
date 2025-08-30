"""
Test suite for production-grade secrets management
================================================
"""
import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from hivemind.secrets_manager import SecretsManager, SecretProvider


class TestSecretsManager:
    """Test the SecretsManager functionality."""
    
    def setup_method(self):
        """Setup for each test method."""
        # Clear any cached instances
        if hasattr(SecretsManager, '_instance'):
            delattr(SecretsManager, '_instance')
        
    def test_environment_fallback(self):
        """Test fallback to environment variables when other providers unavailable."""
        # Mock environment
        with patch.dict(os.environ, {'TEST_SECRET': 'test_value'}):
            # Mock unavailable providers
            with patch('hvac.Client') as mock_hvac:
                mock_hvac.side_effect = Exception("Vault unavailable")
                with patch('boto3.client') as mock_boto3:
                    mock_boto3.side_effect = Exception("AWS unavailable")
                    
                    manager = SecretsManager()
                    assert manager.get_provider() == SecretProvider.ENVIRONMENT
                    assert manager.get_secret('TEST_SECRET') == 'test_value'
    
    def test_vault_provider_initialization(self):
        """Test Vault provider initialization."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                mock_client.return_value = mock_instance
                
                manager = SecretsManager()
                assert manager.get_provider() == SecretProvider.VAULT
                assert manager._vault_client is not None
    
    def test_vault_secret_retrieval_kv_v2(self):
        """Test Vault secret retrieval with KV v2 engine."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                
                # Mock KV v2 response
                mock_instance.secrets.kv.v2.read_secret_version.return_value = {
                    'data': {
                        'data': {
                            'database_url': 'mongodb://localhost:27017/test'
                        }
                    }
                }
                mock_client.return_value = mock_instance
                
                manager = SecretsManager()
                secret = manager.get_secret('database/url')
                assert secret == 'mongodb://localhost:27017/test'
    
    def test_vault_secret_retrieval_kv_v1_fallback(self):
        """Test Vault secret retrieval fallback to KV v1."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                
                # Mock KV v2 failure, v1 success
                mock_instance.secrets.kv.v2.read_secret_version.side_effect = Exception("KV v2 not available")
                mock_instance.secrets.kv.v1.read_secret.return_value = {
                    'data': {
                        'database_url': 'mongodb://localhost:27017/test'
                    }
                }
                mock_client.return_value = mock_instance
                
                manager = SecretsManager()
                secret = manager.get_secret('database/url')
                assert secret == 'mongodb://localhost:27017/test'
    
    def test_aws_secrets_manager_initialization(self):
        """Test AWS Secrets Manager initialization."""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            # Mock successful connection test
            mock_client.describe_secret.side_effect = Exception("ResourceNotFoundException")
            mock_boto3.return_value = mock_client
            
            manager = SecretsManager()
            assert manager.get_provider() == SecretProvider.AWS_SECRETS_MANAGER
            assert manager._aws_client is not None
    
    def test_aws_secret_retrieval_json(self):
        """Test AWS Secrets Manager retrieval with JSON format."""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_client.describe_secret.side_effect = Exception("ResourceNotFoundException")  
            mock_client.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'username': 'admin',
                    'password': 'secret123'
                })
            }
            mock_boto3.return_value = mock_client
            
            manager = SecretsManager()
            secret = manager.get_secret('database/credentials')
            assert secret == {'username': 'admin', 'password': 'secret123'}
    
    def test_aws_secret_retrieval_string(self):
        """Test AWS Secrets Manager retrieval with string format."""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_client.describe_secret.side_effect = Exception("ResourceNotFoundException")
            mock_client.get_secret_value.return_value = {
                'SecretString': 'mongodb://localhost:27017/test'
            }
            mock_boto3.return_value = mock_client
            
            manager = SecretsManager()
            secret = manager.get_secret('database/url')
            assert secret == 'mongodb://localhost:27017/test'
    
    def test_secret_caching(self):
        """Test that secrets are cached after first retrieval."""
        with patch.dict(os.environ, {'TEST_SECRET': 'cached_value'}):
            with patch('hvac.Client') as mock_hvac:
                mock_hvac.side_effect = Exception("Vault unavailable")
                with patch('boto3.client') as mock_boto3:
                    mock_boto3.side_effect = Exception("AWS unavailable")
                    
                    manager = SecretsManager()
                    
                    # First retrieval should call environment
                    secret1 = manager.get_secret('TEST_SECRET')
                    assert secret1 == 'cached_value'
                    
                    # Second retrieval should use cache
                    with patch.dict(os.environ, {'TEST_SECRET': 'new_value'}):
                        secret2 = manager.get_secret('TEST_SECRET')
                        assert secret2 == 'cached_value'  # Should be cached value
    
    def test_database_url_helper(self):
        """Test the database URL helper method."""
        with patch.dict(os.environ, {'MONGO_URL': 'mongodb://test:27017/db'}):
            manager = SecretsManager()
            manager._provider = SecretProvider.ENVIRONMENT
            
            url = manager.get_database_url()
            assert url == 'mongodb://test:27017/db'
    
    def test_redis_url_helper(self):
        """Test the Redis URL helper method.""" 
        with patch.dict(os.environ, {'REDIS_URL': 'redis://test:6379'}):
            manager = SecretsManager()
            manager._provider = SecretProvider.ENVIRONMENT
            
            url = manager.get_redis_url()
            assert url == 'redis://test:6379'
    
    def test_vllm_config_helper(self):
        """Test the vLLM configuration helper method."""
        with patch.dict(os.environ, {
            'VLLM_ENDPOINT': 'http://vllm:8000',
            'VLLM_ENDPOINT_SMALL': 'http://vllm-small:8000',
            'VLLM_API_KEY': 'test-key'
        }):
            manager = SecretsManager()
            manager._provider = SecretProvider.ENVIRONMENT
            
            config = manager.get_vllm_config()
            assert config['vllm_endpoint'] == 'http://vllm:8000'
            assert config['vllm_endpoint_small'] == 'http://vllm-small:8000'
            assert config['vllm_api_key'] == 'test-key'
    
    def test_prometheus_url_helper(self):
        """Test the Prometheus URL helper method."""
        with patch.dict(os.environ, {'PROMETHEUS_BASE_URL': 'http://prometheus:9090'}):
            manager = SecretsManager()
            manager._provider = SecretProvider.ENVIRONMENT
            
            url = manager.get_prometheus_url()
            assert url == 'http://prometheus:9090'
    
    def test_vault_secret_storage(self):
        """Test storing secrets in Vault."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                mock_client.return_value = mock_instance
                
                manager = SecretsManager()
                
                # Test storing string secret
                result = manager.store_secret('test/secret', 'test_value')
                assert result is True
                
                # Verify the call
                mock_instance.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
                    path='test/secret',
                    secret={'value': 'test_value'},
                    mount_point='secret'
                )
    
    def test_environment_secret_storage(self):
        """Test storing secrets in environment (development only)."""
        manager = SecretsManager()
        manager._provider = SecretProvider.ENVIRONMENT
        
        result = manager.store_secret('TEST_ENV_SECRET', 'test_value')
        assert result is True
        assert os.environ.get('TEST_ENV_SECRET') == 'test_value'
    
    def test_cache_clearing(self):
        """Test clearing the secrets cache."""
        with patch.dict(os.environ, {'TEST_SECRET': 'test_value'}):
            manager = SecretsManager()
            manager._provider = SecretProvider.ENVIRONMENT
            
            # Populate cache
            manager.get_secret('TEST_SECRET')
            assert 'TEST_SECRET' in manager._cache
            
            # Clear cache
            manager.clear_cache()
            assert len(manager._cache) == 0
    
    def test_health_check_all_providers(self):
        """Test health check for all providers."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_hvac:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                mock_hvac.return_value = mock_instance
                
                with patch('boto3.client') as mock_boto3:
                    mock_client = Mock()
                    mock_client.list_secrets.return_value = {}
                    mock_boto3.return_value = mock_client
                    
                    manager = SecretsManager()
                    health = manager.health_check()
                    
                    assert 'active_provider' in health
                    assert 'providers' in health
                    assert 'vault' in health['providers']
                    assert 'aws_secrets_manager' in health['providers']
                    assert 'environment' in health['providers']
    
    def test_error_handling_vault_retrieval(self):
        """Test error handling during Vault secret retrieval."""
        with patch.dict(os.environ, {
            'VAULT_ADDR': 'http://localhost:8200',
            'VAULT_TOKEN': 'test-token'
        }):
            with patch('hvac.Client') as mock_client:
                mock_instance = Mock()
                mock_instance.is_authenticated.return_value = True
                mock_instance.secrets.kv.v2.read_secret_version.side_effect = Exception("Network error")
                mock_instance.secrets.kv.v1.read_secret.side_effect = Exception("Network error")
                mock_client.return_value = mock_instance
                
                manager = SecretsManager()
                secret = manager.get_secret('test/secret', 'default_value')
                assert secret == 'default_value'
    
    def test_error_handling_aws_retrieval(self):
        """Test error handling during AWS secret retrieval."""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_client.describe_secret.side_effect = Exception("ResourceNotFoundException")
            mock_client.get_secret_value.side_effect = Exception("AccessDenied")
            mock_boto3.return_value = mock_client
            
            manager = SecretsManager()
            secret = manager.get_secret('test/secret', 'default_value')
            assert secret == 'default_value'


class TestSecretsManagerIntegration:
    """Integration tests for secrets manager with Settings."""
    
    def test_settings_integration(self):
        """Test Settings class integration with secrets manager."""
        from hivemind.config import Settings
        
        with patch.dict(os.environ, {
            'REDIS_URL': 'redis://env-redis:6379',
            'PROMETHEUS_BASE_URL': 'http://env-prometheus:9090'
        }):
            with patch('hivemind.config.secrets_manager') as mock_manager:
                mock_manager.get_redis_url.return_value = 'redis://secrets-redis:6379'
                mock_manager.get_prometheus_url.return_value = 'http://secrets-prometheus:9090'
                mock_manager.get_vllm_config.return_value = {
                    'vllm_endpoint': 'http://secrets-vllm:8000'
                }
                mock_manager.get_secret.return_value = None
                
                settings = Settings()
                
                # Should use secrets manager values over environment
                assert settings.redis_url == 'redis://secrets-redis:6379'
                assert settings.PROMETHEUS_BASE_URL == 'http://secrets-prometheus:9090'
                assert settings.vllm_endpoint == 'http://secrets-vllm:8000'
    
    def test_health_endpoint_integration(self):
        """Test the health endpoint integration."""
        with patch('hivemind.config.secrets_manager') as mock_manager:
            mock_manager.health_check.return_value = {
                'active_provider': 'vault',
                'providers': {
                    'vault': {'status': 'healthy'},
                    'aws_secrets_manager': {'status': 'not_configured'},
                    'environment': {'status': 'healthy'}
                }
            }
            
            from hivemind.config import Settings
            settings = Settings()
            health = settings.get_secrets_health()
            
            assert health['active_provider'] == 'vault'
            assert health['providers']['vault']['status'] == 'healthy'


if __name__ == '__main__':
    pytest.main([__file__])