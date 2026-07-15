from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from strategy_config import effective_strategy_config

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
class ItemStart:
    item_id: str
    task_id: str
    pickup_id: str
    dropoff_id: str


@dataclass(frozen=True)
class TaskStart:
    task_id: str
    pickup_id: str
    dropoff_id: str
    item_id: str


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
    tasks: List[TaskStart]
    items: List[ItemStart]
    default_seed: int = 1
    perception_radius: int = 3
    allocation_strategy: str = "nearest_available"
    routing_strategy: str = "local_memory_astar"
    path_weights: Dict[str, float] = field(default_factory=dict)
    congestion: Dict[str, float] = field(default_factory=dict)
    dynamic_changes: List[Dict[str, object]] = field(default_factory=list)

    @property
    def deliveries(self) -> List[DeliveryStart]:
        return [
            DeliveryStart(
                delivery_id=task.task_id,
                pickup_id=task.pickup_id,
                dropoff_id=task.dropoff_id,
                box_id=task.item_id,
            )
            for task in self.tasks
        ]

    def serialize_summary(self) -> Dict[str, object]:
        config = effective_strategy_config(
            perception_radius=self.perception_radius,
            allocation_strategy=self.allocation_strategy,
            routing_strategy=self.routing_strategy,
            path_weights=self.path_weights,
            congestion=self.congestion,
        )
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "agent_count": len(self.agents),
            "delivery_count": len(self.tasks),
            "task_count": len(self.tasks),
            "default_seed": self.default_seed,
            "perception_radius": self.perception_radius,
            "allocation_strategy": self.allocation_strategy,
            "routing_strategy": self.routing_strategy,
            "path_weights": config["path_weights"],
            "congestion": config["congestion"],
            "config": config,
        }


def position(value: List[int] | Tuple[int, int]) -> Position:
    return (int(value[0]), int(value[1]))


def parse_scenario(data: Dict[str, object]) -> ScenarioConfig:
    grid = data["grid"]
    pickups = {
        str(key): position(value)
        for key, value in data.get("pickups", {}).items()
    }
    dropoff_source = data.get("dropoffs", data.get("delivery_locations", {}))
    if not isinstance(dropoff_source, dict):
        dropoff_source = {}
    dropoffs = {
        str(key): position(value)
        for key, value in dropoff_source.items()
    }
    tasks = [
        TaskStart(
            task_id=str(raw.get("task_id", raw.get("delivery_id"))),
            pickup_id=str(raw["pickup_id"]),
            dropoff_id=str(raw.get("dropoff_id", raw.get("delivery_id", ""))),
            item_id=str(raw.get("item_id", raw.get("box_id"))),
        )
        for raw in data.get("tasks", data.get("deliveries_tasks", []))
    ]
    if not tasks:
        tasks = [
            TaskStart(
                task_id=str(raw.get("delivery_id", raw.get("task_id"))),
                pickup_id=str(raw["pickup_id"]),
                dropoff_id=str(raw["dropoff_id"]),
                item_id=str(raw.get("box_id", raw.get("item_id"))),
            )
            for raw in data.get("deliveries", [])
            if isinstance(raw, dict)
        ]

    item_lookup = {
        str(raw["item_id"]): ItemStart(
            item_id=str(raw["item_id"]),
            task_id=str(raw.get("task_id", "")),
            pickup_id=str(raw.get("pickup_id", "")),
            dropoff_id=str(raw.get("dropoff_id", "")),
        )
        for raw in data.get("items", [])
    }
    items = [
        item_lookup.get(task.item_id)
        or ItemStart(
            item_id=task.item_id,
            task_id=task.task_id,
            pickup_id=task.pickup_id,
            dropoff_id=task.dropoff_id,
        )
        for task in tasks
    ]

    return ScenarioConfig(
        scenario_id=str(data["scenario_id"]),
        name=str(data["name"]),
        description=str(data.get("description", "")),
        width=int(grid["width"]),
        height=int(grid["height"]),
        blocked={position(raw) for raw in grid.get("blocked", [])},
        pickups=pickups,
        dropoffs=dropoffs,
        agents=[
            AgentStart(agent_id=str(raw["agent_id"]), position=position(raw["position"]))
            for raw in data.get("agents", [])
        ],
        tasks=tasks,
        items=[item for item in items if item is not None],
        default_seed=int(data.get("default_seed", 1)),
        perception_radius=int(data.get("perception_radius", data.get("config", {}).get("perception_radius", 3))),
        allocation_strategy=str(data.get("allocation_strategy", data.get("config", {}).get("allocation_strategy", "nearest_available"))),
        routing_strategy=str(data.get("routing_strategy", data.get("config", {}).get("routing_strategy", "local_memory_astar"))),
        path_weights=dict(data.get("path_weights", data.get("config", {}).get("path_weights", {}))),
        congestion=dict(data.get("congestion", data.get("config", {}).get("congestion", {}))),
        dynamic_changes=list(data.get("dynamic_changes", [])),
    )
