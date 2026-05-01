from __future__ import annotations

from typing import Dict, Optional

from models.agent import Agent
from models.delivery import Delivery
from models.engine import SimulationEngine
from models.map import WarehouseMap
from models.perception import PerceptionModule
from models.scenario import AgentStart, DeliveryStart, ScenarioConfig


SCENARIOS: Dict[str, ScenarioConfig] = {
    "default": ScenarioConfig(
        scenario_id="default",
        name="Default Two-Agent Warehouse",
        description="Small baseline scenario with two agents and two delivery tasks.",
        width=12,
        height=8,
        blocked={
            (3, 1), (3, 2), (3, 3), (3, 5), (3, 6),
            (7, 1), (7, 2), (7, 4), (7, 5), (7, 6),
        },
        pickups={
            "pickup_a": (1, 1),
            "pickup_b": (1, 6),
        },
        dropoffs={
            "dropoff_a": (10, 1),
            "dropoff_b": (10, 6),
        },
        agents=[
            AgentStart(agent_id="agent_1", position=(5, 1)),
            AgentStart(agent_id="agent_2", position=(5, 6)),
        ],
        deliveries=[
            DeliveryStart(
                delivery_id="delivery_1",
                pickup_id="pickup_a",
                dropoff_id="dropoff_a",
                box_id="box_1",
            ),
            DeliveryStart(
                delivery_id="delivery_2",
                pickup_id="pickup_b",
                dropoff_id="dropoff_b",
                box_id="box_2",
            ),
        ],
        default_seed=42,
        perception_radius=3,
    ),
    "single_agent": ScenarioConfig(
        scenario_id="single_agent",
        name="Single-Agent Baseline",
        description="One agent completes one delivery in an open warehouse.",
        width=10,
        height=6,
        blocked={(4, 2), (4, 3)},
        pickups={"pickup_a": (1, 1)},
        dropoffs={"dropoff_a": (8, 4)},
        agents=[AgentStart(agent_id="agent_1", position=(2, 1))],
        deliveries=[
            DeliveryStart(
                delivery_id="delivery_1",
                pickup_id="pickup_a",
                dropoff_id="dropoff_a",
                box_id="box_1",
            ),
        ],
        default_seed=7,
        perception_radius=3,
    ),
    "congestion": ScenarioConfig(
        scenario_id="congestion",
        name="Congestion And Conflict",
        description="Three agents share tight routes and must wait or replan.",
        width=14,
        height=9,
        blocked={
            (5, 1), (5, 2), (5, 3), (5, 5), (5, 6), (5, 7),
            (8, 1), (8, 2), (8, 3), (8, 5), (8, 6), (8, 7),
        },
        pickups={
            "pickup_a": (1, 1),
            "pickup_b": (1, 7),
            "pickup_c": (2, 4),
        },
        dropoffs={
            "dropoff_a": (12, 1),
            "dropoff_b": (12, 7),
            "dropoff_c": (11, 4),
        },
        agents=[
            AgentStart(agent_id="agent_1", position=(6, 1)),
            AgentStart(agent_id="agent_2", position=(6, 7)),
            AgentStart(agent_id="agent_3", position=(7, 4)),
        ],
        deliveries=[
            DeliveryStart("delivery_1", "pickup_a", "dropoff_a", "box_1"),
            DeliveryStart("delivery_2", "pickup_b", "dropoff_b", "box_2"),
            DeliveryStart("delivery_3", "pickup_c", "dropoff_c", "box_3"),
        ],
        default_seed=11,
        perception_radius=4,
    ),
}


def build_engine_from_scenario(
    scenario_id: str = "default",
    seed: Optional[int] = None,
) -> SimulationEngine:
    scenario = SCENARIOS.get(scenario_id, SCENARIOS["default"])
    active_seed = scenario.default_seed if seed is None else int(seed)

    warehouse_map = WarehouseMap(
        width=scenario.width,
        height=scenario.height,
        blocked=set(scenario.blocked),
        pickups=dict(scenario.pickups),
        dropoffs=dict(scenario.dropoffs),
    )

    agents = [
        Agent(
            agent_id=agent_start.agent_id,
            position=agent_start.position,
            perception_module=PerceptionModule(radius=scenario.perception_radius),
        )
        for agent_start in scenario.agents
    ]

    deliveries = [
        Delivery(
            delivery_id=delivery_start.delivery_id,
            pickup_id=delivery_start.pickup_id,
            dropoff_id=delivery_start.dropoff_id,
            box_id=delivery_start.box_id,
        )
        for delivery_start in scenario.deliveries
    ]

    return SimulationEngine(
        map=warehouse_map,
        agents=agents,
        deliveries=deliveries,
        seed=active_seed,
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        allocation_strategy=scenario.allocation_strategy,
        routing_strategy=scenario.routing_strategy,
    )


def list_scenarios() -> Dict[str, object]:
    return {
        "scenarios": [
            scenario.serialize_summary()
            for scenario in SCENARIOS.values()
        ],
        "default_scenario_id": "default",
    }
