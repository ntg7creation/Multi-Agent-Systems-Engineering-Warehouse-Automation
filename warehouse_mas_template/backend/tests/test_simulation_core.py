from __future__ import annotations

from models.action import MOVE, PICKUP, PLACE, Action
from models.agent import Agent
from models.item import Item
from models.map import WarehouseMap
from models.memory import KnowledgeEntry, MemoryModule
from models.task import Task
from models.engine import SimulationEngine
from scenarios import build_engine_from_scenario
from strategy_config import config_profile_overrides


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


def test_congestion_decays_without_replaying_old_history_events():
    engine = make_engine()
    agent = engine.get_agent("agent_1")
    congested_cell = (2, 1)

    agent.memory_module.initialize_map(engine.map.width, engine.map.height)
    agent.memory_module.record_wait(congested_cell, tick=1)
    agent.update_congestion(tick=1)
    first_score = agent.memory_module.congestion_score(congested_cell)

    agent.update_congestion(tick=2)
    second_score = agent.memory_module.congestion_score(congested_cell)
    agent.update_congestion(tick=3)
    third_score = agent.memory_module.congestion_score(congested_cell)

    assert first_score > 0
    assert first_score > second_score > third_score


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
    for _ in range(30):
        engine.step()
        if engine.is_complete:
            break
    assert engine.is_complete is True
    assert engine.metrics.route_replans >= 1


def test_scenario_config_overrides_are_applied_to_engine_and_agents():
    engine = build_engine_from_scenario(
        "four_agents_adjacent_access_cluster",
        config_overrides=config_profile_overrides("baseline"),
    )
    agent = engine.agents[0]

    assert engine.serialize_scenario_info()["config"]["path_weights"]["beta_congestion"] == 0.0
    assert agent.path_planning_module.config.distance_weight == 1.0
    assert agent.path_planning_module.config.congestion_weight == 0.0
    assert agent.path_planning_module.config.failed_route_weight == 0.0
    assert agent.path_planning_module.config.uncertainty_weight == 0.0
    assert agent.path_planning_module.config.near_optimal_margin == 0.0
    assert agent.path_planning_module.config.congestion_region_padding == 0
    assert agent.congestion_module.config.decay == 0.0
    assert agent.congestion_module.config.path_padding == 0


def test_agent_replans_when_known_wall_invalidates_planned_path_before_rejection():
    engine = make_engine(
        blocked={(3, 1)},
        agent_positions={"agent_1": (2, 1)},
        pickup=(1, 1),
        dropoff=(5, 1),
    )
    task = engine.get_task("task_1")
    task.status = "carrying"
    task.assigned_agent_id = "agent_1"
    task.carried_by = "agent_1"
    agent = engine.get_agent("agent_1")
    agent.assign_task(task.serialize(engine.map), tick=0)
    agent.carrying_item_id = "item_1"
    agent.planned_path = [(2, 1), (3, 1), (4, 1)]

    agent.perceive_and_remember(engine)
    action = agent.select_intended_action(engine.tick, engine.rng)

    assert action.type == MOVE
    assert action.target != (3, 1)
    assert (3, 1) not in agent.planned_path


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


def test_step_after_completion_does_not_advance_tick_or_congestion():
    engine = build_engine_from_scenario("simple_one_agent_delivery")
    for _ in range(30):
        engine.step()
        if engine.is_complete:
            break

    assert engine.is_complete is True
    completed_tick = engine.tick
    replay_frame_count = len(engine.serialize_replay()["frames"])
    congestion_snapshots = {
        agent.agent_id: agent.memory_module.serialize().get("congestion", [])
        for agent in engine.agents
    }

    engine.step()
    engine.run_steps(10)

    assert engine.tick == completed_tick
    assert engine.metrics.total_steps == completed_tick
    assert len(engine.serialize_replay()["frames"]) == replay_frame_count
    assert {
        agent.agent_id: agent.memory_module.serialize().get("congestion", [])
        for agent in engine.agents
    } == congestion_snapshots


def test_analytics_summary_and_exports_are_available():
    engine = build_engine_from_scenario("simple_one_agent_delivery")
    for _ in range(30):
        engine.step()
        if engine.is_complete:
            break

    summary = engine.analytics.summary(engine)
    assert summary["run_id"] == engine.run_id
    assert summary["system"]["completed_deliveries"] == 1
    assert "social_welfare" in summary["system"]
    assert next(iter(summary["agents"].values()))["utility_score"] is not None
    assert engine.analytics.action_flow_replay_log
    assert any(event["type"] == "SIMULATION_STARTED" for event in engine.analytics.global_event_log)

    exported = engine.analytics.export_json(engine)
    assert exported["summary"]["run_id"] == engine.run_id
    assert exported["events"]
    assert "agent_decisions" in exported

    csv_export = engine.analytics.export_csv(engine)
    assert "# events" in csv_export
    assert "# agent_metrics" in csv_export


def test_symmetric_single_slot_crossing_resolves_with_yielding():
    engine = build_engine_from_scenario("two_agents_single_slot_crossing")
    assert engine.agents[0].position == (2, 3)
    assert engine.agents[1].position == (8, 3)
    for _ in range(120):
        engine.step()
        if engine.is_complete:
            break
    assert engine.is_complete is True
    assert engine.metrics.completed_deliveries == 2
    assert any(
        action["reason"] == "yielding_to_higher_priority_agent"
        for frame in engine.serialize_replay()["frames"]
        for action in frame["intended_actions"]
    )
