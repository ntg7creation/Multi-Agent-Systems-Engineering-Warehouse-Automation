from __future__ import annotations

from models.action import MOVE, PICKUP, PLACE, Action
from models.agent import Agent
from models.item import Item
from models.map import WarehouseMap
from models.memory import KnowledgeEntry, MemoryModule
from models.task import Task
from models.engine import SimulationEngine
from scenarios import build_engine_from_scenario


def make_engine(
    blocked=None,
    agent_positions=None,
    pickup=(1, 1),
    dropoff=(4, 4),
) -> SimulationEngine:
    agent_positions = agent_positions or {"agent_1": (2, 1)}
    warehouse_map = WarehouseMap(
        width=6,
        height=6,
        blocked=set(blocked or []),
        pickups={"pickup_a": pickup},
        dropoffs={"dropoff_a": dropoff},
    )
    agents = [
        Agent(agent_id=agent_id, position=position)
        for agent_id, position in agent_positions.items()
    ]
    tasks = [Task("task_1", "pickup_a", "dropoff_a", "item_1")]
    items = {
        "item_1": Item("item_1", "task_1", "pickup_a", "dropoff_a"),
    }
    return SimulationEngine(
        map=warehouse_map,
        agents=agents,
        tasks=tasks,
        items=items,
        scenario_id="test",
    )


def result_for(engine: SimulationEngine, agent_id: str, action: Action):
    agent = engine.get_agent(agent_id)
    return engine._validate_and_apply_actions([(agent, action)])[agent_id]


def test_move_validity():
    engine = make_engine()
    action = Action(type=MOVE, agent_id="agent_1", direction="right", source=(2, 1))
    result = result_for(engine, "agent_1", action)
    assert result.success is True
    assert engine.get_agent("agent_1").position == (3, 1)


def test_out_of_bounds_rejection():
    engine = make_engine(agent_positions={"agent_1": (0, 0)})
    action = Action(type=MOVE, agent_id="agent_1", direction="left", source=(0, 0))
    result = result_for(engine, "agent_1", action)
    assert result.success is False
    assert result.failure_reason == "out_of_bounds"


def test_blocked_cell_rejection():
    engine = make_engine(blocked={(3, 1)})
    action = Action(type=MOVE, agent_id="agent_1", direction="right", source=(2, 1))
    result = result_for(engine, "agent_1", action)
    assert result.success is False
    assert result.failure_reason == "blocked_cell"


def test_two_agents_attempting_same_target_cell_are_rejected():
    engine = make_engine(agent_positions={"agent_1": (1, 2), "agent_2": (3, 2)})
    actions = [
        (engine.get_agent("agent_1"), Action(type=MOVE, agent_id="agent_1", direction="right", source=(1, 2))),
        (engine.get_agent("agent_2"), Action(type=MOVE, agent_id="agent_2", direction="left", source=(3, 2))),
    ]
    results = engine._validate_and_apply_actions(actions)
    assert results["agent_1"].success is False
    assert results["agent_2"].success is False
    assert results["agent_1"].failure_reason == "target_cell_conflict"
    assert engine.metrics.collision_preventions == 2


def test_swap_collision_is_prevented():
    engine = make_engine(agent_positions={"agent_1": (1, 2), "agent_2": (2, 2)})
    actions = [
        (engine.get_agent("agent_1"), Action(type=MOVE, agent_id="agent_1", direction="right", source=(1, 2))),
        (engine.get_agent("agent_2"), Action(type=MOVE, agent_id="agent_2", direction="left", source=(2, 2))),
    ]
    results = engine._validate_and_apply_actions(actions)
    assert results["agent_1"].failure_reason == "swap_conflict"
    assert results["agent_2"].failure_reason == "swap_conflict"


def test_pickup_only_when_adjacent_and_assigned():
    engine = make_engine(agent_positions={"agent_1": (2, 1)})
    task = engine.get_task("task_1")
    task.status = "assigned"
    task.assigned_agent_id = "agent_1"
    engine.get_agent("agent_1").assign_task(task.serialize(engine.map), tick=0)
    action = Action(type=PICKUP, agent_id="agent_1", task_id="task_1", item_id="item_1", target=(1, 1))
    result = result_for(engine, "agent_1", action)
    assert result.success is True
    assert engine.get_agent("agent_1").carrying_item_id == "item_1"

    bad_engine = make_engine(agent_positions={"agent_1": (4, 1)})
    bad_task = bad_engine.get_task("task_1")
    bad_task.status = "assigned"
    bad_task.assigned_agent_id = "agent_1"
    bad_engine.get_agent("agent_1").assign_task(bad_task.serialize(bad_engine.map), tick=0)
    bad_result = result_for(bad_engine, "agent_1", action)
    assert bad_result.success is False
    assert bad_result.failure_reason == "agent_not_adjacent_to_pickup"


def test_place_only_when_adjacent_and_carrying_correct_item():
    engine = make_engine(agent_positions={"agent_1": (3, 4)})
    task = engine.get_task("task_1")
    task.status = "carrying"
    task.assigned_agent_id = "agent_1"
    task.carried_by = "agent_1"
    engine.items["item_1"].state = "carried"
    engine.items["item_1"].carried_by = "agent_1"
    agent = engine.get_agent("agent_1")
    agent.assign_task(task.serialize(engine.map), tick=0)
    agent.carrying_item_id = "item_1"
    action = Action(type=PLACE, agent_id="agent_1", task_id="task_1", item_id="item_1", target=(4, 4))
    result = result_for(engine, "agent_1", action)
    assert result.success is True
    assert task.status == "delivered"


def test_timestamp_memory_merge_keeps_newest_information():
    older = MemoryModule()
    newer = MemoryModule()
    older.known_cells[(1, 1)] = KnowledgeEntry({"cell_type": "road"}, 1)
    newer.known_cells[(1, 1)] = KnowledgeEntry({"cell_type": "blocked"}, 4)
    assert older.merge_from(newer) == 1
    assert older.known_cells[(1, 1)].value["cell_type"] == "blocked"
    assert newer.merge_from(older) == 0


def test_adjacent_only_communication():
    adjacent = make_engine(agent_positions={"agent_1": (1, 1), "agent_2": (2, 1)})
    for agent in adjacent.agents:
        agent.perceive_and_remember(adjacent)
    adjacent._communicate_adjacent_agents()
    assert adjacent.metrics.communication_events == 1

    separated = make_engine(agent_positions={"agent_1": (1, 1), "agent_2": (4, 4)})
    for agent in separated.agents:
        agent.perceive_and_remember(separated)
    separated._communicate_adjacent_agents()
    assert separated.metrics.communication_events == 0


def test_task_assignment_uses_available_agent():
    engine = make_engine(agent_positions={"far": (5, 5), "near": (2, 1)})
    engine.task_manager.assign_available_tasks(engine)
    task = engine.get_task("task_1")
    assert task.assigned_agent_id == "near"
    assert engine.get_agent("near").current_task_id == "task_1"


def test_replanning_or_wait_on_invalid_next_move():
    engine = build_engine_from_scenario("blocked_route_replanning")
    for _ in range(4):
        engine.step()
    assert engine.metrics.blocked_move_attempts >= 1
    assert any(event["type"] == "MOVE_REJECTED" for event in engine.serialize_events())


def test_metrics_and_logs_update_after_completion():
    engine = build_engine_from_scenario("simple_one_agent_delivery")
    for _ in range(30):
        engine.step()
        if engine.is_complete:
            break
    assert engine.is_complete is True
    assert engine.metrics.completed_deliveries == 1
    assert engine.metrics.pickup_events == 1
    assert engine.metrics.delivery_events == 1
    assert any(event["type"] == "TASK_COMPLETED" for event in engine.serialize_events())
    assert engine.serialize_replay()["frames"]
