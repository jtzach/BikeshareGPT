from pathlib import Path

from bikesharegpt.benchmark import run as runmod
from bikesharegpt.config import load_config
from bikesharegpt.llm.openai_client import LLMResponse, LLMUsage


class _FakeLLM:
    def chat(self, *, model, messages, temperature=0.0):
        user = messages[-1]["content"]
        if "Choices:" in user:
            return LLMResponse(content="A", usage=LLMUsage())
        return LLMResponse(content='''```python\nresult = {"answer": 1}\n```''', usage=LLMUsage())


def test_fake_end_to_end_run(tmp_path, monkeypatch):
    cfg = load_config(Path(__file__).resolve().parents[1] / "configs" / "toy.yaml")
    cfg.run.name = "fake_e2e"
    cfg.run.output_root = str(tmp_path / "outputs")
    cfg.run.summary_enabled = False

    monkeypatch.setattr(runmod, "make_chat_client", lambda **kwargs: _FakeLLM())

    out_dir = runmod.run_benchmark(cfg)

    assert (out_dir / "predictions" / "predictions.jsonl").exists()
    assert (out_dir / "predictions" / "grades.jsonl").exists()
    assert (out_dir / "predictions" / "summary.json").exists()
    assert (out_dir / "status.json").exists()