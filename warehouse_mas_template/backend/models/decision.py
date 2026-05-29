from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Dict, List, Optional, Tuple

from .action import MOVE, PICKUP, PLACE, WAIT, Action

Position = Tuple[int, int]


@dataclass
class DecisionModule:
    def select_action(self, agent: "Agent", tick: int, rng: Optional[Random] = None) -> Action:
        task = agent.current_task_snapshot()
        if task is None:
            agent.mode = "idle"
            return self._action(agent, WAIT, tick, reason="no_assigned_task")

        pickup = tuple(task["pickup_position"])
        dropoff = tuple(task["dropoff_position"])
        item_id = str(task["item_id"])
        carrying_target_item = agent.carrying_item_id == item_id

        if carrying_target_item:
            agent.goal_holder.goal_type = "deliver"
            agent.current_target = dropoff
            agent.mode = "moving_to_delivery"
            if self._adjacent(agent.position, dropoff):
                agent.mode = "placing"
                return self._action(agent, PLACE, tick, target=dropoff, task=task)
            return self._move_toward(agent, tick, dropoff, "delivery", task, rng)

        agent.goal_holder.goal_type = "pickup"
        agent.current_target = pickup
        agent.mode = "moving_to_pickup"
        if self._adjacent(agent.position, pickup):
            agent.mode = "picking"
            return self._action(agent, PICKUP, tick, target=pickup, task=task)
        return self._move_toward(agent, tick, pickup, "pickup", task, rng)

    def _move_toward(
        self,
        agent: "Agent",
        tick: int,
        target: Position,
        label: str,
        task: Dict[str, object],
        rng: Optional[Random],
    ) -> Action:
        target_cells = agent.memory_module.adjacent_candidate_cells(target)
        needs_plan = (
            agent.replanning_flag
            or agent.current_target != target
            or not agent.planned_path
            or agent.position not in agent.planned_path
            or agent.planned_path[-1] not in target_cells
            or self._route_invalidated(agent, tick)
        )
        if needs_plan:
            agent.replanning_flag = False
            if agent.planned_path:
                agent.memory_module.record_blocked_path(agent.position, tick)
            plan = agent.path_planning_module.plan_route_to_any(
                start=agent.position,
                goals=target_cells,
                memory=agent.memory_module,
                current_tick=tick,
                rng=rng,
            )
            agent.planned_path = plan.path
            agent.current_path_cost = plan.cost
            agent.agent_log_module.record(
                tick=tick,
                event_type="REPLAN_TRIGGERED" if plan.path else "BLOCKED_PATH_DETECTED",
                message=f"{agent.agent_id} planned route toward {label}.",
                data=plan.serialize(),
            )
            if plan.path:
                agent.metrics.route_replans += 1
            else:
                agent.memory_module.record_blocked_path(agent.position, tick)

        route = self._remaining_route(agent)
        direction = agent.path_planning_module.next_direction(route)
        if direction is None:
            yield_action = self._yield_action(agent, tick, target, task)
            if yield_action:
                return yield_action
            agent.mode = "waiting"
            reason = f"no_route_to_{label}"
            agent.memory_module.record_blocked_path(agent.position, tick)
            return self._action(agent, WAIT, tick, target=target, task=task, reason=reason)

        next_position = route[1]
        return self._action(
            agent,
            MOVE,
            tick,
            direction=direction,
            target=next_position,
            task=task,
            data={"route_target": target, "route_label": label},
        )

    def _remaining_route(self, agent: "Agent") -> list[Position]:
        if not agent.planned_path:
            return []
        if agent.position not in agent.planned_path:
            return agent.planned_path
        index = agent.planned_path.index(agent.position)
        return agent.planned_path[index:]

    def _action(
        self,
        agent: "Agent",
        action_type: str,
        tick: int,
        direction: Optional[str] = None,
        target: Optional[Position] = None,
        task: Optional[Dict[str, object]] = None,
        reason: str = "",
        data: Optional[Dict[str, object]] = None,
    ) -> Action:
        action = Action(
            type=action_type,
            agent_id=agent.agent_id,
            direction=direction,
            source=agent.position,
            target=target,
            task_id=str(task["task_id"]) if task else agent.current_task_id,
            item_id=str(task["item_id"]) if task else agent.carrying_item_id,
            reason=reason,
            data=data or {},
        )
        agent.intended_action = action
        agent.agent_log_module.record_decision(agent, tick, action)
        return action

    @staticmethod
    def _adjacent(a: Position, b: Position) -> bool:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1

    def _route_invalidated(self, agent: "Agent", tick: int) -> bool:
        route = self._remaining_route(agent)
        if len(route) < 2:
            return False

        recently_occupied = agent.memory_module.recently_occupied_cells(tick)
        for cell in route[1:]:
            if agent.memory_module.is_known_blocked(cell):
                return True
            if agent.memory_module.is_known_service_cell(cell):
                return True

        next_cell = route[1]
        return next_cell in recently_occupied

    def _yield_action(
        self,
        agent: "Agent",
        tick: int,
        target: Position,
        task: Dict[str, object],
    ) -> Optional[Action]:
        blockers = self._nearby_blocking_agents(agent, tick)
        if not blockers:
            return None

        highest_priority_blocker = min(blockers, key=lambda blocker: self._priority_key(blocker["agent_id"]))
        if self._priority_key(agent.agent_id) <= self._priority_key(highest_priority_blocker["agent_id"]):
            return None

        candidate = self._yield_candidate(agent, tick, target, blockers)
        if candidate is None:
            return None

        direction = self._direction_between(agent.position, candidate)
        if direction is None:
            return None

        agent.mode = "yielding"
        agent.planned_path = [agent.position, candidate]
        return self._action(
            agent,
            MOVE,
            tick,
            direction=direction,
            target=candidate,
            task=task,
            reason="yielding_to_higher_priority_agent",
            data={
                "blocked_by": [blocker["agent_id"] for blocker in blockers],
                "yield_target": candidate,
            },
        )

    def _nearby_blocking_agents(self, agent: "Agent", tick: int) -> List[Dict[str, object]]:
        blockers: List[Dict[str, object]] = []
        for agent_id, entry in agent.memory_module.known_agents.items():
            if tick - entry.last_seen_tick > 2:
                continue
            position = tuple(entry.value["position"])
            distance = abs(position[0] - agent.position[0]) + abs(position[1] - agent.position[1])
            if distance <= 2:
                blockers.append({"agent_id": str(agent_id), "position": position})
        return blockers

    def _yield_candidate(
        self,
        agent: "Agent",
        tick: int,
        target: Position,
        blockers: List[Dict[str, object]],
    ) -> Optional[Position]:
        occupied = set(agent.memory_module.recently_occupied_cells(tick))
        blocker_positions = {tuple(blocker["position"]) for blocker in blockers}
        current_distance = self._distance(agent.position, target)
        candidates = []
        for candidate in self._neighbors(agent.position):
            if not agent.memory_module.in_bounds(candidate):
                continue
            if candidate in occupied or candidate in blocker_positions:
                continue
            if agent.memory_module.is_known_blocked(candidate):
                continue
            if agent.memory_module.is_known_service_cell(candidate):
                continue
            known_walkable = agent.memory_module.is_known_walkable(candidate)
            if known_walkable is False:
                continue
            distance_to_target = self._distance(candidate, target)
            if distance_to_target < current_distance:
                continue
            min_blocker_distance = min(self._distance(candidate, blocker) for blocker in blocker_positions)
            candidates.append((known_walkable is True, distance_to_target, min_blocker_distance, candidate))

        if not candidates:
            return None
        candidates.sort(key=lambda value: (value[0], value[1], value[2], value[3]), reverse=True)
        return candidates[0][3]

    @staticmethod
    def _neighbors(position: Position) -> List[Position]:
        x, y = position
        return [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]

    @staticmethod
    def _direction_between(source: Position, target: Position) -> Optional[str]:
        dx = target[0] - source[0]
        dy = target[1] - source[1]
        if (dx, dy) == (0, -1):
            return "up"
        if (dx, dy) == (0, 1):
            return "down"
        if (dx, dy) == (-1, 0):
            return "left"
        if (dx, dy) == (1, 0):
            return "right"
        return None

    @staticmethod
    def _distance(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _priority_key(agent_id: str) -> tuple[int, str]:
        digits = "".join(char for char in agent_id if char.isdigit())
        return (int(digits) if digits else 999999, agent_id)
