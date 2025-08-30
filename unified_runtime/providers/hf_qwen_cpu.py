"""
Qwen 2.5 7B CPU Provider (Local Fallback)
=========================================
"""

from __future__ import annotations
import asyncio
import os
import logging
from typing import Dict, Any, Optional

from .base_provider import BaseProvider, GenRequest, GenResponse

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    HF_AVAILABLE = True
except ImportError:
    torch = None
    AutoTokenizer = None
    AutoModelForCausalLM = None
    pipeline = None
    HF_AVAILABLE = False

class QwenCPUProvider(BaseProvider):
    """Qwen 2.5 7B Instruct local CPU provider as fallback."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("qwen_cpu", config)
        self.model_name = config.get("model", "Qwen/Qwen2.5-7B-Instruct")
        self.device = "cpu"  # Force CPU for fallback reliability
        self.max_memory_mb = config.get("max_memory_mb", 8192)  # 8GB limit
        self.hf_token = config.get("hf_token") or os.getenv("HF_TOKEN")
        
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        self.is_loaded = False
        self.load_error = None
        
        # Cost is essentially zero (local compute)
        self.input_cost_per_1k = 0.0
        self.output_cost_per_1k = 0.0
        
        # Try to load model at initialization
        self._initialize_model()
        
    def _initialize_model(self):
        """Initialize the Qwen model and tokenizer."""
        if not HF_AVAILABLE:
            self.load_error = "transformers/torch not available"
            return
            
        try:
            # Load with 4-bit quantization if available to save memory
            model_kwargs = {
                "torch_dtype": torch.float16,
                "device_map": "cpu",
                "token": self.hf_token,
                "trust_remote_code": True
            }
            
            # 4-bit quantization is not supported on CPU; always load without quantization
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, 
                token=self.hf_token,
                trust_remote_code=True
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **model_kwargs
            )
            
            # Create text generation pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device,
                return_full_text=False,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            self.is_loaded = True
            self.logger.info(f"Successfully loaded Qwen model: {self.model_name}")
            
        except Exception as e:
            self.load_error = str(e)
            self.logger.error(f"Failed to load Qwen model: {e}")
            self.is_loaded = False
    
    async def generate(self, request: GenRequest) -> GenResponse:
        """Generate response using local Qwen model."""
        start_time = asyncio.get_event_loop().time()
        
        if not self.is_loaded:
            return self._fallback_response(request, start_time, self.load_error)
        
        # Format prompt for Qwen chat template
        formatted_prompt = self._format_chat_prompt(request)
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            generation_args = {
                "max_new_tokens": min(request.max_tokens or 2048, 4096),
                "temperature": request.temperature or 0.7,
                "do_sample": True,
                "top_p": 0.9,
                "repetition_penalty": 1.1,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id
            }
            
            # Generate in executor to avoid blocking
            result = await loop.run_in_executor(
                None,
                lambda: self.pipeline(formatted_prompt, **generation_args)
            )
            
            # Extract generated text
            if result and len(result) > 0:
                content = result[0]["generated_text"].strip()
                
                # Estimate token usage
                input_tokens = len(self.tokenizer.encode(formatted_prompt))
                output_tokens = len(self.tokenizer.encode(content))
                
            else:
                content = "I apologize, but I wasn't able to generate a response."
                input_tokens = len(self.tokenizer.encode(formatted_prompt))
                output_tokens = len(self.tokenizer.encode(content))
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            gen_response = GenResponse(
                content=content,
                provider=self.name,
                prompt_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=0.0,  # Local compute
                confidence=0.6,  # Lower confidence for fallback
                metadata={
                    "model": self.model_name,
                    "device": self.device,
                    "local_compute": True,
                    "fallback_provider": True
                }
            )
            
            self._log_generation(request, gen_response)
            return gen_response
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Qwen generation failed: {error_msg}")
            self._log_generation(request, None, error_msg)
            return self._fallback_response(request, start_time, error_msg)
    
    def _format_chat_prompt(self, request: GenRequest) -> str:
        """Format prompt for Qwen chat template."""
        if hasattr(self.tokenizer, 'apply_chat_template'):
            messages = []
            
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            try:
                formatted = self.tokenizer.apply_chat_template(
                    messages, 
                    tokenize=False,
                    add_generation_prompt=True
                )
                return formatted
            except Exception as e:
                self.logger.warning(f"Failed to apply chat template: {e}, using simple format")
        
        # Fallback formatting
        if request.system_prompt:
            return f"System: {request.system_prompt}\n\nUser: {request.prompt}\n\nAssistant:"
        else:
            return f"User: {request.prompt}\n\nAssistant:"
    
    def _fallback_response(self, request: GenRequest, start_time: float, error: str = None) -> GenResponse:
        """Generate static fallback when local model fails."""
        fallback_content = (
            "I apologize, but the local fallback system is currently unavailable. "
            "This could be due to insufficient resources or a configuration issue. "
            "Please try again later or contact support if the issue persists."
        )
        
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return GenResponse(
            content=fallback_content,
            provider=f"{self.name}_error",
            latency_ms=latency_ms,
            metadata={
                "fallback": True, 
                "error": error,
                "load_error": self.load_error,
                "local_compute": True
            }
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Qwen local model health."""
        if not HF_AVAILABLE:
            return {
                "status": "unavailable",
                "reason": "transformers_not_installed",
                "provider": self.name
            }
        
        if not self.is_loaded:
            return {
                "status": "unhealthy",
                "reason": self.load_error or "model_not_loaded",
                "provider": self.name,
                "model": self.model_name
            }
        
        try:
            # Quick health check with minimal generation
            test_request = GenRequest(
                prompt="Hello, how are you?",
                max_tokens=20,
                temperature=0.5
            )
            
            # Don't actually generate for health check to save resources
            # Just verify model is loaded
            health_status = {
                "status": "healthy",
                "provider": self.name,
                "model": self.model_name,
                "device": self.device,
                "local_compute": True,
                "model_loaded": True
            }
            
            # Add memory info if available
            if torch and torch.cuda.is_available():
                try:
                    health_status["gpu_memory_mb"] = torch.cuda.get_device_properties(0).total_memory // (1024**2)
                except:
                    pass
            
            return health_status
            
        except Exception as e:
            return {
                "status": "degraded",
                "reason": str(e),
                "provider": self.name,
                "model": self.model_name
            }
    
    def _estimate_cost(self, prompt_tokens: int, output_tokens: int) -> float:
        """Local compute has no API costs."""
        return 0.0