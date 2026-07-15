# Migration Map

## Backend Python

`backend/models/action.py`
    -> `vercel_build/public/python/warehouse_simulation/models/action.py`

`backend/models/agent.py`
    -> `vercel_build/public/python/warehouse_simulation/models/agent.py`

`backend/models/agent_log.py`
    -> `vercel_build/public/python/warehouse_simulation/models/agent_log.py`

`backend/models/analytics.py`
    -> `vercel_build/public/python/warehouse_simulation/models/analytics.py`

`backend/models/communication.py`
    -> `vercel_build/public/python/warehouse_simulation/models/communication.py`

`backend/models/congestion.py`
    -> `vercel_build/public/python/warehouse_simulation/models/congestion.py`

`backend/models/decision.py`
    -> `vercel_build/public/python/warehouse_simulation/models/decision.py`

`backend/models/delivery.py`
    -> `vercel_build/public/python/warehouse_simulation/models/delivery.py`

`backend/models/engine.py`
    -> `vercel_build/public/python/warehouse_simulation/models/engine.py`

`backend/models/event_log.py`
    -> `vercel_build/public/python/warehouse_simulation/models/event_log.py`

`backend/models/goal.py`
    -> `vercel_build/public/python/warehouse_simulation/models/goal.py`

`backend/models/item.py`
    -> `vercel_build/public/python/warehouse_simulation/models/item.py`

`backend/models/map.py`
    -> `vercel_build/public/python/warehouse_simulation/models/map.py`

`backend/models/memory.py`
    -> `vercel_build/public/python/warehouse_simulation/models/memory.py`

`backend/models/metrics.py`
    -> `vercel_build/public/python/warehouse_simulation/models/metrics.py`

`backend/models/movement.py`
    -> `vercel_build/public/python/warehouse_simulation/models/movement.py`

`backend/models/perception.py`
    -> `vercel_build/public/python/warehouse_simulation/models/perception.py`

`backend/models/scenario.py`
    -> `vercel_build/public/python/warehouse_simulation/models/scenario.py`

`backend/models/task.py`
    -> `vercel_build/public/python/warehouse_simulation/models/task.py`

`backend/models/task_manager.py`
    -> `vercel_build/public/python/warehouse_simulation/models/task_manager.py`

`backend/scenarios.py`
    -> `vercel_build/public/python/warehouse_simulation/scenarios.py`

`backend/strategy_config.py`
    -> `vercel_build/public/python/warehouse_simulation/strategy_config.py`

`backend/scenario_data/*.json`
    -> `vercel_build/public/python/warehouse_simulation/scenario_data/*.json`

`backend/app.py`
    -> Not copied. Flask route behavior adapted into `src/simulation/*` and `pyodide_bridge.py`.

`backend/services/simulation_service.py`
    -> Not copied. Request-driven behavior adapted into `pyodide_bridge.py`; autorun thread replaced by JS timer in `PyodideSimulationAdapter.js`.

## Frontend 2D

`frontend/src/App.jsx`
    -> `vercel_build/src/two_d/App.jsx`

`frontend/src/App.css`
    -> `vercel_build/src/two_d/App.css`

`frontend/src/api.js`
    -> `vercel_build/src/two_d/api.js` with HTTP calls replaced by adapter calls.

`frontend/src/main.jsx`
    -> `vercel_build/src/two_d/main.jsx` copied but not used as the deploy entry point.

## Three.js Viewer

`viewer_three/src/App.jsx`
    -> `vercel_build/src/three_d/App.jsx`

`viewer_three/src/styles.css`
    -> `vercel_build/src/three_d/styles.css` with global element rules scoped to `.app-shell`.

`viewer_three/src/api/simulationClient.js`
    -> `vercel_build/src/three_d/api/simulationClient.js` with HTTP calls replaced by adapter calls.

`viewer_three/src/state/useSimulationStore.js`
    -> `vercel_build/src/three_d/state/useSimulationStore.js`

`viewer_three/src/scene/*`
    -> `vercel_build/src/three_d/scene/*`

`viewer_three/src/ui/*`
    -> `vercel_build/src/three_d/ui/*`

`viewer_three/public/models/*.fbx`
    -> `vercel_build/public/models/*.fbx`

## New Vercel Integration Files

`vercel_build/src/App.jsx`
    Application shell and `/2d`/`/3d` route switcher.

`vercel_build/src/main.jsx`
    Vite entry point.

`vercel_build/src/simulation/*`
    Shared simulation adapter, worker message constants, worker implementation, and interface stubs.

`vercel_build/public/python/warehouse_simulation/pyodide_bridge.py`
    Browser Python command bridge.

`vercel_build/public/python/warehouse_simulation/python-manifest.json`
    Static file manifest loaded by the worker.

`vercel_build/scripts/*`
    Pyodide copy, syntax, Pyodide smoke, and deterministic comparison helpers.
