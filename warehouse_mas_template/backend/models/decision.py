from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Dict, Optional, Tuple

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
        )
        if needs_plan:
            agent.replanning_flag = False
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
