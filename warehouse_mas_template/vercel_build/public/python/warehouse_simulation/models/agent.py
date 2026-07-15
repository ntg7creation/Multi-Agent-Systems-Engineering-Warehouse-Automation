from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .action import Action, ActionResult, MOVE, WAIT
from .agent_log import AgentLogModule
from .communication import CommunicationModule
from .congestion import CongestionEstimationModule
from .decision import DecisionModule
from .goal import GoalHolder
from .memory import MemoryModule
from .metrics import AgentMetrics
from .movement import PathPlanningModule
from .perception import PerceptionModule

Position = Tuple[int, int]


@dataclass
class Agent:
    agent_id: str
    position: Position
    mode: str = "idle"
    goal_holder: GoalHolder = field(default_factory=GoalHolder)
    perception_module: PerceptionModule = field(default_factory=PerceptionModule)
    memory_module: MemoryModule = field(default_factory=MemoryModule)
    path_planning_module: PathPlanningModule = field(default_factory=PathPlanningModule)
    congestion_module: CongestionEstimationModule = field(default_factory=CongestionEstimationModule)
    communication_module: CommunicationModule = field(default_factory=CommunicationModule)
    decision_module: DecisionModule = field(default_factory=DecisionModule)
    agent_log_module: AgentLogModule = field(default_factory=AgentLogModule)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    carrying_item_id: Optional[str] = None
    current_task_id: Optional[str] = None
    current_target: Optional[Position] = None
    planned_path: list[Position] = field(default_factory=list)
    current_path_cost: float = 0.0
    intended_action: Optional[Action] = None
    previous_action_result: Optional[ActionResult] = None
    waiting_counter: int = 0
    failed_movement_counter: int = 0
    replanning_flag: bool = False

    def perceive_and_remember(self, engine: "SimulationEngine") -> Dict[str, object]:
        perception = self.perception_module.perceive(self, engine)
        self.memory_module.remember(perception)
        return perception

    def update_congestion(self, tick: int) -> Dict[str, object]:
        return self.congestion_module.update(self, tick)

    def select_intended_action(self, tick: int, rng=None) -> Action:
        return self.decision_module.select_action(self, tick, rng)

    def assign_task(self, task: Dict[str, object], tick: int) -> None:
        self.current_task_id = str(task["task_id"])
        self.goal_holder.target_delivery_id = self.current_task_id
        self.goal_holder.goal_type = "pickup"
        self.mode = "assigned"
        self.current_target = tuple(task["pickup_position"])
        self.planned_path = []
        self.replanning_flag = True
        self.memory_module.remember_task(task, tick)
        self.agent_log_module.record(
            tick=tick,
            event_type="TASK_ASSIGNED",
            message=f"{self.agent_id} received task {self.current_task_id}.",
            data={"task": task},
        )

    def current_task_snapshot(self) -> Optional[Dict[str, object]]:
        if not self.current_task_id:
            return None
        entry = self.memory_module.known_tasks.get(self.current_task_id)
        return entry.value if entry else None

    def receive_action_result(self, result: ActionResult, tick: int) -> None:
        self.previous_action_result = result
        action_type = result.action.type

        if action_type == WAIT:
            self.waiting_counter += 1
            self.memory_module.record_wait(self.position, tick)
        elif result.success:
            if action_type == MOVE:
                self.waiting_counter = 0
                self.failed_movement_counter = 0
        else:
            if action_type == MOVE:
                self.failed_movement_counter += 1
                self.replanning_flag = True
                if result.target_position:
                    self.memory_module.record_failed_move(result.target_position, tick)
            self.mode = "waiting"

        self.agent_log_module.record(
            tick=tick,
            event_type="ACTION_RESULT",
            message=f"{self.agent_id} received result for {action_type}.",
            data=result.serialize(),
        )

    def clear_task(self) -> None:
        self.current_task_id = None
        self.current_target = None
        self.planned_path = []
        self.current_path_cost = 0.0
        self.goal_holder.clear()
        self.mode = "idle"

    @staticmethod
    def _distance(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @property
    def is_available_for_task(self) -> bool:
        return self.current_task_id is None and self.carrying_item_id is None

    @property
    def state(self) -> str:
        return self.mode

    @state.setter
    def state(self, value: str) -> None:
        self.mode = value

    @property
    def carrying_box_id(self) -> Optional[str]:
        return self.carrying_item_id

    @carrying_box_id.setter
    def carrying_box_id(self, value: Optional[str]) -> None:
        self.carrying_item_id = value

    @property
    def movement_module(self) -> PathPlanningModule:
        return self.path_planning_module

    def serialize(self, include_memory: bool = False) -> Dict[str, object]:
        data = {
            "agent_id": self.agent_id,
            "position": self.position,
            "state": self.mode,
            "mode": self.mode,
            "goal_type": self.goal_holder.goal_type,
            "goal_delivery_id": self.goal_holder.target_delivery_id,
            "goal_task_id": self.goal_holder.target_delivery_id,
            "current_task_id": self.current_task_id,
            "current_target": self.current_target,
            "carrying_box_id": self.carrying_item_id,
            "carrying_item_id": self.carrying_item_id,
            "intended_action": self.intended_action.serialize() if self.intended_action else None,
            "previous_action_result": self.previous_action_result.serialize()
            if self.previous_action_result
            else None,
            "planned_path": self.planned_path,
            "waiting_counter": self.waiting_counter,
            "failed_movement_counter": self.failed_movement_counter,
            "replanning_flag": self.replanning_flag,
            "perception_radius": self.perception_module.radius,
            "perception": self._serialize_perception(),
            "memory": self.memory_module.serialize_summary(),
            "memory_map": self._serialize_memory_map(),
            "communication": self.communication_module.serialize(),
            "movement": self.path_planning_module.serialize(),
            "congestion": self.congestion_module.serialize(),
            "agent_log": self.agent_log_module.serialize(),
            "metrics": self.metrics.serialize(),
        }
        if include_memory:
            data["memory_detail"] = self.memory_module.serialize_detail()
        return data

    def _serialize_perception(self) -> Dict[str, object]:
        perception = self.memory_module.last_perception or {}
        return {
            "tick": perception.get("tick"),
            "radius": self.perception_module.radius,
            "visible_cells": perception.get("visible_cells", []),
            "visible_agents": perception.get("visible_agents", []),
            "visible_items": perception.get("visible_items", []),
            "visible_pickups": perception.get("visible_pickups", []),
            "visible_deliveries": perception.get("visible_deliveries", []),
            "occupied_cells": perception.get("occupied_cells", []),
        }

    def _serialize_memory_map(self) -> Dict[str, object]:
        congestion_values = [
            float(entry.value)
            for entry in self.memory_module.congestion.values()
        ]
        max_congestion = max(congestion_values) if congestion_values else 0.0
        return {
            "map_size": self.memory_module.map_size,
            "known_cells": [
                {
                    "position": position,
                    "cell_type": entry.value.get("cell_type", "unknown"),
                    "walkable": entry.value.get("walkable"),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for position, entry in sorted(self.memory_module.known_cells.items())
            ],
            "known_pickups": [
                {
                    "pickup_id": pickup_id,
                    "position": entry.value.get("position"),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for pickup_id, entry in sorted(self.memory_module.known_pickups.items())
            ],
            "known_deliveries": [
                {
                    "dropoff_id": dropoff_id,
                    "position": entry.value.get("position"),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for dropoff_id, entry in sorted(self.memory_module.known_deliveries.items())
            ],
            "known_items": [
                {
                    "item_id": item_id,
                    "task_id": entry.value.get("task_id"),
                    "position": entry.value.get("position"),
                    "state": entry.value.get("state"),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for item_id, entry in sorted(self.memory_module.known_items.items())
            ],
            "known_agents": [
                {
                    "agent_id": agent_id,
                    "position": entry.value.get("position"),
                    "state": entry.value.get("state"),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for agent_id, entry in sorted(self.memory_module.known_agents.items())
            ],
            "congestion": [
                {
                    "position": position,
                    "value": round(float(entry.value), 4),
                    "last_seen_tick": entry.last_seen_tick,
                }
                for position, entry in sorted(self.memory_module.congestion.items())
            ],
            "cell_history": [
                {"position": position, **history.serialize()}
                for position, history in sorted(self.memory_module.cell_history.items())
            ],
            "max_congestion": round(max_congestion, 4),
        }
