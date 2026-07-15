from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from .action import MOVE, PICKUP, PLACE, WAIT, Action, ActionResult
from .agent import Agent
from .analytics import Analytics
from .event_log import EventLogger, ReplayLog
from .item import Item
from .map import WarehouseMap
from .metrics import GlobalMetrics
from .movement import DIRECTION_VECTORS
from .task import Task
from .task_manager import TaskManager

Position = Tuple[int, int]


@dataclass
class SimulationEngine:
    map: WarehouseMap
    agents: List[Agent]
    tasks: List[Task]
    items: Dict[str, Item]
    seed: int = 1
    scenario_id: str = "default"
    scenario_name: str = "Default Warehouse"
    allocation_strategy: str = "nearest_available"
    routing_strategy: str = "local_memory_astar"
    config: Dict[str, object] = field(default_factory=dict)
    dynamic_changes: List[Dict[str, object]] = field(default_factory=list)
    tick: int = 0
    action_log: List[Dict[str, object]] = field(default_factory=list)
    metrics: GlobalMetrics = field(default_factory=GlobalMetrics)
    rng: Random = field(init=False)
    run_id: str = field(init=False)
    task_manager: TaskManager = field(init=False)
    event_logger: EventLogger = field(init=False)
    analytics: Analytics = field(init=False)
    replay_log: ReplayLog = field(default_factory=ReplayLog)
    _completion_logged: bool = False
    _applied_dynamic_changes: Set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)
        self.run_id = f"{self.scenario_id}-{uuid4().hex[:8]}"
        self.task_manager = TaskManager(self.tasks, self.items)
        self.event_logger = EventLogger(run_id=self.run_id)
        self.analytics = Analytics(run_id=self.run_id)
        self.metrics.total_tasks = len(self.tasks)
        for agent in self.agents:
            agent.memory_module.initialize_map(self.map.width, self.map.height)
        self.log_event(
            "SIMULATION_STARTED",
            f"Scenario '{self.scenario_id}' initialized with seed {self.seed}.",
            result="success",
        )
        for task in self.tasks:
            self.log_event(
                "TASK_CREATED",
                f"{task.task_id} created for {task.item_id}.",
                task_id=task.task_id,
                item_id=task.item_id,
                target=task.pickup_position(self.map),
                result="success",
            )

    @property
    def deliveries(self) -> List[Task]:
        return self.tasks

    @property
    def event_log(self) -> List[Dict[str, object]]:
        return self.event_logger.events

    def step(self) -> Dict[str, object]:
        if self.is_complete:
            self._finalize_completion()
            return self.serialize_state()

        before_state = self._replay_state_snapshot()
        self.tick += 1
        self.metrics.total_steps = self.tick
        self.action_log = []
        self.log_event("TICK_STARTED", f"Tick {self.tick} started.", result="success")

        self._apply_dynamic_changes()

        for agent in self.agents:
            agent.perceive_and_remember(self)

        self._communicate_adjacent_agents()

        for agent in self.agents:
            agent.update_congestion(self.tick)

        self.task_manager.assign_available_tasks(self)

        planned_actions = []
        for agent in self.agents:
            replans_before = agent.metrics.route_replans
            action = agent.select_intended_action(self.tick, self.rng)
            planned_actions.append((agent, action))
            if agent.metrics.route_replans > replans_before:
                self.log_event(
                    "REPLAN_TRIGGERED",
                    f"{agent.agent_id} replanned route.",
                    agent_id=agent.agent_id,
                    task_id=action.task_id,
                    item_id=action.item_id,
                    source=agent.position,
                    target=action.target,
                    result="success",
                    data={"action": action.serialize()},
                )
            self.log_event(
                "ACTION_SELECTED",
                f"{agent.agent_id} selected {action.type}.",
                agent_id=agent.agent_id,
                task_id=action.task_id,
                item_id=action.item_id,
                source=agent.position,
                target=action.target,
                result="selected",
                data=action.serialize(),
            )
            if action.type == MOVE:
                self.log_event(
                    "MOVE_ATTEMPTED",
                    f"{agent.agent_id} attempted move to {action.target}.",
                    agent_id=agent.agent_id,
                    task_id=action.task_id,
                    item_id=action.item_id,
                    source=agent.position,
                    target=action.target,
                    result="attempted",
                    data=action.serialize(),
                )
            if action.type == WAIT and action.reason.startswith("no_route"):
                self.log_event(
                    "BLOCKED_PATH_DETECTED",
                    f"{agent.agent_id} has no route to current target.",
                    agent_id=agent.agent_id,
                    task_id=action.task_id,
                    item_id=action.item_id,
                    source=agent.position,
                    target=action.target,
                    result="blocked",
                    rejection_reason=action.reason,
                    data=action.serialize(),
                )

        results = self._validate_and_apply_actions(planned_actions)
        for agent, action in planned_actions:
            result = results[agent.agent_id]
            agent.receive_action_result(result, self.tick)
            self._record_action(agent, action, result)
            self._record_action_event(result)

        self.log_event("TICK_COMPLETED", f"Tick {self.tick} completed.", result="success")
        replay_frame = {
            "run_id": self.run_id,
            "tick": self.tick,
            "before": before_state,
            "intended_actions": [action.serialize() for _, action in planned_actions],
            "results": [result.serialize() for result in results.values()],
            "after": self._replay_state_snapshot(),
            "metrics": self.serialize_metrics(),
        }
        self.replay_log.record(replay_frame)
        self.analytics.record_replay_frame(replay_frame)

        self._finalize_completion()

        return self.serialize_state()

    def run_steps(self, steps: int) -> Dict[str, object]:
        safe_steps = max(1, min(int(steps), 1000))
        state = self.serialize_state()
        for _ in range(safe_steps):
            state = self.step()
            if self.is_complete:
                break
        return state

    @property
    def is_complete(self) -> bool:
        return bool(self.tasks) and all(task.status == "delivered" for task in self.tasks)

    def _finalize_completion(self) -> None:
        if not self.is_complete or self._completion_logged:
            return
        self._completion_logged = True
        self.log_event(
            "SIMULATION_COMPLETED",
            f"Scenario '{self.scenario_id}' completed in {self.tick} ticks.",
            result="success",
        )

    def item_position(self, item_id: str) -> Optional[Position]:
        item = self.items.get(item_id)
        if item is None:
            return None
        carrier_position = None
        if item.carried_by:
            carrier = self.get_agent(item.carried_by)
            carrier_position = carrier.position if carrier else None
        return item.position(self.map, carrier_position)

    def item_state(self, item_id: str) -> str:
        item = self.items.get(item_id)
        return item.state if item else "unknown"

    def get_agent(self, agent_id: Optional[str]) -> Optional[Agent]:
        if agent_id is None:
            return None
        return next((agent for agent in self.agents if agent.agent_id == agent_id), None)

    def get_task(self, task_id: Optional[str]) -> Optional[Task]:
        return self.task_manager.get_task(task_id)

    def get_delivery(self, delivery_id: Optional[str]) -> Optional[Task]:
        return self.get_task(delivery_id)

    def get_item(self, item_id: Optional[str]) -> Optional[Item]:
        return self.task_manager.get_item(item_id)

    def serialize_state(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "tick": self.tick,
            "seed": self.seed,
            "scenario": self.serialize_scenario_info(),
            "is_complete": self.is_complete,
            "map": self.map.serialize(),
            "board": self.serialize_board(),
            "agents": [agent.serialize() for agent in self.agents],
            "deliveries": self.serialize_tasks(),
            "tasks": self.serialize_tasks(),
            "boxes": self.serialize_items(),
            "items": self.serialize_items(),
            "actions": self.action_log,
            "events": self.serialize_events(limit=35),
            "metrics": self.serialize_metrics(),
        }

    def serialize_board(self) -> Dict[str, object]:
        agents_by_position = {agent.position: agent.agent_id for agent in self.agents}
        items_by_position: Dict[Position, List[str]] = {}
        for item in self.serialize_items():
            position = item.get("position")
            if position is None:
                continue
            items_by_position.setdefault(tuple(position), []).append(str(item["item_id"]))

        rows = []
        for y in range(self.map.height):
            row = []
            for x in range(self.map.width):
                position = (x, y)
                row.append({
                    "position": position,
                    "cell_type": self.map.cell_type(position),
                    "walkable": self.map.is_walkable(position),
                    "agent_id": agents_by_position.get(position),
                    "item_ids": items_by_position.get(position, []),
                    "pickup_id": self.map.pickup_id_at(position),
                    "dropoff_id": self.map.dropoff_id_at(position),
                })
            rows.append(row)
        return {
            "width": self.map.width,
            "height": self.map.height,
            "rows": rows,
        }

    def serialize_agent(self, agent_id: str, include_memory: bool = True) -> Optional[Dict[str, object]]:
        agent = self.get_agent(agent_id)
        return agent.serialize(include_memory=include_memory) if agent else None

    def serialize_tasks(self) -> List[Dict[str, object]]:
        return [task.serialize(self.map) for task in self.tasks]

    def serialize_items(self) -> List[Dict[str, object]]:
        items = []
        for item in self.items.values():
            carrier_position = None
            if item.carried_by:
                carrier = self.get_agent(item.carried_by)
                carrier_position = carrier.position if carrier else None
            serialized = item.serialize(self.map, carrier_position)
            task = self.get_task(item.task_id)
            serialized["assigned_agent_id"] = task.assigned_agent_id if task else None
            items.append(serialized)
        return items

    def serialize_metrics(self) -> Dict[str, object]:
        self.metrics.route_replans = max(
            self.metrics.route_replans,
            sum(agent.metrics.route_replans for agent in self.agents),
        )
        return {
            "global": self.metrics.serialize(),
            "agents": {
                agent.agent_id: agent.metrics.serialize()
                for agent in self.agents
            },
        }

    def serialize_events(self, limit: Optional[int] = None) -> List[Dict[str, object]]:
        return self.event_logger.serialize(limit=limit)

    def serialize_replay(self, limit: Optional[int] = None) -> Dict[str, object]:
        return {"frames": self.replay_log.serialize(limit=limit)}

    def serialize_scenario_info(self) -> Dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.scenario_name,
            "allocation_strategy": self.allocation_strategy,
            "routing_strategy": self.routing_strategy,
            "config": self.config,
        }

    def log_event(
        self,
        event_type: str,
        message: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        item_id: Optional[str] = None,
        source: Optional[Position] = None,
        target: Optional[Position] = None,
        result: Optional[str] = None,
        rejection_reason: str = "",
        data: Optional[Dict[str, object]] = None,
        position: Optional[Position] = None,
    ) -> None:
        event = self.event_logger.log(
            tick=self.tick,
            event_type=event_type,
            message=message,
            agent_id=agent_id,
            task_id=task_id,
            item_id=item_id,
            source=source if source is not None else position,
            target=target,
            result=result,
            rejection_reason=rejection_reason,
            data=data,
        )
        self.analytics.record_event(event)

    def _validate_and_apply_actions(
        self,
        planned_actions: List[Tuple[Agent, Action]],
    ) -> Dict[str, ActionResult]:
        results: Dict[str, ActionResult] = {}
        move_targets: Dict[str, Position] = {}
        initial_positions = {agent.agent_id: agent.position for agent in self.agents}
        occupant_by_position = {position: agent_id for agent_id, position in initial_positions.items()}

        for agent, action in planned_actions:
            if action.type == MOVE:
                target = self._move_target(agent, action)
                if target is None:
                    results[agent.agent_id] = self._reject(agent, action, "invalid_move_direction")
                    continue
                if not self.map.in_bounds(target):
                    results[agent.agent_id] = self._reject(agent, action, "out_of_bounds", target)
                    continue
                if not self.map.is_walkable(target):
                    reason = "blocked_cell" if self.map.is_blocked(target) else "non_walkable_service_cell"
                    results[agent.agent_id] = self._reject(agent, action, reason, target)
                    continue
                move_targets[agent.agent_id] = target

        target_counts: Dict[Position, int] = {}
        for target in move_targets.values():
            target_counts[target] = target_counts.get(target, 0) + 1

        for agent_id, target in move_targets.items():
            if agent_id in results:
                continue
            if target_counts[target] > 1:
                agent = self.get_agent(agent_id)
                results[agent_id] = self._reject(agent, self._action_for(planned_actions, agent_id), "target_cell_conflict", target)

        for agent_id, target in move_targets.items():
            if agent_id in results:
                continue
            occupant_id = occupant_by_position.get(target)
            if not occupant_id:
                continue
            occupant_target = move_targets.get(occupant_id)
            if occupant_target == initial_positions[agent_id]:
                agent = self.get_agent(agent_id)
                results[agent_id] = self._reject(agent, self._action_for(planned_actions, agent_id), "swap_conflict", target)
                occupant = self.get_agent(occupant_id)
                if occupant and occupant_id not in results:
                    results[occupant_id] = self._reject(occupant, self._action_for(planned_actions, occupant_id), "swap_conflict", occupant_target)
            elif occupant_id in results or occupant_id not in move_targets:
                agent = self.get_agent(agent_id)
                results[agent_id] = self._reject(agent, self._action_for(planned_actions, agent_id), "target_occupied", target)

        for agent, action in planned_actions:
            if agent.agent_id in results:
                continue
            if action.type == MOVE:
                target = move_targets[agent.agent_id]
                source = agent.position
                agent.position = target
                agent.mode = "moving_to_delivery" if agent.carrying_item_id else "moving_to_pickup"
                agent.metrics.path_length += 1
                self.metrics.path_length += 1
                task = self.get_task(agent.current_task_id)
                if task:
                    task.actual_path_length += 1
                results[agent.agent_id] = ActionResult(
                    agent_id=agent.agent_id,
                    action=action,
                    success=True,
                    useful=True,
                    source_position=source,
                    target_position=target,
                    task_id=action.task_id,
                    item_id=action.item_id,
                )
            elif action.type == PICKUP:
                results[agent.agent_id] = self._apply_pickup(agent, action)
            elif action.type == PLACE:
                results[agent.agent_id] = self._apply_place(agent, action)
            elif action.type == WAIT:
                agent.mode = "waiting" if action.reason else agent.mode
                results[agent.agent_id] = ActionResult(
                    agent_id=agent.agent_id,
                    action=action,
                    success=True,
                    useful=False,
                    source_position=agent.position,
                    target_position=action.target,
                    task_id=action.task_id,
                    item_id=action.item_id,
                )
            else:
                results[agent.agent_id] = self._reject(agent, action, "unknown_action", action.target)

        return results

    def _apply_pickup(self, agent: Agent, action: Action) -> ActionResult:
        task = self.get_task(action.task_id or agent.current_task_id)
        if task is None:
            return self._reject(agent, action, "unknown_task", action.target)
        pickup = task.pickup_position(self.map)
        if task.assigned_agent_id != agent.agent_id:
            return self._reject(agent, action, "task_not_assigned_to_agent", pickup)
        if task.status not in {"waiting", "assigned"}:
            return self._reject(agent, action, "task_not_waiting_for_pickup", pickup)
        if agent.carrying_item_id is not None:
            return self._reject(agent, action, "agent_already_carrying_item", pickup)
        if agent.position not in self.map.adjacent_walkable_positions(pickup):
            return self._reject(agent, action, "agent_not_adjacent_to_pickup", pickup)

        self.task_manager.mark_picked(task, agent.agent_id, self.tick)
        agent.carrying_item_id = task.item_id
        agent.mode = "carrying_item"
        agent.replanning_flag = True
        agent.memory_module.remember_task(task.serialize(self.map), self.tick)
        agent.memory_module.remember_item(self.items[task.item_id].serialize(self.map, agent.position), self.tick)
        self.metrics.pickup_events += 1
        return ActionResult(
            agent_id=agent.agent_id,
            action=action,
            success=True,
            useful=True,
            source_position=agent.position,
            target_position=pickup,
            task_id=task.task_id,
            item_id=task.item_id,
        )

    def _apply_place(self, agent: Agent, action: Action) -> ActionResult:
        task = self.get_task(action.task_id or agent.current_task_id)
        if task is None:
            return self._reject(agent, action, "unknown_task", action.target)
        dropoff = task.dropoff_position(self.map)
        if task.status != "carrying" or task.carried_by != agent.agent_id:
            return self._reject(agent, action, "task_not_carried_by_agent", dropoff)
        if agent.carrying_item_id != task.item_id:
            return self._reject(agent, action, "carried_item_mismatch", dropoff)
        if agent.position not in self.map.adjacent_walkable_positions(dropoff):
            return self._reject(agent, action, "agent_not_adjacent_to_delivery", dropoff)

        self.task_manager.mark_delivered(task, self.tick)
        task.shortest_path_length = self._shortest_service_distance(task)
        completion_time = self.tick - task.created_tick
        agent.carrying_item_id = None
        agent.metrics.completed_tasks += 1
        agent.metrics.total_completion_time += completion_time
        agent.metrics.path_inefficiency += task.path_inefficiency
        self.metrics.completed_deliveries += 1
        self.metrics.delivery_events += 1
        self.metrics.total_completion_time += completion_time
        self.metrics.path_inefficiency += task.path_inefficiency
        agent.memory_module.remember_task(task.serialize(self.map), self.tick)
        agent.memory_module.remember_item(self.items[task.item_id].serialize(self.map, dropoff), self.tick)
        agent.clear_task()
        return ActionResult(
            agent_id=agent.agent_id,
            action=action,
            success=True,
            useful=True,
            source_position=agent.position,
            target_position=dropoff,
            task_id=task.task_id,
            item_id=task.item_id,
        )

    def _reject(
        self,
        agent: Optional[Agent],
        action: Action,
        reason: str,
        target: Optional[Position] = None,
    ) -> ActionResult:
        if agent and action.type == MOVE:
            self.metrics.blocked_move_attempts += 1
            self.metrics.route_replans += 1
            agent.metrics.blocked_move_attempts += 1
            agent.metrics.route_replans += 1
            if reason in {"target_cell_conflict", "swap_conflict", "target_occupied"}:
                self.metrics.collision_preventions += 1
                self.metrics.collision_violations += 1
                agent.metrics.collision_preventions += 1
            if target:
                agent.memory_module.record_failed_move(target, self.tick)
        return ActionResult(
            agent_id=agent.agent_id if agent else str(action.agent_id),
            action=action,
            success=False,
            useful=False,
            failure_reason=reason,
            source_position=agent.position if agent else action.source,
            target_position=target if target is not None else action.target,
            task_id=action.task_id,
            item_id=action.item_id,
        )

    def _record_action(
        self,
        agent: Agent,
        action: Action,
        result: ActionResult,
    ) -> None:
        self.metrics.record_action(action.type)
        agent.metrics.record_action(action.type, useful=result.useful)
        self.action_log.append({
            "agent_id": agent.agent_id,
            "action": action.type,
            "direction": action.direction,
            "target": action.target,
            "source": result.source_position,
            "reason": action.reason,
            "success": result.success,
            "failure_reason": result.failure_reason,
            "position": agent.position,
            "goal_type": agent.goal_holder.goal_type,
            "goal_delivery_id": agent.goal_holder.target_delivery_id,
            "goal_task_id": agent.goal_holder.target_delivery_id,
            "result": result.serialize(),
        })

    def _record_action_event(self, result: ActionResult) -> None:
        action = result.action
        event_type = {
            MOVE: "MOVE_SUCCEEDED" if result.success else "MOVE_REJECTED",
            PICKUP: "PICKUP_SUCCEEDED" if result.success else "PICKUP_REJECTED",
            PLACE: "DELIVERY_SUCCEEDED" if result.success else "PLACE_REJECTED",
            WAIT: "WAIT_ACTION",
        }.get(action.type, "ACTION_VALIDATION_RESULT")
        if action.type == WAIT:
            self.metrics.wait_actions += 0
        if not result.success and action.type == MOVE:
            self.metrics.blocked_path_events += 1
            self.log_event(
                "BLOCKED_PATH_DETECTED",
                f"{result.agent_id} could not move to {result.target_position}.",
                agent_id=result.agent_id,
                task_id=result.task_id,
                item_id=result.item_id,
                source=result.source_position,
                target=result.target_position,
                result="rejected",
                rejection_reason=result.failure_reason,
            )
        self.log_event(
            event_type,
            self._result_message(result),
            agent_id=result.agent_id,
            task_id=result.task_id,
            item_id=result.item_id,
            source=result.source_position,
            target=result.target_position,
            result="success" if result.success else "rejected",
            rejection_reason=result.failure_reason,
            data=result.serialize(),
        )
        if action.type == PLACE and result.success:
            self.log_event(
                "TASK_COMPLETED",
                f"{result.task_id} completed by {result.agent_id}.",
                agent_id=result.agent_id,
                task_id=result.task_id,
                item_id=result.item_id,
                source=result.source_position,
                target=result.target_position,
                result="success",
                data=result.serialize(),
            )

    def _communicate_adjacent_agents(self) -> None:
        for index, agent in enumerate(self.agents):
            for other in self.agents[index + 1:]:
                if self.map.manhattan(agent.position, other.position) != 1:
                    continue
                result = agent.communication_module.exchange_with(agent, other, self.tick)
                self.metrics.communication_events += 1
                self.log_event(
                    "COMMUNICATION_OCCURRED",
                    f"{agent.agent_id} exchanged knowledge with {other.agent_id}.",
                    agent_id=agent.agent_id,
                    source=agent.position,
                    target=other.position,
                    result="success",
                    data=result,
                )

    def _apply_dynamic_changes(self) -> None:
        for index, change in enumerate(self.dynamic_changes):
            if index in self._applied_dynamic_changes:
                continue
            if int(change.get("tick", -1)) != self.tick:
                continue
            position = tuple(change["position"])
            action = change.get("action")
            if action == "block":
                if position not in [agent.position for agent in self.agents]:
                    self.map.blocked.add(position)
                    self._applied_dynamic_changes.add(index)
            elif action == "unblock":
                self.map.blocked.discard(position)
                self._applied_dynamic_changes.add(index)
            self.log_event(
                "MAP_CHANGED",
                f"Dynamic map change {action} at {position}.",
                target=position,
                result="success",
                data=change,
            )

    def _move_target(self, agent: Agent, action: Action) -> Optional[Position]:
        if action.target is not None and self.map.manhattan(agent.position, action.target) == 1:
            return action.target
        if action.direction not in DIRECTION_VECTORS:
            return None
        dx, dy = DIRECTION_VECTORS[action.direction]
        return (agent.position[0] + dx, agent.position[1] + dy)

    @staticmethod
    def _action_for(planned_actions: List[Tuple[Agent, Action]], agent_id: str) -> Action:
        return next(action for agent, action in planned_actions if agent.agent_id == agent_id)

    def _shortest_service_distance(self, task: Task) -> int:
        starts = self.map.adjacent_walkable_positions(task.pickup_position(self.map))
        goals = set(self.map.adjacent_walkable_positions(task.dropoff_position(self.map)))
        if not starts or not goals:
            return 0
        queue: List[Tuple[Position, int]] = [(start, 0) for start in starts]
        seen = set(starts)
        while queue:
            current, distance = queue.pop(0)
            if current in goals:
                return distance
            for neighbor in self.map.neighbors(current):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, distance + 1))
        return 0

    @staticmethod
    def _result_message(result: ActionResult) -> str:
        if result.success:
            return f"{result.agent_id} {result.action.type} succeeded."
        return f"{result.agent_id} {result.action.type} rejected: {result.failure_reason}."

    def _replay_state_snapshot(self) -> Dict[str, object]:
        return {
            "tick": self.tick,
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "position": agent.position,
                    "mode": agent.mode,
                    "task_id": agent.current_task_id,
                    "carrying_item_id": agent.carrying_item_id,
                    "planned_path": agent.planned_path,
                }
                for agent in self.agents
            ],
            "tasks": self.serialize_tasks(),
            "items": self.serialize_items(),
        }
