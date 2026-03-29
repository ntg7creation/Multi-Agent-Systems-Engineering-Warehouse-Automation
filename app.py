from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import threading
import time

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO


Position = Tuple[int, int]


@dataclass
class Item:
    item_id: str
    pickup: Position
    target: Position
    status: str = "waiting"  # waiting | carrying | delivered
    carried_by: Optional[str] = None


@dataclass
class Agent:
    agent_id: str
    x: int
    y: int
    direction: str = "right"
    carrying: Optional[str] = None
    capacity: int = 1

    def position(self) -> Position:
        return (self.x, self.y)

    def forward_position(self) -> Position:
        offsets = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
        }
        dx, dy = offsets[self.direction]
        return (self.x + dx, self.y + dy)

    def choose_action(self, world: "WarehouseWorld") -> Dict[str, Any]:
        """
        Placeholder agent logic.
        Current behavior:
        1. Pick up if standing on an available item.
        2. Place if standing on the target of the carried item.
        3. Otherwise, move one square forward if possible.
        4. Otherwise, wait.

        Later, this method can be replaced with real MAS logic
        (task allocation, pathfinding, auctions, learning, etc.).
        """
        current_pos = self.position()

        if self.carrying is None:
            item = world.waiting_item_at(current_pos)
            if item is not None:
                return {"type": "pickup", "item_id": item.item_id}
        else:
            carried_item = world.items_by_id[self.carrying]
            if current_pos == carried_item.target:
                return {"type": "place", "item_id": carried_item.item_id}

        next_pos = self.forward_position()
        if world.can_agent_enter(self.agent_id, next_pos):
            return {"type": "move", "to": next_pos}

        return {"type": "wait"}


@dataclass
class WarehouseWorld:
    width: int
    height: int
    blocked: List[Position] = field(default_factory=list)
    pickups: List[Position] = field(default_factory=list)
    dropoffs: List[Position] = field(default_factory=list)
    agents: List[Agent] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    turn: int = 0

    def __post_init__(self) -> None:
        self.items_by_id: Dict[str, Item] = {item.item_id: item for item in self.items}

    def in_bounds(self, pos: Position) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, pos: Position) -> bool:
        return pos in self.blocked

    def agent_at(self, pos: Position) -> Optional[Agent]:
        for agent in self.agents:
            if agent.position() == pos:
                return agent
        return None

    def can_agent_enter(self, agent_id: str, pos: Position) -> bool:
        if not self.in_bounds(pos):
            return False
        if self.is_blocked(pos):
            return False

        occupant = self.agent_at(pos)
        if occupant is not None and occupant.agent_id != agent_id:
            return False

        return True

    def waiting_item_at(self, pos: Position) -> Optional[Item]:
        for item in self.items:
            if item.pickup == pos and item.status == "waiting":
                return item
        return None

    def execute_action(self, agent: Agent, action: Dict[str, Any]) -> None:
        action_type = action["type"]

        if action_type == "move":
            new_x, new_y = action["to"]
            if self.can_agent_enter(agent.agent_id, (new_x, new_y)):
                agent.x = new_x
                agent.y = new_y
            return

        if action_type == "pickup":
            if agent.carrying is not None:
                return
            item = self.items_by_id.get(action["item_id"])
            if item is None:
                return
            if item.status != "waiting":
                return
            if item.pickup != agent.position():
                return

            item.status = "carrying"
            item.carried_by = agent.agent_id
            agent.carrying = item.item_id
            return

        if action_type == "place":
            if agent.carrying is None:
                return
            item = self.items_by_id.get(action["item_id"])
            if item is None:
                return
            if item.item_id != agent.carrying:
                return
            if item.target != agent.position():
                return

            item.status = "delivered"
            item.carried_by = None
            agent.carrying = None
            return

        # wait or unknown action => do nothing

    def step(self) -> None:
        planned_actions: List[Tuple[Agent, Dict[str, Any]]] = []

        for agent in self.agents:
            action = agent.choose_action(self)
            planned_actions.append((agent, action))

        for agent, action in planned_actions:
            self.execute_action(agent, action)

        self.turn += 1

    def state(self) -> Dict[str, Any]:
        cells = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                pos = (x, y)
                if pos in self.blocked:
                    row.append("blocked")
                elif pos in self.pickups:
                    row.append("pickup")
                elif pos in self.dropoffs:
                    row.append("dropoff")
                else:
                    row.append("road")
            cells.append(row)

        rendered_items = []
        for item in self.items:
            item_pos = item.pickup
            if item.status == "carrying" and item.carried_by:
                carrier = next((a for a in self.agents if a.agent_id == item.carried_by), None)
                if carrier is not None:
                    item_pos = carrier.position()
            elif item.status == "delivered":
                item_pos = item.target

            rendered_items.append(
                {
                    "item_id": item.item_id,
                    "pickup": list(item.pickup),
                    "target": list(item.target),
                    "position": list(item_pos),
                    "status": item.status,
                    "carried_by": item.carried_by,
                }
            )

        return {
            "turn": self.turn,
            "grid": {
                "width": self.width,
                "height": self.height,
                "cells": cells,
            },
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "x": agent.x,
                    "y": agent.y,
                    "direction": agent.direction,
                    "carrying": agent.carrying,
                }
                for agent in self.agents
            ],
            "items": rendered_items,
        }


def create_demo_world() -> WarehouseWorld:
    return WarehouseWorld(
        width=8,
        height=6,
        blocked=[(3, 1), (3, 2), (3, 3), (5, 4)],
        pickups=[(1, 1), (1, 4)],
        dropoffs=[(6, 1), (6, 4)],
        agents=[
            Agent(agent_id="A1", x=0, y=1, direction="right"),
            Agent(agent_id="A2", x=0, y=4, direction="right"),
        ],
        items=[
            Item(item_id="I1", pickup=(1, 1), target=(6, 1)),
            Item(item_id="I2", pickup=(1, 4), target=(6, 4)),
        ],
    )


app = Flask(__name__)
app.config["SECRET_KEY"] = "warehouse-template-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
world = create_demo_world()
_world_lock = threading.Lock()
_background_started = False


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    with _world_lock:
        return jsonify(world.state())


@app.route("/api/step")
def manual_step():
    with _world_lock:
        world.step()
        state = world.state()
    socketio.emit("state", state)
    return jsonify(state)


@socketio.on("connect")
def handle_connect() -> None:
    global _background_started
    with _world_lock:
        socketio.emit("state", world.state())

    if not _background_started:
        _background_started = True
        socketio.start_background_task(simulation_loop)


def simulation_loop() -> None:
    while True:
        time.sleep(1.0)
        with _world_lock:
            world.step()
            state = world.state()
        socketio.emit("state", state)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
