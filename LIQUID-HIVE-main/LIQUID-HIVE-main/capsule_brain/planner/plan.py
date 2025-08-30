import asyncio, time, logging
from typing import Dict, Any
log = logging.getLogger(__name__)
async def plan_once(query: str) -> Dict[str, Any]:
    start=time.perf_counter()
    try:
        tool_hints=[]; ql=query.lower()
        if any(k in ql for k in ["latest","current","recent","news"]): tool_hints.append({"tool":"local_search","query":query,"priority":"high"})
        if any(k in ql for k in ["calculate","compute","math"]): tool_hints.append({"tool":"calculator","expression":query,"priority":"medium"})
        await asyncio.sleep(0.05)
        return {"tool_hints": tool_hints, "reasoning_steps":"direct_response" if not tool_hints else "tool_assisted", "confidence":0.8, "lat_ms": (time.perf_counter()-start)*1000}
    except Exception as e:
        log.error(f"Planning failed: {e}"); return {"tool_hints": [], "reasoning_steps":"fallback", "lat_ms": (time.perf_counter()-start)*1000, "error": str(e)}
