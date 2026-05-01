from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

from .action import Action
from .communication import CommunicationModule
from .goal import GoalHolder
from .memory import MemoryModule
from .metrics import AgentMetrics
from .movement import MovementModule
from .perception import PerceptionModule

Position = Tuple[int, int]


@dataclass
class Agent:
    agent_id: str
    position: Position
    state: str = "idle"
    goal_holder: GoalHolder = field(default_factory=GoalHolder)
    perception_module: PerceptionModule = field(default_factory=PerceptionModule)
    memory_module: MemoryModule = field(default_factory=MemoryModule)
    movement_module: MovementModule = field(default_factory=MovementModule)
    communication_module: CommunicationModule = field(default_factory=CommunicationModule)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    carrying_box_id: Optional[str] = None

    def perceive_and_remember(self, engine: "SimulationEngine") -> Dict[str, object]:
        perception = self.perception_module.perceive(self, engine)
        self.memory_module.remember(perception)
        return perception

    def step(self, engine: "SimulationEngine", occupied: Set[Position]) -> Action:
        return self.choose_next_action(engine, occupied)

    def choose_next_action(self, engine: "SimulationEngine", occupied: Set[Position]) -> Action:
        delivery = self._resolve_delivery(engine)
        if delivery is None:
            self.goal_holder.clear()
            self.state = "idle"
            return Action(type="wait", reason="no_available_task")

        pickup_pos = delivery.pickup_position(engine.map)
        dropoff_pos = delivery.dropoff_position(engine.map)

        if self.carrying_box_id == delivery.box_id:
            self.goal_holder.goal_type = "deliver"
            self.goal_holder.target_delivery_id = delivery.delivery_id
            self.state = "moving_to_delivery"
            if self.position in engine.map.adjacent_positions(dropoff_pos):
                self.state = "placing"
                return Action(type="place", target=dropoff_pos)
            targets = engine.map.adjacent_walkable_positions(dropoff_pos, extra_blocked=occupied)
            direction = self.movement_module.next_direction_to_any(
                self.position,
                targets,
                engine.map,
                occupied,
                engine.rng,
            )
            if direction:
                return Action(type="move", direction=direction, target=dropoff_pos)
            self.state = "waiting"
            return Action(type="wait", target=dropoff_pos, reason="no_route_to_delivery")

        self.goal_holder.goal_type = "pickup"
        self.goal_holder.target_delivery_id = delivery.delivery_id
        self.state = "moving_to_pickup"
        if self.position in engine.map.adjacent_positions(pickup_pos):
            self.state = "picking"
            return Action(type="pick", target=pickup_pos)

        targets = engine.map.adjacent_walkable_positions(pickup_pos, extra_blocked=occupied)
        direction = self.movement_module.next_direction_to_any(
            self.position,
            targets,
            engine.map,
            occupied,
            engine.rng,
        )
        if direction:
            return Action(type="move", direction=direction, target=pickup_pos)
        self.state = "waiting"
        return Action(type="wait", target=pickup_pos, reason="no_route_to_pickup")

    def _resolve_delivery(self, engine: "SimulationEngine"):
        if self.goal_holder.target_delivery_id:
            for delivery in engine.deliveries:
                if (
                    delivery.delivery_id == self.goal_holder.target_delivery_id
                    and delivery.status != "delivered"
                ):
                    return delivery

        assigned = engine.assign_task_to_agent(self)
        if assigned:
            self.goal_holder.target_delivery_id = assigned.delivery_id
        return assigned

    @staticmethod
    def _distance(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def serialize(self, include_memory: bool = False) -> Dict[str, object]:
        data = {
            "agent_id": self.agent_id,
            "position": self.position,
            "state": self.state,
            "goal_type": self.goal_holder.goal_type,
            "goal_delivery_id": self.goal_holder.target_delivery_id,
            "goal_task_id": self.goal_holder.target_delivery_id,
            "carrying_box_id": self.carrying_box_id,
            "carrying_item_id": self.carrying_box_id,
            "perception_radius": self.perception_module.radius,
            "memory": self.memory_module.serialize_summary(),
            "communication": self.communication_module.serialize(),
            "movement": self.movement_module.serialize(),
            "metrics": self.metrics.serialize(),
        }
        if include_memory:
            data["memory_detail"] = self.memory_module.serialize_detail()
        return data
