from pathlib import Path

from bikesharegpt.config import load_config
from bikesharegpt.scripts.paper_artifacts import export_suite_artifacts
from bikesharegpt.utils.io import read_json


def test_ollama_suite_config_loads():
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / 'configs' / 'mv_rad_gem_full_suite.yaml')
    assert len(cfg.model_suite) == 9
    names = [m.name for m in cfg.model_suite]
    assert names[:3] == ['llama3.2-3b', 'llama3.1-8b', 'llama3.3-70b']
    assert 'qwen3-8b' in names
    assert 'gemma3-12b' in names
    assert 'deepseek-r1-8b' in names
    assert 'mistral-7b' in names
    assert 'gpt-oss-20b' in names
    assert 'gpt-5' in names
    providers = {m.name: m.provider for m in cfg.model_suite}
    assert providers['gpt-5'] == 'openai'
    assert all(providers[n] == 'ollama' for n in names if n != 'gpt-5')


def test_suite_artifact_export(tmp_path):
    suite_dir = tmp_path / 'suite'
    suite_dir.mkdir(parents=True)
    (suite_dir / 'suite_summary.json').write_text(
        '{"run":"suite_test","models":[{"model_label":"llama3.2-3b","provider":"ollama","model_main":"llama3.2:3b","size_label":"3B","overall":{"accuracy":0.5,"exec_success_rate":0.6,"total_tokens":1000,"total_wall_time_s":12.0},"by_category":{"semantics":{"accuracy":0.4},"retrieval":{"accuracy":0.5},"synthesis":{"accuracy":0.6}}}]}'
    )
    out = export_suite_artifacts(suite_dir)
    assert (out / 'table_model_comparison.tex').exists()
    assert (out / 'table_model_cost.tex').exists()
