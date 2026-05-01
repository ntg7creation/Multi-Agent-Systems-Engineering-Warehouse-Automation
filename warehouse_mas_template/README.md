# Warehouse MAS Project

This repository contains three cooperating projects for the warehouse automation MAS:

- `backend/`: Python Flask simulation server. This is the source of truth for warehouse state, agent logic, tasks, routing, events, metrics, seeding, and scenario control.
- `frontend/`: existing lightweight React/Vite 2D board viewer for debugging and fast simulation control.
- `viewer_three/`: new React/Vite/Three.js viewer skeleton. The architecture is ready, but the actual 3D warehouse scene is intentionally not implemented yet.

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
    delivery.py
    engine.py
    goal.py
    map.py
    memory.py
    metrics.py
    movement.py
    perception.py
    scenario.py
  services/
    simulation_service.py
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
- `GET /api/metrics`
- `GET /api/events?limit=25`

Simulation control:

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
- server-side autorun start/stop
- agent selection
- task display
- event display
- basic global metrics

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

- Discrete ticks.
- Agents perform one primary action per tick.
- Communication is modeled as a free adjacent-agent exchange.
- Agents maintain timestamped memory summaries.
- Agents pick and place from adjacent cells, matching the SRS.
- Pickup and delivery cells are treated as service cells, not normal walking cells.
- Movement avoids blocked cells, service cells, occupied cells, and reserved cells.
- Agents plan from the start-of-tick snapshot. If another action makes the planned move, pickup, or placement invalid during execution, the action fails and the agent replans on the next tick.
- The backend records actions, events, and metrics.
- Scenarios can be selected and seeded.

## Next Technical Steps

1. Wire the MAS engine to Repast4Py or create a Repast adapter layer.
2. Add richer task queues and dynamic task generation.
3. Expand route scoring beyond seeded BFS.
4. Add auction-based task allocation.
5. Implement validation scenarios from the SRS.
6. Build the actual React Three Fiber warehouse scene.
