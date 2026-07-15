from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

Position = Tuple[int, int]


@dataclass
class PerceptionModule:
    radius: int = 3

    def perceive(self, agent: "Agent", engine: "SimulationEngine") -> Dict[str, object]:
        ax, ay = agent.position

        def visible(pos: Position) -> bool:
            x, y = pos
            return abs(x - ax) + abs(y - ay) <= self.radius

        visible_cells = []
        visible_pickups = []
        visible_deliveries = []
        for y in range(engine.map.height):
            for x in range(engine.map.width):
                pos = (x, y)
                if visible(pos):
                    cell_type = engine.map.cell_type(pos)
                    visible_cells.append({
                        "position": pos,
                        "cell_type": cell_type,
                        "walkable": engine.map.is_walkable(pos),
                    })
                    pickup_id = engine.map.pickup_id_at(pos)
                    if pickup_id:
                        visible_pickups.append({"pickup_id": pickup_id, "position": pos})
                    dropoff_id = engine.map.dropoff_id_at(pos)
                    if dropoff_id:
                        visible_deliveries.append({"dropoff_id": dropoff_id, "position": pos})

        visible_agents = [
            {
                "agent_id": other.agent_id,
                "position": other.position,
                "state": other.state,
                "carrying_box_id": other.carrying_box_id,
            }
            for other in engine.agents
            if other.agent_id != agent.agent_id and visible(other.position)
        ]

        visible_tasks = []
        visible_items = []
        for task in engine.tasks:
            pickup_pos = task.pickup_position(engine.map)
            dropoff_pos = task.dropoff_position(engine.map)
            assigned_to_self = task.assigned_agent_id == agent.agent_id
            if visible(pickup_pos) or visible(dropoff_pos) or assigned_to_self:
                visible_tasks.append(task.serialize(engine.map))

            item = engine.items.get(task.item_id)
            item_position = engine.item_position(task.item_id)
            if item_position is not None and (visible(item_position) or assigned_to_self):
                visible_items.append(item.serialize(engine.map, item_position) if item else {
                    "item_id": task.item_id,
                    "task_id": task.task_id,
                    "position": item_position,
                    "state": task.status,
                })

        return {
            "tick": engine.tick,
            "map_width": engine.map.width,
            "map_height": engine.map.height,
            "self_position": agent.position,
            "visible_cells": visible_cells,
            "visible_pickups": visible_pickups,
            "visible_deliveries": visible_deliveries,
            "visible_agents": visible_agents,
            "occupied_cells": [
                {"position": other["position"], "agent_id": other["agent_id"]}
                for other in visible_agents
            ],
            "visible_tasks": visible_tasks,
            "visible_items": visible_items,
            "carrying_box_id": agent.carrying_item_id,
            "carrying_item_id": agent.carrying_item_id,
        }
