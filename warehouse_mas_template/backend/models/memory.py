from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple

Position = Tuple[int, int]


@dataclass
class KnowledgeEntry:
    value: object
    last_seen_tick: int

    def serialize(self) -> Dict[str, object]:
        return {
            "value": self.value,
            "last_seen_tick": self.last_seen_tick,
        }


@dataclass
class MemoryModule:
    known_cells: Dict[Position, KnowledgeEntry] = field(default_factory=dict)
    known_agents: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_items: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_tasks: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    last_perception: Dict[str, object] = field(default_factory=dict)
    history: Deque[Dict[str, object]] = field(default_factory=lambda: deque(maxlen=50))

    def remember(self, perception: Dict[str, object]) -> None:
        tick = int(perception["tick"])
        self.last_perception = perception
        self.history.append(perception)

        for cell in perception.get("visible_cells", []):
            self._set_newer(self.known_cells, tuple(cell["position"]), cell, tick)
        for agent in perception.get("visible_agents", []):
            self._set_newer(self.known_agents, agent["agent_id"], agent, tick)
        for item in perception.get("visible_items", []):
            self._set_newer(self.known_items, item["item_id"], item, tick)
        for task in perception.get("visible_tasks", []):
            self._set_newer(self.known_tasks, task["task_id"], task, tick)

    def merge_from(self, other: "MemoryModule") -> int:
        updates = 0
        updates += self._merge_dict(self.known_cells, other.known_cells)
        updates += self._merge_dict(self.known_agents, other.known_agents)
        updates += self._merge_dict(self.known_items, other.known_items)
        updates += self._merge_dict(self.known_tasks, other.known_tasks)
        return updates

    def serialize_summary(self) -> Dict[str, object]:
        return {
            "known_cell_count": len(self.known_cells),
            "known_agent_count": len(self.known_agents),
            "known_item_count": len(self.known_items),
            "known_task_count": len(self.known_tasks),
            "last_perception_tick": self.last_perception.get("tick"),
        }

    def serialize_detail(self) -> Dict[str, object]:
        return {
            "summary": self.serialize_summary(),
            "known_cells": [
                {"position": position, **entry.serialize()}
                for position, entry in sorted(self.known_cells.items())
            ],
            "known_agents": {
                agent_id: entry.serialize()
                for agent_id, entry in sorted(self.known_agents.items())
            },
            "known_items": {
                item_id: entry.serialize()
                for item_id, entry in sorted(self.known_items.items())
            },
            "known_tasks": {
                task_id: entry.serialize()
                for task_id, entry in sorted(self.known_tasks.items())
            },
        }

    @staticmethod
    def _set_newer(
        target: Dict[object, KnowledgeEntry],
        key: object,
        value: object,
        tick: int,
    ) -> None:
        current = target.get(key)
        if current is None or tick >= current.last_seen_tick:
            target[key] = KnowledgeEntry(value=value, last_seen_tick=tick)

    @staticmethod
    def _merge_dict(
        target: Dict[object, KnowledgeEntry],
        source: Dict[object, KnowledgeEntry],
    ) -> int:
        updates = 0
        for key, incoming in source.items():
            current = target.get(key)
            if current is None or incoming.last_seen_tick > current.last_seen_tick:
                target[key] = KnowledgeEntry(
                    value=incoming.value,
                    last_seen_tick=incoming.last_seen_tick,
                )
                updates += 1
        return updates
