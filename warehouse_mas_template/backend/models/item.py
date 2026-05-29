from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class Item:
    item_id: str
    task_id: str
    pickup_id: str
    dropoff_id: str
    state: str = "waiting"  # waiting | carried | delivered
    carried_by: Optional[str] = None

    def position(self, warehouse_map, carrier_position: Optional[Position] = None) -> Optional[Position]:
        if self.state == "waiting":
            return warehouse_map.pickups[self.pickup_id]
        if self.state == "carried":
            return carrier_position
        if self.state == "delivered":
            return warehouse_map.dropoffs[self.dropoff_id]
        return None

    def serialize(
        self,
        warehouse_map=None,
        carrier_position: Optional[Position] = None,
    ) -> Dict[str, object]:
        data: Dict[str, object] = {
            "item_id": self.item_id,
            "box_id": self.item_id,
            "task_id": self.task_id,
            "delivery_id": self.task_id,
            "pickup_id": self.pickup_id,
            "dropoff_id": self.dropoff_id,
            "state": self.state,
            "carried_by": self.carried_by,
        }
        if warehouse_map is not None:
            data["position"] = self.position(warehouse_map, carrier_position)
        return data
