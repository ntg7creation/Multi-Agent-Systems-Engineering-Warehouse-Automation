from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from io import StringIO
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import SimulationEngine


@dataclass
class UtilityWeights:
    alpha: float = 10.0
    beta: float = 0.2
    gamma: float = 0.5
    delta: float = 1.0
    epsilon: float = 2.0


@dataclass
class Analytics:
    run_id: str
    utility_weights: UtilityWeights = field(default_factory=UtilityWeights)
    global_event_log: List[Dict[str, object]] = field(default_factory=list)
    action_flow_replay_log: List[Dict[str, object]] = field(default_factory=list)
    metric_timeline: List[Dict[str, object]] = field(default_factory=list)
    blocked_movements_by_cell: Dict[str, int] = field(default_factory=dict)
    waiting_events_by_cell: Dict[str, int] = field(default_factory=dict)
    final_run_summary: Optional[Dict[str, object]] = None

    def record_event(self, event: Dict[str, object]) -> None:
        self.global_event_log.append(event)
        event_type = event.get("type")
        cell = event.get("target") or event.get("position") or event.get("source")
        if event_type in {"MOVE_REJECTED", "BLOCKED_PATH_DETECTED"}:
            self._increment_cell(self.blocked_movements_by_cell, cell)
        if event_type == "WAIT_ACTION":
            self._increment_cell(self.waiting_events_by_cell, cell)

    def record_replay_frame(self, frame: Dict[str, object]) -> None:
        self.action_flow_replay_log.append(frame)
        metrics = frame.get("metrics", {})
        global_metrics = metrics.get("global", {}) if isinstance(metrics, dict) else {}
        self.metric_timeline.append({
            "tick": frame.get("tick"),
            "completed_deliveries": global_metrics.get("completed_deliveries", 0),
            "throughput": global_metrics.get("throughput", 0),
            "wait_actions": global_metrics.get("wait_actions", 0),
            "blocked_move_attempts": global_metrics.get("blocked_move_attempts", 0),
            "route_replans": global_metrics.get("route_replans", 0),
        })

    def summary(self, engine: "SimulationEngine") -> Dict[str, object]:
        metrics = engine.serialize_metrics()
        global_metrics = dict(metrics["global"])
        agents = self.agent_metrics(engine)
        utility_values = [agent["utility_score"] for agent in agents.values()]
        social_welfare = sum(utility_values) / len(utility_values) if utility_values else 0
        global_metrics.update({
            "run_id": self.run_id,
            "current_tick": engine.tick,
            "completion_time": engine.tick if engine.is_complete else None,
            "active_agent_count": len(engine.agents),
            "total_waiting_actions": global_metrics.get("wait_actions", 0),
            "total_blocked_movements": global_metrics.get("blocked_move_attempts", 0),
            "replanning_frequency": (
                global_metrics.get("route_replans", 0) / engine.tick if engine.tick else 0
            ),
            "social_welfare": round(social_welfare, 4),
            "utility_weights": asdict(self.utility_weights),
        })
        path_metrics = self.path_metrics(engine)
        summary = {
            "run_id": self.run_id,
            "scenario": engine.serialize_scenario_info(),
            "is_complete": engine.is_complete,
            "system": global_metrics,
            "agents": agents,
            "path_congestion": path_metrics,
            "timeline": list(self.metric_timeline),
            "event_count": len(self.global_event_log),
            "replay_frame_count": len(self.action_flow_replay_log),
        }
        if engine.is_complete:
            self.final_run_summary = summary
        return summary

    def agent_metrics(self, engine: "SimulationEngine") -> Dict[str, Dict[str, object]]:
        agents: Dict[str, Dict[str, object]] = {}
        for agent in engine.agents:
            serialized = dict(agent.metrics.serialize())
            utility = self._utility(serialized)
            serialized.update({
                "agent_id": agent.agent_id,
                "tasks_completed": serialized.get("completed_tasks", 0),
                "wait_count": serialized.get("wait_actions", 0),
                "failed_movement_count": serialized.get("blocked_move_attempts", 0),
                "replanning_count": serialized.get("route_replans", 0),
                "actual_path_length": serialized.get("path_length", 0),
                "utility_score": round(utility, 4),
            })
            agents[agent.agent_id] = serialized
        return agents

    def local_agent_decision_log(self, engine: "SimulationEngine") -> List[Dict[str, object]]:
        decisions: List[Dict[str, object]] = []
        for agent in engine.agents:
            for entry in agent.agent_log_module.serialize(limit=200)["entries"]:
                row = dict(entry)
                row["run_id"] = self.run_id
                row["agent_id"] = agent.agent_id
                decisions.append(row)
        return sorted(decisions, key=lambda row: (int(row.get("tick") or 0), str(row.get("agent_id"))))

    def path_metrics(self, engine: "SimulationEngine") -> Dict[str, object]:
        completed_tasks = [task for task in engine.tasks if task.status == "delivered"]
        task_paths = [
            {
                "task_id": task.task_id,
                "agent_id": task.assigned_agent_id,
                "actual_path_length": task.actual_path_length,
                "shortest_feasible_path_length": task.shortest_path_length,
                "path_inefficiency": task.path_inefficiency,
            }
            for task in completed_tasks
        ]
        problematic_cells = self._problematic_cells()
        congestion_replans = [
            event for event in self.global_event_log
            if event.get("type") in {"REPLAN_TRIGGERED", "BLOCKED_PATH_DETECTED"}
        ]
        return {
            "completed_task_paths": task_paths,
            "blocked_movements_by_cell": self._cell_counts(self.blocked_movements_by_cell),
            "waiting_events_by_cell": self._cell_counts(self.waiting_events_by_cell),
            "replanning_events_caused_by_congestion": len(congestion_replans),
            "problematic_cells": problematic_cells,
        }

    def export_json(self, engine: "SimulationEngine") -> Dict[str, object]:
        return {
            "summary": self.summary(engine),
            "events": list(self.global_event_log),
            "agent_decisions": self.local_agent_decision_log(engine),
            "replay": list(self.action_flow_replay_log),
            "final_run_summary": self.final_run_summary,
        }

    def export_csv(self, engine: "SimulationEngine") -> str:
        output = StringIO()
        output.write("# events\n")
        event_fields = [
            "event_id", "run_id", "tick", "type", "agent_id", "task_id", "item_id",
            "result", "rejection_reason", "message", "source", "target",
        ]
        writer = csv.DictWriter(output, fieldnames=event_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.global_event_log)

        output.write("\n# agent_metrics\n")
        agents = list(self.agent_metrics(engine).values())
        if agents:
            agent_fields = [
                "agent_id", "tasks_completed", "total_actions", "useful_actions",
                "efficiency", "wait_count", "failed_movement_count", "replanning_count",
                "actual_path_length", "average_delivery_time", "path_inefficiency",
                "utility_score",
            ]
            writer = csv.DictWriter(output, fieldnames=agent_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(agents)
        return output.getvalue()

    def _utility(self, metrics: Dict[str, object]) -> float:
        weights = self.utility_weights
        tasks = float(metrics.get("completed_tasks", 0) or 0)
        steps = float(metrics.get("total_actions", 0) or 0)
        waits = float(metrics.get("wait_actions", 0) or 0)
        inefficiency = float(metrics.get("path_inefficiency", 0) or 0)
        collisions = float(metrics.get("blocked_move_attempts", 0) or 0)
        return (
            weights.alpha * tasks
            - weights.beta * steps
            - weights.gamma * waits
            - weights.delta * inefficiency
            - weights.epsilon * collisions
        )

    def _problematic_cells(self) -> List[Dict[str, object]]:
        scores: Dict[str, Dict[str, int]] = {}
        for cell, count in self.blocked_movements_by_cell.items():
            scores.setdefault(cell, {"blocked_movements": 0, "waiting_events": 0})
            scores[cell]["blocked_movements"] = count
        for cell, count in self.waiting_events_by_cell.items():
            scores.setdefault(cell, {"blocked_movements": 0, "waiting_events": 0})
            scores[cell]["waiting_events"] = count
        rows = [
            {
                "cell": cell,
                "blocked_movements": values["blocked_movements"],
                "waiting_events": values["waiting_events"],
                "score": values["blocked_movements"] + values["waiting_events"],
            }
            for cell, values in scores.items()
        ]
        return sorted(rows, key=lambda row: row["score"], reverse=True)[:10]

    @staticmethod
    def _increment_cell(counter: Dict[str, int], cell: object) -> None:
        if cell is None:
            return
        if isinstance(cell, (list, tuple)) and len(cell) >= 2:
            key = f"{cell[0]},{cell[1]}"
        else:
            key = str(cell)
        counter[key] = counter.get(key, 0) + 1

    @staticmethod
    def _cell_counts(counter: Dict[str, int]) -> List[Dict[str, object]]:
        return [
            {"cell": cell, "count": count}
            for cell, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
        ]
