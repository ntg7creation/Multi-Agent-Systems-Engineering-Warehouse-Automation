from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class Delivery:
    delivery_id: str
    pickup_id: str
    dropoff_id: str
    box_id: str
    status: str = "waiting"  # waiting | carrying | delivered
    assigned_agent_id: Optional[str] = None
    carried_by: Optional[str] = None
    created_tick: int = 0
    assigned_tick: Optional[int] = None
    picked_tick: Optional[int] = None
    delivered_tick: Optional[int] = None

    def pickup_position(self, warehouse_map) -> Position:
        return warehouse_map.pickups[self.pickup_id]

    def dropoff_position(self, warehouse_map) -> Position:
        return warehouse_map.dropoffs[self.dropoff_id]

    @property
    def task_id(self) -> str:
        return self.delivery_id

    def serialize(self, warehouse_map=None) -> Dict[str, object]:
        data = {
            "delivery_id": self.delivery_id,
            "task_id": self.delivery_id,
            "pickup_id": self.pickup_id,
            "dropoff_id": self.dropoff_id,
            "box_id": self.box_id,
            "item_id": self.box_id,
            "status": self.status,
            "assigned_agent_id": self.assigned_agent_id,
            "carried_by": self.carried_by,
            "created_tick": self.created_tick,
            "assigned_tick": self.assigned_tick,
            "picked_tick": self.picked_tick,
            "delivered_tick": self.delivered_tick,
        }
        if warehouse_map is not None:
            data["pickup_position"] = self.pickup_position(warehouse_map)
            data["dropoff_position"] = self.dropoff_position(warehouse_map)
        return data
