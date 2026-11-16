from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from rich import print
from rich.progress import track

from bikesharegpt.benchmark.build import build_benchmark
from bikesharegpt.benchmark.evaluate import Grade, grade_task
from bikesharegpt.benchmark.task import Task
from bikesharegpt.config import AppConfig, ModelSpec
from bikesharegpt.gbfs.downloader import download_multi_snapshot, download_snapshot
from bikesharegpt.gbfs.snapshot import GBFSSnapshot
from bikesharegpt.llm.openai_client import make_chat_client, resolve_provider_settings
from bikesharegpt.pipeline import solve_task
from bikesharegpt.sandbox.executor import SandboxExecutor
from bikesharegpt.utils.io import ensure_dir, read_jsonl, write_json, write_jsonl


def _empty_snapshot() -> GBFSSnapshot:
    return GBFSSnapshot(system_id="__none__", auto_discovery_url="", raw={}, frames={}, meta={})


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "model"


def _resolve_model_suite(cfg: AppConfig) -> List[ModelSpec]:
    if cfg.model_suite:
        return cfg.model_suite
    return [
        ModelSpec(
            name=cfg.run.model_main,
            provider=cfg.run.provider,
            api_key_env=cfg.run.api_key_env,
            base_url=cfg.run.base_url,
            model_main=cfg.run.model_main,
            model_summary=cfg.run.model_summary,
            model_moderation=cfg.run.model_moderation,
            temperature=cfg.run.temperature,
            max_retries=cfg.run.max_retries,
            summary_enabled=cfg.run.summary_enabled,
        )
    ]


def _ordered_rows(tasks: List[Task], row_map: Dict[str, Dict]) -> List[Dict]:
    ordered: List[Dict] = []
    for task in tasks:
        row = row_map.get(task.id)
        if row is not None:
            ordered.append(row)
    return ordered


def _dedupe_rows(path: Path) -> Dict[str, Dict]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    deduped: Dict[str, Dict] = {}
    for row in rows:
        task_id = row.get("task_id")
        if task_id:
            deduped[task_id] = row
    return deduped


def _remove_dir_if_empty(path: Path) -> None:
    """Best-effort cleanup for empty artifact folders."""
    try:
        if path.exists() and path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except Exception:
        # Cleanup should never break a benchmark run.
        pass


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None

    # Support fenced JSON blocks.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if m:
        raw = m.group(1).strip()

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    m2 = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m2:
        return None
    try:
        obj = json.loads(m2.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _build_answer_archive(*, tasks: List[Task], pred_map: Dict[str, Dict], grade_map: Dict[str, Dict]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in tasks:
        pred = pred_map.get(task.id, {})
        grade = grade_map.get(task.id, {})
        rows.append(
            {
                "task_id": task.id,
                "category": task.category,
                "system_id": task.system_id,
                "query": task.query,
                "grader": task.grader,
                "expected": task.expected,
                "predicted": grade.get("predicted"),
                "answer": pred.get("answer"),
                "exec_success": bool(pred.get("exec_success", False)),
                "strict_correct": bool(grade.get("correct", False)),
                "strict_reason": grade.get("reason"),
                "model_text": pred.get("model_text"),
                "executed_code": pred.get("executed_code"),
                "summary_text": pred.get("summary_text"),
                "error_message": pred.get("error_message"),
            }
        )
    return rows


def _run_gpt5_sanity_adjudication(answer_archive_rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Evaluate strict failures with GPT-5 for semantic-equivalence scoring."""
    if not answer_archive_rows:
        return [], None

    # Optional secondary adjudication must be explicitly enabled. It is never
    # part of the primary deterministic score or an offline validation run.
    try:
        configured_max_checks = max(0, int(os.getenv("BSGPT_SANITY_MAX_CHECKS", "0")))
    except ValueError:
        configured_max_checks = 0
    if configured_max_checks == 0:
        return [], None

    try:
        llm = make_chat_client(provider="openai", api_key_env="OPENAI_API_KEY", base_url=None)
    except Exception as e:
        print(f"[yellow]Skipping GPT-5 sanity adjudication[/yellow]: {e}")
        return [], None

    system_prompt = (
        "You are a strict benchmark adjudicator. "
        "Decide whether a model's answer should be considered correct for one GBFS benchmark task. "
        "Treat semantically equivalent wording as correct (for example: 'The answer is A' vs 'A'). "
        "Do not give credit when the value is wrong, missing, or not equivalent. "
        "Return only JSON: {\"correct\": true|false, \"reason\": \"short reason\"}."
    )

    adjudicated: List[Dict[str, Any]] = []
    checked = 0
    changed_to_correct = 0
    total_tokens = 0
    total_time_s = 0.0
    max_checks = configured_max_checks
    try:
        max_checks = int(os.getenv("BSGPT_SANITY_MAX_CHECKS", str(max_checks)))
    except Exception:
        pass
    max_checks = max(0, max_checks)

    import time

    for row in answer_archive_rows:
        base = {
            "task_id": row["task_id"],
            "category": row["category"],
            "strict_correct": bool(row.get("strict_correct", False)),
            "sanity_correct": bool(row.get("strict_correct", False)),
            "sanity_reason": "strict_pass" if row.get("strict_correct", False) else "not_checked",
        }

        if row.get("strict_correct", False):
            adjudicated.append(base)
            continue

        # Sanity adjudication is only useful for plausible semantic-equivalence
        # misses, not for execution failures or missing answers.
        answer = row.get("answer")
        predicted = row.get("predicted")
        reason = str(row.get("strict_reason") or "")
        if not row.get("exec_success", False):
            base["sanity_reason"] = "not_checked_exec_failed"
            adjudicated.append(base)
            continue
        if answer is None and predicted is None:
            base["sanity_reason"] = "not_checked_missing_answer"
            adjudicated.append(base)
            continue
        if reason not in {"mismatch", "set_mismatch"}:
            base["sanity_reason"] = "not_checked_non_semantic_reason"
            adjudicated.append(base)
            continue
        if checked >= max_checks:
            base["sanity_reason"] = "not_checked_budget"
            adjudicated.append(base)
            continue

        checked += 1
        t0 = time.time()
        payload = {
            "task_id": row.get("task_id"),
            "category": row.get("category"),
            "query": row.get("query"),
            "grader": row.get("grader"),
            "expected": row.get("expected"),
            "predicted": row.get("predicted"),
            "answer": row.get("answer"),
            "strict_reason": row.get("strict_reason"),
            "exec_success": row.get("exec_success"),
        }
        try:
            resp = llm.chat(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,
            )
            total_time_s += time.time() - t0
            total_tokens += int(resp.usage.total_tokens or 0)
            parsed = _extract_json_object(resp.content)
            if parsed and isinstance(parsed.get("correct"), bool):
                base["sanity_correct"] = bool(parsed["correct"])
                base["sanity_reason"] = str(parsed.get("reason") or "gpt5_judged")
            else:
                base["sanity_correct"] = bool(row.get("strict_correct", False))
                base["sanity_reason"] = "gpt5_parse_error"
        except Exception as e:
            base["sanity_correct"] = bool(row.get("strict_correct", False))
            base["sanity_reason"] = f"gpt5_error:{type(e).__name__}"

        if (not row.get("strict_correct", False)) and base["sanity_correct"]:
            changed_to_correct += 1
        adjudicated.append(base)

    meta = {
        "checked_failures": checked,
        "promoted_to_correct": changed_to_correct,
        "max_checks": max_checks,
        "total_tokens": total_tokens,
        "total_wall_time_s": total_time_s,
    }
    return adjudicated, meta


def _build_accuracy_summary(rows: List[Dict[str, Any]], *, key: str) -> Dict[str, Any]:
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_cat.setdefault(str(row.get("category")), []).append(row)

    out = {"by_category": {}, "overall": {}}
    total_correct = 0
    for cat, cat_rows in by_cat.items():
        n = len(cat_rows)
        c = sum(1 for r in cat_rows if bool(r.get(key, False)))
        out["by_category"][cat] = {"n": n, "accuracy": c / max(1, n)}
        total_correct += c
    out["overall"] = {
        "n": len(rows),
        "accuracy": total_correct / max(1, len(rows)),
    }
    return out


def _write_status(
    *,
    run_dir: Path,
    model_spec: ModelSpec,
    tasks: List[Task],
    completed: int,
    state: str,
    message: str | None = None,
) -> None:
    write_json(
        run_dir / "status.json",
        {
            "model_label": model_spec.name,
            "provider": model_spec.provider,
            "model_main": model_spec.model_main,
            "size_label": model_spec.size_label,
            "state": state,
            "completed_tasks": completed,
            "total_tasks": len(tasks),
            "remaining_tasks": max(0, len(tasks) - completed),
            "message": message,
        },
    )


def _can_run_model(model_spec: ModelSpec) -> tuple[bool, str | None]:
    try:
        resolve_provider_settings(
            provider=model_spec.provider,
            api_key_env=model_spec.api_key_env,
            base_url=model_spec.base_url,
        )
        return True, None
    except Exception as e:
        return False, str(e)


def _finalize_model_run(
    *,
    cfg: AppConfig,
    model_spec: ModelSpec,
    tasks: List[Task],
    run_dir: Path,
    pred_map: Dict[str, Dict],
    grade_map: Dict[str, Dict],
) -> None:
    ordered_preds = _ordered_rows(tasks, pred_map)
    ordered_grades = _ordered_rows(tasks, grade_map)

    write_jsonl(run_dir / "predictions" / "predictions.jsonl", ordered_preds)
    write_jsonl(run_dir / "predictions" / "grades.jsonl", ordered_grades)

    answer_archive_rows = _build_answer_archive(tasks=tasks, pred_map=pred_map, grade_map=grade_map)
    write_jsonl(run_dir / "predictions" / "answer_archive.jsonl", answer_archive_rows)

    sanity_rows, sanity_meta = _run_gpt5_sanity_adjudication(answer_archive_rows)
    sanity_summary: Optional[Dict[str, Any]] = None
    if sanity_rows:
        write_jsonl(run_dir / "predictions" / "grades_sanity.jsonl", sanity_rows)
        sanity_summary = _build_accuracy_summary(sanity_rows, key="sanity_correct")
        sanity_summary["meta"] = sanity_meta
        write_json(run_dir / "predictions" / "summary_sanity.json", sanity_summary)

    by_cat = {}
    for row in ordered_grades:
        by_cat.setdefault(row["category"], []).append(row)

    summary = {
        "run": run_dir.name,
        "model_label": model_spec.name,
        "provider": model_spec.provider,
        "model_main": model_spec.model_main,
        "size_label": model_spec.size_label,
        "num_tasks": len(tasks),
        "completed_tasks": len(ordered_grades),
        "by_category": {},
    }
    total_correct = 0
    total_exec = 0
    total_tokens = 0
    total_time_s = 0.0
    for cat, rows in by_cat.items():
        acc = sum(1 for r in rows if r["correct"]) / max(1, len(rows))
        exec_rate = sum(1 for r in rows if r["exec_success"]) / max(1, len(rows))
        tokens = sum((r["usage_main"]["total_tokens"] or 0) + (r["usage_summary"]["total_tokens"] or 0) for r in rows)
        time_s = sum(r["wall_time_s"] for r in rows)
        summary["by_category"][cat] = {
            "n": len(rows),
            "accuracy": acc,
            "exec_success_rate": exec_rate,
            "total_tokens": tokens,
            "total_wall_time_s": time_s,
        }
        total_correct += sum(1 for r in rows if r["correct"])
        total_exec += sum(1 for r in rows if r["exec_success"])
        total_tokens += tokens
        total_time_s += time_s

    summary["overall"] = {
        "n": len(ordered_grades),
        "accuracy": total_correct / max(1, len(ordered_grades)),
        "exec_success_rate": total_exec / max(1, len(ordered_grades)),
        "total_tokens": total_tokens,
        "total_wall_time_s": total_time_s,
    }
    write_json(run_dir / "predictions" / "summary.json", summary)

    report_lines = [
        "# BikeshareGPT Run Report\n",
        f"Run: {run_dir.name}\n",
        f"Model: {model_spec.name} ({model_spec.provider}:{model_spec.model_main})\n",
        f"Tasks completed: {len(ordered_grades)}/{len(tasks)}\n",
        "\n## Category Summary\n",
    ]
    for cat, s in summary["by_category"].items():
        report_lines.append(
            f"- **{cat}**: n={s['n']}, accuracy={s['accuracy']:.3f}, exec_success={s['exec_success_rate']:.3f}, "
            f"tokens={s['total_tokens']}, time_s={s['total_wall_time_s']:.1f}"
        )

    if sanity_summary is not None:
        report_lines.append("\n## GPT-5 Sanity Summary\n")
        report_lines.append(
            f"- overall_accuracy_sanity={sanity_summary['overall']['accuracy']:.3f} "
            f"(strict={summary['overall']['accuracy']:.3f})"
        )
        meta = sanity_summary.get("meta") or {}
        report_lines.append(
            f"- checked_failures={meta.get('checked_failures', 0)}, "
            f"promoted_to_correct={meta.get('promoted_to_correct', 0)}, "
            f"tokens={meta.get('total_tokens', 0)}, time_s={meta.get('total_wall_time_s', 0.0):.1f}"
        )
    (run_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

    _write_status(
        run_dir=run_dir,
        model_spec=model_spec,
        tasks=tasks,
        completed=len(ordered_grades),
        state="complete" if len(ordered_grades) == len(tasks) else "partial",
    )

    try:
        from bikesharegpt.scripts.paper_artifacts import export_paper_artifacts

        export_paper_artifacts(run_dir)
    except Exception as e:
        print(f"[yellow]Warning[/yellow]: could not export paper artifacts for {model_spec.name}: {e}")


def _load_or_build_shared_dataset(cfg: AppConfig, shared_dir: Path) -> Tuple[Dict[str, GBFSSnapshot], List[Task]]:
    """Prepare benchmark inputs once, then reuse across all model runs."""
    ensure_dir(shared_dir)
    ensure_dir(shared_dir / "snapshots")
    ensure_dir(shared_dir / "benchmark")

    snapshots: Dict[str, GBFSSnapshot] = {}
    tasks: List[Task] = []

    if cfg.benchmark.dataset_path:
        dataset_dir = Path(cfg.benchmark.dataset_path)
        print(f"[bold]Step 1[/bold] Loading benchmark dataset from: {dataset_dir}")
        from bikesharegpt.utils.io import read_jsonl

        task_rows = read_jsonl(dataset_dir / "tasks.jsonl")
        tasks = [Task.from_dict(r) for r in task_rows]
        tasks = [
            t
            for t in tasks
            if (t.category == "semantics" and cfg.benchmark.semantics)
            or (t.category == "retrieval" and cfg.benchmark.retrieval)
            or (t.category == "synthesis" and cfg.benchmark.synthesis)
        ]

        needed_systems = sorted({t.system_id for t in tasks if t.system_id})
        for sys_id in needed_systems:
            gbfs_path = dataset_dir / "snapshots" / sys_id / "gbfs.json"
            if not gbfs_path.exists():
                raise FileNotFoundError(f"Missing gbfs.json for system_id='{sys_id}': {gbfs_path}")
            snap = download_snapshot(sys_id, str(gbfs_path), language="en", timeout=cfg.run.timeout_seconds)
            snapshots[sys_id] = snap
            snap.save(shared_dir / "snapshots" / sys_id)

        write_jsonl(shared_dir / "benchmark" / "tasks.jsonl", [t.to_dict() for t in tasks])
        print(f"Loaded {len(tasks)} tasks from dataset (systems={len(needed_systems)}).")
        return snapshots, tasks

    print("[bold]Step 1[/bold] Downloading GBFS snapshots...")
    for feed_cfg in cfg.feeds:
        sys_id = feed_cfg.id
        auto_url = feed_cfg.snapshot_path or feed_cfg.auto_discovery_url

        if cfg.benchmark.multi_snapshot:
            snaps = download_multi_snapshot(
                sys_id,
                auto_url,
                language=feed_cfg.language,
                timeout=cfg.run.timeout_seconds,
                snapshots=cfg.benchmark.snapshots_per_feed,
                interval_seconds=cfg.benchmark.snapshot_interval_seconds,
            )
            snapshots[sys_id] = snaps[0]
            for i, s in enumerate(snaps):
                s.save(shared_dir / "snapshots" / sys_id / f"t{i}")
        else:
            snap = download_snapshot(sys_id, auto_url, language=feed_cfg.language, timeout=cfg.run.timeout_seconds)
            snapshots[sys_id] = snap
            snap.save(shared_dir / "snapshots" / sys_id)

    print("[bold]Step 2[/bold] Building benchmark tasks...")
    tasks = build_benchmark(
        snapshots=snapshots,
        include_semantics=cfg.benchmark.semantics,
        include_retrieval=cfg.benchmark.retrieval,
        include_synthesis=cfg.benchmark.synthesis,
        retrieval_tasks_per_feed=cfg.benchmark.retrieval_tasks_per_feed,
        synthesis_tasks_per_feed=cfg.benchmark.synthesis_tasks_per_feed,
        seed=cfg.run.seed,
        semantics_path=Path(__file__).with_name("semantics_questions.yaml"),
    )
    write_jsonl(shared_dir / "benchmark" / "tasks.jsonl", [t.to_dict() for t in tasks])
    print(
        f"Generated {len(tasks)} tasks (semantics={cfg.benchmark.semantics}, "
        f"retrieval={cfg.benchmark.retrieval}, synthesis={cfg.benchmark.synthesis})."
    )
    return snapshots, tasks


def _run_one_model(
    *,
    cfg: AppConfig,
    model_spec: ModelSpec,
    tasks: List[Task],
    snapshots: Dict[str, GBFSSnapshot],
    run_dir: Path,
) -> Path:
    ensure_dir(run_dir)
    ensure_dir(run_dir / "predictions")
    ensure_dir(run_dir / "artifacts")

    pred_path = run_dir / "predictions" / "predictions.jsonl"
    grade_path = run_dir / "predictions" / "grades.jsonl"

    existing_pred_map = _dedupe_rows(pred_path)
    existing_grade_map = _dedupe_rows(grade_path)
    completed_ids = set(existing_grade_map.keys()) & {task.id for task in tasks}

    if completed_ids:
        print(
            f"[cyan]Resume check[/cyan] {model_spec.name}: found {len(completed_ids)}/{len(tasks)} completed tasks in {run_dir}"
        )

    resolved_summary_enabled = (
        model_spec.summary_enabled if model_spec.summary_enabled is not None else cfg.run.summary_enabled
    )
    resolved_temperature = model_spec.temperature if model_spec.temperature is not None else cfg.run.temperature
    resolved_max_retries = model_spec.max_retries if model_spec.max_retries is not None else cfg.run.max_retries
    resolved_summary_model = model_spec.model_summary or cfg.run.model_summary or model_spec.model_main

    llm = make_chat_client(
        provider=model_spec.provider,
        api_key_env=model_spec.api_key_env,
        base_url=model_spec.base_url,
    )
    executor = SandboxExecutor(timeout_seconds=cfg.run.timeout_seconds)

    write_json(
        run_dir / "model_spec.json",
        {
            "name": model_spec.name,
            "provider": model_spec.provider,
            "model_main": model_spec.model_main,
            "model_summary": resolved_summary_model,
            "size_label": model_spec.size_label,
            "notes": model_spec.notes,
            "summary_enabled": resolved_summary_enabled,
            "temperature": resolved_temperature,
            "max_retries": resolved_max_retries,
            "base_url": model_spec.base_url,
            "api_key_env": model_spec.api_key_env,
        },
    )

    if len(completed_ids) >= len(tasks):
        print(f"[green]Skipping[/green] {model_spec.name}: existing results are already complete.")
        _finalize_model_run(
            cfg=cfg,
            model_spec=model_spec,
            tasks=tasks,
            run_dir=run_dir,
            pred_map=existing_pred_map,
            grade_map=existing_grade_map,
        )
        return run_dir

    _write_status(
        run_dir=run_dir,
        model_spec=model_spec,
        tasks=tasks,
        completed=len(completed_ids),
        state="running",
        message="Resuming from existing predictions." if completed_ids else "Starting fresh.",
    )

    print(
        f"[bold]Step 3[/bold] Running tasks for model [cyan]{model_spec.name}[/cyan] "
        f"({model_spec.provider}:{model_spec.model_main})"
    )
    remaining_tasks = [task for task in tasks if task.id not in completed_ids]

    for task in track(remaining_tasks, description=f"Running {model_spec.name}"):
        feed = snapshots.get(task.system_id) if task.system_id else _empty_snapshot()
        # An absolute output directory avoids double-prefixing a model-returned
        # path when the artifact grader resolves relative artifact names.
        task_dir = (run_dir / "artifacts" / task.id).resolve()
        try:
            pred = solve_task(
                task=task,
                feed=feed,
                llm=llm,
                executor=executor,
                task_output_dir=str(task_dir),
                model_main=model_spec.model_main,
                model_summary=resolved_summary_model,
                temperature=resolved_temperature,
                max_retries=resolved_max_retries,
                summary_enabled=resolved_summary_enabled,
                model_label=model_spec.name,
                provider=model_spec.provider,
                size_label=model_spec.size_label,
                few_shot_path=cfg.run.few_shot_path or str(Path(__file__).resolve().parents[2] / "data" / "few_shot_gbfs.yaml"),
            )
            pred_dict = pred.to_dict()
            existing_pred_map[task.id] = pred_dict

            if task.grader == "artifact_exists":
                # Artifact paths are siblings of "answer" in the result schema.
                # Passing only the answer silently marked every plot as missing.
                predicted_answer = pred.result_obj
            elif isinstance(pred.result_obj, dict) and "answer" in pred.result_obj:
                predicted_answer = pred.result_obj.get("answer")
            else:
                predicted_answer = pred.result_obj

            g = _grade_prediction(task, pred, predicted_answer, task_dir)
            existing_grade_map[task.id] = {
                "task_id": task.id,
                "category": task.category,
                "system_id": task.system_id,
                "model_label": model_spec.name,
                "provider": model_spec.provider,
                "size_label": model_spec.size_label,
                "correct": g.correct,
                "reason": g.reason,
                "expected": g.expected,
                "predicted": g.predicted,
                "exec_success": pred.exec_success,
                "wall_time_s": pred.wall_time_s,
                "usage_main": pred.usage_main.__dict__,
                "usage_summary": pred.usage_summary.__dict__,
            }
        except Exception as e:
            # Never lose the full run because one task or one provider request failed.
            existing_pred_map[task.id] = {
                "task_id": task.id,
                "category": task.category,
                "query": task.query,
                "system_id": task.system_id,
                "model_label": model_spec.name,
                "provider": model_spec.provider,
                "size_label": model_spec.size_label,
                "model_text": "",
                "executed_code": None,
                "exec_success": False,
                "result_obj": {"answer": None},
                "summary_text": f"(pipeline_error) {e}",
                "usage_main": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "usage_summary": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "wall_time_s": 0.0,
                "attempts": 0,
                "error_message": str(e),
            }
            existing_grade_map[task.id] = {
                "task_id": task.id,
                "category": task.category,
                "system_id": task.system_id,
                "model_label": model_spec.name,
                "provider": model_spec.provider,
                "size_label": model_spec.size_label,
                "correct": False,
                "reason": f"pipeline_exception:{type(e).__name__}",
                "expected": task.expected,
                "predicted": None,
                "exec_success": False,
                "wall_time_s": 0.0,
                "usage_main": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "usage_summary": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        # Persist after every task so interrupted runs can resume without repeating work.
        write_jsonl(pred_path, _ordered_rows(tasks, existing_pred_map))
        write_jsonl(grade_path, _ordered_rows(tasks, existing_grade_map))
        _write_status(
            run_dir=run_dir,
            model_spec=model_spec,
            tasks=tasks,
            completed=len(existing_grade_map),
            state="running",
        )
        _remove_dir_if_empty(task_dir)

    _remove_dir_if_empty(run_dir / "artifacts")

    _finalize_model_run(
        cfg=cfg,
        model_spec=model_spec,
        tasks=tasks,
        run_dir=run_dir,
        pred_map=existing_pred_map,
        grade_map=existing_grade_map,
    )

    return run_dir


def _export_suite_summary(suite_dir: Path, model_dirs: List[Path], skipped_models: List[Dict[str, str]] | None = None) -> None:
    from bikesharegpt.utils.io import read_json
    from bikesharegpt.scripts.paper_artifacts import export_suite_artifacts

    suite_summary = {"run": suite_dir.name, "models": [], "skipped_models": skipped_models or []}
    for model_dir in model_dirs:
        summary = read_json(model_dir / "predictions" / "summary.json")
        suite_summary["models"].append(summary)

    write_json(suite_dir / "suite_summary.json", suite_summary)

    lines = [
        "# BikeshareGPT Model Suite Report\n",
        f"Suite: {suite_dir.name}\n",
        "\n## Models\n",
    ]
    for model_summary in suite_summary["models"]:
        overall = model_summary.get("overall", {})
        lines.append(
            f"- **{model_summary['model_label']}** ({model_summary['provider']}:{model_summary['model_main']}) | "
            f"accuracy={overall.get('accuracy', 0):.3f}, exec_success={overall.get('exec_success_rate', 0):.3f}, "
            f"tokens={overall.get('total_tokens', 0)}, time_s={overall.get('total_wall_time_s', 0):.1f}"
        )
    if skipped_models:
        lines.append("\n## Skipped Models\n")
        for row in skipped_models:
            lines.append(f"- **{row['name']}**: {row['reason']}")
    (suite_dir / "suite_report.md").write_text("\n".join(lines), encoding="utf-8")
    export_suite_artifacts(suite_dir)


def _grade_prediction(task: Task, prediction, answer: Any, task_dir: Path) -> Grade:
    """A missing/failed result is not an intentional unknown-value answer."""
    if task.expected is None and task.grader == "exact":
        if not prediction.exec_success:
            return Grade(False, "null_requires_successful_execution", None, answer)
        if not isinstance(prediction.result_obj, dict) or "answer" not in prediction.result_obj:
            return Grade(False, "null_requires_explicit_answer", None, answer)
    return grade_task(task, answer, task_output_dir=str(task_dir))


def run_benchmark(cfg: AppConfig) -> Path:
    """Run the benchmark once or as a multi-model suite."""
    out_root = Path(cfg.run.output_root)
    suite_dir = out_root / cfg.run.name
    ensure_dir(suite_dir)
    # Check before overwriting saved inputs/configuration or contacting a model.
    from bikesharegpt.benchmark.identity import guard_run_identity
    guard_run_identity(cfg, suite_dir)
    write_json(suite_dir / "config.json", cfg.model_dump())

    model_suite = _resolve_model_suite(cfg)

    if len(model_suite) == 1:
        snapshots, tasks = _load_or_build_shared_dataset(cfg, suite_dir)
        model_dir = _run_one_model(
            cfg=cfg,
            model_spec=model_suite[0],
            tasks=tasks,
            snapshots=snapshots,
            run_dir=suite_dir,
        )
        print(f"\n[green]Done.[/green] Outputs written to: {model_dir}")
        return model_dir

    print(f"[bold]Model suite[/bold]: running {len(model_suite)} models in one command.")
    shared_dir = suite_dir / "shared"
    snapshots, tasks = _load_or_build_shared_dataset(cfg, shared_dir)

    model_dirs: List[Path] = []
    skipped_models: List[Dict[str, str]] = []
    for spec in model_suite:
        model_dir = suite_dir / "models" / _slugify(spec.name)
        ensure_dir(model_dir)
        runnable, reason = _can_run_model(spec)
        if not runnable:
            print(f"[yellow]Skipping[/yellow] {spec.name}: {reason}")
            write_json(
                model_dir / "skipped.json",
                {
                    "name": spec.name,
                    "provider": spec.provider,
                    "model_main": spec.model_main,
                    "reason": reason,
                },
            )
            _write_status(
                run_dir=model_dir,
                model_spec=spec,
                tasks=tasks,
                completed=0,
                state="skipped",
                message=reason,
            )
            skipped_models.append({"name": spec.name, "reason": reason or "unavailable"})
            continue

        model_dirs.append(
            _run_one_model(
                cfg=cfg,
                model_spec=spec,
                tasks=tasks,
                snapshots=snapshots,
                run_dir=model_dir,
            )
        )

    _export_suite_summary(suite_dir, model_dirs, skipped_models=skipped_models)
    print(f"\n[green]Done.[/green] Suite outputs written to: {suite_dir}")
    return suite_dir
