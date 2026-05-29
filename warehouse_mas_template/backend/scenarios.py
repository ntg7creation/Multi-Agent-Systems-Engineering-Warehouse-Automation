from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from models.agent import Agent
from models.congestion import CongestionConfig, CongestionEstimationModule
from models.item import Item
from models.map import WarehouseMap
from models.movement import PathPlanningConfig, PathPlanningModule
from models.perception import PerceptionModule
from models.scenario import ScenarioConfig, parse_scenario
from models.task import Task
from models.engine import SimulationEngine


SCENARIO_DIR = Path(__file__).parent / "scenario_data"


def load_scenario_configs() -> Dict[str, ScenarioConfig]:
    scenarios: Dict[str, ScenarioConfig] = {}
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            scenario = parse_scenario(json.load(handle))
        scenarios[scenario.scenario_id] = scenario
    if not scenarios:
        raise RuntimeError(f"No scenario JSON files found in {SCENARIO_DIR}.")
    return scenarios


def build_engine_from_scenario(
    scenario_id: str = "default",
    seed: Optional[int] = None,
) -> SimulationEngine:
    scenarios = load_scenario_configs()
    scenario = scenarios.get(scenario_id, scenarios["default"])
    active_seed = scenario.default_seed if seed is None else int(seed)

    warehouse_map = WarehouseMap(
        width=scenario.width,
        height=scenario.height,
        blocked=set(scenario.blocked),
        pickups=dict(scenario.pickups),
        dropoffs=dict(scenario.dropoffs),
    )

    path_config = PathPlanningConfig(
        distance_weight=float(scenario.path_weights.get("alpha_distance", 1.0)),
        congestion_weight=float(scenario.path_weights.get("beta_congestion", 2.0)),
        failed_route_weight=float(scenario.path_weights.get("gamma_failed_route", 1.5)),
        uncertainty_weight=float(scenario.path_weights.get("delta_uncertainty", 0.3)),
        occupied_penalty=float(scenario.path_weights.get("occupied_penalty", 4.0)),
        max_candidates=int(scenario.path_weights.get("max_candidates", 6)),
        near_optimal_margin=float(scenario.path_weights.get("near_optimal_margin", 0.35)),
    )
    congestion_config = CongestionConfig(
        decay=float(scenario.congestion.get("decay", 0.85)),
        nearby_agent_weight=float(scenario.congestion.get("nearby_agent_weight", 1.2)),
        waiting_weight=float(scenario.congestion.get("waiting_weight", 0.7)),
        failed_move_weight=float(scenario.congestion.get("failed_move_weight", 1.0)),
        blocked_path_weight=float(scenario.congestion.get("blocked_path_weight", 0.9)),
        communicated_weight=float(scenario.congestion.get("communicated_weight", 0.5)),
        path_padding=int(scenario.congestion.get("path_padding", 1)),
    )

    agents = [
        Agent(
            agent_id=agent_start.agent_id,
            position=agent_start.position,
            perception_module=PerceptionModule(radius=scenario.perception_radius),
            path_planning_module=PathPlanningModule(config=path_config),
            congestion_module=CongestionEstimationModule(config=congestion_config),
        )
        for agent_start in scenario.agents
    ]

    tasks = [
        Task(
            task_id=task_start.task_id,
            pickup_id=task_start.pickup_id,
            dropoff_id=task_start.dropoff_id,
            item_id=task_start.item_id,
        )
        for task_start in scenario.tasks
    ]

    items = {
        item_start.item_id: Item(
            item_id=item_start.item_id,
            task_id=item_start.task_id,
            pickup_id=item_start.pickup_id,
            dropoff_id=item_start.dropoff_id,
        )
        for item_start in scenario.items
    }

    return SimulationEngine(
        map=warehouse_map,
        agents=agents,
        tasks=tasks,
        items=items,
        seed=active_seed,
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        allocation_strategy=scenario.allocation_strategy,
        routing_strategy=scenario.routing_strategy,
        dynamic_changes=scenario.dynamic_changes,
    )


def list_scenarios() -> Dict[str, object]:
    scenarios = load_scenario_configs()
    return {
        "scenarios": [
            scenario.serialize_summary()
            for scenario in scenarios.values()
        ],
        "default_scenario_id": "default",
    }
