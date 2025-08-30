import httpx, os
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from hivemind.adapter_deployment_manager import AdapterDeploymentManager

class VLLMClient:
    def __init__(self, endpoint: str, api_key: str, max_new_tokens: int = 512,
                 adapter: str | None = None, adapter_manager: 'AdapterDeploymentManager | None' = None,
                 role: str = "implementer"):
        """
        Parameters
        ----------
        endpoint: str
            The vLLM API base URL.
        api_key: str
            API key or token for the vLLM server.
        max_new_tokens: int
            Maximum number of tokens to generate.
        adapter: Optional[str]
            Path to the active LoRA adapter for this client.  If provided,
            requests will include this adapter by default.  Adapter A/B
            testing is handled via ``adapter_manager``.
        adapter_manager: Optional[AdapterDeploymentManager]
            If supplied, allows the client to route a fraction of requests to
            a challenger adapter for the configured role.
        role: str
            Logical role name associated with this client (e.g. "architect",
            "implementer").  This is used to look up adapters in the
            deployment manager.  Defaults to "implementer".
        """
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.mnt = max_new_tokens
        self.adapter = adapter
        self.adapter_manager = adapter_manager
        self.role = role
        self.current_adapter_version: str = "champion"

    async def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Invoke the vLLM API to generate a chat completion.

        This method optionally performs LoRA adapter A/B testing if an
        ``AdapterDeploymentManager`` is configured.  A small fraction of
        requests will be routed to a challenger adapter when one exists.
        The chosen adapter version is recorded on the client instance in
        ``current_adapter_version`` for downstream metrics.
        """
        # Determine which adapter to use for this call
        adapter_path = self.adapter
        version_label = "champion"
        if self.adapter_manager is not None:
            try:
                # Use challenger with 5% probability when available
                import random
                challenger = self.adapter_manager.get_challenger(self.role)
                if challenger and random.random() < 0.05:
                    adapter_path = challenger
                    version_label = "challenger"
                else:
                    # Fallback to active adapter if specified for this role
                    active = self.adapter_manager.get_active(self.role)
                    if active:
                        adapter_path = active
                        version_label = "champion"
            except Exception:
                pass
        self.current_adapter_version = version_label
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": "vllm",
            "messages": [
                {"role": "system", "content": system if system else ""},
                {"role": "user", "content": user}
            ],
            "max_tokens": self.mnt,
            "temperature": temperature
        }
        if adapter_path:
            payload["lora"] = {"modules": [{"name": "text-role-adapter", "path": adapter_path}]}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
