from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bikesharegpt.benchmark.task import Task
from bikesharegpt.gbfs.snapshot import GBFSSnapshot
from bikesharegpt.llm.fewshot import load_few_shot
from bikesharegpt.llm.openai_client import LLMUsage, OpenAIChat
from bikesharegpt.llm.prompts import (
    MAIN_SYSTEM_PROMPT,
    RETRY_SYSTEM_SUFFIX,
    SUMMARY_SYSTEM_PROMPT,
    make_summary_user_prompt,
    make_user_prompt,
)
from bikesharegpt.sandbox.executor import SandboxExecutor
from bikesharegpt.utils.io import ensure_dir


@dataclass
class Prediction:
    task_id: str
    category: str
    query: str
    model_text: str
    executed_code: Optional[str]
    exec_success: bool
    result_obj: Any
    summary_text: str

    usage_main: LLMUsage
    usage_summary: LLMUsage
    wall_time_s: float
    attempts: int

    system_id: Optional[str] = None
    model_label: Optional[str] = None
    provider: Optional[str] = None
    size_label: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        answer = self.result_obj.get("answer") if isinstance(self.result_obj, dict) and "answer" in self.result_obj else self.result_obj
        return {
            "task_id": self.task_id,
            "category": self.category,
            "query": self.query,
            "system_id": self.system_id,
            "model_label": self.model_label,
            "provider": self.provider,
            "size_label": self.size_label,
            "model_text": self.model_text,
            "executed_code": self.executed_code,
            "exec_success": self.exec_success,
            "answer": answer,
            "result_obj": self.result_obj,
            "summary_text": self.summary_text,
            "usage_main": self.usage_main.__dict__,
            "usage_summary": self.usage_summary.__dict__,
            "wall_time_s": self.wall_time_s,
            "attempts": self.attempts,
            "error_message": self.error_message,
        }


def _extract_answer_from_text(text: str) -> Any:
    """Best-effort parser for non-code answers.

    This is mainly useful for semantics questions where some models answer with
    plain text or a small JSON blob instead of code.
    """
    raw = (text or "").strip()
    if not raw:
        return ""

    # JSON object / array / scalar
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "answer" in parsed:
            return parsed
        return {"answer": parsed}
    except Exception:
        pass

    # Python-literal fallback
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, dict) and "answer" in parsed:
            return parsed
        return {"answer": parsed}
    except Exception:
        pass

    # Common multiple-choice output patterns.
    m = re.search(r"\b([ABCD])\b", raw, flags=re.IGNORECASE)
    if m:
        return {"answer": m.group(1).upper()}

    # If the text looks like a single scalar, keep it as the answer.
    if len(raw.splitlines()) == 1:
        return {"answer": raw}

    return {"answer": raw}


def solve_task(
    *,
    task: Task,
    feed: GBFSSnapshot,
    llm: OpenAIChat,
    executor: SandboxExecutor,
    task_output_dir: str,
    model_main: str,
    model_summary: str,
    temperature: float,
    max_retries: int,
    summary_enabled: bool = True,
    model_label: Optional[str] = None,
    provider: Optional[str] = None,
    size_label: Optional[str] = None,
    few_shot_path: Optional[str] = None,
) -> Prediction:
    """Run the (TransitGPT-style) loop: prompt -> code -> execute -> summarize."""
    t0 = time.time()
    ensure_dir(task_output_dir)

    few_shot = load_few_shot(few_shot_path) if few_shot_path else ""

    system_prompt = MAIN_SYSTEM_PROMPT
    user_prompt = make_user_prompt(task.query, few_shot=few_shot)

    attempts = 0
    total_usage = LLMUsage()
    last_error: Optional[str] = None
    last_model_text: str = ""
    last_exec_code: Optional[str] = None
    last_result_obj: Any = None
    exec_success = False

    while attempts <= max_retries:
        attempts += 1
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = llm.chat(model=model_main, messages=messages, temperature=temperature)
        last_model_text = resp.content
        total_usage.prompt_tokens += resp.usage.prompt_tokens
        total_usage.completion_tokens += resp.usage.completion_tokens
        total_usage.total_tokens += resp.usage.total_tokens

        exec_res = executor.execute(last_model_text, feed=feed, output_dir=task_output_dir)
        last_exec_code = exec_res.executed_code

        if exec_res.only_text:
            # If the model did not output code, salvage the answer when possible
            # (especially useful for semantics / MCQ questions).
            last_result_obj = _extract_answer_from_text(str(exec_res.code_output))
            exec_success = False
            last_error = "No python code block found."
        elif exec_res.eval_success:
            last_result_obj = exec_res.code_output
            exec_success = True
            last_error = None
            break
        else:
            exec_success = False
            last_error = exec_res.error_message or "Unknown execution error"

        # Retry with error feedback
        system_prompt = MAIN_SYSTEM_PROMPT + RETRY_SYSTEM_SUFFIX.format(error=last_error)

    # Summary step (always; keeps outputs consistent)
    summary_text = ""
    usage_summary = LLMUsage()
    if summary_enabled:
        try:
            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": make_summary_user_prompt(task.query, last_result_obj if isinstance(last_result_obj, dict) else {"answer": last_result_obj})},
            ]
            sresp = llm.chat(model=model_summary, messages=messages, temperature=0.0)
            summary_text = sresp.content
            usage_summary = sresp.usage
        except Exception as e:
            summary_text = f"(summary_error) {e}"
    else:
        try:
            summary_text = json.dumps(last_result_obj, ensure_ascii=False)
        except Exception:
            summary_text = str(last_result_obj)

    t1 = time.time()
    return Prediction(
        task_id=task.id,
        category=task.category,
        query=task.query,
        system_id=task.system_id,
        model_label=model_label,
        provider=provider,
        size_label=size_label,
        model_text=last_model_text,
        executed_code=last_exec_code,
        exec_success=exec_success,
        result_obj=last_result_obj,
        summary_text=summary_text,
        usage_main=total_usage,
        usage_summary=usage_summary,
        wall_time_s=t1 - t0,
        attempts=attempts,
        error_message=last_error,
    )
