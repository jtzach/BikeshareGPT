import json
from pathlib import Path

import numpy as np

from bikesharegpt.benchmark.evaluate import grade_task
from bikesharegpt.benchmark.task import Task
from bikesharegpt.pipeline import _extract_answer_from_text
from bikesharegpt.sandbox.executor import extract_python_block
from bikesharegpt.utils.io import read_jsonl, write_jsonl


def test_write_jsonl_sanitizes_numpy_scalars(tmp_path: Path):
    out = tmp_path / "predictions.jsonl"
    rows = [{"task_id": "t1", "result": {"answer": np.int64(7)}}]
    write_jsonl(out, rows)
    loaded = read_jsonl(out)
    assert loaded[0]["result"]["answer"] == 7


def test_extract_python_block_supports_generic_fences():
    text = "```\nresult = {'answer': 1}\n```"
    assert "result" in extract_python_block(text)


def test_extract_answer_from_text_parses_json_and_mcq():
    assert _extract_answer_from_text('{"answer": "A"}') == {"answer": "A"}
    assert _extract_answer_from_text("The correct answer is C.") == {"answer": "C"}


def test_exact_grader_accepts_mcq_prose_answer():
    task = Task(id="sem_1", category="semantics", query="q", expected="B", grader="exact")
    grade = grade_task(task, "The answer is B.")
    assert grade.correct is True


def test_numeric_grader_extracts_number_from_text():
    task = Task(id="syn_1", category="synthesis", query="q", expected=335, grader="numeric", tolerance=0.0)
    grade = grade_task(task, "Total bikes available: 335 bikes")
    assert grade.correct is True