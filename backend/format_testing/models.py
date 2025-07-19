from enum import Enum
from typing import TypedDict, Literal
import json

class MOD_DEG(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

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
    