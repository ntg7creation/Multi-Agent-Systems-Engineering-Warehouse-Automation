from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

Position = Tuple[int, int]


@dataclass(frozen=True)
class AgentStart:
    agent_id: str
    position: Position


@dataclass(frozen=True)
class DeliveryStart:
    delivery_id: str
    pickup_id: str
    dropoff_id: str
    box_id: str


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    name: str
    description: str
    width: int
    height: int
    blocked: Set[Position]
    pickups: Dict[str, Position]
    dropoffs: Dict[str, Position]
    agents: List[AgentStart]
    deliveries: List[DeliveryStart]
    default_seed: int = 1
    perception_radius: int = 3
    allocation_strategy: str = "nearest_available"
    routing_strategy: str = "seeded_bfs"
    dynamic_changes: List[Dict[str, object]] = field(default_factory=list)

    def serialize_summary(self) -> Dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "agent_count": len(self.agents),
            "delivery_count": len(self.deliveries),
            "default_seed": self.default_seed,
            "perception_radius": self.perception_radius,
            "allocation_strategy": self.allocation_strategy,
            "routing_strategy": self.routing_strategy,
        }
