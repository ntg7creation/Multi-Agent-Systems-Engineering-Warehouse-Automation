from __future__ import annotations

from threading import Lock, Thread
from time import sleep
from typing import Dict, Optional

from models.engine import SimulationEngine
from scenarios import build_engine_from_scenario


class SimulationService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._engine = build_engine_from_scenario()
        self._autorun_active = False
        self._autorun_delay_seconds = 0.6
        self._autorun_max_ticks: Optional[int] = None
        self._autorun_thread: Optional[Thread] = None

    @property
    def engine(self) -> SimulationEngine:
        return self._engine

    def reset(self, scenario_id: str = "default", seed: Optional[int] = None) -> Dict[str, object]:
        self.stop_autorun()
        with self._lock:
            self._engine = build_engine_from_scenario(scenario_id=scenario_id, seed=seed)
            return self._engine.serialize_state()

    def load_scenario(self, scenario_id: str, seed: Optional[int] = None) -> Dict[str, object]:
        return self.reset(scenario_id=scenario_id, seed=seed)

    def state(self) -> Dict[str, object]:
        with self._lock:
            state = self._engine.serialize_state()
            state["autorun"] = self.autorun_status()
            return state

    def board(self) -> Dict[str, object]:
        with self._lock:
            return self._engine.serialize_board()

    def agents(self) -> Dict[str, object]:
        with self._lock:
            return {"agents": [agent.serialize() for agent in self._engine.agents]}

    def agent(self, agent_id: str) -> Optional[Dict[str, object]]:
        with self._lock:
            return self._engine.serialize_agent(agent_id, include_memory=True)

    def tasks(self) -> Dict[str, object]:
        with self._lock:
            return {"tasks": self._engine.serialize_tasks()}

    def task(self, task_id: str) -> Optional[Dict[str, object]]:
        with self._lock:
            delivery = self._engine.get_delivery(task_id)
            return delivery.serialize(self._engine.map) if delivery else None

    def items(self) -> Dict[str, object]:
        with self._lock:
            return {"items": self._engine.serialize_items()}

    def metrics(self) -> Dict[str, object]:
        with self._lock:
            return self._engine.serialize_metrics()

    def events(self, limit: Optional[int] = None) -> Dict[str, object]:
        with self._lock:
            return {"events": self._engine.serialize_events(limit=limit)}

    def step(self, steps: int = 1) -> Dict[str, object]:
        with self._lock:
            return self._engine.run_steps(steps)

    def start_autorun(
        self,
        delay_ms: int = 600,
        max_ticks: Optional[int] = None,
    ) -> Dict[str, object]:
        delay_ms = max(50, min(int(delay_ms), 10000))
        with self._lock:
            if self._autorun_active:
                return self.autorun_status()
            self._autorun_active = True
            self._autorun_delay_seconds = delay_ms / 1000
            self._autorun_max_ticks = max_ticks

        self._autorun_thread = Thread(target=self._autorun_loop, daemon=True)
        self._autorun_thread.start()
        return self.autorun_status()

    def stop_autorun(self) -> Dict[str, object]:
        with self._lock:
            self._autorun_active = False
        return self.autorun_status()

    def autorun_status(self) -> Dict[str, object]:
        return {
            "active": self._autorun_active,
            "delay_ms": int(self._autorun_delay_seconds * 1000),
            "max_ticks": self._autorun_max_ticks,
        }

    def _autorun_loop(self) -> None:
        ticks_run = 0
        while True:
            with self._lock:
                if not self._autorun_active:
                    return
                if self._engine.is_complete:
                    self._autorun_active = False
                    return
                if self._autorun_max_ticks is not None and ticks_run >= self._autorun_max_ticks:
                    self._autorun_active = False
                    return
                self._engine.step()
                ticks_run += 1
                delay = self._autorun_delay_seconds
            sleep(delay)
