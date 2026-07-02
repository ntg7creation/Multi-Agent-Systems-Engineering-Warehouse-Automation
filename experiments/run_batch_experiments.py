from __future__ import annotations

import argparse
import base64
import csv
import json
import subprocess
import statistics
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

# Resolve repository paths.
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "warehouse_mas_template" / "backend"
FRONTEND_DIR = REPO_ROOT / "warehouse_mas_template" / "frontend"
FRONTEND_MAP_RENDERER = FRONTEND_DIR / "scripts" / "render_final_map_cli.mjs"
SCENARIO_DIR = BACKEND_DIR / "scenario_data"
OUTPUTS_DIR = REPO_ROOT / "experiments" / "outputs"

# Keep required default step policy centralized.
DEFAULT_MAX_STEPS = 1000
MAX_STEP_OVERRIDES: Dict[str, int] = {
    "ten_agents_twenty_tasks_stress": 2000,
    "six_agents_corridor_passing_bays": 1500,
    "six_agents_twelve_tasks_hotspots": 1500,
    "eight_agents_dense_crossing": 1500,
}

SUMMARY_COLUMNS = [
    "run_id",
    "experiment_label",
    "config_profile",
    "scenario",
    "seed",
    "max_steps",
    "finished",
    "termination_reason",
    "agents",
    "tasks",
    "ticks",
    "completed_tasks",
    "task_completion_rate",
    "throughput",
    "avg_task_completion_time",
    "total_waits",
    "total_blocked_moves",
    "total_replans",
    "collision_preventions",
    "avg_utility",
    "social_welfare",
    "raw_json_path",
    "raw_csv_path",
    "final_state_path",
    "final_map_path",
    "config_snapshot_path",
]

AGENT_COLUMNS = [
    "run_id",
    "experiment_label",
    "config_profile",
    "scenario",
    "seed",
    "agent_id",
    "tasks_completed",
    "total_actions",
    "useful_actions",
    "efficiency",
    "wait_count",
    "failed_movement_count",
    "replanning_count",
    "actual_path_length",
    "average_delivery_time",
    "path_inefficiency",
    "utility_score",
]

# Fallback tiny valid PNG (1x1 transparent) in case map rendering fails.
FALLBACK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAAHo3x0AAAAASUVORK5CYII="
)


# Import simulator directly from backend source to preserve runtime behavior.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scenarios import build_engine_from_scenario  # type: ignore  # noqa: E402
from strategy_config import (  # type: ignore  # noqa: E402
    config_profile_from_label,
    config_profile_overrides,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch runner for Warehouse Automation MAS simulator.",
    )
    parser.add_argument(
        "--experiment-label",
        required=True,
        help="Metadata label only. Does not change simulator behavior.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=None,
        help="Optional subset of scenario IDs (filename stem from scenario_data).",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=1,
        help="First seed to run (inclusive). Default: 1",
    )
    parser.add_argument(
        "--seed-end",
        type=int,
        default=10,
        help="Last seed to run (inclusive). Default: 10",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Global max steps override for all scenarios.",
    )
    parser.add_argument(
        "--config-profile",
        choices=["scenario", "advanced", "baseline"],
        default=None,
        help=(
            "Strategy config profile. Defaults from --experiment-label: "
            "Baseline-* uses baseline, Advanced-* uses scenario config."
        ),
    )
    args = parser.parse_args()

    if args.seed_start <= 0 or args.seed_end <= 0:
        raise ValueError("seed-start and seed-end must be positive integers.")
    if args.seed_start > args.seed_end:
        raise ValueError("seed-start must be less than or equal to seed-end.")
    if args.max_steps is not None and args.max_steps <= 0:
        raise ValueError("max-steps must be a positive integer if provided.")

    return args


def discover_scenarios() -> List[str]:
    if not SCENARIO_DIR.exists():
        raise FileNotFoundError(f"Scenario directory not found: {SCENARIO_DIR}")
    return sorted(path.stem for path in SCENARIO_DIR.glob("*.json"))


def resolve_scenarios(requested: Optional[Iterable[str]]) -> List[str]:
    available = discover_scenarios()
    if not requested:
        return available

    requested_list = list(requested)
    unknown = sorted(set(requested_list) - set(available))
    if unknown:
        raise ValueError(
            f"Unknown scenarios: {unknown}. Available: {available}",
        )

    # Preserve the command-line order.
    return requested_list


def scenario_file_path(scenario_id: str) -> Path:
    return SCENARIO_DIR / f"{scenario_id}.json"


def load_scenario_config(scenario_id: str) -> Dict[str, object]:
    file_path = scenario_file_path(scenario_id)
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def max_steps_for(scenario_id: str, global_override: Optional[int]) -> int:
    if global_override is not None:
        return int(global_override)
    return int(MAX_STEP_OVERRIDES.get(scenario_id, DEFAULT_MAX_STEPS))


def ensure_output_dirs(experiment_label: str) -> Dict[str, Path]:
    roots = {
        "raw_json": OUTPUTS_DIR / "raw_json" / experiment_label,
        "raw_csv": OUTPUTS_DIR / "raw_csv" / experiment_label,
        "final_states": OUTPUTS_DIR / "final_states" / experiment_label,
        "final_maps": OUTPUTS_DIR / "final_maps" / experiment_label,
        "config_snapshots": OUTPUTS_DIR / "config_snapshots" / experiment_label,
        "summary": OUTPUTS_DIR / "summary",
        "logs": OUTPUTS_DIR / "logs",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    return roots


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def append_csv_row(path: Path, columns: List[str], row: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in columns})


def append_many_csv_rows(path: Path, columns: List[str], rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except Exception:
        return str(path.resolve())


def write_error_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message)
        if not message.endswith("\n"):
            handle.write("\n")


def save_fallback_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(FALLBACK_PNG_BYTES)


def render_final_map_with_frontend(
    final_state: Dict[str, object],
    replay_frames: List[Dict[str, object]],
    out_path: Path,
) -> None:
    if not FRONTEND_MAP_RENDERER.exists():
        raise FileNotFoundError(f"Frontend map renderer script not found: {FRONTEND_MAP_RENDERER}")

    with tempfile.TemporaryDirectory(prefix="warehouse_final_map_") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        state_path = temp_dir / "state.json"
        replay_path = temp_dir / "replay.json"

        write_json(state_path, final_state)
        write_json(replay_path, replay_frames)

        command = [
            "node",
            str(FRONTEND_MAP_RENDERER),
            "--state",
            str(state_path),
            "--replay",
            str(replay_path),
            "--out",
            str(out_path),
        ]
        result = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or f"exit code {result.returncode}"
            raise RuntimeError(f"Frontend renderer failed: {details}")

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("Frontend renderer finished without creating a valid PNG file.")


def render_final_map_png(final_state: Dict[str, object], out_path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except Exception as exc:
        save_fallback_png(out_path)
        raise RuntimeError(
            "matplotlib is required for final map rendering; wrote fallback PNG instead.",
        ) from exc

    map_data = final_state.get("map", {}) if isinstance(final_state, dict) else {}
    width = int(map_data.get("width", 0) or 0)
    height = int(map_data.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        save_fallback_png(out_path)
        return

    blocked = {tuple(cell) for cell in (map_data.get("blocked") or [])}
    pickups = map_data.get("pickups") or {}
    dropoffs = map_data.get("dropoffs") or {}

    fig_w = max(6, min(22, width * 0.55))
    fig_h = max(4, min(18, height * 0.55))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=140)

    # Base background.
    ax.add_patch(Rectangle((0, 0), width, height, facecolor="#f6f7fb", edgecolor="none"))

    # Grid lines.
    for x in range(width + 1):
        ax.plot([x, x], [0, height], color="#d3d7e0", linewidth=0.6, zorder=1)
    for y in range(height + 1):
        ax.plot([0, width], [y, y], color="#d3d7e0", linewidth=0.6, zorder=1)

    # Blocked cells.
    for x, y in blocked:
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#212529", edgecolor="#111", linewidth=0.4, zorder=2))

    # Pickup and delivery service cells.
    for pickup_id, pos in pickups.items():
        x, y = int(pos[0]), int(pos[1])
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#2e7d32", alpha=0.6, edgecolor="#1b5e20", linewidth=1.0, zorder=3))
        ax.text(x + 0.5, y + 0.5, str(pickup_id), fontsize=6, ha="center", va="center", color="white", zorder=4)

    for dropoff_id, pos in dropoffs.items():
        x, y = int(pos[0]), int(pos[1])
        ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#1565c0", alpha=0.55, edgecolor="#0d47a1", linewidth=1.0, zorder=3))
        ax.text(x + 0.5, y + 0.5, str(dropoff_id), fontsize=6, ha="center", va="center", color="white", zorder=4)

    # Agent positions.
    for agent in final_state.get("agents", []) or []:
        position = agent.get("position") if isinstance(agent, dict) else None
        if not position:
            continue
        x, y = float(position[0]), float(position[1])
        ax.scatter(x + 0.5, y + 0.5, s=130, marker="o", color="#d62828", edgecolors="white", linewidths=0.9, zorder=6)
        ax.text(x + 0.5, y + 0.5, str(agent.get("agent_id", "A")), fontsize=6, ha="center", va="center", color="white", zorder=7)

    # Item positions if known.
    for item in final_state.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if position is None:
            continue
        x, y = float(position[0]), float(position[1])
        ax.scatter(x + 0.5, y + 0.5, s=55, marker="x", color="#ff8f00", linewidths=1.4, zorder=8)

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect("equal")
    ax.set_xticks(range(width + 1))
    ax.set_yticks(range(height + 1))
    ax.tick_params(axis="both", labelsize=7)
    ax.set_title("Final Warehouse State", fontsize=11)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def run_single(
    experiment_label: str,
    config_profile: str,
    config_overrides: Optional[Dict[str, object]],
    scenario_id: str,
    seed: int,
    max_steps: int,
    roots: Dict[str, Path],
) -> Dict[str, object]:
    scenario_config = load_scenario_config(scenario_id)
    scenario_path = scenario_file_path(scenario_id)

    engine = build_engine_from_scenario(
        scenario_id=scenario_id,
        seed=seed,
        config_overrides=config_overrides,
    )

    while engine.tick < max_steps and not engine.is_complete:
        engine.step()

    finished = bool(engine.is_complete)
    termination_reason = "completed" if finished else "max_steps_reached"

    summary = engine.analytics.summary(engine)
    analytics_json = engine.analytics.export_json(engine)
    analytics_csv = engine.analytics.export_csv(engine)
    final_state = engine.serialize_state()
    replay_frames = analytics_json.get("replay", []) if isinstance(analytics_json, dict) else []
    if not isinstance(replay_frames, list):
        replay_frames = []

    run_id = str(engine.run_id)
    timestamp = now_iso()

    raw_json_path = roots["raw_json"] / scenario_id / f"seed_{seed}.json"
    raw_csv_path = roots["raw_csv"] / scenario_id / f"seed_{seed}.csv"
    final_state_path = roots["final_states"] / f"{scenario_id}_seed_{seed}_final_state.json"
    final_map_path = roots["final_maps"] / f"{scenario_id}_seed_{seed}_final_map.png"
    config_snapshot_path = roots["config_snapshots"] / f"{scenario_id}_seed_{seed}_config_snapshot.json"

    write_json(raw_json_path, analytics_json)
    raw_csv_path.parent.mkdir(parents=True, exist_ok=True)
    raw_csv_path.write_text(analytics_csv, encoding="utf-8")
    write_json(final_state_path, final_state)

    # Try to render map; preserve execution by writing fallback png on errors.
    map_render_error = None
    map_renderer = "frontend_canvas"
    try:
        render_final_map_with_frontend(final_state, replay_frames, final_map_path)
    except Exception as exc:  # pragma: no cover - safety path
        map_render_error = f"frontend renderer: {exc}"
        map_renderer = "matplotlib_fallback"
        try:
            render_final_map_png(final_state, final_map_path)
        except Exception as fallback_exc:  # pragma: no cover - safety path
            map_render_error = f"{map_render_error}; matplotlib fallback: {fallback_exc}"
            map_renderer = "fallback_png"
            save_fallback_png(final_map_path)

    config_snapshot = {
        "experiment_label": experiment_label,
        "scenario_id": scenario_id,
        "seed": seed,
        "max_steps": max_steps,
        "run_id": run_id,
        "timestamp": timestamp,
        "scenario_file_path": str(scenario_path.resolve()),
        "config_profile": config_profile,
        "scenario_configuration": scenario_config,
        "effective_configuration": engine.config,
        "config_overrides": config_overrides or {},
        "final_map_renderer": map_renderer,
    }
    if map_render_error:
        config_snapshot["final_map_warning"] = map_render_error

    write_json(config_snapshot_path, config_snapshot)

    system = summary.get("system", {}) if isinstance(summary, dict) else {}
    agents_summary = summary.get("agents", {}) if isinstance(summary, dict) else {}

    completed_tasks = int(system.get("completed_deliveries", 0) or 0)
    total_tasks = int(system.get("total_tasks", len(final_state.get("tasks", []) or [])) or 0)
    ticks = int(system.get("current_tick", final_state.get("tick", engine.tick)) or engine.tick)

    utilities = []
    for agent_data in (agents_summary or {}).values():
        if isinstance(agent_data, dict):
            value = agent_data.get("utility_score")
            if value is not None:
                try:
                    utilities.append(float(value))
                except Exception:
                    pass

    avg_utility = round(statistics.fmean(utilities), 4) if utilities else 0.0

    summary_row = {
        "run_id": run_id,
        "experiment_label": experiment_label,
        "config_profile": config_profile,
        "scenario": scenario_id,
        "seed": seed,
        "max_steps": max_steps,
        "finished": str(finished).lower(),
        "termination_reason": termination_reason,
        "agents": len(final_state.get("agents", []) or []),
        "tasks": total_tasks,
        "ticks": ticks,
        "completed_tasks": completed_tasks,
        "task_completion_rate": system.get("task_completion_rate", ""),
        "throughput": system.get("throughput", ""),
        "avg_task_completion_time": system.get("average_completion_time", ""),
        "total_waits": system.get("wait_actions", ""),
        "total_blocked_moves": system.get("blocked_move_attempts", ""),
        "total_replans": system.get("route_replans", ""),
        "collision_preventions": system.get("collision_preventions", ""),
        "avg_utility": avg_utility,
        "social_welfare": system.get("social_welfare", ""),
        "raw_json_path": repo_relative(raw_json_path),
        "raw_csv_path": repo_relative(raw_csv_path),
        "final_state_path": repo_relative(final_state_path),
        "final_map_path": repo_relative(final_map_path),
        "config_snapshot_path": repo_relative(config_snapshot_path),
    }

    per_agent_rows: List[Dict[str, object]] = []
    for agent_id, agent_data in (agents_summary or {}).items():
        if not isinstance(agent_data, dict):
            continue
        per_agent_rows.append(
            {
                "run_id": run_id,
                "experiment_label": experiment_label,
                "config_profile": config_profile,
                "scenario": scenario_id,
                "seed": seed,
                "agent_id": agent_id,
                "tasks_completed": agent_data.get("tasks_completed", agent_data.get("completed_tasks", "")),
                "total_actions": agent_data.get("total_actions", ""),
                "useful_actions": agent_data.get("useful_actions", ""),
                "efficiency": agent_data.get("efficiency", ""),
                "wait_count": agent_data.get("wait_count", agent_data.get("wait_actions", "")),
                "failed_movement_count": agent_data.get("failed_movement_count", agent_data.get("blocked_move_attempts", "")),
                "replanning_count": agent_data.get("replanning_count", agent_data.get("route_replans", "")),
                "actual_path_length": agent_data.get("actual_path_length", agent_data.get("path_length", "")),
                "average_delivery_time": agent_data.get("average_delivery_time", ""),
                "path_inefficiency": agent_data.get("path_inefficiency", ""),
                "utility_score": agent_data.get("utility_score", ""),
            }
        )

    return {
        "summary_row": summary_row,
        "per_agent_rows": per_agent_rows,
    }


def main() -> int:
    args = parse_args()
    roots = ensure_output_dirs(args.experiment_label)
    config_profile = args.config_profile or config_profile_from_label(args.experiment_label)
    config_overrides = config_profile_overrides(config_profile)

    scenarios = resolve_scenarios(args.scenarios)
    seeds = list(range(args.seed_start, args.seed_end + 1))

    summary_path = roots["summary"] / "all_runs_summary.csv"
    agent_summary_path = roots["summary"] / "all_agent_metrics.csv"
    error_log_path = roots["logs"] / "errors.log"

    completed_runs = 0
    failed_runs = 0

    for scenario_id in scenarios:
        for seed in seeds:
            max_steps = max_steps_for(scenario_id, args.max_steps)
            try:
                result = run_single(
                    experiment_label=args.experiment_label,
                    config_profile=config_profile,
                    config_overrides=config_overrides,
                    scenario_id=scenario_id,
                    seed=seed,
                    max_steps=max_steps,
                    roots=roots,
                )

                summary_row = result["summary_row"]
                agent_rows = result["per_agent_rows"]

                append_csv_row(summary_path, SUMMARY_COLUMNS, summary_row)
                append_many_csv_rows(agent_summary_path, AGENT_COLUMNS, agent_rows)

                completed_runs += 1
                print(
                    f"{args.experiment_label} | {scenario_id} | {seed} | "
                    f"{summary_row.get('ticks', '')} | "
                    f"{summary_row.get('completed_tasks', '')}/{summary_row.get('tasks', '')} tasks | "
                    f"{summary_row.get('social_welfare', '')} | "
                    f"{summary_row.get('finished', '')}"
                )
            except Exception:
                failed_runs += 1
                tb = traceback.format_exc()
                error_message = (
                    f"[{now_iso()}] experiment_label={args.experiment_label} "
                    f"scenario={scenario_id} seed={seed} max_steps={max_steps}\n{tb}\n"
                )
                write_error_log(error_log_path, error_message)

                error_row = {
                    "run_id": "",
                    "experiment_label": args.experiment_label,
                    "config_profile": config_profile,
                    "scenario": scenario_id,
                    "seed": seed,
                    "max_steps": max_steps,
                    "finished": "false",
                    "termination_reason": "error",
                    "agents": "",
                    "tasks": "",
                    "ticks": "",
                    "completed_tasks": "",
                    "task_completion_rate": "",
                    "throughput": "",
                    "avg_task_completion_time": "",
                    "total_waits": "",
                    "total_blocked_moves": "",
                    "total_replans": "",
                    "collision_preventions": "",
                    "avg_utility": "",
                    "social_welfare": "",
                    "raw_json_path": "",
                    "raw_csv_path": "",
                    "final_state_path": "",
                    "final_map_path": "",
                    "config_snapshot_path": "",
                }
                append_csv_row(summary_path, SUMMARY_COLUMNS, error_row)

                print(
                    f"{args.experiment_label} | {scenario_id} | {seed} | "
                    f"error | 0/0 tasks | n/a | false"
                )

    print(f"completed runs: {completed_runs}")
    print(f"failed runs: {failed_runs}")
    print(f"all runs summary: {repo_relative(summary_path)}")
    print(f"all agent metrics: {repo_relative(agent_summary_path)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
