# Warehouse Automation Template

Minimal Flask + websocket starter for a warehouse MAS simulation.

## What this includes
- Grid-based warehouse world
- Placeholder `Agent` class
- Very simple agent policy: pick up if possible, place if possible, otherwise move forward if possible, else wait
- JSON API for world state
- Websocket broadcast of state updates
- Small browser viewer for the grid

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## API

- `GET /api/state` -> current world state as JSON
- `GET /api/step` -> manually advance one step and return updated JSON
- websocket event `state` -> pushed every second

## Next steps
- Replace `Agent.choose_action()` with real MAS logic
- Add task allocation / bidding
- Add A* or cooperative pathfinding
- Replace the HTML viewer with a Three.js frontend that reads the same JSON state
