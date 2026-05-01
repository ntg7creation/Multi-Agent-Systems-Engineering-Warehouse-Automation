from __future__ import annotations

from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

from scenarios import list_scenarios
from services.simulation_service import SimulationService

app = Flask(__name__)
CORS(app)

simulation = SimulationService()


def payload() -> dict:
    return request.get_json(silent=True) or {}


def int_payload(name: str, default: int, minimum: int, maximum: int) -> int:
    value = payload().get(name, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def optional_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "warehouse-mas-backend"})


@app.get("/api/state")
def get_state():
    return jsonify(simulation.state())


@app.get("/api/board")
def get_board():
    return jsonify(simulation.board())


@app.get("/api/agents")
def get_agents():
    return jsonify(simulation.agents())


@app.get("/api/agents/<agent_id>")
def get_agent(agent_id: str):
    agent = simulation.agent(agent_id)
    if agent is None:
        return jsonify({"error": f"Unknown agent '{agent_id}'."}), 404
    return jsonify(agent)


@app.get("/api/tasks")
def get_tasks():
    return jsonify(simulation.tasks())


@app.get("/api/tasks/<task_id>")
def get_task(task_id: str):
    task = simulation.task(task_id)
    if task is None:
        return jsonify({"error": f"Unknown task '{task_id}'."}), 404
    return jsonify(task)


@app.get("/api/items")
def get_items():
    return jsonify(simulation.items())


@app.get("/api/metrics")
def get_metrics():
    return jsonify(simulation.metrics())


@app.get("/api/events")
def get_events():
    limit = optional_int(request.args.get("limit"))
    return jsonify(simulation.events(limit=limit))


@app.get("/api/scenarios")
def get_scenarios():
    return jsonify(list_scenarios())


@app.post("/api/scenario/load")
def load_scenario():
    data = payload()
    scenario_id = str(data.get("scenario_id") or "default")
    seed = optional_int(data.get("seed"))
    return jsonify(simulation.load_scenario(scenario_id=scenario_id, seed=seed))


@app.post("/api/reset")
def reset():
    data = payload()
    scenario_id = str(data.get("scenario_id") or "default")
    seed = optional_int(data.get("seed"))
    return jsonify(simulation.reset(scenario_id=scenario_id, seed=seed))


@app.post("/api/tick")
@app.post("/api/step")
def step():
    steps = int_payload("steps", default=1, minimum=1, maximum=1000)
    return jsonify(simulation.step(steps))


@app.post("/api/run")
def run():
    steps = int_payload("steps", default=10, minimum=1, maximum=1000)
    return jsonify(simulation.step(steps))


@app.get("/api/autorun")
def autorun_status():
    return jsonify(simulation.autorun_status())


@app.post("/api/autorun/start")
def autorun_start():
    data = payload()
    delay_ms = int_payload("delay_ms", default=600, minimum=50, maximum=10000)
    max_ticks = optional_int(data.get("max_ticks"))
    return jsonify(simulation.start_autorun(delay_ms=delay_ms, max_ticks=max_ticks))


@app.post("/api/autorun/stop")
def autorun_stop():
    return jsonify(simulation.stop_autorun())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
