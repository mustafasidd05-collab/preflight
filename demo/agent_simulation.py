"""
Agent Simulation: Demonstrates Preflight intercepting hallucinated/deprecated
code assumptions before execution.

Scenario: An AI coding agent is tasked with creating a settings module for a
modern Python backend using Pydantic v2.
"""

import sys
import time
import json
import asyncio

# Ensure UTF-8 output across platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich import box

from preflight.server import verify_claim


console = Console(highlight=False)


async def run_simulation(replay: bool = False):
    console.print()
    badge_mode = "[bold magenta][REPLAY FIXTURE][/bold magenta]" if replay else "[bold green][LIVE SERPAPI][/bold green]"
    console.print(Panel(
        f"[bold cyan]Preflight[/bold cyan] * [bold white]AI Coding Agent Simulation[/bold white] * {badge_mode}\n"
        "[dim]Demonstrating live search grounding preventing silent API breaking changes[/dim]",
        border_style="cyan" if not replay else "magenta",
        padding=(1, 2),
    ))

    # Step 1: User Prompt to Agent
    user_task = "Write an application config loader for FastAPI using Pydantic v2."
    console.print(f"[bold yellow][Step 1] User Prompt Received:[/bold yellow]")
    console.print(f"  [italic white]\"{user_task}\"[/italic white]\n")
    time.sleep(0.5)

    # Step 2: Agent's Initial Cutoff Generation
    agent_draft = '''from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    app_name: str = "SerpApi Agent Service"
    api_key: str = Field(..., env="SERVICE_API_KEY")
    debug_mode: bool = False

config = Settings()'''

    console.print(f"[bold yellow][Step 2] Agent Training Data Generation (Pre-cutoff Knowledge):[/bold yellow]")
    console.print(Syntax(agent_draft, "python", theme="monokai", line_numbers=True))
    console.print("[dim red][!] Warning: If executed on Pydantic v2, this raises ImportError: cannot import name 'BaseSettings' from 'pydantic'[/dim red]\n")
    time.sleep(0.5)

    # Step 3: Fact Dock Pre-flight Verification Interception
    claim = "In Pydantic v2, BaseSettings is imported directly from pydantic"
    console.print(f"[bold yellow][Step 3] Preflight Interception (Calling verify_claim MCP Tool):[/bold yellow]")
    console.print(f"  [dim]Evaluating claim:[/dim] [cyan]{claim}[/cyan]")
    if replay:
        console.print("  [dim magenta]Mode: REPLAY FIXTURE (replaying recorded SerpApi query)...[/dim magenta]\n")
    else:
        console.print("  [dim green]Mode: LIVE SERPAPI (executing real outbound HTTP request to SerpApi)...[/dim green]\n")

    t0 = time.perf_counter()
    verdict_raw = await verify_claim(claim=claim, replay=replay)
    verdict = json.loads(verdict_raw)
    total_latency_ms = (time.perf_counter() - t0) * 1000

    # Step 4: Verification Result Breakdown
    status = verdict.get("verdict")
    conf = verdict.get("confidence", 0.0) * 100
    canonical = verdict.get("canonical_reference")
    correction = verdict.get("correction")
    is_replayed = verdict.get("is_replayed", False)

    table = Table(title="Preflight Verification Interception", box=box.ROUNDED)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")

    table.add_row("Execution Mode", "[bold magenta]REPLAY FIXTURE[/bold magenta]" if is_replayed else "[bold green]LIVE SERPAPI[/bold green]")
    table.add_row("Verdict", f"[bold red]{status} ({conf:.0f}% confidence)[/bold red]")
    table.add_row("Canonical Source", f"{canonical}")
    table.add_row("Identified Issue", verdict.get("summary"))
    table.add_row("Recommended Fix", f"[bold green]{correction}[/bold green]")
    table.add_row("Full Pipeline Latency", f"[bold]{total_latency_ms:.1f}ms[/bold] (Decomposition -> Search -> Rank -> Synthesize)")
    console.print(table)
    console.print()
    time.sleep(0.5)

    # Step 5: Grounded Agent Self-Correction
    corrected_code = '''# Automatically grounded and verified by Preflight
from pydantic_settings import BaseSettings  # Updated from official docs
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "SerpApi Agent Service"
    api_key: str = Field(..., validation_alias="SERVICE_API_KEY")
    debug_mode: bool = False

config = Settings()'''

    console.print(f"[bold yellow][Step 5] Agent Emits Grounded, Verified Code:[/bold yellow]")
    console.print(Syntax(corrected_code, "python", theme="monokai", line_numbers=True))
    console.print()

    console.print(Panel(
        "[bold green][OK] Mission Accomplished![/bold green]\n"
        "Preflight successfully prevented a runtime `ImportError` by validating the agent's assumption "
        "against authoritative SerpApi documentation before generating code.",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


if __name__ == "__main__":
    import os
    has_api_key = bool(os.getenv("SERPAPI_API_KEY"))

    if "--replay" in sys.argv:
        use_replay = True
    elif "--live" in sys.argv:
        use_replay = False
    else:
        # Default: if key is present run LIVE, otherwise run REPLAY with notification
        use_replay = not has_api_key

    if not has_api_key and not use_replay:
        console.print("[bold red][!] Error:[/bold red] --live requested but SERPAPI_API_KEY is not set.")
        sys.exit(1)

    if not has_api_key and use_replay:
        console.print("[dim yellow][*] Note: SERPAPI_API_KEY not set in environment. Running with pre-recorded SerpApi replay fixture (--replay).[/dim yellow]")

    asyncio.run(run_simulation(replay=use_replay))
