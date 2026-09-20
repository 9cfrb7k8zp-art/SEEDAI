# ==========================================================
# FILE: relay_core.py
# PATH: SEED_ROOT/seed/core/relay/relay_core.py
# VERSION: 2.0.0
# PURPOSE: SEED Relay orchestration nucleus
# ==========================================================

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from .relay_auth import RelayAuth
from .relay_emergency_stop import RelayEmergencyStop
from .relay_operations import RelayOperations
from .relay_rate_limiter import RelayRateLimiter
from .relay_router import RelayRouter
from .relay_gateway import RelayGateway
from .relay_watchdog import RelayWatchdog
from .relay_audit import RelayAudit
from .relay_github import RelayGitHub
from .relay_policy import RelayPolicy
from .relay_protocol import (
    RelayRequest,
    RelayResponse,
    RelayStatus,
)
from .relay_queue import RelayQueue
from .relay_resource_gate import RelayResourceGate


MODULE_ID = "CORE_RELAY"
MODULE_VERSION = "2.0.0"


class SEEDRelay:


    def __init__(
        self,
        *,
        cpu_ceiling: float = 50.0,
        memory_ceiling: float = 80.0,
        queue_size: int = 100,
        allow_prepare: bool = False,
        audit_path: str = "SEED_ROOT/relay_audit.jsonl",
    ):
        self.relay_id = "SEED-RELAY-2"

        self.policy = RelayPolicy(
            allow_prepare=allow_prepare
        )

        self.resource_gate = RelayResourceGate(
            cpu_ceiling=cpu_ceiling,
            memory_ceiling=memory_ceiling,
        )

        self.queue = RelayQueue(
            maxsize=queue_size
        )

        self.audit = RelayAudit(
            path=audit_path
        )

        self.github = RelayGitHub()
        # --------------------------------------------------
        # RELAY 2.0 CONTROL STACK
        # --------------------------------------------------

        self.auth = RelayAuth(
            seed_id="SEED-CORE",
            relay_id=self.relay_id,
        )

        self.rate_limiter = RelayRateLimiter()

        self.emergency_controller = RelayEmergencyStop()

        self.router = RelayRouter()

        self.gateway = RelayGateway(
            auth=self.auth,
            rate_limiter=self.rate_limiter,
            emergency_stop=self.emergency_controller,
        )

        self.watchdog = RelayWatchdog(
            self,
            interval=5.0,
        )

        # --------------------------------------------------
        # INITIAL ROUTES
        # --------------------------------------------------

        self.router.register(
            "CREATE_REPORT",
            self._handle_create_report,
        )

        self.router.register(
            "READ_REPOSITORY",
            self.github.execute,
        )

        self.router.register(
            "READ_ISSUE",
            self.github.execute,
        )

        self.router.register(
            "READ_PR",
            self.github.execute,
        )

        self.router.register(
            "READ_COMMENTS",
            self.github.execute,
        )


        self._running = False
        self._worker: Optional[threading.Thread] = None

        self._lock = threading.RLock()

    # ------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return

            self.queue.start()
            self._running = True

            self._worker = threading.Thread(
                target=self._worker_loop,
                name="SEEDRelayWorker",
                daemon=True,
            )

            self._worker.start()
            self.watchdog.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self.queue.stop()
            self.watchdog.stop()

    def _handle_create_report(
        self,
        request: RelayRequest,
    ) -> Dict[str, Any]:

        return {
            "success": True,
            "status": "LOCAL_REPORT",
            "payload": request.payload,
            "mission_id": request.mission_id,
            "track_id": request.track_id,
            "channel_id": request.channel_id,
        }
    # ------------------------------------------------------
    # REQUEST
    # ------------------------------------------------------

    def submit(
        self,
        request: RelayRequest,
        *,
        token: Optional[str] = None,
    ) -> RelayResponse:

        self.audit.record_request(
            request
        )

        # --------------------------------------------------
        # GATEWAY
        # --------------------------------------------------

        admitted, reason = self.gateway.admit(
            request,
            token=token,
        )

        if not admitted:

            response = self._response(
                request,
                RelayStatus.REJECTED,
                error=reason,
            )

            self.audit.record_response(
                response
            )

            return response

        # --------------------------------------------------
        # POLICY
        # --------------------------------------------------

        authorized, reason = self.policy.authorize(
            request
        )

        if not authorized:

            response = self._response(
                request,
                RelayStatus.REJECTED,
                error=reason,
            )

            self.audit.record_response(
                response
            )

            return response

        # --------------------------------------------------
        # RESOURCE GATE
        # --------------------------------------------------

        allowed, reason = self.resource_gate.allow(
            request.cpu_budget
        )

        if not allowed:

            response = self._response(
                request,
                RelayStatus.DEFERRED,
                error=reason,
            )

            self.audit.record_response(
                response
            )

            return response

        # --------------------------------------------------
        # QUEUE
        # --------------------------------------------------

        queued = self.queue.put(
            request
        )

        if not queued:

            response = self._response(
                request,
                RelayStatus.REJECTED,
                error="Relay queue unavailable or full.",
            )

            self.audit.record_response(
                response
            )

            return response

        response = self._response(
            request,
            RelayStatus.QUEUED,
        )

        self.audit.record_response(
            response
        )

        return response

    # ------------------------------------------------------
    # WORKER
    # ------------------------------------------------------

    def _worker_loop(self) -> None:
        while self._running:

            request = self.queue.get(
                timeout=0.5
            )

            if request is None:
                continue

            try:
                self._execute(request)

            except Exception as exc:
                response = self._response(
                    request,
                    RelayStatus.FAILED,
                    error=str(exc),
                )

                self.audit.record_response(
                    response
                )

            finally:
                self.queue.task_done()

    def _execute(
        self,
        request: RelayRequest,
    ) -> None:

        allowed, reason = self.resource_gate.allow(
            request.cpu_budget
        )

        if not allowed:

            response = self._response(
                request,
                RelayStatus.DEFERRED,
                error=reason,
            )

            self.audit.record_response(
                response
            )

            return

        try:

            result = self.router.route(
                request
            )

            success = bool(
                isinstance(result, dict)
                and result.get("success", False)
            )

            response = self._response(
                request,
                RelayStatus.SUCCESS
                if success
                else RelayStatus.FAILED,
                result=result,
            )

        except Exception as exc:

            response = self._response(
                request,
                RelayStatus.FAILED,
                error=str(exc),
            )

        self.audit.record_response(
            response
        )

    def emergency_stop(
        self,
        reason: str = "Relay emergency stop.",
    ) -> None:

        self.emergency_controller.engage(
            reason
        )

        self.queue.stop()

    def reset_emergency_stop(self) -> None:

        self.emergency_controller.reset()

        if self._running:
            self.queue.start()

    # ------------------------------------------------------
    # RESPONSE
    # ------------------------------------------------------

    def _response(
        self,
        request: RelayRequest,
        status: RelayStatus,
        *,
        result: Any = None,
        error: Optional[str] = None,
    ) -> RelayResponse:

        return RelayResponse(
            request_id=request.request_id,
            status=status,
            operation=request.operation,
            target=request.target,
            result=result,
            error=error,
            relay_id=self.relay_id,
            metadata={
                "module": MODULE_ID,
                "version": MODULE_VERSION,
                "mission_id": request.mission_id,
                "track_id": request.track_id,
                "channel_id": request.channel_id,
                "qbit_id": request.qbit_id,
                "parent_qbit_id": request.parent_qbit_id,
                "source": request.source,
                "source_of_start": request.source_of_start,
                "classification": request.classification,
                "intent": request.intent,
                "provenance": dict(request.provenance),
            },
        )

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "relay_id": self.relay_id,
            "module": MODULE_ID,
            "version": MODULE_VERSION,

            "running": self._running,

            "queue_depth": self.queue.qsize(),

            "resource": self.resource_gate.snapshot(),

            "github_enabled": self.github.enabled,

            "allowed_operations": sorted(
                self.policy.allowed_operations()
            ),

            "gateway": self.gateway.status(),

            "router": self.router.status(),

            "rate_limiter": self.rate_limiter.status(),

            "emergency_stop": self.emergency_controller.status(),

            "watchdog": self.watchdog.status(),
        }