from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class EventLogger:
    run_id: str
    events: List[Dict[str, object]] = field(default_factory=list)

    def log(
        self,
        tick: int,
        event_type: str,
        message: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        item_id: Optional[str] = None,
        source: Optional[Position] = None,
        target: Optional[Position] = None,
        result: Optional[str] = None,
        rejection_reason: str = "",
        data: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        entry = {
            "event_id": len(self.events) + 1,
            "run_id": self.run_id,
            "tick": tick,
            "type": event_type,
            "agent_id": agent_id,
            "task_id": task_id,
            "item_id": item_id,
            "position": source,
            "source": source,
            "target": target,
            "result": result,
            "rejection_reason": rejection_reason,
            "message": message,
            "data": data or {},
        }
        self.events.append(entry)
        return entry

    def serialize(self, limit: Optional[int] = None) -> List[Dict[str, object]]:
        if limit is None or limit <= 0:
            return list(self.events)
        return self.events[-limit:]


@dataclass
class ReplayLog:
    frames: List[Dict[str, object]] = field(default_factory=list)

    def record(self, frame: Dict[str, object]) -> None:
        self.frames.append(frame)

    def serialize(self, limit: Optional[int] = None) -> List[Dict[str, object]]:
        if limit is None or limit <= 0:
            return list(self.frames)
        return self.frames[-limit:]
