from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import yaml


def load_few_shot(path: str | Path) -> str:
    """Load few-shot examples and format them as a single text block."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    examples: List[Dict[str, Any]] = data.get("examples", []) if isinstance(data, dict) else []
    chunks: List[str] = []
    for ex in examples:
        user = ex.get("user", "")
        code = ex.get("code", "")
        if not user or not code:
            continue
        chunks.append(f"Example user question: {user}\nExample solution:\n{code}\n")
    return "\n".join(chunks).strip()
