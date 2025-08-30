import re, logging
log = logging.getLogger(__name__)
def sanitize_input(s: str) -> str:
    if not isinstance(s,str): return ""
    s=re.sub(r'[<>()/\"\']','',s); s=s[:2000]; s=re.sub(r'\s+',' ',s).strip(); return s
def validate_tool_params(params: dict) -> dict:
    clean={}
    for k,v in params.items():
        if isinstance(v,str): clean[k]=sanitize_input(v)
        elif isinstance(v,(int,float,bool)): clean[k]=v
        elif isinstance(v,list): clean[k]=[sanitize_input(str(i)) for i in v[:10]]
    return clean
