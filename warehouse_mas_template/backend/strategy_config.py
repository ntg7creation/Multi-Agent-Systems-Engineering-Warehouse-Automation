from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional


PATH_WEIGHT_DEFAULTS: Dict[str, float | int] = {
    "alpha_distance": 1.0,
    "beta_congestion": 2.0,
    "gamma_failed_route": 1.5,
    "delta_uncertainty": 0.3,
    "occupied_penalty": 4.0,
    "max_candidates": 6,
    "near_optimal_margin": 0.35,
    "max_expansion_multiplier": 10,
}

CONGESTION_DEFAULTS: Dict[str, float | int] = {
    "decay": 0.85,
    "nearby_agent_weight": 1.2,
    "waiting_weight": 0.7,
    "failed_move_weight": 1.0,
    "blocked_path_weight": 0.9,
    "communicated_weight": 0.5,
    "path_padding": 1,
}

BASELINE_CONFIG: Dict[str, object] = {
    "perception_radius": 3,
    "allocation_strategy": "nearest_available",
    "routing_strategy": "local_memory_astar",
    "path_weights": {
        "alpha_distance": 1.0,
        "beta_congestion": 0.0,
        "gamma_failed_route": 0.0,
        "delta_uncertainty": 0.0,
        "occupied_penalty": 0.0,
        "max_candidates": 1,
        "near_optimal_margin": 0.0,
        "max_expansion_multiplier": 10,
    },
    "congestion": {
        "decay": 0.0,
        "nearby_agent_weight": 0.0,
        "waiting_weight": 0.0,
        "failed_move_weight": 0.0,
        "blocked_path_weight": 0.0,
        "communicated_weight": 0.0,
        "path_padding": 0,
    },
}

STRATEGY_PROFILES: Dict[str, Optional[Dict[str, object]]] = {
    "scenario": None,
    "advanced": None,
    "baseline": BASELINE_CONFIG,
}

INT_PATH_KEYS = {"max_candidates", "max_expansion_multiplier"}
INT_CONGESTION_KEYS = {"path_padding"}


def config_profile_from_label(experiment_label: str) -> str:
    label = experiment_label.lower()
    if "baseline" in label:
        return "baseline"
    if "advanced" in label:
        return "advanced"
    return "scenario"


def config_profile_overrides(profile: Optional[str]) -> Optional[Dict[str, object]]:
    if profile is None:
        return None
    normalized = str(profile).strip().lower()
    if normalized not in STRATEGY_PROFILES:
        known = ", ".join(sorted(STRATEGY_PROFILES))
        raise ValueError(f"Unknown config profile '{profile}'. Available: {known}.")
    profile_config = STRATEGY_PROFILES[normalized]
    return deepcopy(profile_config) if profile_config is not None else None


def normalize_config_overrides(raw: Optional[Mapping[str, Any]]) -> Dict[str, object]:
    if not isinstance(raw, Mapping):
        return {}

    source: Mapping[str, Any] = raw
    if isinstance(raw.get("config"), Mapping):
        source = raw["config"]

    normalized: Dict[str, object] = {}
    if "perception_radius" in source:
        normalized["perception_radius"] = max(0, _to_int(source["perception_radius"], 3))
    if "allocation_strategy" in source:
        normalized["allocation_strategy"] = str(source["allocation_strategy"])
    if "routing_strategy" in source:
        normalized["routing_strategy"] = str(source["routing_strategy"])

    path_weights = _normalize_numeric_section(
        source.get("path_weights"),
        allowed_keys=set(PATH_WEIGHT_DEFAULTS),
        int_keys=INT_PATH_KEYS,
    )
    if path_weights:
        normalized["path_weights"] = path_weights

    congestion = _normalize_numeric_section(
        source.get("congestion"),
        allowed_keys=set(CONGESTION_DEFAULTS),
        int_keys=INT_CONGESTION_KEYS,
    )
    if congestion:
        normalized["congestion"] = congestion

    return normalized


def effective_strategy_config(
    *,
    perception_radius: int,
    allocation_strategy: str,
    routing_strategy: str,
    path_weights: Mapping[str, Any],
    congestion: Mapping[str, Any],
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, object]:
    clean_overrides = normalize_config_overrides(overrides)

    effective_path_weights: Dict[str, float | int] = dict(PATH_WEIGHT_DEFAULTS)
    effective_path_weights.update(
        _normalize_numeric_section(path_weights, set(PATH_WEIGHT_DEFAULTS), INT_PATH_KEYS),
    )
    effective_path_weights.update(clean_overrides.get("path_weights", {}))

    effective_congestion: Dict[str, float | int] = dict(CONGESTION_DEFAULTS)
    effective_congestion.update(
        _normalize_numeric_section(congestion, set(CONGESTION_DEFAULTS), INT_CONGESTION_KEYS),
    )
    effective_congestion.update(clean_overrides.get("congestion", {}))

    return {
        "perception_radius": int(clean_overrides.get("perception_radius", perception_radius)),
        "allocation_strategy": str(clean_overrides.get("allocation_strategy", allocation_strategy)),
        "routing_strategy": str(clean_overrides.get("routing_strategy", routing_strategy)),
        "path_weights": effective_path_weights,
        "congestion": effective_congestion,
    }


def _normalize_numeric_section(
    raw: object,
    allowed_keys: set[str],
    int_keys: set[str],
) -> Dict[str, float | int]:
    if not isinstance(raw, Mapping):
        return {}
    normalized: Dict[str, float | int] = {}
    for key, value in raw.items():
        key_text = str(key)
        if key_text not in allowed_keys:
            continue
        if key_text in int_keys:
            normalized[key_text] = max(0, _to_int(value, 0))
        else:
            normalized[key_text] = _to_float(value, 0.0)
    return normalized


def _to_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
