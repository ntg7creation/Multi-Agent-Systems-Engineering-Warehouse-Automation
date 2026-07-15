from __future__ import annotations

from typing import Any, Dict, Optional

from scenarios import build_engine_from_scenario, list_scenarios
from strategy_config import config_profile_overrides

_engine = None
_scenario_id = "default"
_seed: Optional[int] = None
_config: Optional[Dict[str, object]] = None


def initialize() -> Dict[str, object]:
    _ensure_engine()
    return {"ok": True}


def handle(command: Dict[str, Any]) -> Any:
    command_type = str(command.get("type", ""))
    payload = command.get("payload") or {}

    if command_type == "INITIALIZE":
        return initialize()
    if command_type == "LIST_SCENARIOS":
        return list_scenarios()
    if command_type == "LOAD_SCENARIO":
        return load_scenario(
            scenario_id=str(payload.get("scenario_id") or payload.get("scenarioId") or "default"),
            seed=_optional_int(payload.get("seed")),
            config_overrides=_optional_config(payload),
        )
    if command_type == "RESET":
        return reset(
            scenario_id=str(payload.get("scenario_id") or payload.get("scenarioId") or "default"),
            seed=_optional_int(payload.get("seed")),
            config_overrides=_optional_config(payload),
        )
    if command_type == "GET_STATE":
        return state()
    if command_type == "GET_BOARD":
        return _ensure_engine().serialize_board()
    if command_type == "GET_AGENTS":
        return {"agents": [agent.serialize() for agent in _ensure_engine().agents]}
    if command_type == "GET_TASKS":
        return {"tasks": _ensure_engine().serialize_tasks()}
    if command_type == "GET_ITEMS":
        return {"items": _ensure_engine().serialize_items()}
    if command_type == "GET_METRICS":
        return _ensure_engine().serialize_metrics()
    if command_type == "GET_EVENTS":
        return {"events": _ensure_engine().serialize_events(limit=_optional_int(payload.get("limit")))}
    if command_type == "GET_REPLAY":
        return _ensure_engine().serialize_replay(limit=_optional_int(payload.get("limit")))
    if command_type == "STEP":
        return step(steps=_bounded_steps(payload.get("steps"), default=1))
    if command_type == "RUN":
        return step(steps=_bounded_steps(payload.get("steps"), default=10))
    if command_type == "SET_STRATEGY":
        return set_strategy(str(payload.get("strategy") or "scenario"), payload)
    if command_type == "GET_ANALYTICS_SUMMARY":
        engine = _ensure_engine()
        return engine.analytics.summary(engine)
    if command_type == "GET_ANALYTICS_EVENTS":
        events = _ensure_engine().analytics.global_event_log
        return {"events": _limited(events, _optional_int(payload.get("limit")))}
    if command_type == "GET_ANALYTICS_AGENTS":
        engine = _ensure_engine()
        return {
            "agents": engine.analytics.agent_metrics(engine),
            "decision_log": engine.analytics.local_agent_decision_log(engine),
        }
    if command_type == "GET_ANALYTICS_REPLAY":
        frames = _ensure_engine().analytics.action_flow_replay_log
        return {"frames": _limited(frames, _optional_int(payload.get("limit")))}
    if command_type == "EXPORT_ANALYTICS_JSON":
        engine = _ensure_engine()
        return engine.analytics.export_json(engine)
    if command_type == "EXPORT_ANALYTICS_CSV":
        engine = _ensure_engine()
        return engine.analytics.export_csv(engine)

    raise ValueError(f"Unknown simulation command: {command_type}")


def load_scenario(
    scenario_id: str = "default",
    seed: Optional[int] = None,
    config_overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    return reset(scenario_id=scenario_id, seed=seed, config_overrides=config_overrides)


def reset(
    scenario_id: str = "default",
    seed: Optional[int] = None,
    config_overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    global _engine, _scenario_id, _seed, _config
    _scenario_id = scenario_id
    _seed = seed
    _config = config_overrides
    _engine = build_engine_from_scenario(
        scenario_id=scenario_id,
        seed=seed,
        config_overrides=config_overrides,
    )
    return _engine.serialize_state()


def state() -> Dict[str, object]:
    return _ensure_engine().serialize_state()


def step(steps: int = 1) -> Dict[str, object]:
    return _ensure_engine().run_steps(steps)


def set_strategy(strategy_name: str, payload: Dict[str, Any]) -> Dict[str, object]:
    overrides = config_profile_overrides(strategy_name)
    scenario_id = str(payload.get("scenario_id") or payload.get("scenarioId") or _scenario_id)
    seed = _optional_int(payload.get("seed"))
    if seed is None:
        seed = _seed
    if overrides is None:
        overrides = _config
    return reset(scenario_id=scenario_id, seed=seed, config_overrides=overrides)


def _ensure_engine():
    global _engine
    if _engine is None:
        _engine = build_engine_from_scenario()
    return _engine


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded_steps(value: Any, default: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        parsed = default
    return max(1, min(parsed, 1000))


def _optional_config(payload: Dict[str, Any]) -> Optional[Dict[str, object]]:
    raw = payload.get("config", payload.get("config_overrides"))
    return raw if isinstance(raw, dict) else None


def _limited(rows: list, limit: Optional[int]) -> list:
    if limit is not None and limit > 0:
        return list(rows[-limit:])
    return list(rows)
