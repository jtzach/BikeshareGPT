from __future__ import annotations

import ast
import io
import multiprocessing as mp
import re
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd
import numpy as np

from bikesharegpt.gbfs.snapshot import GBFSSnapshot


_FENCED_BLOCKS_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\s*(?P<code>.*?)```", re.DOTALL)


def extract_python_block(text: str) -> Optional[str]:
    text = text or ""

    fenced = list(_FENCED_BLOCKS_RE.finditer(text))
    if fenced:
        # Prefer explicitly python/py fenced blocks, otherwise fall back to the first block.
        for m in fenced:
            lang = (m.group("lang") or "").strip().lower()
            if lang in {"python", "py"}:
                return m.group("code").strip()
        return fenced[0].group("code").strip()

    stripped = text.strip()
    # Heuristic: some models emit raw Python without fences.
    if (
        ("result" in stripped and ("feed." in stripped or "import " in stripped or "=" in stripped))
        or stripped.startswith(("import ", "from ", "print(", "df =", "result ="))
    ):
        return stripped
    return None


def _parse_stdout(stdout_text: str) -> Any:
    text = (stdout_text or "").strip()
    if not text:
        raise RuntimeError("Code did not set a `result` variable and produced no parseable stdout.")

    candidates = [text]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        candidates.append(lines[-1])

    for candidate in candidates:
        try:
            import json

            return json.loads(candidate)
        except Exception:
            pass
        try:
            return ast.literal_eval(candidate)
        except Exception:
            pass

    return text


@dataclass
class SandboxResult:
    eval_success: bool
    only_text: bool
    code_output: Any = None
    error_message: Optional[str] = None
    executed_code: Optional[str] = None


def _run_exec(code: str, feed: GBFSSnapshot, output_dir: str, q: mp.Queue) -> None:
    """Worker process: exec code and return `result`."""
    # Minimal namespace
    nm: Dict[str, Any] = {
        "pd": pd,
        "np": np,
        "feed": feed,
        "output_dir": output_dir,
        "__name__": "__main__",
    }
    try:
        stdout_buf = io.StringIO()
        with redirect_stdout(stdout_buf):
            exec(code, nm)  # noqa: S102
        if "result" in nm:
            q.put({"ok": True, "result": nm.get("result")})
            return
        q.put({"ok": True, "result": _parse_stdout(stdout_buf.getvalue())})
    except Exception:
        q.put({"ok": False, "error": traceback.format_exc()})


class SandboxExecutor:
    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    def execute(self, model_text: str, *, feed: GBFSSnapshot, output_dir: str) -> SandboxResult:
        py = extract_python_block(model_text)
        if py is None:
            return SandboxResult(eval_success=False, only_text=True, code_output=model_text, executed_code=None)

        q: mp.Queue = mp.Queue()
        p = mp.Process(target=_run_exec, args=(py, feed, output_dir, q), daemon=True)
        p.start()
        p.join(self.timeout_seconds)

        if p.is_alive():
            p.terminate()
            return SandboxResult(
                eval_success=False,
                only_text=False,
                code_output=None,
                error_message=f"TimeoutError: code execution exceeded {self.timeout_seconds}s",
                executed_code=py,
            )

        if q.empty():
            return SandboxResult(
                eval_success=False,
                only_text=False,
                code_output=None,
                error_message="SandboxError: no result returned",
                executed_code=py,
            )

        msg = q.get()
        if msg.get("ok"):
            return SandboxResult(eval_success=True, only_text=False, code_output=msg.get("result"), executed_code=py)
        return SandboxResult(eval_success=False, only_text=False, code_output=None, error_message=msg.get("error"), executed_code=py)
