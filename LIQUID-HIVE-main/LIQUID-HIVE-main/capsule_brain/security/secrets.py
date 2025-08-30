import os, logging
log = logging.getLogger(__name__)
class SecretManager:
    @staticmethod
    def get_secret(key: str, default=None):
        v=os.getenv(key, default)
        if not v and default is None: log.warning(f"Secret {key} not found")
        return v
    @staticmethod
    def get_required_secret(key: str)->str:
        v=os.getenv(key)
        if not v: raise ValueError(f"Required secret {key} not found")
        return v
    @staticmethod
    def validate_api_key(api_key: str) -> bool: return bool(api_key and len(api_key)>=10)
