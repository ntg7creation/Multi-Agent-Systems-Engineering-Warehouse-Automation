from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Set, Tuple

Position = Tuple[int, int]


@dataclass(frozen=True)
class CongestionConfig:
    decay: float = 0.85
    nearby_agent_weight: float = 1.2
    waiting_weight: float = 0.7
    failed_move_weight: float = 1.0
    blocked_path_weight: float = 0.9
    communicated_weight: float = 0.5
    path_padding: int = 1


@dataclass
class CongestionEstimationModule:
    config: CongestionConfig = field(default_factory=CongestionConfig)

    def update(self, agent: "Agent", tick: int) -> Dict[str, object]:
        memory = agent.memory_module
        observed_agent_cells = {
            tuple(entry.value["position"])
            for entry in memory.known_agents.values()
            if tick - entry.last_seen_tick <= 1
        }
        candidate_cells: Set[Position] = set(memory.known_cells)
        candidate_cells.update(memory.cell_history)
        candidate_cells.update(observed_agent_cells)
        candidate_cells.update(memory.congestion)

        changed = 0
        for cell in candidate_cells:
            previous = memory.congestion_score(cell)
            history = memory.cell_history_for(cell)
            nearby_agents = self._nearby_count(cell, observed_agent_cells)
            communicated = previous
            score = (
                self.config.decay * previous
                + self.config.nearby_agent_weight * nearby_agents
                + self.config.waiting_weight * history.waiting_events
                + self.config.failed_move_weight * history.failed_move_attempts
                + self.config.blocked_path_weight * history.blocked_path_events
                + self.config.communicated_weight * communicated
            )
            if score > 0.001:
                memory.set_congestion(cell, score, tick)
                changed += 1

        return {
            "updated_cells": changed,
            "observed_agent_cells": sorted(observed_agent_cells),
        }

    def score_path_region(self, memory, path: Iterable[Position]) -> float:
        region = self.path_region(path, self.config.path_padding)
        if not region:
            return 0.0
        return sum(memory.congestion_score(cell) for cell in region) / len(region)

    @staticmethod
    def path_region(path: Iterable[Position], padding: int = 1) -> Set[Position]:
        region: Set[Position] = set()
        for x, y in path:
            for dx in range(-padding, padding + 1):
                for dy in range(-padding, padding + 1):
                    if abs(dx) + abs(dy) <= padding:
                        region.add((x + dx, y + dy))
        return region

    @staticmethod
    def _nearby_count(cell: Position, agent_cells: Iterable[Position]) -> int:
        cx, cy = cell
        return sum(abs(cx - ax) + abs(cy - ay) <= 1 for ax, ay in agent_cells)
