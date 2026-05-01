from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

Position = Tuple[int, int]


@dataclass
class WarehouseMap:
    width: int
    height: int
    blocked: Set[Position] = field(default_factory=set)
    pickups: Dict[str, Position] = field(default_factory=dict)
    dropoffs: Dict[str, Position] = field(default_factory=dict)

    def in_bounds(self, pos: Position) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def cell_type(self, pos: Position) -> str:
        if not self.in_bounds(pos):
            return "out_of_bounds"
        if pos in self.blocked:
            return "blocked"
        if pos in self.pickups.values():
            return "pickup"
        if pos in self.dropoffs.values():
            return "dropoff"
        return "road"

    def is_blocked(self, pos: Position) -> bool:
        return pos in self.blocked

    def is_service_cell(self, pos: Position) -> bool:
        return pos in set(self.pickups.values()) | set(self.dropoffs.values())

    def is_walkable(self, pos: Position, extra_blocked: Optional[Iterable[Position]] = None) -> bool:
        if not self.in_bounds(pos) or self.is_blocked(pos) or self.is_service_cell(pos):
            return False
        extra = set(extra_blocked or [])
        return pos not in extra

    def neighbors(self, pos: Position, extra_blocked: Optional[Iterable[Position]] = None) -> List[Position]:
        x, y = pos
        candidates = [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]
        return [candidate for candidate in candidates if self.is_walkable(candidate, extra_blocked)]

    def adjacent_positions(self, pos: Position) -> List[Position]:
        x, y = pos
        candidates = [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]
        return [candidate for candidate in candidates if self.in_bounds(candidate)]

    def adjacent_walkable_positions(
        self,
        pos: Position,
        extra_blocked: Optional[Iterable[Position]] = None,
    ) -> List[Position]:
        return [
            candidate
            for candidate in self.adjacent_positions(pos)
            if self.is_walkable(candidate, extra_blocked)
        ]

    @staticmethod
    def manhattan(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def as_grid(self) -> List[List[str]]:
        grid = [["road" for _ in range(self.width)] for _ in range(self.height)]
        for x, y in self.blocked:
            grid[y][x] = "blocked"
        for _, (x, y) in self.pickups.items():
            grid[y][x] = "pickup"
        for _, (x, y) in self.dropoffs.items():
            grid[y][x] = "dropoff"
        return grid

    def serialize(self) -> Dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "cells": self.as_grid(),
            "blocked": sorted(self.blocked),
            "pickups": self.pickups,
            "dropoffs": self.dropoffs,
        }
