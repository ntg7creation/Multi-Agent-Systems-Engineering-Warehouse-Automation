# Warehouse Automation MAS - Implementation Summary

This file summarizes the implementation work completed on top of the existing Warehouse Automation baseline codebase.

## Summary

The project was extended from a lightweight prototype into a working backend multi-agent warehouse simulation with a clearer 2D dashboard. The implementation follows the SRS and SDD direction: the simulation is discrete and tick-based, the backend owns the authoritative warehouse state, agents reason through local modules, and visualization consumes backend state without mutating simulation logic.

The optional 3D visualization was intentionally not implemented.

## Backend Simulation

Implemented and refactored the core simulation around these components:

- `SimulationEngine`
- `WarehouseMap` and `MapCell`
- `Agent`
- `Task`
- `Item`
- `Action` and `ActionResult`
- `TaskManager`
- JSON scenario loader
- Metrics collector
- Structured event log
- Replay log

The simulation engine now runs the main tick cycle:

1. Start tick
2. Agents perceive local environment
3. Agents update timestamped memory
4. Adjacent agents communicate
5. Agents merge communication updates
6. Agents update congestion estimates
7. Available agents receive tasks
8. Agents plan or replan routes
9. Agents select intended actions
10. Engine validates actions
11. Engine applies valid actions
12. Engine rejects invalid or conflicting actions
13. Agents receive action results
14. Logs, replay data, and metrics update

Agents do not directly mutate the authoritative warehouse state. They produce intended actions, and the simulation engine is the only component that validates and applies those actions.

## Agent Architecture

Each warehouse agent now has separated internal modules:

- Perception Module
- Memory Module
- Communication Module
- Path Planning Module
- Congestion Estimation Module
- Decision Module
- Agent Log Module

The selected intended action is stored on the agent before it is sent to the engine. The previous action result is also stored so the dashboard and replay data can compare intended behavior with accepted or rejected behavior.

## Perception And Memory

Agents observe only a local radius around their current position. Perception includes:

- visible free cells
- visible blocked cells
- visible pickup cells
- visible delivery cells
- visible agents
- visible items
- local occupancy
- task information relevant to assigned tasks

Agent memory stores timestamped knowledge:

- map size
- explored cells
- known free and blocked cells
- known pickup and delivery locations
- known item locations
- observed agent positions
- known task information
- congestion estimates
- per-cell waiting, failed movement, and blocked-path history

When perception or communication provides overlapping information, the memory module keeps the newest timestamped information.

## Communication

Agents communicate only when they are adjacent. Communication happens before action selection and does not consume the primary physical action for the tick.

The communication model uses lightweight FIPA-style message performatives:

- `INFORM_MAP_UPDATE`
- `INFORM_CURRENT_TASK`
- `INFORM_CURRENT_TARGET`
- `ACCEPT_UPDATE`
- `REJECT_UPDATE`
- `CONFIRM_UPDATE`

Agents exchange selected local knowledge, including map updates, item and task knowledge, observed agent positions, congestion information, current task, and current target.

## Path Planning

The old seeded BFS behavior was replaced with a local-memory path planner using an A*-style weighted search.

The planner supports targets adjacent to pickup and delivery cells. This matches the SRS/SDD rule that agents pick up and place items from adjacent valid free cells rather than standing directly on the pickup or delivery cell.

Path cost follows the SDD structure:

```text
Cost(P) = alpha * D(P) + beta * C(P) + gamma * F(P) + delta * U(P)
```

Where:

- `D(P)` is estimated travel distance
- `C(P)` is congestion near the path
- `F(P)` is failed-route or blocked-path penalty
- `U(P)` is unexplored or uncertain-area penalty

The path weights are configurable through scenario JSON configuration.

The planner also supports probabilistic route selection among near-optimal candidate paths so agents do not always choose identical deterministic routes.

## Congestion Estimation

Agents maintain local congestion estimates instead of using perfect global congestion knowledge.

Congestion is learned from:

- nearby agents
- waiting events
- failed movement attempts
- blocked paths
- congestion information received from adjacent agents

The implementation follows the SDD formula:

```text
C_t(r) = lambda * C_t-1(r) + w_a * A_t(r) + w_w * W_t(r) + w_f * F_t(r) + w_b * B_t(r) + w_m * M_t(r)
```

Weights are static configuration values selected at scenario load time. They are not learned during the simulation.

For path evaluation, congestion is evaluated over a padded region around the path rather than only exact route cells.

## Action Validation

The simulation engine validates all intended actions against:

- map boundaries
- blocked cells
- non-walkable pickup and delivery service cells
- occupied cells
- two agents attempting the same target cell
- agent swap conflicts
- pickup validity
- placement validity
- task assignment validity
- carrying capacity

Invalid actions are rejected, logged, returned to the agent as failed `ActionResult`, and used to update memory, counters, congestion, and replanning flags.

## Task Allocation

Implemented simple availability-based task allocation.

When multiple agents are available, tasks are assigned to the available agent with the lowest estimated cost to a valid pickup-adjacent cell.

The architecture keeps allocation in `TaskManager`, so future auction-based allocation can be added without rewriting agent reasoning or engine validation.

## Metrics And Analytics

Implemented global and per-agent metrics, including:

- current tick
- total tasks
- completed deliveries
- task completion rate
- throughput
- average task completion time
- wait actions
- move, pickup, and place action counts
- failed or blocked movement attempts
- route replans
- path length
- path inefficiency
- collision prevention statistics
- communication events
- per-agent completed tasks
- per-agent wait and failed movement counters
- per-agent efficiency

## Logging And Replay

Implemented structured event logging for:

- simulation start
- tick start and completion
- task creation
- task assignment
- action selection
- movement success and rejection
- pickup success and rejection
- placement and delivery success
- wait actions
- blocked path detection
- communication events
- task completion
- simulation completion

Replay frames store before/after tick state, intended actions, validation results, conflict results, and metrics snapshots.

## Backend API

The Flask API was extended with:

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
- `GET /api/scenarios`
- `POST /api/scenario/load`
- `POST /api/reset`
- `POST /api/tick`
- `POST /api/step`
- `POST /api/run`
- `POST /api/start`
- `POST /api/pause`
- `POST /api/resume`

Existing autorun endpoints remain available.

## Scenario Configuration

Scenarios are now JSON files under:

```text
warehouse_mas_template/backend/scenario_data/
```

Added scenarios:

- default two-agent warehouse
- simple one-agent delivery
- two agents crossing paths
- blocked route requiring replanning
- congested narrow corridor
- pickup or delivery surrounded by obstacles but still reachable from adjacent cells
- temporary blocked/wait/replan scenario

Each scenario can define:

- grid size
- blocked cells
- pickup locations
- delivery locations
- initial agents
- items
- tasks
- seed
- perception radius
- path weights
- congestion weights
- optional dynamic changes

## 2D Dashboard

The existing React/Vite dashboard was improved and kept strictly 2D.

It now shows:

- warehouse grid
- free cells
- blocked cells
- pickup cells
- delivery cells
- agents
- agents carrying items
- waiting items
- selected agent planned path
- current tick
- active tasks
- completed deliveries
- metrics panel
- event log panel

Controls include:

- start
- pause
- resume
- step once
- run 10 ticks
- reset
- speed control
- scenario selection

Agent inspection includes:

- agent id
- mode/state
- current task
- carried item
- current target
- intended action
- previous action result
- planned path length
- waiting counter
- failed movement counter
- memory summary
- per-agent metrics

Task and item inspection were also added.

## Tests

Added backend tests for:

- valid movement
- out-of-bounds rejection
- blocked-cell rejection
- collision prevention
- same-target conflict
- swap conflict
- pickup only when adjacent and assigned
- placement only when adjacent and carrying the correct item
- timestamp memory merge
- adjacent-only communication
- task assignment
- replanning or waiting after invalid movement
- metrics and log updates

Test file:

```text
warehouse_mas_template/backend/tests/test_simulation_core.py
```

## Verification Performed

The following verification was performed:

```powershell
C:\Users\natai\anaconda3\python.exe -m compileall backend
```

Passed.

Manual execution of all pytest-style test functions passed because the available Anaconda environment does not currently have `pytest` installed.

All JSON scenarios were smoke-tested and completed within 120 ticks:

- `adjacent_access_obstacles`
- `blocked_route_replanning`
- `congested_narrow_corridor`
- `default`
- `simple_one_agent_delivery`
- `temporary_blocked_wait_replan`
- `two_agents_crossing_paths`

The frontend production build was also verified:

```powershell
npm.cmd run build
```

Passed.

The Vite dev server was started and returned HTTP 200.

## How To Run

Backend:

```powershell
cd warehouse_mas_template\backend
pip install -r requirements.txt
python app.py
```

Frontend:

```powershell
cd warehouse_mas_template\frontend
npm install
npm run dev
```

Tests:

```powershell
cd warehouse_mas_template\backend
python -m pytest
```

## Known Limitations And Future Work

The following parts were intentionally left for future work:

- full auction-based allocation
- advanced cooperative pathfinding and reservation-table logic
- optional 3D visualization
- reinforcement learning
- learned congestion weights
- deeper experiment export and comparison tooling

The current implementation is a Python-first simulation engine and is structured so a future Repast4Py adapter can be added if required by the course.
