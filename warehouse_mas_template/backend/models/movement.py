from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from random import Random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Position = Tuple[int, int]

DIRECTION_VECTORS: Dict[str, Tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class PathPlanningConfig:
    distance_weight: float = 1.0
    congestion_weight: float = 0.0
    failed_route_weight: float = 0.0
    uncertainty_weight: float = 0.0
    occupied_penalty: float = 0.0
    max_candidates: int = 1
    near_optimal_margin: float = 0.0
    max_expansion_multiplier: int = 10


@dataclass
class PathPlan:
    path: List[Position]
    cost: float
    candidates_considered: int
    selected_index: int = 0

    def serialize(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "cost": round(self.cost, 4),
            "candidates_considered": self.candidates_considered,
            "selected_index": self.selected_index,
        }


@dataclass
class PathPlanningModule:
    config: PathPlanningConfig = field(default_factory=PathPlanningConfig)
    last_route: List[Position] = field(default_factory=list)
    last_plan_cost: float = 0.0
    last_candidates: List[Dict[str, object]] = field(default_factory=list)
    failed_routes: int = 0

    def plan_route_to_any(
        self,
        start: Position,
        goals: Iterable[Position],
        memory,
        current_tick: int,
        rng: Optional[Random] = None,
        extra_blocked: Iterable[Position] = (),
    ) -> PathPlan:
        goal_set = {tuple(goal) for goal in goals if memory.in_bounds(tuple(goal))}
        if not goal_set:
            self.failed_routes += 1
            self.last_route = []
            self.last_plan_cost = 0.0
            return PathPlan(path=[], cost=0.0, candidates_considered=0)
        if start in goal_set:
            plan = PathPlan(path=[start], cost=0.0, candidates_considered=1)
            self._store_plan(plan, [plan])
            return plan

        candidates = self._candidate_paths(
            start=start,
            goals=goal_set,
            memory=memory,
            current_tick=current_tick,
            extra_blocked=set(extra_blocked),
        )
        if not candidates:
            self.failed_routes += 1
            self.last_route = []
            self.last_plan_cost = 0.0
            return PathPlan(path=[], cost=0.0, candidates_considered=0)

        best_cost = min(candidate.cost for candidate in candidates)
        near_optimal = [
            candidate
            for candidate in candidates
            if candidate.cost <= best_cost * (1 + self.config.near_optimal_margin) + 0.001
        ]
        selected = self._weighted_choice(near_optimal, rng)
        selected.selected_index = candidates.index(selected)
        self._store_plan(selected, candidates)
        return selected

    def next_direction(self, route: Sequence[Position]) -> Optional[str]:
        if len(route) < 2:
            return None
        sx, sy = route[0]
        nx, ny = route[1]
        vector = (nx - sx, ny - sy)
        for direction, vector in DIRECTION_VECTORS.items():
            if vector == (nx - sx, ny - sy):
                return direction
        return None

    def estimate_cost_to_any(
        self,
        start: Position,
        goals: Iterable[Position],
        memory,
        current_tick: int,
    ) -> float:
        plan = self.plan_route_to_any(start, goals, memory, current_tick)
        return plan.cost if plan.path else 999999.0

    def path_cost(self, path: Sequence[Position], memory, current_tick: int) -> float:
        if not path:
            return 999999.0
        distance = max(0, len(path) - 1)
        congestion = self._region_congestion(path, memory)
        failed = sum(
            memory.cell_history_for(cell).failed_move_attempts
            + memory.cell_history_for(cell).blocked_path_events
            for cell in path
        )
        uncertainty = sum(1 for cell in path if memory.is_known_walkable(cell) is None)
        recent_occupied = memory.recently_occupied_cells(current_tick)
        occupied_penalty = sum(1 for cell in path[1:] if cell in recent_occupied)
        return (
            self.config.distance_weight * distance
            + self.config.congestion_weight * congestion
            + self.config.failed_route_weight * failed
            + self.config.uncertainty_weight * uncertainty
            + self.config.occupied_penalty * occupied_penalty
        )

    def serialize(self) -> Dict[str, object]:
        return {
            "last_route": self.last_route or [],
            "last_plan_cost": round(self.last_plan_cost, 4),
            "last_candidates": self.last_candidates,
            "failed_routes": self.failed_routes,
            "weights": {
                "alpha_distance": self.config.distance_weight,
                "beta_congestion": self.config.congestion_weight,
                "gamma_failed_route": self.config.failed_route_weight,
                "delta_uncertainty": self.config.uncertainty_weight,
            },
        }

    def _candidate_paths(
        self,
        start: Position,
        goals: set[Position],
        memory,
        current_tick: int,
        extra_blocked: set[Position],
    ) -> List[PathPlan]:
        width, height = memory.map_size
        max_expansions = max(50, width * height * self.config.max_expansion_multiplier)
        occupied = set(memory.recently_occupied_cells(current_tick)) | extra_blocked
        queue: List[Tuple[float, float, Position, Tuple[Position, ...]]] = []
        heappush(queue, (0.0, 0.0, start, (start,)))
        best_seen: Dict[Position, float] = {start: 0.0}
        candidates: List[PathPlan] = []
        expansions = 0

        while queue and expansions < max_expansions and len(candidates) < self.config.max_candidates:
            _, cost_so_far, current, path = heappop(queue)
            expansions += 1
            if current in goals:
                candidate_path = list(path)
                candidates.append(PathPlan(
                    path=candidate_path,
                    cost=self.path_cost(candidate_path, memory, current_tick),
                    candidates_considered=0,
                ))
                continue

            for neighbor in self._neighbors(current):
                if neighbor in path:
                    continue
                if not self._is_traversable(neighbor, start, goals, memory, occupied):
                    continue
                step_cost = self._step_cost(neighbor, memory, current_tick, occupied)
                new_cost = cost_so_far + step_cost
                if new_cost >= best_seen.get(neighbor, 999999.0):
                    continue
                best_seen[neighbor] = new_cost
                priority = new_cost + self._heuristic(neighbor, goals)
                heappush(queue, (priority, new_cost, neighbor, (*path, neighbor)))

        for candidate in candidates:
            candidate.candidates_considered = len(candidates)
        return sorted(candidates, key=lambda candidate: candidate.cost)

    def _step_cost(
        self,
        position: Position,
        memory,
        current_tick: int,
        occupied: set[Position],
    ) -> float:
        history = memory.cell_history_for(position)
        uncertainty = 1 if memory.is_known_walkable(position) is None else 0
        occupied_penalty = 1 if position in occupied else 0
        return (
            1.0
            + self.config.congestion_weight * memory.congestion_score(position)
            + self.config.failed_route_weight * (
                history.failed_move_attempts + history.blocked_path_events
            )
            + self.config.uncertainty_weight * uncertainty
            + self.config.occupied_penalty * occupied_penalty
        )

    @staticmethod
    def _is_traversable(
        position: Position,
        start: Position,
        goals: set[Position],
        memory,
        occupied: set[Position],
    ) -> bool:
        if not memory.in_bounds(position):
            return False
        if position != start and position in occupied and position not in goals:
            return False
        if memory.is_known_blocked(position):
            return False
        if memory.is_known_service_cell(position):
            return False
        return True

    @staticmethod
    def _neighbors(position: Position) -> List[Position]:
        x, y = position
        return [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]

    @staticmethod
    def _heuristic(position: Position, goals: set[Position]) -> int:
        return min(abs(position[0] - goal[0]) + abs(position[1] - goal[1]) for goal in goals)

    @staticmethod
    def _weighted_choice(candidates: List[PathPlan], rng: Optional[Random]) -> PathPlan:
        if len(candidates) == 1 or rng is None:
            return candidates[0]
        weights = [1 / max(candidate.cost, 0.001) for candidate in candidates]
        total = sum(weights)
        marker = rng.random() * total
        cumulative = 0.0
        for candidate, weight in zip(candidates, weights):
            cumulative += weight
            if marker <= cumulative:
                return candidate
        return candidates[-1]

    @staticmethod
    def _region_congestion(path: Sequence[Position], memory, padding: int = 1) -> float:
        region = set()
        for x, y in path:
            for dx in range(-padding, padding + 1):
                for dy in range(-padding, padding + 1):
                    if abs(dx) + abs(dy) <= padding:
                        region.add((x + dx, y + dy))
        if not region:
            return 0.0
        return sum(memory.congestion_score(cell) for cell in region) / len(region)

    def _store_plan(self, selected: PathPlan, candidates: List[PathPlan]) -> None:
        self.last_route = selected.path
        self.last_plan_cost = selected.cost
        self.last_candidates = [
            {
                "path": candidate.path,
                "cost": round(candidate.cost, 4),
                "selected": candidate is selected,
            }
            for candidate in candidates
        ]


MovementModule = PathPlanningModule
