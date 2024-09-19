from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InferenceResult:
    ok: bool
    images: List[str]
    error: Optional[str] = None


@dataclass
class StandardResponse:
    results: List[InferenceResult]
