
"""
DS-Router v1: Model Router with Intelligence Routing

"""

from __future__ import annotations
import asyncio
import re
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .providers import (
    BaseProvider, GenRequest, GenResponse,
    DeepSeekChatProvider, DeepSeekThinkingProvider, 
    DeepSeekR1Provider, QwenCPUProvider
)

try:
    from ..safety.pre_guard import PreGuard
    from ..safety.post_guard import PostGuard
except ImportError:
    PreGuard = None
    PostGuard = None

log = logging.getLogger(__name__)

@dataclass
class RouterConfig:
    """Configuration for the DS-Router."""
    conf_threshold: float = 0.62
    support_threshold: float = 0.55
    max_cot_tokens: int = 6000
    max_oracle_tokens_per_day: int = 250000
    max_oracle_usd_per_day: float = 50.0
    budget_enforcement: str = "hard"  # hard|warn
    
    # Provider configurations
    deepseek_api_key: Optional[str] = None
    hf_token: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'RouterConfig':
        """Load configuration from environment variables."""
        return cls(
            conf_threshold=float(os.getenv("CONF_THRESHOLD", "0.62")),
            support_threshold=float(os.getenv("SUPPORT_THRESHOLD", "0.55")),
            max_cot_tokens=int(os.getenv("MAX_COT_TOKENS", "6000")),
            max_oracle_tokens_per_day=int(os.getenv("MAX_ORACLE_TOKENS_PER_DAY", "250000")),
            max_oracle_usd_per_day=float(os.getenv("MAX_ORACLE_USD_PER_DAY", "50.0")),
            budget_enforcement=os.getenv("BUDGET_ENFORCEMENT", "hard"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            hf_token=os.getenv("HF_TOKEN")
        )

class DSRouter:
    """Intelligent model router with safety and fallback capabilities."""
    
    def __init__(self, config: RouterConfig = None):
        self.config = config or RouterConfig.from_env()
        self.logger = logging.getLogger(__name__)
        
        # Initialize providers
        self.providers: Dict[str, BaseProvider] = {}
        self._initialize_providers()
        
        # Initialize safety guards
        self.pre_guard = PreGuard() if PreGuard else None
        self.post_guard = PostGuard() if PostGuard else None
        
        # Budget tracking (should use Redis in production)
        self._budget_tracker = BudgetTracker(self.config)
        
        # Compile regex patterns for hard problem detection
        self._hard_patterns = self._compile_hard_patterns()
        
    def _initialize_providers(self):
        """Initialize all available providers."""
        try:
            # DeepSeek providers
            deepseek_config = {"api_key": self.config.deepseek_api_key}
            
            self.providers["deepseek_chat"] = DeepSeekChatProvider(deepseek_config)
            self.providers["deepseek_thinking"] = DeepSeekThinkingProvider(deepseek_config)
            self.providers["deepseek_r1"] = DeepSeekR1Provider(deepseek_config)
            
            # Local fallback
            qwen_config = {"hf_token": self.config.hf_token}
            self.providers["qwen_cpu"] = QwenCPUProvider(qwen_config)
            
            self.logger.info("Initialized DS-Router with providers: %s", list(self.providers.keys()))
            
        except Exception as e:
            self.logger.error(f"Failed to initialize providers: {e}")
    
    def _compile_hard_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for detecting hard problems."""
        patterns = [
            # Math and logic
            r'\b(prove|derive|optimize|constraints?)\b',
            r'\b(induction|deduction|axiom|theorem)\b',
            r'\b(NP-complete|complexity|Big-O|algorithm)\b',
            
            # Code and technical
            r'\b(regex|regular expression|compiler|parser)\b',
            r'\b(unit test|test case|debugging)\b',
            r'\b(refactor|optimize code|performance)\b',
            
            # Complex reasoning
            r'\b(paradox|contradiction|logical fallacy)\b',
            r'\b(multi-step|step-by-step|systematic)\b',
            r'\b(analyze|compare|evaluate|critique)\b',
            
            # Mathematical symbols and operations
            r'[∀∃∈∉∪∩⊂⊃∧∨¬→↔]',  # Logical symbols
            r'\b(integral|derivative|limit|convergence)\b',
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    async def generate(self, request: GenRequest) -> GenResponse:
        """Main router entry point with full safety and intelligence routing."""
        start_time = asyncio.get_event_loop().time()
        
        # Step 1: Pre-filtering and sanitization
        if self.pre_guard:
            sanitized_request, pre_guard_result = await self.pre_guard.process(request)
            if pre_guard_result.blocked:
                return self._create_blocked_response(pre_guard_result.reason, start_time)
        else:
            sanitized_request = request
            pre_guard_result = None
        
        # Step 2: Budget check
        budget_status = await self._budget_tracker.check_budget()
        if budget_status.exceeded and self.config.budget_enforcement == "hard":
            return self._create_budget_exceeded_response(budget_status, start_time)
        
        # Step 3: Determine routing strategy
        routing_decision = await self._determine_routing(sanitized_request)
        
        # Step 4: Generate response with chosen provider
        try:
            response = await self._generate_with_routing(sanitized_request, routing_decision)
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            # Fallback to local provider
            response = await self._fallback_generate(sanitized_request, str(e))
        
        # Step 5: Confidence assessment and escalation
        if routing_decision.provider != "qwen_cpu":  # Skip confidence check for fallback
            confidence = await self._assess_confidence(response, sanitized_request)
            response.confidence = confidence
            
            # Escalate if confidence too low and not already using R1
            if (confidence < self.config.conf_threshold and 
                routing_decision.provider != "deepseek_r1"):
                
                escalation_decision = RoutingDecision(
                    provider="deepseek_r1",
                    reasoning="low_confidence_escalation", 
                    cot_budget=self.config.max_cot_tokens
                )
                
                try:
                    response = await self._generate_with_routing(sanitized_request, escalation_decision)
                    response.confidence = await self._assess_confidence(response, sanitized_request)
                    response.metadata["escalated"] = True
                    response.metadata["escalation_reason"] = "low_confidence"
                except Exception as e:
                    self.logger.warning(f"Escalation to R1 failed: {e}")
        
        # Step 6: Post-filtering and verification
        if self.post_guard:
            final_response, post_guard_result = await self.post_guard.process(response, sanitized_request)
            if post_guard_result.blocked:
                return self._create_blocked_response(post_guard_result.reason, start_time)
        else:
            final_response = response
            post_guard_result = None
        
        # Step 7: Budget tracking and audit logging
        await self._budget_tracker.record_usage(final_response)
        await self._audit_log(sanitized_request, final_response, routing_decision, pre_guard_result, post_guard_result)
        
        return final_response
    
    async def _determine_routing(self, request: GenRequest) -> 'RoutingDecision':
        """Determine which provider to use based on request characteristics."""
        
        # Check if this is a hard problem
        is_hard = self._is_hard_problem(request.prompt)
        
        # TODO: Implement RAG support scoring
        # support_score = await self._get_rag_support_score(request.prompt)
        support_score = 0.7  # Mock for now
        
        if support_score < self.config.support_threshold:
            is_hard = True
        
        if not is_hard:
            return RoutingDecision(
                provider="deepseek_chat",
                reasoning="simple_query",
                cot_budget=None
            )
        else:
            return RoutingDecision(
                provider="deepseek_thinking", 
                reasoning="complex_query",
                cot_budget=min(self.config.max_cot_tokens, 3000)
            )
    
    def _is_hard_problem(self, prompt: str) -> bool:
        """Detect if a prompt represents a hard problem requiring reasoning."""
        for pattern in self._hard_patterns:
            if pattern.search(prompt):
                return True
        return False
    
    async def _generate_with_routing(self, request: GenRequest, decision: 'RoutingDecision') -> GenResponse:
        """Generate response using the specified routing decision."""
        provider = self.providers.get(decision.provider)
        if not provider:
            raise ValueError(f"Provider {decision.provider} not available")
        
        # Modify request for CoT budget if applicable
        if decision.cot_budget:
            request.cot_budget = decision.cot_budget
        
        response = await provider.generate(request)
        response.metadata.update({
            "routing_decision": decision.provider,
            "routing_reasoning": decision.reasoning
        })
        
        return response
    
    async def _fallback_generate(self, request: GenRequest, error: str) -> GenResponse:
        """Generate response using local fallback provider."""
        qwen_provider = self.providers.get("qwen_cpu")
        if qwen_provider:
            response = await qwen_provider.generate(request)
            response.metadata["fallback_reason"] = error
            return response
        else:
            # Ultimate fallback
            return GenResponse(
                content="I apologize, but I'm currently unable to process your request due to system limitations.",
                provider="system_fallback",
                metadata={"error": error, "ultimate_fallback": True}
            )
    
    async def _assess_confidence(self, response: GenResponse, request: GenRequest) -> float:
        """Assess confidence in the generated response."""
        # Simple heuristic-based confidence assessment
        # In production, this could use a dedicated confidence model
        
        confidence = 0.7  # Base confidence
        
        # Adjust based on response length
        if len(response.content) < 50:
            confidence -= 0.2
        elif len(response.content) > 500:
            confidence += 0.1
        
        # Adjust based on provider
        if response.provider.startswith("deepseek_r1"):
            confidence += 0.2
        elif response.provider.startswith("deepseek_thinking"):
            confidence += 0.1
        elif response.provider.startswith("qwen_cpu"):
            confidence -= 0.3
        
        # Check for uncertainty indicators
        uncertainty_markers = ["i'm not sure", "i don't know", "uncertain", "maybe", "possibly"]
        content_lower = response.content.lower()
        for marker in uncertainty_markers:
            if marker in content_lower:
                confidence -= 0.15
                break
        
        return max(0.0, min(1.0, confidence))
    
    def _create_blocked_response(self, reason: str, start_time: float) -> GenResponse:
        """Create response for blocked requests."""
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return GenResponse(
            content="I cannot provide a response to this request due to safety or policy restrictions.",
            provider="safety_filter",
            latency_ms=latency_ms,
            metadata={"blocked": True, "block_reason": reason}
        )
    
    def _create_budget_exceeded_response(self, budget_status: 'BudgetStatus', start_time: float) -> GenResponse:
        """Create response for budget exceeded scenarios."""
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return GenResponse(
            content=f"Daily budget limit has been exceeded. Service will resume at {budget_status.next_reset_utc}.",
            provider="budget_limiter",
            latency_ms=latency_ms,
            metadata={
                "budget_exceeded": True,
                "next_reset": budget_status.next_reset_utc,
                "usage_tokens": budget_status.tokens_used,
                "usage_usd": budget_status.usd_spent
            }
        )
    
    async def _audit_log(self, request: GenRequest, response: GenResponse, routing: 'RoutingDecision', 
                        pre_guard=None, post_guard=None):
        """Log audit information for compliance and monitoring."""
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "input_sha256": self._hash_content(request.prompt),
            "provider": response.provider,
            "confidence": response.confidence,
            "routing_decision": routing.provider,
            "routing_reasoning": routing.reasoning,
            "blocked": response.metadata.get("blocked", False),
            "escalated": response.metadata.get("escalated", False),
            "filters": {
                "pre_guard": pre_guard.status if pre_guard else "disabled",
                "post_guard": post_guard.status if post_guard else "disabled"
            },
            "tokens": {
                "prompt": response.prompt_tokens,
                "output": response.output_tokens
            },
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms
        }
        
        # In production, send to audit log service
        self.logger.info("Audit log", extra={"audit": audit_entry})
    
    def _hash_content(self, content: str) -> str:
        """Create SHA256 hash of content for audit logging."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        status = {}
        for name, provider in self.providers.items():
            try:
                health = await provider.health_check()
                status[name] = health
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        
        return status

@dataclass
class RoutingDecision:
    """Represents a routing decision made by the router."""
    provider: str
    reasoning: str
    cot_budget: Optional[int] = None

@dataclass 
class BudgetStatus:
    """Budget tracking status."""
    exceeded: bool
    tokens_used: int
    usd_spent: float
    next_reset_utc: str

class BudgetTracker:
    """Tracks daily budget usage."""
    
    def __init__(self, config: RouterConfig):
        self.config = config
        self.tokens_used = 0
        self.usd_spent = 0.0
        
    async def check_budget(self) -> BudgetStatus:
        """Check current budget status."""
        # In production, this would query Redis for daily counters
        
        exceeded = (
            self.tokens_used >= self.config.max_oracle_tokens_per_day or
            self.usd_spent >= self.config.max_oracle_usd_per_day
        )
        
        # Mock next reset time (should be actual next UTC midnight)
        from datetime import datetime, timedelta
        next_reset = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00 UTC")
        
        return BudgetStatus(
            exceeded=exceeded,
            tokens_used=self.tokens_used,
            usd_spent=self.usd_spent,
            next_reset_utc=next_reset
        )
    
    async def record_usage(self, response: GenResponse):
        """Record token and cost usage."""
        self.tokens_used += response.prompt_tokens + response.output_tokens
        self.usd_spent += response.cost_usd
        
        # In production, atomically increment Redis counters
        # redis.hincrby(f"oracle:day:{date}", "tokens", response.prompt_tokens + response.output_tokens)
        # redis.hincrbyfloat(f"oracle:day:{date}", "usd", response.cost_usd)

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Dict, List, Optional

from .providers.base import GenReq, GenResp
from .providers.vllm_provider import VLLMProvider
from .providers.openai_provider import OpenAIProvider
from .providers.hf_cpu_provider import HFCpuProvider

try:
    from hivemind.config import Settings
except Exception:
    Settings = None  # type: ignore

log = logging.getLogger(__name__)


class ModelRouter:
    def __init__(self) -> None:
        self.MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "auto").lower()
        self.HF_MODEL = os.environ.get("HF_MODEL")
        self.PROVIDER_TIMEOUT_MS = int(os.environ.get("PROVIDER_TIMEOUT_MS", "120000"))
        self.settings = Settings() if Settings is not None else None

        vllm_endpoint = getattr(self.settings, "vllm_endpoint", None) if self.settings else os.environ.get("VLLM_ENDPOINT")
        vllm_key = getattr(self.settings, "vllm_api_key", None) if self.settings else os.environ.get("VLLM_API_KEY")

        self.vllm = VLLMProvider(vllm_endpoint, vllm_key, timeout_ms=self.PROVIDER_TIMEOUT_MS)
        self.openai = OpenAIProvider(timeout_ms=self.PROVIDER_TIMEOUT_MS)
        self.hf = HFCpuProvider(self.HF_MODEL, timeout_ms=self.PROVIDER_TIMEOUT_MS)

        self._last_provider: Optional[str] = None

    async def providers_status(self) -> Dict[str, bool]:
        v = await self.vllm.health()
        o = await self.openai.health()
        h = await self.hf.health()
        return {"vllm": v, "openai": o, "hf_cpu": h}

    async def any_live(self) -> bool:
        status = await self.providers_status()
        return any(status.values())

    def active_name(self) -> Optional[str]:
        return self._last_provider

    def _order(self) -> List[str]:
        mp = self.MODEL_PROVIDER
        if mp == "vllm":
            return ["vllm"]
        if mp == "openai":
            return ["openai"]
        if mp == "hf_cpu":
            return ["hf_cpu"]
        # auto
        return ["vllm", "openai", "hf_cpu"]

    def _get(self, name: str):
        return {"vllm": self.vllm, "openai": self.openai, "hf_cpu": self.hf}[name]

    async def generate(self, req: GenReq) -> GenResp:
        errors: Dict[str, str] = {}
        for name in self._order():
            prov = self._get(name)
            healthy = False
            try:
                healthy = await prov.health()
            except Exception:
                healthy = False
            if not healthy:
                errors[name] = "unhealthy"
                continue
            # simple per-provider retry with jitter
            for attempt in range(3):
                try:
                    resp = await prov.generate(req)
                    self._last_provider = name
                    return resp
                except Exception as e:
                    errors[name] = str(e)
                    await asyncio.sleep(0.1 + random.random() * 0.2)
            # provider exhausted, try next
        # if all failed
        msg = "; ".join([f"{k}: {v}" for k, v in errors.items()]) or "no providers available"
        raise RuntimeError(f"All providers failed: {msg}")
        main
