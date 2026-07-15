# Pyodide Compatibility Audit

## Summary

The copied simulation engine is compatible with Pyodide. The Flask server layer and threaded service layer were not loaded in the browser. The browser build runs only the pure simulation engine and a small bridge.

## Dependency Classification

| Dependency or capability | Where used | Classification | Adaptation |
| --- | --- | --- | --- |
| `flask`, `flask_cors` | `backend/app.py` only | Unsupported/server-only | Not copied into runtime; route behavior moved to JS adapter and Python bridge. |
| `threading`, `Thread`, `Lock`, `sleep` | `backend/services/simulation_service.py` | Avoided | Original service was not used. Playback uses JS interval and queued worker commands. |
| `subprocess` | Not found | Not applicable | None. |
| `multiprocessing` | Not found | Not applicable | None. |
| `socket` | Not found | Not applicable | None. |
| `requests` | Not found | Not applicable | None. |
| `pathlib.Path` | `scenarios.py` | Standard library, compatible | Scenario files are written into Pyodide FS before import. |
| `open` / file reads | `scenarios.py` uses `Path.open` | Compatible in virtual FS | Files are copied from static assets to `/warehouse_simulation`. |
| Local file writes | None for runtime persistence | Avoided | CSV export uses `StringIO`; browser handles downloads. |
| `csv` | `models/analytics.py` | Standard library, compatible | No change. |
| `io.StringIO` | `models/analytics.py` | Standard library, compatible | No change. |
| `dataclasses` | model classes | Standard library, compatible | No change. |
| `random` | engine and decisions | Standard library, compatible | No change. |
| `heapq` | path planning | Standard library, compatible | No change. |
| `collections.deque` | memory and task manager | Standard library, compatible | No change. |
| `uuid.uuid4` | run IDs | Standard library, compatible | No change. |
| `numpy` | Listed in requirements, not imported | Pyodide package exists, unused | Not loaded. |
| `pandas` | Listed in requirements, not imported | Pyodide package exists, unused | Not loaded. |
| `networkx` | Listed in requirements, not imported | Pure Python but unused | Not installed/loaded. |
| `pydantic` | Listed in requirements, not imported | Unused | Not installed/loaded. |
| Native extensions | Not used by copied engine | Not applicable | None. |
| WebSockets | Not used | Not applicable | None. |
| OS-specific paths | Original scenario path was relative | Adapted by virtual FS | No Windows paths in runtime. |

## Bridge

`public/python/warehouse_simulation/pyodide_bridge.py` exposes command functions for:

- initialization
- scenario listing
- scenario load/reset
- state retrieval
- single and multi-step execution
- strategy profile reset
- analytics summary/events/agents/replay
- JSON and CSV analytics export

The bridge returns dictionaries, lists, strings, numbers, booleans, or `None`. Tuples are serialized to JSON arrays by `json.dumps`.

## Unsupported Pieces Removed From Browser Runtime

- Flask app startup.
- CORS configuration.
- HTTP request parsing.
- Server response attachment headers.
- Python autorun thread.
- Process-global cross-user singleton.

## Behavior Impact

No simulation decision logic was rewritten. The behavior change is in orchestration: playback timing and downloads are browser-owned.
