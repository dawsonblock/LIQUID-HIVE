import asyncio, time, logging, ast, operator as op
from typing import List, Dict, Any, Tuple
from ..security.input_sanitizer import validate_tool_params
from ..retrieval.index import retrieve_topk
log = logging.getLogger(__name__)
ALLOWED_OPS={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Pow:op.pow,ast.USub:lambda x:-x}
def _safe_eval(expr:str):
    def eval_(node):
        if isinstance(node, ast.Num): return node.n
        if isinstance(node, ast.BinOp): return ALLOWED_OPS[type(node.op)](eval_(node.left),eval_(node.right))
        if isinstance(node, ast.UnaryOp): return ALLOWED_OPS[type(node.op)](eval_(node.operand))
        raise ValueError("Unsafe expression")
    return eval_(ast.parse(expr, mode='eval').body)
class ToolAggregator:
    def __init__(self): self.tools={}; self.results_cache={}
    async def maybe_batch(self, tool_hints: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        start=time.perf_counter()
        if not tool_hints: return {"results":[]}, 0.0
        results=[]
        for hint in tool_hints[:5]:
            try:
                clean=validate_tool_params(hint); results.append(await self._execute_tool(clean))
            except Exception as e:
                log.error(f"Tool failure: {e}"); results.append({"error": str(e), "tool": hint.get("tool","unknown")})
        return {"results": results}, (time.perf_counter()-start)*1000
    async def _execute_tool(self, hint: Dict[str, Any]) -> Dict[str, Any]:
        name=hint.get("tool","unknown"); await asyncio.sleep(0.05)
        if name=="local_search":
            q=hint.get("query",""); return {"tool":"local_search","query":q,"results": (await retrieve_topk(q)).get("abstracts",[])}
        if name=="calculator":
            expr=hint.get("expression","0"); return {"tool":"calculator","expression":expr,"result": _safe_eval(expr)}
        return {"tool": name, "status": "completed", "data": "Mock tool execution result"}
    async def health_check(self) -> bool: return True
