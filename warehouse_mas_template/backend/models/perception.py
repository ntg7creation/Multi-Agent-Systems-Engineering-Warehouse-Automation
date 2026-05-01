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
        for y in range(engine.map.height):
            for x in range(engine.map.width):
                pos = (x, y)
                if visible(pos):
                    visible_cells.append({
                        "position": pos,
                        "cell_type": engine.map.cell_type(pos),
                    })

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
        for delivery in engine.deliveries:
            pickup_pos = delivery.pickup_position(engine.map)
            dropoff_pos = delivery.dropoff_position(engine.map)
            assigned_to_self = delivery.assigned_agent_id == agent.agent_id
            if visible(pickup_pos) or visible(dropoff_pos) or assigned_to_self:
                visible_tasks.append({
                    "task_id": delivery.delivery_id,
                    "pickup": pickup_pos,
                    "dropoff": dropoff_pos,
                    "status": delivery.status,
                    "assigned_agent_id": delivery.assigned_agent_id,
                    "item_id": delivery.box_id,
                })

            item_position = engine.item_position(delivery)
            if item_position is not None and (visible(item_position) or assigned_to_self):
                visible_items.append({
                    "item_id": delivery.box_id,
                    "task_id": delivery.delivery_id,
                    "position": item_position,
                    "state": engine.item_state(delivery),
                })

        return {
            "tick": engine.tick,
            "self_position": agent.position,
            "visible_cells": visible_cells,
            "visible_agents": visible_agents,
            "visible_tasks": visible_tasks,
            "visible_items": visible_items,
            "carrying_box_id": agent.carrying_box_id,
        }
