from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Tuple

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
class CellHistory:
    waiting_events: int = 0
    failed_move_attempts: int = 0
    blocked_path_events: int = 0
    last_updated_tick: int = 0

    def serialize(self) -> Dict[str, int]:
        return {
            "waiting_events": self.waiting_events,
            "failed_move_attempts": self.failed_move_attempts,
            "blocked_path_events": self.blocked_path_events,
            "last_updated_tick": self.last_updated_tick,
        }


@dataclass
class MemoryModule:
    map_size: Tuple[int, int] = (0, 0)
    known_cells: Dict[Position, KnowledgeEntry] = field(default_factory=dict)
    known_pickups: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_deliveries: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_agents: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_items: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    known_tasks: Dict[str, KnowledgeEntry] = field(default_factory=dict)
    congestion: Dict[Position, KnowledgeEntry] = field(default_factory=dict)
    cell_history: Dict[Position, CellHistory] = field(default_factory=dict)
    last_perception: Dict[str, object] = field(default_factory=dict)
    history: Deque[Dict[str, object]] = field(default_factory=lambda: deque(maxlen=50))

    def initialize_map(self, width: int, height: int) -> None:
        self.map_size = (int(width), int(height))

    def remember(self, perception: Dict[str, object]) -> None:
        tick = int(perception["tick"])
        self.initialize_map(int(perception["map_width"]), int(perception["map_height"]))
        self.last_perception = perception
        self.history.append(perception)

        for cell in perception.get("visible_cells", []):
            self._set_newer(self.known_cells, tuple(cell["position"]), cell, tick)
        for pickup in perception.get("visible_pickups", []):
            self._set_newer(self.known_pickups, pickup["pickup_id"], pickup, tick)
        for delivery in perception.get("visible_deliveries", []):
            self._set_newer(self.known_deliveries, delivery["dropoff_id"], delivery, tick)
        for agent in perception.get("visible_agents", []):
            self._set_newer(self.known_agents, agent["agent_id"], agent, tick)
        for item in perception.get("visible_items", []):
            self._set_newer(self.known_items, item["item_id"], item, tick)
        for task in perception.get("visible_tasks", []):
            self._set_newer(self.known_tasks, task["task_id"], task, tick)

    def remember_task(self, task: Dict[str, object], tick: int) -> None:
        self._set_newer(self.known_tasks, str(task["task_id"]), task, tick)
        pickup = task.get("pickup_position")
        dropoff = task.get("dropoff_position")
        if pickup is not None:
            self._set_newer(
                self.known_pickups,
                str(task.get("pickup_id", "")),
                {"pickup_id": task.get("pickup_id"), "position": tuple(pickup)},
                tick,
            )
        if dropoff is not None:
            self._set_newer(
                self.known_deliveries,
                str(task.get("dropoff_id", "")),
                {"dropoff_id": task.get("dropoff_id"), "position": tuple(dropoff)},
                tick,
            )

    def remember_item(self, item: Dict[str, object], tick: int) -> None:
        self._set_newer(self.known_items, str(item["item_id"]), item, tick)

    def merge_from(self, other: "MemoryModule") -> int:
        updates = 0
        updates += self._merge_dict(self.known_cells, other.known_cells)
        updates += self._merge_dict(self.known_pickups, other.known_pickups)
        updates += self._merge_dict(self.known_deliveries, other.known_deliveries)
        updates += self._merge_dict(self.known_agents, other.known_agents)
        updates += self._merge_dict(self.known_items, other.known_items)
        updates += self._merge_dict(self.known_tasks, other.known_tasks)
        updates += self._merge_dict(self.congestion, other.congestion)
        for position, incoming in other.cell_history.items():
            current = self.cell_history.get(position)
            if current is None or incoming.last_updated_tick > current.last_updated_tick:
                self.cell_history[position] = CellHistory(
                    waiting_events=incoming.waiting_events,
                    failed_move_attempts=incoming.failed_move_attempts,
                    blocked_path_events=incoming.blocked_path_events,
                    last_updated_tick=incoming.last_updated_tick,
                )
                updates += 1
        return updates

    def export_for_communication(self) -> Dict[str, object]:
        return {
            "map_size": self.map_size,
            "known_cells": self._export_entries(self.known_cells),
            "known_pickups": self._export_entries(self.known_pickups),
            "known_deliveries": self._export_entries(self.known_deliveries),
            "known_agents": self._export_entries(self.known_agents),
            "known_items": self._export_entries(self.known_items),
            "known_tasks": self._export_entries(self.known_tasks),
            "congestion": self._export_entries(self.congestion),
            "cell_history": [
                {"position": position, **history.serialize()}
                for position, history in self.cell_history.items()
            ],
        }

    def merge_snapshot(self, snapshot: Dict[str, object]) -> Dict[str, int]:
        if "map_size" in snapshot:
            width, height = snapshot["map_size"]
            if width and height:
                self.initialize_map(int(width), int(height))

        counts = {
            "cells": self._merge_snapshot_entries(self.known_cells, snapshot.get("known_cells", []), tuple_keys=True),
            "pickups": self._merge_snapshot_entries(self.known_pickups, snapshot.get("known_pickups", [])),
            "deliveries": self._merge_snapshot_entries(self.known_deliveries, snapshot.get("known_deliveries", [])),
            "agents": self._merge_snapshot_entries(self.known_agents, snapshot.get("known_agents", [])),
            "items": self._merge_snapshot_entries(self.known_items, snapshot.get("known_items", [])),
            "tasks": self._merge_snapshot_entries(self.known_tasks, snapshot.get("known_tasks", [])),
            "congestion": self._merge_snapshot_entries(self.congestion, snapshot.get("congestion", []), tuple_keys=True),
            "history": 0,
        }

        for incoming in snapshot.get("cell_history", []):
            position = tuple(incoming["position"])
            current = self.cell_history.get(position)
            incoming_tick = int(incoming.get("last_updated_tick", 0))
            if current is None or incoming_tick > current.last_updated_tick:
                self.cell_history[position] = CellHistory(
                    waiting_events=int(incoming.get("waiting_events", 0)),
                    failed_move_attempts=int(incoming.get("failed_move_attempts", 0)),
                    blocked_path_events=int(incoming.get("blocked_path_events", 0)),
                    last_updated_tick=incoming_tick,
                )
                counts["history"] += 1
        return counts

    def record_wait(self, position: Position, tick: int) -> None:
        history = self.cell_history.setdefault(position, CellHistory())
        history.waiting_events += 1
        history.last_updated_tick = tick

    def record_failed_move(self, position: Position, tick: int) -> None:
        history = self.cell_history.setdefault(position, CellHistory())
        history.failed_move_attempts += 1
        history.last_updated_tick = tick

    def record_blocked_path(self, position: Position, tick: int) -> None:
        history = self.cell_history.setdefault(position, CellHistory())
        history.blocked_path_events += 1
        history.last_updated_tick = tick

    def set_congestion(self, position: Position, score: float, tick: int) -> None:
        self._set_newer(self.congestion, position, round(float(score), 4), tick)

    def congestion_score(self, position: Position) -> float:
        entry = self.congestion.get(position)
        return float(entry.value) if entry else 0.0

    def cell_history_for(self, position: Position) -> CellHistory:
        return self.cell_history.get(position, CellHistory())

    def in_bounds(self, position: Position) -> bool:
        width, height = self.map_size
        return 0 <= position[0] < width and 0 <= position[1] < height

    def known_cell_type(self, position: Position) -> Optional[str]:
        entry = self.known_cells.get(position)
        if entry is None:
            return None
        return str(entry.value.get("cell_type"))

    def is_known_blocked(self, position: Position) -> bool:
        return self.known_cell_type(position) == "blocked"

    def is_known_service_cell(self, position: Position) -> bool:
        if self.known_cell_type(position) in {"pickup", "dropoff"}:
            return True
        return any(tuple(entry.value["position"]) == position for entry in self.known_pickups.values()) or any(
            tuple(entry.value["position"]) == position for entry in self.known_deliveries.values()
        )

    def is_known_walkable(self, position: Position) -> Optional[bool]:
        entry = self.known_cells.get(position)
        if entry is None:
            return None
        return bool(entry.value.get("walkable"))

    def recently_occupied_cells(self, current_tick: int, max_age: int = 2) -> Dict[Position, str]:
        occupied: Dict[Position, str] = {}
        for agent_id, entry in self.known_agents.items():
            if current_tick - entry.last_seen_tick <= max_age:
                value = entry.value
                occupied[tuple(value["position"])] = str(agent_id)
        return occupied

    def adjacent_candidate_cells(self, target: Position) -> List[Position]:
        x, y = target
        candidates = [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]
        return [
            candidate
            for candidate in candidates
            if self.in_bounds(candidate)
            and not self.is_known_blocked(candidate)
            and not self.is_known_service_cell(candidate)
        ]

    def serialize_summary(self) -> Dict[str, object]:
        known_blocked = sum(
            1 for entry in self.known_cells.values()
            if entry.value.get("cell_type") == "blocked"
        )
        known_free = sum(
            1 for entry in self.known_cells.values()
            if entry.value.get("walkable")
        )
        return {
            "map_size": self.map_size,
            "explored_cell_count": len(self.known_cells),
            "known_cell_count": len(self.known_cells),
            "known_free_cell_count": known_free,
            "known_blocked_cell_count": known_blocked,
            "known_pickup_count": len(self.known_pickups),
            "known_delivery_count": len(self.known_deliveries),
            "known_agent_count": len(self.known_agents),
            "known_item_count": len(self.known_items),
            "known_task_count": len(self.known_tasks),
            "congestion_cell_count": len(self.congestion),
            "history_cell_count": len(self.cell_history),
            "last_perception_tick": self.last_perception.get("tick"),
        }

    def serialize_detail(self) -> Dict[str, object]:
        return {
            "summary": self.serialize_summary(),
            "known_cells": [
                {"position": position, **entry.serialize()}
                for position, entry in sorted(self.known_cells.items())
            ],
            "known_pickups": {
                pickup_id: entry.serialize()
                for pickup_id, entry in sorted(self.known_pickups.items())
            },
            "known_deliveries": {
                delivery_id: entry.serialize()
                for delivery_id, entry in sorted(self.known_deliveries.items())
            },
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
            "congestion": [
                {"position": position, **entry.serialize()}
                for position, entry in sorted(self.congestion.items())
            ],
            "cell_history": [
                {"position": position, **history.serialize()}
                for position, history in sorted(self.cell_history.items())
            ],
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

    @staticmethod
    def _export_entries(source: Dict[object, KnowledgeEntry]) -> List[Dict[str, object]]:
        exported = []
        for key, entry in source.items():
            exported.append({
                "key": key,
                "value": entry.value,
                "last_seen_tick": entry.last_seen_tick,
            })
        return exported

    @staticmethod
    def _merge_snapshot_entries(
        target: Dict[object, KnowledgeEntry],
        entries: Iterable[Dict[str, object]],
        tuple_keys: bool = False,
    ) -> int:
        updates = 0
        for incoming in entries:
            key = incoming["key"]
            if tuple_keys:
                key = tuple(key)
            value = incoming["value"]
            last_seen_tick = int(incoming["last_seen_tick"])
            current = target.get(key)
            if current is None or last_seen_tick > current.last_seen_tick:
                target[key] = KnowledgeEntry(value=value, last_seen_tick=last_seen_tick)
                updates += 1
        return updates
