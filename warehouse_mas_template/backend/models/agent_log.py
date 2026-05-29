from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional


@dataclass
class AgentLogModule:
    entries: Deque[Dict[str, object]] = field(default_factory=lambda: deque(maxlen=200))

    def record(
        self,
        tick: int,
        event_type: str,
        message: str,
        data: Optional[Dict[str, object]] = None,
    ) -> None:
        self.entries.append({
            "tick": tick,
            "type": event_type,
            "message": message,
            "data": data or {},
        })

    def record_decision(self, agent: "Agent", tick: int, action) -> None:
        self.record(
            tick=tick,
            event_type="ACTION_SELECTED",
            message=f"{agent.agent_id} selected {action.type}.",
            data={
                "mode": agent.mode,
                "task_id": agent.current_task_id,
                "target": agent.current_target,
                "planned_path": agent.planned_path,
                "action": action.serialize(),
                "previous_action_result": agent.previous_action_result.serialize()
                if agent.previous_action_result
                else None,
            },
        )

    def serialize(self, limit: int = 25) -> Dict[str, object]:
        entries = list(self.entries)
        return {
            "entries": entries[-limit:],
            "count": len(entries),
        }
