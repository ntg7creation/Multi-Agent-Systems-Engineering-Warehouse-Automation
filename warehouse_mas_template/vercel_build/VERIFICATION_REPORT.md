# Verification Report

## Commands Run

```bash
cd vercel_build
npm install
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run preview -- --port 4173
```

Additional checks:

```bash
node -e "<HTTP 404 sweep against preview server>"
C:\Users\natai\anaconda3\python.exe -B vercel_build\scripts\compare-original-backend.py
python -B -m pytest -p no:cacheprovider backend\tests
```

## Results

| Check | Result |
| --- | --- |
| npm install | Passed. 187 packages installed. npm audit reported 1 moderate and 1 high transitive finding. |
| typecheck | Passed. No TypeScript sources; script documents this and build validates JSX/modules. |
| npm test | Passed. JS syntax check and Pyodide smoke test passed. |
| Pyodide smoke | Passed: 24 scenarios listed; simple scenario reached tick 9; stress scenario reached tick 5 with 10 agents; CSV and JSON analytics exported. |
| production build | Passed. Vite built `dist`; warning only for large JS chunk size. |
| preview routes | Passed. `/2d` and `/3d` returned HTTP 200. |
| static asset sweep | Passed. 61 URLs checked with no failures, including Python files, scenarios, Pyodide runtime files, and FBX models. |
| deterministic original comparison | Passed for `simple_one_agent_delivery` seed 42 for 8 ticks and `ten_agents_twenty_tasks_stress` seed 77 for 5 ticks. |
| original pytest suite | Not run to completion: sandbox Python could not start; unsandboxed Anaconda Python did not have `pytest` installed. |
| headless browser route screenshots | Passed for shell rendering of `/2d` and `/3d`; screenshots were captured before Pyodide readiness. Runtime behavior is covered by the Pyodide smoke test. |

## Pyodide Smoke Output

```json
{"scenarios":24,"simpleTick":9,"stressTick":5,"stressAgents":10,"csvBytes":5979}
```

## Deterministic Comparison Output

```json
{
  "matched_cases": [
    {
      "scenario_id": "simple_one_agent_delivery",
      "seed": 42,
      "steps": 8,
      "tick": 8,
      "agent_count": 1,
      "task_count": 1,
      "analytics_event_count": 43,
      "replay_frame_count": 8
    },
    {
      "scenario_id": "ten_agents_twenty_tasks_stress",
      "seed": 77,
      "steps": 5,
      "tick": 5,
      "agent_count": 10,
      "task_count": 20,
      "analytics_event_count": 206,
      "replay_frame_count": 5
    }
  ]
}
```

## Feature Verification

| Feature | Verification |
| --- | --- |
| Scenario selection/listing | Pyodide smoke listed 24 scenarios; route screenshots showed scenario controls. |
| Scenario JSON loading | Pyodide smoke reset simple and stress scenarios; 404 sweep checked all scenario JSON files. |
| Start/pause/resume | Adapter implements JS timer start/resume and pause; direct visual timing should be checked manually in browser. |
| Single-step controls | Pyodide smoke executed `STEP`. |
| Multi-step run | Pyodide smoke executed `RUN`. |
| Reset | Pyodide smoke reset simple and stress scenarios. |
| Agent movement | Pyodide smoke confirmed simple scenario position changed after running. |
| Pickup/delivery actions | Python engine unchanged; deterministic comparison matched original action/state projections. |
| 2D visualization | Headless screenshot confirmed `/2d` route shell and controls render; state behavior validated in Pyodide. |
| 3D visualization | Headless screenshot confirmed `/3d` route shell and canvas render; model asset URLs passed 404 sweep. |
| 3D animations | Animation code and FBX assets copied; asset URLs passed. Full visual animation timing requires an interactive browser check. |
| Metrics/analytics | Pyodide smoke checked analytics summary and event counts. |
| Analytics export | Pyodide smoke checked JSON and CSV exports. Browser downloads use `Blob`. |
| Direct `/2d` and `/3d` navigation | HTTP 200 from production preview. |
| Asset paths | 61-file HTTP sweep passed with no 404s. |
| Session isolation | Architecture isolates each tab in its own worker/Pyodide runtime. Not directly browser-tested because available automation could not wait for worker readiness. |
| Refresh behavior | Documented as a new worker/session on refresh. |

## Original Folder Integrity

Final protected-folder status:

```text
 M warehouse_mas_template/backend/scenario_data/four_agents_adjacent_access_cluster.json
?? warehouse_mas_template/vercel_build/
```

The modified backend scenario file was present before work began and was treated as a pre-existing user change. No new edits were made inside `backend`, `frontend`, or `viewer_three`.
