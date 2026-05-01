from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class GoalHolder:
    goal_type: Optional[str] = None
    target_delivery_id: Optional[str] = None

    def clear(self) -> None:
        self.goal_type = None
        self.target_delivery_id = None

    def serialize(self) -> Dict[str, object]:
        return {
            "goal_type": self.goal_type,
            "target_delivery_id": self.target_delivery_id,
        }
