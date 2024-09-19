from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InferenceResult:
    ok: bool
    error: Optional[str] = None


@dataclass
class StandardResponse:
    results: List[InferenceResult]
