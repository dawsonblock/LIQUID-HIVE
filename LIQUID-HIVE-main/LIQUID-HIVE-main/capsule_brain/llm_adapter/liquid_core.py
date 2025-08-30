import logging, torch, numpy as np
from typing import List, Dict, Any
log = logging.getLogger(__name__)
INPUT_SIZE=384; HIDDEN_SIZE=256; OUTPUT_SIZE=384

class MockCfC(torch.nn.Module):
    def __init__(self,in_features,hidden_size,out_features):
        super().__init__(); self.l1=torch.nn.Linear(in_features,hidden_size); self.l2=torch.nn.Linear(hidden_size,out_features); self.act=torch.nn.Tanh()
    def forward(self,inputs,hidden):
        outs=[]; 
        for t in range(inputs.shape[1]):
            x=inputs[:,t,:]; hidden=self.act(self.l1(x)+hidden); outs.append(self.l2(hidden).unsqueeze(1))
        return torch.cat(outs,dim=1), hidden

class LiquidReasoningCore:
    def __init__(self):
        self.device="cuda" if torch.cuda.is_available() else "cpu"
        log.info(f"Liquid Core on {self.device}")
        self.cfc_model=MockCfC(INPUT_SIZE,HIDDEN_SIZE,OUTPUT_SIZE).to(self.device)
        self.hidden_state=torch.zeros(1,HIDDEN_SIZE).to(self.device)
        self.engine_ref=None; self.state_health_checks=True
    def _text_to_embedding(self, text:str)->torch.Tensor:
        h=hash(text)%(2**31); arr=[(h>>i)&1 for i in range(INPUT_SIZE)]
        return torch.tensor(arr,dtype=torch.float32,device=self.device).unsqueeze(0)
    def _check_state(self)->bool:
        if not self.state_health_checks: return True
        arr=self.hidden_state.detach().cpu().numpy()
        if not np.isfinite(arr).all(): self.hidden_state=torch.zeros(1,HIDDEN_SIZE).to(self.device); return False
        if abs(arr).max()>100: self.hidden_state=torch.tanh(self.hidden_state); return False
        return True
    async def _decode(self, vec: torch.Tensor)->str:
        if self.engine_ref:
            vec_list=vec.squeeze(0).detach().cpu().numpy().tolist()
            results=self.engine_ref.search_memory(vec_list, top_k=1)
            if results: return f"[Liquid Thought] Focusing on: {results[0].get('text','processing')}."
        norm=float(torch.norm(vec).item())
        return "[Liquid Thought] High-intensity cognitive processing detected." if norm>5 else "[Liquid Thought] Moderate cognitive activity." if norm>2 else "[Liquid Thought] Low-level background processing."
    async def process_stream(self, context_snippets: List[str])->Dict[str,Any]:
        try:
            if not self._check_state(): pass
            inputs=torch.zeros(1,1,INPUT_SIZE,device=self.device) if not context_snippets else torch.stack([self._text_to_embedding(t) for t in context_snippets[:10]], dim=1)
            with torch.no_grad(): out,self.hidden_state=self.cfc_model(inputs,self.hidden_state); final=out[:,-1,:]
            decoded=await self._decode(final); self._check_state()
            return {"text": decoded, "output_norm": float(torch.norm(final).item()), "context_length": len(context_snippets)}
        except Exception as e:
            log.error(f"Liquid processing error: {e}"); return {"text":"[Error] Liquid core processing failed."}
    def attach_engine_reference(self, engine): self.engine_ref=engine
