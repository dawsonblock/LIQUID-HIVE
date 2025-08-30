try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from typing import Optional
import os

# Import secrets manager with graceful fallback
try:
    from .secrets_manager import secrets_manager
    SECRETS_MANAGER_AVAILABLE = True
except ImportError:
    secrets_manager = None
    SECRETS_MANAGER_AVAILABLE = False


class Settings(BaseSettings):
    # External service URLs must come from environment for portability
    # Provide sensible defaults for docker-compose network
    vllm_endpoint: Optional[str] = "http://vllm:8000"  # default for local compose
    vllm_endpoint_small: Optional[str] = None
    vllm_endpoint_large: Optional[str] = None
    MODEL_ROUTING_ENABLED: bool = False
    vllm_api_key: str = "unused"
    redis_url: Optional[str] = None      # e.g., redis://redis:6379
    neo4j_url: Optional[str] = None      # e.g., bolt://neo4j:7687

    # Observability / estimator config
    PROMETHEUS_BASE_URL: Optional[str] = None
    COST_PER_1K_TOKENS_SMALL: float = 0.0008
    COST_PER_1K_TOKENS_LARGE: float = 0.0030

    # RAG / Embeddings
    embed_model: Optional[str] = "sentence-transformers/all-MiniLM-L6-v2"

    vl_model_id: str = "LiquidAI/LFM2-VL-1.6B"
    committee_k: int = 3
    max_new_tokens: int = 512

    # Persisted state locations (mounted via PVC in Kubernetes)
    runs_dir: str = "/app/runs"
    rag_index: str = "/app/rag_index"
    adapters_dir: str = "/app/adapters"

    # Optional currently active text adapter path
    text_adapter_path: Optional[str] = None

    # Foundational adapter path (centralized)
    foundational_adapter_path: str = "/app/adapters/foundational/champion_v1"

    # --- Arbiter Governor Controls ---
    ENABLE_ORACLE_REFINEMENT: bool = True
    FORCE_GPT4O_ARBITER: bool = False

    # --- Autonomy Governor ---
    ENABLE_AUTONOMOUS_EXECUTIVE: bool = True

    # --- Trusted Autonomy (Confidence Modeler) ---
    TRUSTED_AUTONOMY_ENABLED: bool = False
    TRUST_THRESHOLD: float = 0.999
    TRUST_MIN_SAMPLES: int = 200
    TRUST_ALLOWLIST: Optional[str] = None  # comma-separated action types

    # --- Auto-Promotion ---
    AUTOPROMOTE_ENABLED: bool = False
    AUTOPROMOTE_MIN_SAMPLES: int = 300
    AUTOPROMOTE_P_THRESHOLD: float = 0.05
    AUTOPROMOTE_COOLDOWN_HOURS: int = 24

    # --- Secrets Management ---
    SECRETS_PROVIDER: Optional[str] = None  # auto-detected
    VAULT_ADDR: Optional[str] = None
    VAULT_TOKEN: Optional[str] = None
    AWS_SECRETS_PREFIX: Optional[str] = "liquid-hive"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize secrets from secrets manager if available
        if SECRETS_MANAGER_AVAILABLE and secrets_manager:
            self._load_secrets_from_manager()
    
    def _load_secrets_from_manager(self):
        """Load configuration from secrets manager with fallback to env vars."""
        if not secrets_manager:
            return
            
        # Database URL
        if not self.redis_url:
            redis_url = secrets_manager.get_redis_url()
            if redis_url:
                self.redis_url = redis_url
                
        # Prometheus URL
        if not self.PROMETHEUS_BASE_URL:
            prometheus_url = secrets_manager.get_prometheus_url()
            if prometheus_url:
                self.PROMETHEUS_BASE_URL = prometheus_url
                
        # vLLM configuration
        vllm_config = secrets_manager.get_vllm_config()
        if not self.vllm_endpoint and vllm_config.get('vllm_endpoint'):
            self.vllm_endpoint = vllm_config['vllm_endpoint']
        if not self.vllm_endpoint_small and vllm_config.get('vllm_endpoint_small'):
            self.vllm_endpoint_small = vllm_config['vllm_endpoint_small']
        if not self.vllm_endpoint_large and vllm_config.get('vllm_endpoint_large'):
            self.vllm_endpoint_large = vllm_config['vllm_endpoint_large']
        if self.vllm_api_key == "unused" and vllm_config.get('vllm_api_key'):
            self.vllm_api_key = vllm_config['vllm_api_key']
            
        # Neo4j URL
        if not self.neo4j_url:
            neo4j_url = secrets_manager.get_secret('neo4j_url') or secrets_manager.get_secret('NEO4J_URL')
            if neo4j_url:
                self.neo4j_url = str(neo4j_url)

    def get_secrets_health(self) -> dict:
        """Get secrets manager health status."""
        if SECRETS_MANAGER_AVAILABLE and secrets_manager:
            return secrets_manager.health_check()
        return {'status': 'not_available', 'providers': {}}
        
    def get_secret(self, key: str, default=None):
        """Get a secret value from the secrets manager."""
        if SECRETS_MANAGER_AVAILABLE and secrets_manager:
            return secrets_manager.get_secret(key, default)
        return os.environ.get(key, default)

    class Config:
        env_prefix = ""
        env_file = ".env"
        extra = "allow"  # Allow extra fields from environment