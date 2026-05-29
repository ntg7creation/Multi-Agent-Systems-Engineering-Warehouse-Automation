# Warehouse MAS Project

This repository contains three cooperating projects for the warehouse automation MAS:

- `backend/`: Python Flask simulation server. This is the source of truth for warehouse state, agent logic, tasks, routing, events, metrics, seeding, and scenario control.
- `frontend/`: existing lightweight React/Vite 2D board viewer for debugging and fast simulation control.
- `viewer_three/`: existing React/Vite/Three.js viewer skeleton. The actual 3D warehouse scene is intentionally left for future work.

The academic behavior is defined in the PDFs and SRS. The technical build direction is summarized in `../TECHNICAL_BUILD_GUIDE.md`.

## Backend

The backend owns all simulation logic. JavaScript clients should not duplicate MAS behavior.

Current backend modules:

```text
backend/
  app.py
  scenarios.py
  requirements.txt
  models/
    action.py
    agent.py
    communication.py
    task.py
    item.py
    delivery.py
    engine.py
    event_log.py
    goal.py
    map.py
    memory.py
    metrics.py
    movement.py
    congestion.py
    decision.py
    task_manager.py
    perception.py
    scenario.py
  services/
    simulation_service.py
  scenario_data/
    *.json
  tests/
```

The current implementation is still a Python-first simulation engine, but the intended MAS framework direction is Repast/Repast4Py. The code is split so that the engine can later be adapted to Repast without changing the frontend API.

### Run Backend With Conda

```powershell
conda activate MAS
cd backend
pip install -r requirements.txt
python app.py
```

If Repast4Py is needed in the `MAS` environment:

```powershell
conda activate MAS
conda install -c conda-forge repast4py
```

The Flask server runs on `http://localhost:5000`.

## Backend API

Core state:

- `GET /api/health`
- `GET /api/state`
- `GET /api/board`
- `GET /api/agents`
- `GET /api/agents/<agent_id>`
- `GET /api/tasks`
- `GET /api/tasks/<task_id>`
- `GET /api/items`
- `GET /api/items/<item_id>`
- `GET /api/metrics`
- `GET /api/events?limit=25`
- `GET /api/replay?limit=25`

Simulation control:

- `POST /api/start` with `{ "delay_ms": 600, "max_ticks": 100 }`
- `POST /api/pause`
- `POST /api/resume` with `{ "delay_ms": 600, "max_ticks": 100 }`
- `POST /api/tick` with `{ "steps": 1 }`
- `POST /api/step` with `{ "steps": 1 }`
- `POST /api/run` with `{ "steps": 10 }`
- `POST /api/reset` with `{ "scenario_id": "default", "seed": 42 }`

Scenarios:

- `GET /api/scenarios`
- `POST /api/scenario/load` with `{ "scenario_id": "default", "seed": 42 }`

Server-side autorun:

- `GET /api/autorun`
- `POST /api/autorun/start` with `{ "delay_ms": 600, "max_ticks": 100 }`
- `POST /api/autorun/stop`

## Seeding

Every simulation run has a seed. Resetting or loading a scenario can provide a seed:

```json
{
  "scenario_id": "default",
  "seed": 42
}
```

The engine uses the seed for route tie-breaking now and can use the same seeded random generator for future stochastic decisions, probabilistic route choice, auctions, and dynamic events.

## Current 2D Viewer

```powershell
cd frontend
npm install
npm run dev
```

The 2D viewer runs on `http://localhost:5173`.

It supports:

- scenario and seed reset
- tick once
- run multiple ticks
- server-side start/pause/resume
- agent selection
- selected-agent planned path highlighting
- task display
- item inspection
- event display
- global and per-agent metrics

## Three.js Viewer Skeleton

```powershell
cd viewer_three
npm install
npm run dev
```

The Three.js viewer skeleton runs on `http://localhost:5174`.

It currently contains:

- API client
- Zustand state store
- control panel
- inspector panel
- placeholder scene
- reserved `WarehouseScene.jsx` for the future React Three Fiber implementation

The real 3D scene should later render the same backend state used by the 2D viewer.

## Implemented Simulation Behavior

- Discrete tick cycle with perception, memory update, adjacent communication, congestion update, task assignment, planning, engine validation, action application, metrics, and replay logging.
- Agents perform one primary physical action per tick: move, pickup, place, or wait.
- Communication is modeled as a free adjacent-agent exchange using lightweight FIPA-style messages.
- Agents maintain timestamped local memory for cells, pickups, deliveries, items, tasks, observed agents, congestion, and per-cell history.
- Agents pick and place from adjacent cells, matching the SRS.
- Pickup and delivery cells are treated as service cells, not normal walking cells.
- Movement validation rejects out-of-bounds moves, blocked cells, service cells, occupied cells, same-target conflicts, and swaps.
- Agents plan from local memory with A*-style weighted path search using distance, congestion, failure history, and uncertainty costs.
- Route selection can choose probabilistically among near-optimal candidate paths.
- Task allocation assigns waiting tasks to available agents using nearest valid pickup-adjacent access cost.
- The backend records actions, events, and metrics.
- Replay frames capture before/after tick state, intended actions, validation results, and metrics.
- Scenarios are JSON files under `backend/scenario_data/`.

## Next Technical Steps

1. Wire the MAS engine to Repast4Py or create a Repast adapter layer if the course requires it.
2. Add full auction-based allocation.
3. Add advanced cooperative pathfinding / reservation-table planning.
4. Add richer dynamic task generation and experiment exports.
5. Build the optional 3D visualization.
6. Explore reinforcement learning or learned congestion weights.
