from enum import Enum
from typing import TypedDict, get_type_hints

class MOD_DEG(Enum):
    LOW         = "low"
    MID_LOW     = "medium-low"
    MEDIUM      = "medium"
    MID_HIGH    = "medium-high"
    HIGH        = "high"

class LLM_I(TypedDict):
    full_resume:str
    placeholders:dict[str, str]
    mod_deg:MOD_DEG
    faux:bool
    job_posting:str
    acc:str

class LLM_O(TypedDict):
    placeholders: dict[str, str]
    changes_made: str

def get_mod_deg_str()->str:
    a   = "MOD_DEG(Enum):\n"
    b   = "\n".join(f"{m.name} = '{m.value}'" for m in MOD_DEG)
    c   = "\n"    
    return a+b+c

def get_LLM_I_str() -> str:    
    hints = get_type_hints(LLM_I)
    a   = "LLM_I(TypedDict):\n"
    b   = "\n".join(f"{k}: {hints[k].__name__}" for k in hints)
    c   = "\n"
    return a+b+c

def get_LLM_O_str() -> str:    
    hints = get_type_hints(LLM_O)
    a   = "LLM_I(TypedDict):\n"
    b   = "\n".join(f"{k}: {hints[k].__name__}" for k in hints)
    c   = "\n"
    return a+b+c