import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bikesharegpt.benchmark.evaluate import grade_task
from bikesharegpt.benchmark.identity import guard_run_identity
from bikesharegpt.benchmark.run import _grade_prediction, _run_gpt5_sanity_adjudication
from bikesharegpt.benchmark.task import Task
from bikesharegpt.config import AppConfig


@pytest.mark.parametrize("answer,correct", [(64, True), (64.0, True), ("64", True), (64.9, False), ("64.9", False), (True, False), (float("inf"), False)])
def test_exact_integer_never_truncates_or_accepts_boolean(answer, correct):
    task = Task(id="count", category="retrieval", query="Count", expected=64)
    assert grade_task(task, answer).correct is correct


def test_numeric_scientific_notation_and_nonfinite():
    task = Task(id="numeric", category="synthesis", query="Number", expected=1000, grader="numeric")
    assert grade_task(task, "1e3").correct
    assert not grade_task(task, "1e309").correct
    assert not grade_task(task, float("nan")).correct


@pytest.mark.parametrize("success,result,correct", [(True, {"answer": None}, True), (False, {"answer": None}, False), (True, {}, False), (True, None, False), (True, {"answer": "null"}, False), (True, {"answer": 0}, False)])
def test_null_target_requires_success_and_explicit_null(tmp_path, success, result, correct):
    task = Task(id="unknown", category="synthesis", query="Unknown", expected=None)
    pred = SimpleNamespace(exec_success=success, result_obj=result)
    answer = result.get("answer") if isinstance(result, dict) else result
    assert _grade_prediction(task, pred, answer, tmp_path).correct is correct


def config_and_dataset(tmp_path):
    dataset = tmp_path / "data"
    dataset.mkdir()
    (dataset / "tasks.jsonl").write_text('{"id":"same-id","query":"original"}\n')
    (dataset / "manifest.json").write_text('{"version":"1.1.0"}')
    cfg = AppConfig()
    cfg.benchmark.dataset_path = str(dataset)
    suite = tmp_path / "run"
    suite.mkdir()
    return cfg, dataset, suite


def test_resume_refuses_changed_question_with_same_id_without_overwriting(tmp_path):
    cfg, dataset, suite = config_and_dataset(tmp_path)
    guard_run_identity(cfg, suite)
    identity = (suite / "run_identity.json").read_bytes()
    (suite / "predictions").mkdir()
    stored = suite / "predictions/grades.jsonl"
    stored.write_text('original saved grades')
    guard_run_identity(cfg, suite)  # Identical inputs can resume.
    (dataset / "tasks.jsonl").write_text('{"id":"same-id","query":"changed"}\n')
    with pytest.raises(ValueError, match="fresh run"):
        guard_run_identity(cfg, suite)
    assert (suite / "run_identity.json").read_bytes() == identity
    assert stored.read_text() == 'original saved grades'


def test_resume_refuses_legacy_directory_and_changed_model(tmp_path):
    cfg, dataset, suite = config_and_dataset(tmp_path)
    (suite / "config.json").write_text('{}')
    with pytest.raises(ValueError, match="no verifiable"):
        guard_run_identity(cfg, suite)
    assert not (suite / "run_identity.json").exists()
    clean = tmp_path / "clean"
    clean.mkdir()
    guard_run_identity(cfg, clean)
    cfg.run.model_main = "another-model"
    with pytest.raises(ValueError, match="fresh run"):
        guard_run_identity(cfg, clean)


def test_optional_model_adjudication_is_off_by_default(monkeypatch):
    monkeypatch.delenv("BSGPT_SANITY_MAX_CHECKS", raising=False)
    assert _run_gpt5_sanity_adjudication([{"correct": False}]) == ([], None)


@pytest.mark.parametrize("provider,env", [("openai", "OPENAI_BASE_URL"), ("ollama", "OLLAMA_BASE_URL")])
def test_resume_refuses_changed_effective_endpoint(tmp_path, monkeypatch, provider, env):
    cfg, dataset, suite = config_and_dataset(tmp_path)
    cfg.run.provider = provider
    monkeypatch.setenv(env, "https://first.example/v1?token=private-value")
    guard_run_identity(cfg, suite)
    saved = (suite / "run_identity.json").read_text()
    assert "private-value" not in saved
    monkeypatch.setenv(env, "https://second.example/v1")
    with pytest.raises(ValueError, match="fresh run"):
        guard_run_identity(cfg, suite)
    assert (suite / "run_identity.json").read_text() == saved


def test_resume_fingerprints_enabled_sanity_endpoint(tmp_path, monkeypatch):
    cfg, dataset, suite = config_and_dataset(tmp_path)
    cfg.run.provider = "ollama"
    cfg.run.base_url = "https://fixed.example/v1"
    monkeypatch.setenv("BSGPT_SANITY_MAX_CHECKS", "1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://first.example/v1")
    guard_run_identity(cfg, suite)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://second.example/v1")
    with pytest.raises(ValueError, match="fresh run"):
        guard_run_identity(cfg, suite)
