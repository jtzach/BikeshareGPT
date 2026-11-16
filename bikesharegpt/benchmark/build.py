from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, List

import yaml

from bikesharegpt.benchmark.generators import generate_retrieval_tasks, generate_synthesis_tasks
from bikesharegpt.benchmark.task import Task
from bikesharegpt.gbfs.snapshot import GBFSSnapshot


def load_semantics_tasks(path: str | Path) -> List[Task]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    questions = data.get("questions", []) if isinstance(data, dict) else []
    tasks: List[Task] = []
    for q in questions:
        tid = q.get("id")
        question = q.get("question")
        choices = q.get("choices", {})
        ans = q.get("answer")
        if not tid or not question or not choices or not ans:
            continue
        # Format prompt as MCQ
        formatted = (
            question
            + "\n\nChoices:\n"
            + "\n".join([f"{k}. {v}" for k, v in choices.items()])
            + "\n\nAnswer with a single letter (A/B/C/D)."
        )
        tasks.append(
            Task(
                id=tid,
                category="semantics",
                query=formatted,
                expected=ans,
                grader="exact",
                meta={"choices": choices, "explanation": q.get("explanation", "")},
            )
        )
    return tasks


def build_benchmark(
    *,
    snapshots: Dict[str, GBFSSnapshot],
    include_semantics: bool,
    include_retrieval: bool,
    include_synthesis: bool,
    retrieval_tasks_per_feed: int,
    synthesis_tasks_per_feed: int,
    seed: int,
    semantics_path: str | Path,
) -> List[Task]:
    tasks: List[Task] = []

    if include_semantics:
        tasks.extend(load_semantics_tasks(semantics_path))

    if include_retrieval:
        for sys_id, snap in snapshots.items():
            tasks.extend(generate_retrieval_tasks(snap, retrieval_tasks_per_feed, seed=seed))

    if include_synthesis:
        for sys_id, snap in snapshots.items():
            tasks.extend(generate_synthesis_tasks(snap, synthesis_tasks_per_feed, seed=seed))

    # make ids unique (defensive)
    seen = set()
    for t in tasks:
        if t.id in seen:
            # suffix duplicates
            i = 2
            while f"{t.id}_{i}" in seen:
                i += 1
            t.id = f"{t.id}_{i}"
        seen.add(t.id)

    return tasks
