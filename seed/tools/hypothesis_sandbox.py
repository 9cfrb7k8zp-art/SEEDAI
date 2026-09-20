# ==============================================================
# FILE: SEED_ROOT/seed/tools/hypothesis_sandbox.py
# PURPOSE: Safely simulate SEED-AI changes for testing
# VERSION: 2.0.0
# ROLE: hypothesis-simulation / isolated-testing node
# ==============================================================

import asyncio
import inspect
import logging
import threading
import time
import uuid
from copy import deepcopy

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("HypothesisSandbox")


class HypothesisSandbox(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        name="hypothesis_sandbox",
        capabilities=None,
        dependencies=None,
        role="hypothesis-simulation",
        version="2.0.0",
        always_on=False,
    ):
        default_capabilities = {
            "hypothesis_testing",
            "state_simulation",
            "isolated_mutation",
            "event_simulation",
            "handler_simulation",
            "async_simulation",
            "state_comparison",
            "simulation_history",
            "recovery_testing",
            "change_validation",
        }

        if capabilities:
            default_capabilities.update(capabilities)

        super().__init__(
            name=name,
            capabilities=default_capabilities,
            dependencies=dependencies,
            role=role,
            version=version,
            always_on=always_on,
        )

        self._lock = threading.RLock()

        # Isolated simulation state.
        self._sandbox_state = {}

        # Simulation records.
        self._simulations = []

        # Event simulation records.
        self._event_results = []

        # Local lifecycle.
        self._running = False

        self._simulation_count = 0
        self._successful_simulations = 0
        self._failed_simulations = 0

        self._last_simulation = None
        self._last_error = None

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return self.status()

            self._running = True
            self.active = True

        logger.info(f"[{self.name}] Started")

        return self.status()

    def stop(self):
        with self._lock:
            self._running = False
            self.active = False

        logger.info(f"[{self.name}] Stopped")

        return self.status()

    # ----------------------------------------------------------
    # Load isolated state
    # ----------------------------------------------------------

    def load_state(self, state_snapshot):
        if not isinstance(state_snapshot, dict):
            raise TypeError("state_snapshot must be a dict")

        with self._lock:
            self._sandbox_state = deepcopy(state_snapshot)

            loaded = {
                "type": "sandbox_state_loaded",
                "source_node": self.node_id,
                "keys": list(self._sandbox_state.keys()),
                "timestamp": time.time(),
            }

        logger.info(
            f"[{self.name}] State loaded: "
            f"keys={loaded['keys']}"
        )

        return loaded

    # ----------------------------------------------------------
    # Replace sandbox state
    # ----------------------------------------------------------

    def set_state(self, state):
        return self.load_state(state)

    # ----------------------------------------------------------
    # Simulate a state mutation
    # ----------------------------------------------------------

    def mutate(self, key, value):
        if not key:
            raise ValueError("key is required")

        with self._lock:
            old_value = deepcopy(
                self._sandbox_state.get(key)
            )

            new_value = deepcopy(value)

            self._sandbox_state[key] = new_value

            simulation = {
                "type": "state_mutation",
                "simulation_id": (
                    f"SIM.{uuid.uuid4().hex[:12]}"
                ),
                "source_node": self.node_id,
                "timestamp": time.time(),
                "key": key,
                "old_value": old_value,
                "new_value": deepcopy(new_value),
            }

            self._simulations.append(simulation)
            self._simulation_count += 1
            self._successful_simulations += 1
            self._last_simulation = simulation
            self._last_error = None

        logger.info(
            f"[{self.name}] Simulated mutation "
            f"{key}: {old_value} -> {new_value}"
        )

        return deepcopy(simulation)

    # ----------------------------------------------------------
    # Remove a simulated state value
    # ----------------------------------------------------------

    def remove(self, key):
        if not key:
            raise ValueError("key is required")

        with self._lock:
            if key not in self._sandbox_state:
                return {
                    "type": "state_remove",
                    "source_node": self.node_id,
                    "key": key,
                    "removed": False,
                    "reason": "key_not_found",
                    "timestamp": time.time(),
                }

            old_value = deepcopy(
                self._sandbox_state[key]
            )

            del self._sandbox_state[key]

            simulation = {
                "type": "state_remove",
                "simulation_id": (
                    f"SIM.{uuid.uuid4().hex[:12]}"
                ),
                "source_node": self.node_id,
                "timestamp": time.time(),
                "key": key,
                "old_value": old_value,
                "removed": True,
            }

            self._simulations.append(simulation)
            self._simulation_count += 1
            self._successful_simulations += 1
            self._last_simulation = simulation

        return deepcopy(simulation)

    # ----------------------------------------------------------
    # Read simulated value
    # ----------------------------------------------------------

    def get(self, key, default=None):
        with self._lock:
            return deepcopy(
                self._sandbox_state.get(key, default)
            )

    # ----------------------------------------------------------
    # Simulate an event
    # ----------------------------------------------------------

    async def simulate_event(
        self,
        event_name,
        payload=None,
        handlers=None,
    ):
        if not event_name:
            raise ValueError("event_name is required")

        handlers = handlers or []

        with self._lock:
            sandbox_state = deepcopy(
                self._sandbox_state
            )

        results = []

        event_record = {
            "type": "event_simulation",
            "simulation_id": (
                f"SIM.{uuid.uuid4().hex[:12]}"
            ),
            "source_node": self.node_id,
            "event_name": event_name,
            "timestamp": time.time(),
            "handler_count": len(handlers),
            "results": [],
            "errors": [],
        }

        for handler in handlers:
            handler_name = getattr(
                handler,
                "__name__",
                handler.__class__.__name__,
            )

            try:
                simulated_payload = deepcopy(payload)
                simulated_state = deepcopy(
                    sandbox_state
                )

                if inspect.iscoroutinefunction(handler):
                    result = await handler(
                        simulated_payload,
                        simulated_state,
                    )
                else:
                    result = handler(
                        simulated_payload,
                        simulated_state,
                    )

                    if inspect.isawaitable(result):
                        result = await result

                result_copy = deepcopy(result)

                results.append(result_copy)

                event_record["results"].append(
                    {
                        "handler": handler_name,
                        "success": True,
                        "result": result_copy,
                    }
                )

            except Exception as exc:
                error_record = {
                    "handler": handler_name,
                    "success": False,
                    "error": str(exc),
                    "error_type": (
                        type(exc).__name__
                    ),
                }

                event_record["errors"].append(
                    error_record
                )

                logger.error(
                    f"[{self.name}] "
                    f"Simulated handler failed | "
                    f"event={event_name} | "
                    f"handler={handler_name} | "
                    f"error={exc}"
                )

        event_record["success"] = not bool(
            event_record["errors"]
        )

        with self._lock:
            self._event_results.append(
                deepcopy(event_record)
            )

            self._simulation_count += 1

            if event_record["success"]:
                self._successful_simulations += 1
            else:
                self._failed_simulations += 1
                self._last_error = (
                    event_record["errors"][-1]
                    if event_record["errors"]
                    else None
                )

            self._last_simulation = event_record

        return deepcopy(event_record)

    # ----------------------------------------------------------
    # Synchronous wrapper for event simulation
    # ----------------------------------------------------------

    def simulate_event_sync(
        self,
        event_name,
        payload=None,
        handlers=None,
    ):

        return asyncio.run(
            self.simulate_event(
                event_name=event_name,
                payload=payload,
                handlers=handlers,
            )
        )

    # ----------------------------------------------------------
    # Run an externally supplied coroutine
    # ----------------------------------------------------------

    def run_async(self, coro):

        if not inspect.iscoroutine(coro):
            raise TypeError(
                "Must pass a coroutine"
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        raise RuntimeError(
            "run_async() cannot synchronously execute a "
            "coroutine while an event loop is already running; "
            "await the coroutine from the authoritative runtime "
            "context instead"
        )

    # ----------------------------------------------------------
    # Snapshot sandbox state
    # ----------------------------------------------------------

    def snapshot(self):
        with self._lock:
            return deepcopy(
                self._sandbox_state
            )

    # ----------------------------------------------------------
    # Compare sandbox state with another state
    # ----------------------------------------------------------

    def compare_state(self, reference_state):
        if not isinstance(reference_state, dict):
            raise TypeError(
                "reference_state must be a dict"
            )

        with self._lock:
            sandbox = deepcopy(
                self._sandbox_state
            )

        sandbox_keys = set(sandbox)
        reference_keys = set(reference_state)

        added = {
            key: deepcopy(sandbox[key])
            for key in sandbox_keys - reference_keys
        }

        removed = {
            key: deepcopy(reference_state[key])
            for key in reference_keys - sandbox_keys
        }

        changed = {}

        for key in sandbox_keys & reference_keys:
            if sandbox[key] != reference_state[key]:
                changed[key] = {
                    "before": deepcopy(
                        reference_state[key]
                    ),
                    "after": deepcopy(
                        sandbox[key]
                    ),
                }

        unchanged = [
            key
            for key in sandbox_keys & reference_keys
            if sandbox[key] == reference_state[key]
        ]

        return {
            "type": "sandbox_state_comparison",
            "source_node": self.node_id,
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
            "changed_count": len(changed),
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # Clear simulation history
    # ----------------------------------------------------------

    def clear_simulations(self):
        with self._lock:
            self._simulations.clear()
            self._event_results.clear()

        logger.info(
            f"[{self.name}] Simulation history cleared"
        )

        return {
            "cleared": True,
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # Simulation history
    # ----------------------------------------------------------

    def simulation_history(self, limit=None):
        with self._lock:
            records = list(self._simulations)

            if limit is not None:
                if limit < 0:
                    raise ValueError(
                        "limit must be >= 0"
                    )

                records = records[-limit:]

            return deepcopy(records)

    def event_history(self, limit=None):
        with self._lock:
            records = list(self._event_results)

            if limit is not None:
                if limit < 0:
                    raise ValueError(
                        "limit must be >= 0"
                    )

                records = records[-limit:]

            return deepcopy(records)

    # ----------------------------------------------------------
    # Build hypothesis report
    # ----------------------------------------------------------

    def build_report(self):
        with self._lock:
            return {
                "type": "hypothesis_sandbox_report",
                "source_node": self.node_id,
                "running": self._running,
                "state_keys": list(
                    self._sandbox_state.keys()
                ),
                "simulation_count": (
                    self._simulation_count
                ),
                "successful_simulations": (
                    self._successful_simulations
                ),
                "failed_simulations": (
                    self._failed_simulations
                ),
                "event_simulation_count": len(
                    self._event_results
                ),
                "last_simulation": deepcopy(
                    self._last_simulation
                ),
                "last_error": deepcopy(
                    self._last_error
                ),
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # CLI-friendly display
    # ----------------------------------------------------------

    def show_simulations(self, last_n=5):
        if last_n < 0:
            raise ValueError(
                "last_n must be >= 0"
            )

        with self._lock:
            simulations = self._simulations[-last_n:]

        for simulation in simulations:
            logger.info(
                f"[{self.name}] "
                f"{simulation.get('timestamp', 0):.3f} | "
                f"{simulation.get('key', '<event>')}: "
                f"{simulation.get('old_value')} -> "
                f"{simulation.get('new_value')}"
            )

        return deepcopy(simulations)

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------

    def status(self):
        with self._lock:
            return {
                "node_id": self.node_id,
                "name": self.name,
                "role": self.role,
                "version": self.version,
                "running": self._running,
                "active": self.active,
                "ready": self.ready,
                "degraded": self.degraded,
                "failed": self.failed,
                "state_keys": len(
                    self._sandbox_state
                ),
                "simulation_count": (
                    self._simulation_count
                ),
                "successful_simulations": (
                    self._successful_simulations
                ),
                "failed_simulations": (
                    self._failed_simulations
                ),
                "event_simulation_count": len(
                    self._event_results
                ),
                "last_error": deepcopy(
                    self._last_error
                ),
            }

    # ----------------------------------------------------------
    # Health
    # ----------------------------------------------------------

    def health(self):
        with self._lock:
            if self.failed:
                state = "FAILED"
            elif self._failed_simulations > 0:
                state = "DEGRADED"
            elif self._running:
                state = "HEALTHY"
            else:
                state = "STOPPED"

            return {
                "state": state,
                "running": self._running,
                "simulation_count": (
                    self._simulation_count
                ),
                "failed_simulations": (
                    self._failed_simulations
                ),
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # Representation
    # ----------------------------------------------------------

    def __repr__(self):
        return (
            f"<HypothesisSandbox "
            f"name={self.name!r} "
            f"running={self._running} "
            f"simulations={self._simulation_count}>"
        )