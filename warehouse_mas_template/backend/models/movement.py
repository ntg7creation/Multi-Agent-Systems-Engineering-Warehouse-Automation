from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from random import Random
from typing import Deque, Dict, Iterable, List, Optional, Tuple

Position = Tuple[int, int]

DIRECTION_VECTORS: Dict[str, Tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass
class MovementModule:
    last_route: List[Position] = None
    failed_routes: int = 0

    def next_direction_to_any(
        self,
        start: Position,
        goals: Iterable[Position],
        warehouse_map,
        occupied: Iterable[Position],
        rng: Optional[Random] = None,
    ) -> Optional[str]:
        route = self.shortest_route_to_any(start, goals, warehouse_map, occupied, rng)
        self.last_route = route or []
        if not route or len(route) < 2:
            self.failed_routes += 1
            return None

        sx, sy = route[0]
        nx, ny = route[1]
        dx, dy = nx - sx, ny - sy
        for direction, vector in DIRECTION_VECTORS.items():
            if vector == (dx, dy):
                return direction
        self.failed_routes += 1
        return None

    def shortest_route_to_any(
        self,
        start: Position,
        goals: Iterable[Position],
        warehouse_map,
        occupied: Iterable[Position],
        rng: Optional[Random] = None,
    ) -> List[Position]:
        goal_set = set(goals)
        if not goal_set:
            return []
        if start in goal_set:
            return [start]

        blocked = set(occupied)
        queue: Deque[Position] = deque([start])
        parents: Dict[Position, Optional[Position]] = {start: None}
        found_goal: Optional[Position] = None

        while queue:
            current = queue.popleft()
            neighbors = warehouse_map.neighbors(current, extra_blocked=blocked)
            if rng is not None:
                rng.shuffle(neighbors)
            for neighbor in neighbors:
                if neighbor in parents:
                    continue
                parents[neighbor] = current
                if neighbor in goal_set:
                    found_goal = neighbor
                    queue.clear()
                    break
                queue.append(neighbor)

        if found_goal is None:
            return []

        route = [found_goal]
        current = found_goal
        while parents[current] is not None:
            current = parents[current]
            route.append(current)
        route.reverse()
        return route

    def serialize(self) -> Dict[str, object]:
        return {
            "last_route": self.last_route or [],
            "failed_routes": self.failed_routes,
        }
