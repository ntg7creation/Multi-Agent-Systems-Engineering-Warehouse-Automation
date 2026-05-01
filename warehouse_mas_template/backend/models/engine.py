from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .action import Action
from .agent import Agent
from .delivery import Delivery
from .map import WarehouseMap
from .metrics import GlobalMetrics
from .movement import DIRECTION_VECTORS

Position = Tuple[int, int]


@dataclass
class SimulationEngine:
    map: WarehouseMap
    agents: List[Agent]
    deliveries: List[Delivery]
    seed: int = 1
    scenario_id: str = "default"
    scenario_name: str = "Default Warehouse"
    allocation_strategy: str = "nearest_available"
    routing_strategy: str = "seeded_bfs"
    tick: int = 0
    action_log: List[Dict[str, object]] = field(default_factory=list)
    event_log: List[Dict[str, object]] = field(default_factory=list)
    metrics: GlobalMetrics = field(default_factory=GlobalMetrics)
    rng: Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)
        self.metrics.total_tasks = len(self.deliveries)
        self.log_event(
            "simulation_initialized",
            f"Scenario '{self.scenario_id}' initialized with seed {self.seed}.",
        )

    def step(self) -> Dict[str, object]:
        self.tick += 1
        self.metrics.total_steps = self.tick
        self.action_log = []

        for agent in self.agents:
            agent.perceive_and_remember(self)

        self._communicate_adjacent_agents()

        start_positions = {agent.agent_id: agent.position for agent in self.agents}
        planned_actions = []

        for agent in self.agents:
            occupied = {
                pos for other_id, pos in start_positions.items()
                if other_id != agent.agent_id
            }
            action = agent.step(self, occupied)
            planned_actions.append((agent, action))

        reserved_positions: Set[Position] = set()
        for agent, action in planned_actions:
            result = self._apply_action(agent, action, reserved_positions)
            reserved_positions.add(agent.position)
            self._record_action(agent, action, result)

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
        return all(delivery.status == "delivered" for delivery in self.deliveries)

    def assign_task_to_agent(self, agent: Agent) -> Optional[Delivery]:
        available = [
            delivery
            for delivery in self.deliveries
            if delivery.status in {"waiting", "assigned"}
            and (
                delivery.assigned_agent_id is None
                or delivery.assigned_agent_id == agent.agent_id
            )
        ]
        if not available:
            return None

        ranked = sorted(
            available,
            key=lambda delivery: self._task_distance(agent.position, delivery),
        )
        chosen = ranked[0]
        if chosen.assigned_agent_id is None:
            chosen.assigned_agent_id = agent.agent_id
            chosen.status = "assigned"
            chosen.assigned_tick = self.tick
            self.metrics.task_assignments += 1
            self.log_event(
                "task_assigned",
                f"{chosen.delivery_id} assigned to {agent.agent_id}.",
                agent_id=agent.agent_id,
                task_id=chosen.delivery_id,
                item_id=chosen.box_id,
                position=agent.position,
            )
        return chosen

    def item_position(self, delivery: Delivery) -> Optional[Position]:
        if delivery.status in {"waiting", "assigned"}:
            return delivery.pickup_position(self.map)
        if delivery.status == "carrying":
            carrier = self.get_agent(delivery.carried_by)
            return carrier.position if carrier else None
        if delivery.status == "delivered":
            return delivery.dropoff_position(self.map)
        return None

    def item_state(self, delivery: Delivery) -> str:
        if delivery.status == "assigned":
            return "waiting"
        if delivery.status == "carrying":
            return "carried"
        return delivery.status

    def get_agent(self, agent_id: Optional[str]) -> Optional[Agent]:
        if agent_id is None:
            return None
        return next((agent for agent in self.agents if agent.agent_id == agent_id), None)

    def get_delivery(self, delivery_id: Optional[str]) -> Optional[Delivery]:
        if delivery_id is None:
            return None
        return next(
            (delivery for delivery in self.deliveries if delivery.delivery_id == delivery_id),
            None,
        )

    def serialize_state(self) -> Dict[str, object]:
        return {
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
            "events": self.serialize_events(limit=25),
            "metrics": self.serialize_metrics(),
        }

    def serialize_board(self) -> Dict[str, object]:
        agents_by_position = {
            agent.position: agent.agent_id
            for agent in self.agents
        }
        items_by_position: Dict[Position, List[str]] = {}
        for item in self.serialize_items():
            position = tuple(item["position"])
            items_by_position.setdefault(position, []).append(item["item_id"])

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
        return [delivery.serialize(self.map) for delivery in self.deliveries]

    def serialize_items(self) -> List[Dict[str, object]]:
        items = []
        for delivery in self.deliveries:
            position = self.item_position(delivery)
            if position is None:
                continue
            items.append({
                "item_id": delivery.box_id,
                "box_id": delivery.box_id,
                "task_id": delivery.delivery_id,
                "delivery_id": delivery.delivery_id,
                "position": position,
                "state": self.item_state(delivery),
                "assigned_agent_id": delivery.assigned_agent_id,
                "carried_by": delivery.carried_by,
            })
        return items

    def serialize_metrics(self) -> Dict[str, object]:
        return {
            "global": self.metrics.serialize(),
            "agents": {
                agent.agent_id: agent.metrics.serialize()
                for agent in self.agents
            },
        }

    def serialize_events(self, limit: Optional[int] = None) -> List[Dict[str, object]]:
        if limit is None or limit <= 0:
            return list(self.event_log)
        return self.event_log[-limit:]

    def serialize_scenario_info(self) -> Dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.scenario_name,
            "allocation_strategy": self.allocation_strategy,
            "routing_strategy": self.routing_strategy,
        }

    def log_event(
        self,
        event_type: str,
        message: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        item_id: Optional[str] = None,
        position: Optional[Position] = None,
        data: Optional[Dict[str, object]] = None,
    ) -> None:
        self.event_log.append({
            "event_id": len(self.event_log) + 1,
            "tick": self.tick,
            "type": event_type,
            "agent_id": agent_id,
            "task_id": task_id,
            "item_id": item_id,
            "position": position,
            "message": message,
            "data": data or {},
        })

    def _apply_action(
        self,
        agent: Agent,
        action: Action,
        reserved_positions: Set[Position],
    ) -> Dict[str, object]:
        if action.type == "move":
            return self._apply_move(agent, action, reserved_positions)
        if action.type == "pick":
            return self._apply_pick(agent, action)
        if action.type == "place":
            return self._apply_place(agent, action)
        agent.state = "waiting" if action.reason else agent.state
        return {
            "success": action.type == "wait",
            "useful": False,
            "failure_reason": "" if action.type == "wait" else "unknown_action",
        }

    def _apply_move(
        self,
        agent: Agent,
        action: Action,
        reserved_positions: Set[Position],
    ) -> Dict[str, object]:
        if action.direction not in DIRECTION_VECTORS:
            self.metrics.blocked_move_attempts += 1
            self.metrics.route_replans += 1
            agent.metrics.blocked_move_attempts += 1
            agent.metrics.route_replans += 1
            agent.state = "waiting"
            self.log_event(
                "route_blocked",
                f"{agent.agent_id} could not find a valid route and will replan next tick.",
                agent_id=agent.agent_id,
                position=agent.position,
                data={"reason": action.reason},
            )
            return {
                "success": False,
                "useful": False,
                "failure_reason": action.reason or "no_valid_direction",
            }

        dx, dy = DIRECTION_VECTORS[action.direction]
        next_position = (agent.position[0] + dx, agent.position[1] + dy)
        occupied_by_other = {
            other.position
            for other in self.agents
            if other.agent_id != agent.agent_id
        }
        blocked_positions = reserved_positions | occupied_by_other

        if self.map.is_walkable(next_position, extra_blocked=blocked_positions):
            agent.position = next_position
            agent.metrics.path_length += 1
            agent.state = (
                "carrying_item"
                if agent.carrying_box_id
                else "moving_to_pickup"
            )
            return {"success": True, "useful": True}

        self.metrics.blocked_move_attempts += 1
        self.metrics.route_replans += 1
        agent.metrics.blocked_move_attempts += 1
        agent.metrics.route_replans += 1
        agent.state = "waiting"
        failure_reason = "move_target_unavailable"
        if next_position in occupied_by_other or next_position in reserved_positions:
            self.metrics.collision_violations += 1
            failure_reason = "target_occupied_or_reserved"
        self.log_event(
            "move_rejected",
            f"{agent.agent_id} was blocked from moving to {next_position} and will replan next tick.",
            agent_id=agent.agent_id,
            position=agent.position,
            data={
                "next_position": next_position,
                "direction": action.direction,
                "failure_reason": failure_reason,
            },
        )
        return {"success": False, "useful": False, "failure_reason": failure_reason}

    def _apply_pick(self, agent: Agent, action: Action) -> Dict[str, object]:
        delivery = self.get_delivery(agent.goal_holder.target_delivery_id)
        if (
            delivery
            and delivery.status in {"waiting", "assigned"}
            and delivery.assigned_agent_id == agent.agent_id
            and agent.carrying_box_id is None
            and agent.position in self.map.adjacent_positions(delivery.pickup_position(self.map))
        ):
            delivery.status = "carrying"
            delivery.carried_by = agent.agent_id
            delivery.picked_tick = self.tick
            agent.carrying_box_id = delivery.box_id
            agent.state = "carrying_item"
            self.metrics.pickup_events += 1
            self.log_event(
                "item_picked",
                f"{agent.agent_id} picked {delivery.box_id}.",
                agent_id=agent.agent_id,
                task_id=delivery.delivery_id,
                item_id=delivery.box_id,
                position=agent.position,
            )
            return {"success": True, "useful": True}

        self.log_event(
            "pickup_rejected",
            f"{agent.agent_id} could not pick up an item and will re-evaluate next tick.",
            agent_id=agent.agent_id,
            position=agent.position,
        )
        agent.state = "waiting"
        return {"success": False, "useful": False, "failure_reason": "pickup_conditions_not_met"}

    def _apply_place(self, agent: Agent, action: Action) -> Dict[str, object]:
        delivery = self.get_delivery(agent.goal_holder.target_delivery_id)
        if (
            delivery
            and delivery.status == "carrying"
            and delivery.carried_by == agent.agent_id
            and agent.carrying_box_id == delivery.box_id
            and agent.position in self.map.adjacent_positions(delivery.dropoff_position(self.map))
        ):
            delivery.status = "delivered"
            delivery.carried_by = None
            delivery.delivered_tick = self.tick
            agent.carrying_box_id = None
            agent.goal_holder.clear()
            agent.state = "idle"
            agent.metrics.completed_tasks += 1
            self.metrics.completed_deliveries += 1
            self.metrics.delivery_events += 1
            self.metrics.total_completion_time += self.tick - delivery.created_tick
            self.log_event(
                "item_delivered",
                f"{agent.agent_id} delivered {delivery.box_id}.",
                agent_id=agent.agent_id,
                task_id=delivery.delivery_id,
                item_id=delivery.box_id,
                position=agent.position,
            )
            return {"success": True, "useful": True}

        self.log_event(
            "place_rejected",
            f"{agent.agent_id} could not place an item and will re-evaluate next tick.",
            agent_id=agent.agent_id,
            position=agent.position,
        )
        agent.state = "waiting"
        return {"success": False, "useful": False, "failure_reason": "place_conditions_not_met"}

    def _record_action(
        self,
        agent: Agent,
        action: Action,
        result: Dict[str, object],
    ) -> None:
        useful = bool(result.get("useful"))
        self.metrics.record_action(action.type)
        agent.metrics.record_action(action.type, useful=useful)
        self.action_log.append({
            "agent_id": agent.agent_id,
            "action": action.type,
            "direction": action.direction,
            "target": action.target,
            "reason": action.reason,
            "success": bool(result.get("success")),
            "failure_reason": result.get("failure_reason", ""),
            "position": agent.position,
            "goal_type": agent.goal_holder.goal_type,
            "goal_delivery_id": agent.goal_holder.target_delivery_id,
            "goal_task_id": agent.goal_holder.target_delivery_id,
        })

    def _communicate_adjacent_agents(self) -> None:
        for index, agent in enumerate(self.agents):
            for other in self.agents[index + 1:]:
                if self.map.manhattan(agent.position, other.position) != 1:
                    continue
                result = agent.communication_module.exchange_with(agent, other)
                if result["owner_updates"] or result["other_updates"]:
                    self.log_event(
                        "agents_communicated",
                        f"{agent.agent_id} exchanged knowledge with {other.agent_id}.",
                        agent_id=agent.agent_id,
                        position=agent.position,
                        data=result,
                    )

    def _task_distance(self, start: Position, delivery: Delivery) -> int:
        pickup_pos = delivery.pickup_position(self.map)
        adjacent = self.map.adjacent_walkable_positions(pickup_pos)
        if not adjacent:
            return 999999
        return min(self.map.manhattan(start, pos) for pos in adjacent)
