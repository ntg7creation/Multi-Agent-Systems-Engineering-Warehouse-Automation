# Warehouse MAS Technical Build Guide

This file describes how we intend to build the warehouse automation project technically. The PDFs and SRS define the academic requirements and expected behavior; this file defines the implementation shape, project structure, libraries, data contracts, and engineering direction.

## Project Goal

Build a simulation-based Multi-Agent System (MAS) for warehouse automation.

The system will simulate autonomous warehouse transport agents that operate on a grid, receive pickup-and-delivery tasks, navigate around obstacles and other agents, communicate locally, update internal knowledge, and produce measurable performance data.

The project should support two kinds of visualization:

1. A simple existing 2D React grid viewer for fast debugging.
2. A new richer Three.js-based viewer for a more visual, interactive warehouse simulation.

## Repository Structure

The root folder contains the assignment PDFs, extracted reference text, and the implementation folder:

```text
warehouse/
  TECHNICAL_BUILD_GUIDE.md
  Assignment PDFs...
  warehouse_mas_template/
    backend/
    frontend/
    viewer_three/
```

`warehouse_mas_template/backend/` is the Python simulation server.

`warehouse_mas_template/frontend/` is the current lightweight React/Vite 2D viewer.

`warehouse_mas_template/viewer_three/` will be a new independent Vite project using React and Three.js. It should consume the same backend API as the simple frontend, but render the warehouse with a richer 3D/interactive view.

## Backend

The backend is the source of truth for the simulation.

Technology:

- Python
- Flask
- flask-cors
- Repast / Repast4Py for the MAS simulation layer
- dataclasses or Pydantic models for structured state
- pytest for backend tests

Current backend routes should remain:

- `GET /api/state`
- `POST /api/step`
- `POST /api/reset`
- `GET /api/health`

Additional backend routes we likely want:

- `GET /api/scenarios`
- `POST /api/scenario/load`
- `GET /api/metrics`
- `GET /api/events`
- `GET /api/replay`
- `POST /api/config`

The backend should eventually support deterministic scenarios with seeds, so the same simulation can be replayed and compared.

## MAS / Simulation Libraries

The MAS implementation should use Repast as the primary simulation framework.

Preferred core choice:

- `Repast`: primary agent-based simulation framework for the MAS layer.
- `Repast4Py`: preferred if we keep the simulation implementation in Python.

Reason for choosing Repast:

- It is aimed at advanced researchers and engineers.
- It supports more scalable simulations than beginner-focused frameworks.
- It is appropriate for analytical and visual agent-based modeling.
- It has stronger long-term fit for larger warehouse scenarios and experiment comparison.

Supporting Python libraries:

- `NetworkX`: graph/pathfinding support, shortest paths, graph analysis, route comparison, and path inefficiency metrics.
- `NumPy`: numerical calculations for metrics, probability weights, and scenario analysis.
- `Pydantic`: typed API/state schemas between backend and frontend.
- `pytest`: regression tests for movement, tasks, collisions, metrics, and scenarios.
- `pandas`: useful for metrics export, experiment comparison, and tabular reports.

Alternative libraries:

- `Mesa`: useful as a simpler Python MAS framework, but not the preferred direction if we choose Repast.
- `SimPy`: only if we decide to model the simulation as a discrete-event system instead of a turn-based tick system.

Implementation note: Repast has multiple ecosystem options. If the project remains Python-first, use `Repast4Py`. If the lecturer expects Java-based Repast Simphony specifically, we should separate the MAS engine into a Java service and keep Flask only as a bridge/API layer. The current preference is Python-first with Repast4Py unless course requirements force Java.

## Simulation Model

The simulation is discrete and turn-based.

Each tick:

1. Agents perceive nearby cells and nearby agents.
2. Agents update their local memory/internal map.
3. Adjacent agents may communicate as a free secondary action.
4. Each agent chooses one primary action.
5. The engine resolves movement, pickup, placement, waiting, and conflicts.
6. Global state, event logs, and metrics are updated.

Agents should not replan inside the same tick after an action fails. Each tick should have a planning phase based on the state known at the start of that tick, followed by an execution phase. If an agent planned to move into a cell that another agent claimed first, or if pickup/place preconditions are no longer valid, that action fails, is logged, and the agent replans on the next tick.

Primary agent actions:

- `move`
- `pick`
- `place`
- `wait`

Communication:

- Local only.
- Only adjacent agents can communicate.
- Communication does not consume the primary action.
- Agents exchange timestamped knowledge.

## Agent Architecture

Each agent should be built from clear internal modules:

- `GoalHolder`: current task and target.
- `PerceptionModule`: local view of nearby cells, agents, items, pickup points, and delivery points.
- `MemoryModule`: timestamped internal map and task/item knowledge.
- `CommunicationModule`: peer-to-peer adjacent information exchange.
- `MovementModule`: path planning and route selection.
- `DecisionModule`: chooses the next action based on goal, memory, route, congestion, and task status.
- `MetricsTracker`: tracks useful actions, waits, path length, completed tasks, and failed/replanned moves.

The current code already has some of these modules, but they are simple. We should keep the modular design and deepen the behavior.

## Pickup And Delivery Rules

The SRS says pickup and placement should happen from an adjacent valid free cell.

That means:

- Agents should not stand directly on the pickup cell to pick up an item.
- Agents should stand next to the pickup cell and execute `pick`.
- Agents should not stand directly on the delivery cell to place an item.
- Agents should stand next to the delivery cell and execute `place`.

This is different from the current prototype and should be corrected in the simulation model.

## Path Planning

Initial routing can use BFS or A* over the grid.

The target behavior should become adaptive and partially non-deterministic:

- Prefer shorter paths.
- Prefer less congested paths.
- Avoid recently failed routes.
- Consider occupied cells and temporary blockers.
- Consider unknown/unexplored areas.
- Replan when local conditions change.
- Use weighted route choice so agents do not always make identical decisions.

`NetworkX` can be used for graph representation and shortest path calculations. Custom route scoring can sit above it.

## Task Allocation

Initial task allocation:

- Available agents take available tasks.
- If multiple agents are available, use nearest-agent or first-available selection.

Extended task allocation:

- Auction-based assignment.
- New tasks are announced.
- Eligible agents compute bids.
- Bid can include distance, current load, congestion, expected path cost, and availability.
- The task is assigned to the lowest-cost or highest-value bidder.

The architecture should make allocation strategy pluggable:

- `SimpleAllocationStrategy`
- `NearestAgentAllocationStrategy`
- `AuctionAllocationStrategy`

## Internal Map And Knowledge

Agents should not rely on full global state.

Each agent should maintain an internal map with timestamped entries:

- known free cells
- known blocked cells
- pickup locations
- delivery locations
- item locations
- observed agent positions
- congestion information
- recently blocked paths

When new information arrives through perception or communication:

- compare timestamps
- keep the newer information
- discard stale conflicting information

The backend may still hold the complete ground-truth state, but agents should make decisions using their own local knowledge.

## Metrics And Logs

Metrics are central to the project, not just decoration.

Track globally:

- simulation tick count
- completed deliveries
- total deliveries
- task completion rate
- throughput
- average task completion time
- total waiting actions
- total movement actions
- blocked move attempts
- collision violations
- route replanning events

Track per agent:

- completed tasks
- total actions
- useful actions
- wait actions
- path length
- path inefficiency
- collision violations
- utility score

Event log entries should include:

- tick
- event type
- agent id if relevant
- task id if relevant
- item id if relevant
- position if relevant
- human-readable message

## Frontend: Current 2D Viewer

The existing `frontend/` project should remain as a simple debugging UI.

Technology:

- Vite
- React
- plain CSS

Purpose:

- fast simulation stepping
- state inspection
- debugging agents/tasks/deliveries
- simple grid view
- basic action log

This viewer should stay lightweight and easy to run.

## Frontend: New Three.js Viewer

Create a new Vite project:

```text
warehouse_mas_template/viewer_three/
```

Technology:

- Vite
- React
- Three.js
- `@react-three/fiber`
- `@react-three/drei`
- optional: `zustand` for frontend state management

Purpose:

- richer visual warehouse simulation
- 3D grid/floor
- shelves/blocked cells as warehouse objects
- agents as moving robots or simple 3D vehicles
- boxes/items as separate objects
- pickup/dropoff zones visually distinct
- camera controls
- speed controls
- step/run/pause/reset controls
- agent inspection panel
- task/metrics panel
- optional path visualization
- optional perception-radius visualization

The Three.js viewer should consume the same API as the 2D viewer. The backend should not need separate simulation logic for each viewer.

## Shared API State Shape

The backend should expose a stable JSON state contract:

```json
{
  "tick": 0,
  "map": {
    "width": 12,
    "height": 8,
    "cells": []
  },
  "agents": [],
  "items": [],
  "tasks": [],
  "events": [],
  "metrics": {}
}
```

Use consistent naming:

- Prefer `items` for physical objects.
- Prefer `tasks` for pickup-and-delivery jobs.
- Keep `deliveries` only if we decide not to rename the current model.

The frontend should not infer important simulation logic. It should display the state given by the backend.

## Scenario System

Scenarios should be explicit configuration objects.

Each scenario should define:

- map size
- blocked cells
- pickup locations
- delivery locations
- initial agents
- task queue
- random seed
- perception radius
- allocation strategy
- routing strategy
- optional dynamic changes

Required validation scenarios from the SRS:

- single-agent baseline
- multi-agent cooperative delivery
- obstacle-dense environment
- congestion and conflict resolution
- limited observability
- dynamic change during execution
- allocation strategy comparison
- scalability test
- temporary agent trap
- blocked delivery

## Testing Strategy

Backend tests should verify:

- grid initialization
- legal and illegal movement
- pickup/placement adjacency rules
- one-item carrying limit
- task assignment
- collision prevention
- no agent swaps through another agent
- local perception radius
- timestamped memory merge
- adjacent-only communication
- route replanning
- metrics updates
- deterministic replay with seed

Frontend tests can be lighter:

- API loading states
- rendering cells/agents/items/tasks
- controls call expected API routes
- Three.js scene renders non-empty

## Development Order

The technical build should progress in this order:

1. Stabilize backend models and API state contract.
2. Correct pickup/dropoff adjacency behavior.
3. Add scenario loading and deterministic task queues.
4. Add metrics and event logging.
5. Implement limited perception and timestamped internal maps.
6. Implement adjacent communication.
7. Improve routing with replanning and route scoring.
8. Add allocation strategies.
9. Create the new Three.js Vite viewer.
10. Add validation scenarios and comparison metrics.

## Design Principle

The backend should be the simulation brain.

The current React viewer and the future Three.js viewer should both be clients of the same simulation API. The project should avoid duplicating MAS logic in JavaScript. JavaScript is for visualization and controls; Repast/Python is for simulation, agents, tasks, routing, coordination, and metrics.
