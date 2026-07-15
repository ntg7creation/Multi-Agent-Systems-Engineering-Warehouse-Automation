from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = REPO_ROOT / "backend"
COPIED = REPO_ROOT / "vercel_build" / "public" / "python" / "warehouse_simulation"


def purge_modules() -> None:
    for name in list(sys.modules):
        if name == "scenarios" or name == "strategy_config" or name.startswith("models"):
            del sys.modules[name]


def run_projection(source: Path, scenario_id: str, seed: int, steps: int) -> Dict[str, object]:
    purge_modules()
    sys.path.insert(0, str(source))
    try:
        from scenarios import build_engine_from_scenario

        engine = build_engine_from_scenario(scenario_id=scenario_id, seed=seed)
        for _ in range(steps):
            engine.step()
        state = engine.serialize_state()
        summary = engine.analytics.summary(engine)
        return {
            "scenario_id": state["scenario"]["scenario_id"],
            "tick": state["tick"],
            "agents": [
                {
                    "agent_id": agent["agent_id"],
                    "position": agent["position"],
                    "mode": agent["mode"],
                    "current_task_id": agent["current_task_id"],
                    "carrying_item_id": agent["carrying_item_id"],
                    "previous_action": agent.get("previous_action_result", {}).get("action", {}).get("type")
                    if agent.get("previous_action_result")
                    else None,
                }
                for agent in state["agents"]
            ],
            "tasks": [
                {
                    "task_id": task["task_id"],
                    "status": task["status"],
                    "assigned_agent_id": task["assigned_agent_id"],
                    "carried_by": task["carried_by"],
                }
                for task in state["tasks"]
            ],
            "completed_tasks": state["metrics"]["global"]["completed_deliveries"],
            "waiting_actions": state["metrics"]["global"]["wait_actions"],
            "blocked_move_attempts": state["metrics"]["global"]["blocked_move_attempts"],
            "route_replans": state["metrics"]["global"]["route_replans"],
            "analytics_event_count": summary["event_count"],
            "replay_frame_count": summary["replay_frame_count"],
        }
    finally:
        if str(source) in sys.path:
            sys.path.remove(str(source))
        purge_modules()


def main() -> None:
    cases = [
        ("simple_one_agent_delivery", 42, 8),
        ("ten_agents_twenty_tasks_stress", 77, 5),
    ]
    results: List[Dict[str, object]] = []
    for scenario_id, seed, steps in cases:
        original = run_projection(ORIGINAL, scenario_id, seed, steps)
        copied = run_projection(COPIED, scenario_id, seed, steps)
        if original != copied:
            print(json.dumps({
                "scenario_id": scenario_id,
                "seed": seed,
                "steps": steps,
                "original": original,
                "copied": copied,
            }, indent=2))
            raise SystemExit(1)
        results.append({
            "scenario_id": scenario_id,
            "seed": seed,
            "steps": steps,
            "tick": copied["tick"],
            "agent_count": len(copied["agents"]),
            "task_count": len(copied["tasks"]),
            "analytics_event_count": copied["analytics_event_count"],
            "replay_frame_count": copied["replay_frame_count"],
        })

    print(json.dumps({"matched_cases": results}, indent=2))


if __name__ == "__main__":
    main()
