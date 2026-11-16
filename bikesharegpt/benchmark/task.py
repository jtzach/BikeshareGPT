from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Task:
    id: str
    category: str  # semantics | retrieval | synthesis
    query: str

    system_id: Optional[str] = None  # which GBFS system / feed (for retrieval/synthesis)
    expected: Any = None  # ground truth (JSON-serializable)

    grader: str = "exact"  # exact | set | numeric | contains | artifact_exists
    tolerance: float = 0.0  # numeric tolerance
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Task":
        return Task(**d)
