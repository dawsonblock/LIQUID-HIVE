"""
Production-Grade Secrets Management Service
==========================================
Supports HashiCorp Vault (local dev) and AWS Secrets Manager (production)
with intelligent fallback to environment variables.
"""
import os
import json
import logging
from typing import Optional, Dict, Any, Union
from enum import Enum

# Third-party imports with graceful handling
try:
    import hvac
except ImportError:
    hvac = None

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class SecretProvider(Enum):
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    ENVIRONMENT = "environment"


class SecretsManager:
    """
    Production-grade secrets manager with multi-provider support.
    
    Priority order:
    1. HashiCorp Vault (if configured and available)
    2. AWS Secrets Manager (if configured and available)  
    3. Environment variables (fallback)
    """
    
    def __init__(self):
        self._vault_client: Optional[Any] = None
        self._aws_client: Optional[Any] = None
        self._cache: Dict[str, Any] = {}
        self._provider: Optional[SecretProvider] = None
        
        # Initialize providers
        self._init_providers()
        
    def _init_providers(self) -> None:
        """Initialize available secret providers in priority order."""
        
        # Try HashiCorp Vault first
        if self._init_vault():
            self._provider = SecretProvider.VAULT
            logger.info("Initialized HashiCorp Vault as secrets provider")
            return
            
        # Try AWS Secrets Manager second
        if self._init_aws_secrets_manager():
            self._provider = SecretProvider.AWS_SECRETS_MANAGER
            logger.info("Initialized AWS Secrets Manager as secrets provider")
            return
            
        # Fallback to environment variables
        self._provider = SecretProvider.ENVIRONMENT
        logger.info("Using environment variables as secrets provider")
        
    def _init_vault(self) -> bool:
        """Initialize HashiCorp Vault client."""
        if hvac is None:
            logger.debug("HVAC library not available")
            return False
            
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        
        if not vault_addr:
            logger.debug("VAULT_ADDR not configured")
            return False
            
        try:
            client = hvac.Client(url=vault_addr)
            
            # Authenticate with token if provided
            if vault_token:
                client.token = vault_token
                
            # Test connection and authentication
            if client.is_authenticated():
                self._vault_client = client
                logger.debug(f"Connected to Vault at {vault_addr}")
                return True
            else:
                logger.debug("Vault authentication failed")
                return False
                
        except Exception as e:
            logger.debug(f"Failed to connect to Vault: {e}")
            return False
            
    def _init_aws_secrets_manager(self) -> bool:
        """Initialize AWS Secrets Manager client."""
        if boto3 is None:
            logger.debug("Boto3 library not available")
            return False
            
        try:
            # Try to create client - will use IAM role, profile, or env vars
            client = boto3.client('secretsmanager')
            
            # Test connectivity with a simple call
            client.describe_secret(SecretId='test-connectivity-check')
            
        except ClientError as e:
            # ResourceNotFoundException is expected for test call
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._aws_client = client
                logger.debug("Connected to AWS Secrets Manager")
                return True
            else:
                logger.debug(f"AWS Secrets Manager authentication failed: {e}")
                return False
        except Exception as e:
            logger.debug(f"Failed to connect to AWS Secrets Manager: {e}")
            return False
            
    def get_secret(self, secret_path: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieve a secret from the configured provider.
        
        Args:
            secret_path: Path/key for the secret
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        # Check cache first
        if secret_path in self._cache:
            return self._cache[secret_path]
            
        value = None
        
        try:
            if self._provider == SecretProvider.VAULT:
                value = self._get_vault_secret(secret_path, default)
            elif self._provider == SecretProvider.AWS_SECRETS_MANAGER:
                value = self._get_aws_secret(secret_path, default)
            else:
                value = self._get_env_secret(secret_path, default)
                
            # Cache the value if retrieved successfully
            if value is not None:
                self._cache[secret_path] = value
                
        except Exception as e:
            logger.error(f"Error retrieving secret '{secret_path}': {e}")
            value = default
            
        return value
        
    def _get_vault_secret(self, secret_path: str, default: Optional[Any] = None) -> Optional[Any]:
        """Retrieve secret from HashiCorp Vault."""
        if not self._vault_client:
            return default
            
        try:
            # Try KV v2 first (most common)
            try:
                response = self._vault_client.secrets.kv.v2.read_secret_version(
                    path=secret_path,
                    mount_point='secret'
                )
                if response and 'data' in response and 'data' in response['data']:
                    data = response['data']['data']
                    # Return the whole object if multiple keys, or single value if only one key
                    if len(data) == 1:
                        return list(data.values())[0]
                    return data
            except Exception:
                # Fallback to KV v1
                response = self._vault_client.secrets.kv.v1.read_secret(
                    path=secret_path,
                    mount_point='secret'
                )
                if response and 'data' in response:
                    data = response['data']
                    if len(data) == 1:
                        return list(data.values())[0]
                    return data
                    
        except Exception as e:
            logger.debug(f"Vault secret retrieval failed for '{secret_path}': {e}")
            
        return default
        
    def _get_aws_secret(self, secret_name: str, default: Optional[Any] = None) -> Optional[Any]:
        """Retrieve secret from AWS Secrets Manager."""
        if not self._aws_client:
            return default
            
        try:
            response = self._aws_client.get_secret_value(SecretId=secret_name)
            secret_value = response.get('SecretString')
            
            if secret_value:
                # Try to parse as JSON first
                try:
                    data = json.loads(secret_value)
                    # Return the whole object if multiple keys, or single value if only one key
                    if isinstance(data, dict) and len(data) == 1:
                        return list(data.values())[0]
                    return data
                except json.JSONDecodeError:
                    # Return as string if not JSON
                    return secret_value
                    
        except ClientError as e:
            logger.debug(f"AWS secret retrieval failed for '{secret_name}': {e}")
        except Exception as e:
            logger.debug(f"AWS secret retrieval error for '{secret_name}': {e}")
            
        return default
        
    def _get_env_secret(self, env_var: str, default: Optional[Any] = None) -> Optional[Any]:
        """Retrieve secret from environment variable."""
        return os.environ.get(env_var, default)
        
    def get_database_url(self) -> Optional[str]:
        """Get database connection URL."""
        # Try different common secret paths/names
        for path in ['database/mongo_url', 'mongo_url', 'MONGO_URL']:
            url = self.get_secret(path)
            if url:
                return str(url)
        return None
        
    def get_redis_url(self) -> Optional[str]:
        """Get Redis connection URL."""
        for path in ['redis/url', 'redis_url', 'REDIS_URL']:
            url = self.get_secret(path)
            if url:
                return str(url)
        return None
        
    def get_vllm_config(self) -> Dict[str, Optional[str]]:
        """Get vLLM configuration."""
        config = {}
        
        # Main vLLM endpoint
        for path in ['vllm/endpoint', 'vllm_endpoint', 'VLLM_ENDPOINT']:
            endpoint = self.get_secret(path)
            if endpoint:
                config['vllm_endpoint'] = str(endpoint)
                break
                
        # Small model endpoint  
        for path in ['vllm/endpoint_small', 'vllm_endpoint_small', 'VLLM_ENDPOINT_SMALL']:
            endpoint = self.get_secret(path)
            if endpoint:
                config['vllm_endpoint_small'] = str(endpoint)
                break
                
        # Large model endpoint
        for path in ['vllm/endpoint_large', 'vllm_endpoint_large', 'VLLM_ENDPOINT_LARGE']:
            endpoint = self.get_secret(path)
            if endpoint:
                config['vllm_endpoint_large'] = str(endpoint)
                break
                
        # API key
        for path in ['vllm/api_key', 'vllm_api_key', 'VLLM_API_KEY']:
            key = self.get_secret(path)
            if key:
                config['vllm_api_key'] = str(key)
                break
                
        return config
        
    def get_prometheus_url(self) -> Optional[str]:
        """Get Prometheus base URL."""
        for path in ['prometheus/base_url', 'prometheus_base_url', 'PROMETHEUS_BASE_URL']:
            url = self.get_secret(path)
            if url:
                return str(url)
        return None
        
    def store_secret(self, secret_path: str, value: Union[str, Dict[str, Any]]) -> bool:
        """
        Store a secret (only supported by Vault and environment in dev).
        
        Args:
            secret_path: Path/key for the secret
            value: Secret value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self._provider == SecretProvider.VAULT and self._vault_client:
                # Store in Vault KV v2
                data_to_store = value if isinstance(value, dict) else {'value': value}
                self._vault_client.secrets.kv.v2.create_or_update_secret(
                    path=secret_path,
                    secret=data_to_store,
                    mount_point='secret'
                )
                # Update cache
                self._cache[secret_path] = value
                return True
            elif self._provider == SecretProvider.ENVIRONMENT:
                # For development, we can set environment variables
                # In production, this would not be used
                if isinstance(value, dict):
                    os.environ[secret_path] = json.dumps(value)
                else:
                    os.environ[secret_path] = str(value)
                # Update cache
                self._cache[secret_path] = value
                return True
            else:
                logger.warning(f"Secret storage not supported for provider {self._provider}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to store secret '{secret_path}': {e}")
            return False
            
    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cache.clear()
        logger.debug("Secrets cache cleared")
        
    def get_provider(self) -> Optional[SecretProvider]:
        """Get the current active provider."""
        return self._provider
        
    def health_check(self) -> Dict[str, Any]:
        """Check health of all configured providers."""
        health = {
            'active_provider': self._provider.value if self._provider else None,
            'providers': {}
        }
        
        # Check Vault
        if hvac and os.environ.get("VAULT_ADDR"):
            try:
                if self._vault_client and self._vault_client.is_authenticated():
                    health['providers']['vault'] = {'status': 'healthy', 'authenticated': True}
                else:
                    health['providers']['vault'] = {'status': 'unhealthy', 'authenticated': False}
            except Exception as e:
                health['providers']['vault'] = {'status': 'error', 'error': str(e)}
        else:
            health['providers']['vault'] = {'status': 'not_configured'}
            
        # Check AWS Secrets Manager
        if boto3:
            try:
                if self._aws_client:
                    # Try a simple operation to test connectivity
                    self._aws_client.list_secrets(MaxResults=1)
                    health['providers']['aws_secrets_manager'] = {'status': 'healthy'}
                else:
                    health['providers']['aws_secrets_manager'] = {'status': 'not_initialized'}
            except Exception as e:
                health['providers']['aws_secrets_manager'] = {'status': 'error', 'error': str(e)}
        else:
            health['providers']['aws_secrets_manager'] = {'status': 'not_configured'}
            
        # Environment variables are always available
        health['providers']['environment'] = {'status': 'healthy'}
        
        return health


# Global instance for easy import
secrets_manager = SecretsManager()