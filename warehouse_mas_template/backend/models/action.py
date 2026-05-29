from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

Position = Tuple[int, int]

MOVE = "move"
PICKUP = "pickup"
PLACE = "place"
WAIT = "wait"
REPLAN = "replan"


@dataclass
class Action:
    type: str
    agent_id: Optional[str] = None
    direction: Optional[str] = None
    target: Optional[Position] = None
    source: Optional[Position] = None
    task_id: Optional[str] = None
    item_id: Optional[str] = None
    reason: str = ""
    data: Dict[str, object] = field(default_factory=dict)

    def serialize(self) -> Dict[str, object]:
        return {
            "type": self.type,
            "agent_id": self.agent_id,
            "direction": self.direction,
            "target": self.target,
            "source": self.source,
            "task_id": self.task_id,
            "item_id": self.item_id,
            "reason": self.reason,
            "data": self.data,
        }


@dataclass
class ActionResult:
    agent_id: str
    action: Action
    success: bool
    useful: bool = False
    failure_reason: str = ""
    source_position: Optional[Position] = None
    target_position: Optional[Position] = None
    task_id: Optional[str] = None
    item_id: Optional[str] = None
    data: Dict[str, object] = field(default_factory=dict)

    def serialize(self) -> Dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "action": self.action.serialize(),
            "success": self.success,
            "useful": self.useful,
            "failure_reason": self.failure_reason,
            "source_position": self.source_position,
            "target_position": self.target_position,
            "task_id": self.task_id,
            "item_id": self.item_id,
            "data": self.data,
        }
