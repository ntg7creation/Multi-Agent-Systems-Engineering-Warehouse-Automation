# Warehouse MAS Three.js Viewer

This is the future 3D viewer for the warehouse MAS simulation.

It is intentionally only a project skeleton right now. The backend simulation logic stays in `../backend`, and this viewer will consume the same Flask API as the simple `../frontend` viewer.

## Planned Stack

- Vite
- React
- Three.js
- `@react-three/fiber`
- `@react-three/drei`
- `zustand`

## Planned Folders

```text
viewer_three/
  src/
    api/
      simulationClient.js
    scene/
      WarehouseScene.jsx
      ScenePlaceholder.jsx
    state/
      useSimulationStore.js
    ui/
      ControlPanel.jsx
      InspectorPanel.jsx
```

## Run

```bash
npm install
npm run dev
```

The dev server uses port `5174` so it can run beside the existing 2D viewer on port `5173`.
