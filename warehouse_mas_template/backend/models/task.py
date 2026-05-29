from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class Task:
    task_id: str
    pickup_id: str
    dropoff_id: str
    item_id: str
    status: str = "waiting"  # waiting | assigned | carrying | delivered
    assigned_agent_id: Optional[str] = None
    carried_by: Optional[str] = None
    created_tick: int = 0
    assigned_tick: Optional[int] = None
    picked_tick: Optional[int] = None
    delivered_tick: Optional[int] = None
    actual_path_length: int = 0
    shortest_path_length: Optional[int] = None

    @property
    def delivery_id(self) -> str:
        return self.task_id

    @property
    def box_id(self) -> str:
        return self.item_id

    def pickup_position(self, warehouse_map) -> Position:
        return warehouse_map.pickups[self.pickup_id]

    def dropoff_position(self, warehouse_map) -> Position:
        return warehouse_map.dropoffs[self.dropoff_id]

    def serialize(self, warehouse_map=None) -> Dict[str, object]:
        data: Dict[str, object] = {
            "task_id": self.task_id,
            "delivery_id": self.task_id,
            "pickup_id": self.pickup_id,
            "dropoff_id": self.dropoff_id,
            "item_id": self.item_id,
            "box_id": self.item_id,
            "status": self.status,
            "assigned_agent_id": self.assigned_agent_id,
            "carried_by": self.carried_by,
            "created_tick": self.created_tick,
            "assigned_tick": self.assigned_tick,
            "picked_tick": self.picked_tick,
            "delivered_tick": self.delivered_tick,
            "actual_path_length": self.actual_path_length,
            "shortest_path_length": self.shortest_path_length,
            "path_inefficiency": self.path_inefficiency,
        }
        if warehouse_map is not None:
            data["pickup_position"] = self.pickup_position(warehouse_map)
            data["dropoff_position"] = self.dropoff_position(warehouse_map)
        return data

    @property
    def path_inefficiency(self) -> int:
        if self.shortest_path_length is None:
            return 0
        return max(0, self.actual_path_length - self.shortest_path_length)
