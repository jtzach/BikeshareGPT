from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich import print

from bikesharegpt.config import load_config
from bikesharegpt.benchmark.run import run_benchmark

app = typer.Typer(add_completion=False, help="BikeshareGPT: GBFS benchmark runner and framework")


@app.command()
def run(config: str = typer.Option("configs/mv_rad_gemma_ministral_gpt5_suite.yaml", "--config", "-c", help="Path to YAML config.")):
    load_dotenv()
    cfg = load_config(config)
    print(f"[bold]BikeshareGPT[/bold] | run={cfg.run.name} | feeds={len(cfg.feeds)}")
    run_benchmark(cfg)


if __name__ == "__main__":
    app()
