from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from .item import Item
from .task import Task

Position = Tuple[int, int]


@dataclass
class TaskManager:
    tasks: List[Task]
    items: Dict[str, Item]
    task_queue: Deque[str] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if not self.task_queue:
            self.task_queue = deque(task.task_id for task in self.tasks)

    def waiting_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == "waiting"]

    def active_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status != "delivered"]

    def get_task(self, task_id: Optional[str]) -> Optional[Task]:
        if task_id is None:
            return None
        return next((task for task in self.tasks if task.task_id == task_id), None)

    def get_item(self, item_id: Optional[str]) -> Optional[Item]:
        if item_id is None:
            return None
        return self.items.get(item_id)

    def assign_available_tasks(self, engine: "SimulationEngine") -> List[Dict[str, object]]:
        assignments = []
        available_agents = [
            agent for agent in engine.agents
            if agent.is_available_for_task
        ]
        if not available_agents:
            return assignments

        for task in self.waiting_tasks():
            if not available_agents:
                break
            agent = min(
                available_agents,
                key=lambda candidate: self._allocation_cost(candidate.position, task, engine.map),
            )
            task.status = "assigned"
            task.assigned_agent_id = agent.agent_id
            task.assigned_tick = engine.tick
            agent.assign_task(task.serialize(engine.map), engine.tick)
            engine.metrics.task_assignments += 1
            engine.log_event(
                "TASK_ASSIGNED",
                f"{task.task_id} assigned to {agent.agent_id}.",
                agent_id=agent.agent_id,
                task_id=task.task_id,
                item_id=task.item_id,
                source=agent.position,
                target=task.pickup_position(engine.map),
                result="success",
            )
            assignments.append({"agent_id": agent.agent_id, "task_id": task.task_id})
            available_agents.remove(agent)
        return assignments

    def mark_picked(self, task: Task, agent_id: str, tick: int) -> None:
        task.status = "carrying"
        task.carried_by = agent_id
        task.picked_tick = tick
        item = self.items[task.item_id]
        item.state = "carried"
        item.carried_by = agent_id

    def mark_delivered(self, task: Task, tick: int) -> None:
        task.status = "delivered"
        task.carried_by = None
        task.delivered_tick = tick
        item = self.items[task.item_id]
        item.state = "delivered"
        item.carried_by = None

    def _allocation_cost(self, start: Position, task: Task, warehouse_map) -> int:
        targets = warehouse_map.adjacent_walkable_positions(task.pickup_position(warehouse_map))
        if not targets:
            return 999999
        return self._shortest_distance(start, targets, warehouse_map)

    @staticmethod
    def _shortest_distance(start: Position, goals: Iterable[Position], warehouse_map) -> int:
        goal_set = set(goals)
        if start in goal_set:
            return 0
        queue: Deque[Tuple[Position, int]] = deque([(start, 0)])
        seen = {start}
        while queue:
            current, distance = queue.popleft()
            for neighbor in warehouse_map.neighbors(current):
                if neighbor in seen:
                    continue
                if neighbor in goal_set:
                    return distance + 1
                seen.add(neighbor)
                queue.append((neighbor, distance + 1))
        return 999999
