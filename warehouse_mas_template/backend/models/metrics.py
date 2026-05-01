from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class AgentMetrics:
    total_actions: int = 0
    useful_actions: int = 0
    wait_actions: int = 0
    move_actions: int = 0
    pick_actions: int = 0
    place_actions: int = 0
    blocked_move_attempts: int = 0
    path_length: int = 0
    completed_tasks: int = 0
    route_replans: int = 0

    def record_action(self, action_type: str, useful: bool = False) -> None:
        self.total_actions += 1
        if useful:
            self.useful_actions += 1
        if action_type == "wait":
            self.wait_actions += 1
        elif action_type == "move":
            self.move_actions += 1
        elif action_type == "pick":
            self.pick_actions += 1
        elif action_type == "place":
            self.place_actions += 1

    def serialize(self) -> Dict[str, object]:
        efficiency = self.useful_actions / self.total_actions if self.total_actions else 0
        return {
            "total_actions": self.total_actions,
            "useful_actions": self.useful_actions,
            "wait_actions": self.wait_actions,
            "move_actions": self.move_actions,
            "pick_actions": self.pick_actions,
            "place_actions": self.place_actions,
            "blocked_move_attempts": self.blocked_move_attempts,
            "path_length": self.path_length,
            "completed_tasks": self.completed_tasks,
            "route_replans": self.route_replans,
            "efficiency": round(efficiency, 4),
        }


@dataclass
class GlobalMetrics:
    total_steps: int = 0
    total_tasks: int = 0
    completed_deliveries: int = 0
    wait_actions: int = 0
    move_actions: int = 0
    pick_actions: int = 0
    place_actions: int = 0
    blocked_move_attempts: int = 0
    collision_violations: int = 0
    route_replans: int = 0
    task_assignments: int = 0
    pickup_events: int = 0
    delivery_events: int = 0
    total_completion_time: int = 0

    def record_action(self, action_type: str) -> None:
        if action_type == "wait":
            self.wait_actions += 1
        elif action_type == "move":
            self.move_actions += 1
        elif action_type == "pick":
            self.pick_actions += 1
        elif action_type == "place":
            self.place_actions += 1

    def serialize(self) -> Dict[str, object]:
        task_completion_rate = (
            self.completed_deliveries / self.total_tasks if self.total_tasks else 0
        )
        throughput = self.completed_deliveries / self.total_steps if self.total_steps else 0
        movement_attempts = self.move_actions + self.blocked_move_attempts
        collision_score = (
            1 - (self.collision_violations / movement_attempts)
            if movement_attempts
            else 1
        )
        average_completion_time = (
            self.total_completion_time / self.completed_deliveries
            if self.completed_deliveries
            else 0
        )
        return {
            "total_steps": self.total_steps,
            "total_tasks": self.total_tasks,
            "completed_deliveries": self.completed_deliveries,
            "task_completion_rate": round(task_completion_rate, 4),
            "throughput": round(throughput, 4),
            "average_completion_time": round(average_completion_time, 4),
            "wait_actions": self.wait_actions,
            "move_actions": self.move_actions,
            "pick_actions": self.pick_actions,
            "place_actions": self.place_actions,
            "blocked_move_attempts": self.blocked_move_attempts,
            "collision_violations": self.collision_violations,
            "collision_avoidance_score": round(collision_score, 4),
            "route_replans": self.route_replans,
            "task_assignments": self.task_assignments,
            "pickup_events": self.pickup_events,
            "delivery_events": self.delivery_events,
        }
