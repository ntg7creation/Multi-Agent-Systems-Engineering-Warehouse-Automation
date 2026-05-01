from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class Action:
    type: str
    direction: Optional[str] = None
    target: Optional[Position] = None
    reason: str = ""
    data: Dict[str, object] = field(default_factory=dict)

    def serialize(self) -> Dict[str, object]:
        return {
            "type": self.type,
            "direction": self.direction,
            "target": self.target,
            "reason": self.reason,
            "data": self.data,
        }
