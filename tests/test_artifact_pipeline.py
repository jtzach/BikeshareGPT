from pathlib import Path

from bikesharegpt.benchmark import run as runmod
from bikesharegpt.benchmark.task import Task
from bikesharegpt.config import AppConfig, ModelSpec
from bikesharegpt.llm.openai_client import LLMUsage
from bikesharegpt.pipeline import Prediction
from bikesharegpt.utils.io import read_jsonl


def test_runner_grades_artifacts_from_full_result_and_keeps_scalar_grading(tmp_path, monkeypatch):
    """Exercise the runner/grader boundary with present and missing artifacts."""
    tasks = [
        Task(id="plot_present", category="synthesis", query="plot", expected=True, grader="artifact_exists"),
        Task(id="plot_missing", category="synthesis", query="plot", expected=True, grader="artifact_exists"),
        Task(id="count", category="retrieval", query="count", expected=7, grader="exact"),
    ]

    def fake_solve(**kwargs):
        task = kwargs["task"]
        output = Path(kwargs["task_output_dir"])
        assert output.is_absolute()
        output.mkdir(parents=True, exist_ok=True)
        result = {"answer": 7}
        if task.id.startswith("plot"):
            target = output / "chart.png"
            if task.id == "plot_present":
                target.write_bytes(b"existence-only regression fixture")
            result = {"answer": "saved", "artifacts": [str(target)]}
        return Prediction(
            task_id=task.id, category=task.category, query=task.query,
            model_text="", executed_code="", exec_success=True,
            result_obj=result, summary_text="", usage_main=LLMUsage(),
            usage_summary=LLMUsage(), wall_time_s=0.0, attempts=1,
        )

    monkeypatch.setattr(runmod, "make_chat_client", lambda **kwargs: object())
    monkeypatch.setattr(runmod, "solve_task", fake_solve)
    # Finalization may invoke optional GPT adjudication; this regression is offline.
    monkeypatch.setattr(runmod, "_finalize_model_run", lambda **kwargs: None)
    runmod._run_one_model(
        cfg=AppConfig(), model_spec=ModelSpec(name="fake", model_main="fake"),
        tasks=tasks, snapshots={}, run_dir=tmp_path / "run",
    )
    rows = read_jsonl(tmp_path / "run" / "predictions" / "grades.jsonl")
    assert [(row["task_id"], row["correct"]) for row in rows] == [
        ("plot_present", True), ("plot_missing", False), ("count", True),
    ]
