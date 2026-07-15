# Warehouse MAS Vercel Build

## 1. Architecture Overview

This folder is an independently deployable Vercel app. It runs the copied Python simulation engine in Pyodide inside a Web Worker. React renders both the copied 2D dashboard and the copied Three.js viewer.

No Flask, FastAPI, Docker container, VM, external database, or dedicated backend service is required.

## 2. Folder Structure

- `src/`: React app, route shell, 2D viewer, 3D viewer, and simulation adapter.
- `src/simulation/`: worker protocol and Pyodide adapter.
- `public/python/warehouse_simulation/`: copied Python engine, scenarios, and bridge.
- `public/models/`: copied FBX character and animation assets.
- `scripts/`: build and verification helpers.
- `dist/`: production build output after `npm run build`.

## 3. Requirements

- Node.js 20 or newer.
- npm.
- A modern browser with WebAssembly support.

## 4. Installation

```bash
cd vercel_build
npm install
```

## 5. Local Development

```bash
npm run dev
```

Then open:

- `http://127.0.0.1:5173/2d`
- `http://127.0.0.1:5173/3d`

## 6. Production Build

```bash
npm run build
npm run preview
```

The build script copies the Pyodide runtime from `node_modules/pyodide` into `public/pyodide` before Vite builds.

## 7. Vercel Deployment

Set `vercel_build` as the Vercel project root.

CLI option:

```bash
cd vercel_build
npm install
npm run build
vercel
vercel --prod
```

In the Vercel dashboard, use:

- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Install command: `npm install`

## 8. Routes

- `/` renders the 2D simulator by default.
- `/2d` renders the copied 2D React dashboard.
- `/3d` renders the copied Three.js viewer.

The route switcher is inside the app header. Direct navigation works through `vercel.json` rewrites.

## 9. Python Integration

`src/simulation/simulationWorker.js` loads Pyodide and copies the files listed in `public/python/warehouse_simulation/python-manifest.json` into Pyodide's virtual filesystem. It then imports `pyodide_bridge.py`.

The UI calls `PyodideSimulationAdapter`, not Flask routes. The adapter sends typed commands to the worker and receives JSON-compatible state.

## 10. Known Limitations

- First load can take several seconds while Pyodide downloads and initializes.
- Refreshing the page starts a new browser-local simulation session.
- Large replay persistence is not implemented; active replay data remains in worker memory.
- `npm audit` reports two transitive findings from the current dependency tree. A forced audit fix was not applied because it may change major versions used by the Three.js viewer.

## 11. Troubleshooting

- If the UI stays on "Downloading Python runtime", confirm `/pyodide/pyodide.js`, `/pyodide/pyodide.asm.wasm`, and `/pyodide/python_stdlib.zip` return 200.
- If scenarios do not load, confirm `/python/warehouse_simulation/python-manifest.json` and every listed file return 200.
- If the 3D character is missing, confirm files under `/models` return 200, especially `character.fbx`, `Normal_Walking.fbx`, `Carry_walking.fbx`, `Idle.fbx`, `Carrying_idle.fbx`, `Picking Up.fbx`, and `Carrying_Turn_left.fbx`.
- If direct `/2d` or `/3d` navigation 404s on Vercel, confirm `vercel.json` is present and the project root is `vercel_build`.

## 12. Scenarios And Assets

Scenarios are stored in:

```text
public/python/warehouse_simulation/scenario_data
```

3D assets are stored in:

```text
public/models
```

## 13. Add A New Scenario

1. Add the JSON file to `public/python/warehouse_simulation/scenario_data`.
2. Add the relative path to `public/python/warehouse_simulation/python-manifest.json`.
3. Run `npm test`.
4. Run `npm run build`.

## 14. Verify Analytics Export

1. Open `/2d`.
2. Step or run the simulation.
3. Open the Analytics tab.
4. Click `Download JSON` or `Download CSV`.
5. Confirm the downloaded file contains events and agent metrics.

The automated Pyodide smoke test also checks both export formats:

```bash
npm test
```

## 15. Original Folder Protection

The Vercel app was created under `vercel_build`. The original `backend`, `frontend`, and `viewer_three` folders were not intentionally edited, moved, renamed, reformatted, or deleted.

The final git check still showed the pre-existing modified file:

```text
backend/scenario_data/four_agents_adjacent_access_cluster.json
```

That modification existed before this migration work began.
