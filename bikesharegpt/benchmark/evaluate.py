from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from bikesharegpt.benchmark.task import Task


@dataclass
class Grade:
    correct: bool
    reason: str = ""
    expected: Any = None
    predicted: Any = None


GRADING_PROTOCOL_VERSION = "1.1.0"


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _normalize_str(x: Any) -> str:
    return str(x).strip().lower()


def _normalize_exact(predicted: Any, expected: Any) -> Any:
    """Make exact grading more robust for common model-output patterns."""
    if isinstance(expected, bool):
        if isinstance(predicted, str):
            p = predicted.strip().lower()
            if p in {"true", "yes", "1"}:
                return True
            if p in {"false", "no", "0"}:
                return False

    if _is_number(expected):
        px = _extract_numeric(predicted)
        if px is not None:
            if isinstance(expected, int):
                # Exact integer answers must not silently truncate 64.9 to 64.
                return int(px) if px.is_integer() else px
            return float(px)

    if isinstance(expected, str):
        if isinstance(predicted, str):
            text = predicted.strip()
            # Multiple-choice benchmark items often contain "The answer is A".
            if len(expected.strip()) == 1 and expected.strip().isalpha():
                m = re.search(r"\b([A-Za-z])\b", text)
                if m:
                    return m.group(1).upper()

            # Try JSON or python-literal wrappers like {"answer": "A"}
            for parser in (json.loads, None):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and "answer" in parsed:
                        return parsed["answer"]
                except Exception:
                    pass

            return text.strip()
    return predicted


def _extract_numeric(x: Any) -> Optional[float]:
    if _is_number(x):
        value = float(x)
        return value if math.isfinite(value) else None
    if isinstance(x, str):
        m = re.search(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", x.replace(",", ""))
        if m:
            try:
                value = float(m.group(0))
                return value if math.isfinite(value) else None
            except Exception:
                return None
    return None


def _coerce_iterable(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, (list, tuple, set)):
        return [str(v) for v in x]
    if isinstance(x, str):
        text = x.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except Exception:
            pass
        parts = [p.strip() for p in re.split(r"[\n,;]+", text) if p.strip()]
        return parts
    return [str(x)]


def _deep_equal(a: Any, b: Any) -> bool:
    # cheap deep equality with numeric tolerance handled elsewhere
    if isinstance(a, bool) != isinstance(b, bool) and (_is_number(a) or _is_number(b)):
        return False
    return a == b


def grade_task(task: Task, predicted: Any, *, task_output_dir: Optional[str] = None) -> Grade:
    expected = task.expected
    grader = task.grader

    if grader == "exact":
        predicted = _normalize_exact(predicted, expected)
        if isinstance(expected, str) and isinstance(predicted, str):
            ok = _normalize_str(predicted) == _normalize_str(expected)
            return Grade(correct=ok, reason="exact_norm" if ok else "mismatch", expected=expected, predicted=predicted)
        ok = _deep_equal(predicted, expected)
        return Grade(correct=ok, reason="exact_match" if ok else "mismatch", expected=expected, predicted=predicted)

    if grader == "set":
        exp_set = {_normalize_str(x) for x in _coerce_iterable(expected)}
        pred_set = {_normalize_str(x) for x in _coerce_iterable(predicted)}
        ok = exp_set == pred_set
        return Grade(correct=ok, reason="set_match" if ok else "set_mismatch", expected=sorted(exp_set), predicted=sorted(pred_set))

    if grader == "contains":
        # expected should be a list of required keywords
        req = [_normalize_str(x) for x in (expected or [])]
        pred_text = _normalize_str(predicted)
        missing = [k for k in req if k not in pred_text]
        ok = len(missing) == 0
        return Grade(correct=ok, reason="contains" if ok else f"missing:{missing}", expected=req, predicted=predicted)

    if grader == "numeric":
        tol = task.tolerance or 0.0
        # Case 1: scalar numeric
        if _is_number(expected):
            if not math.isfinite(float(expected)):
                return Grade(False, reason="invalid_numeric_target", expected=expected, predicted=predicted)
            px = _extract_numeric(predicted)
            if px is None:
                return Grade(False, reason="pred_not_numeric", expected=expected, predicted=predicted)
            ok = abs(px - float(expected)) <= tol
            return Grade(ok, reason="within_tol" if ok else "out_of_tol", expected=expected, predicted=px)

        # Case 2: dict with distance + name (used for nearest-station task)
        if isinstance(expected, dict) and isinstance(predicted, dict):
            # name exact (case-insensitive)
            exp_name = expected.get("name")
            pred_name = predicted.get("name")
            if exp_name is not None and pred_name is None:
                return Grade(False, reason="missing_name", expected=expected, predicted=predicted)
            if exp_name is not None and pred_name is not None:
                if _normalize_str(exp_name) != _normalize_str(pred_name):
                    return Grade(False, reason="name_mismatch", expected=expected, predicted=predicted)

            # distance within tolerance (if present)
            exp_d = expected.get("distance_m")
            pred_d = predicted.get("distance_m")
            if exp_d is not None and pred_d is not None:
                try:
                    exp_d = float(exp_d)
                    pred_d = float(pred_d)
                except Exception:
                    return Grade(False, reason="distance_not_numeric", expected=expected, predicted=predicted)
                ok = abs(pred_d - exp_d) <= tol
                return Grade(ok, reason="within_tol" if ok else "out_of_tol", expected=expected, predicted=predicted)

            # If we can't compare, fallback to exact
            ok = expected == predicted
            return Grade(ok, reason="dict_exact" if ok else "dict_mismatch", expected=expected, predicted=predicted)

        return Grade(False, reason="unsupported_numeric_shape", expected=expected, predicted=predicted)

    if grader == "artifact_exists":
        # expected is boolean; predicted should contain artifacts list with existing files
        if not task_output_dir:
            return Grade(False, reason="missing_task_output_dir", expected=expected, predicted=predicted)
        artifacts = []
        if isinstance(predicted, dict):
            artifacts = predicted.get("artifacts") or []
        if not artifacts:
            return Grade(False, reason="no_artifacts", expected=True, predicted=predicted)
        # Check file exists
        missing = []
        for p in artifacts:
            # allow absolute or relative
            full = p
            if not os.path.isabs(full):
                full = os.path.join(task_output_dir, p)
            if not os.path.exists(full):
                missing.append(full)
        ok = len(missing) == 0
        return Grade(ok, reason="artifact_ok" if ok else f"missing_files:{len(missing)}", expected=True, predicted=artifacts)

    return Grade(False, reason=f"unknown_grader:{grader}", expected=expected, predicted=predicted)
