# ==========================================================
# FILE: qbit_router.py
# PATH: C:\SEED_ROOT\seed\core\router\qbit_router.py
# VERSION: 3.0.0
# BUILD: QBIT-ROUTER / AUTHORITATIVE-ROUTING
#
# PURPOSE:
#   Resolve Qbits to processing handlers.
#
# AUTHORITY:
#
#   QbitRouter
#       = routing authority
#
#   Qbit
#       = carrier / identity / state
#
#   QbitQueueLoop
#       = transport
#
#   QbitDialer
#       = processing + command authority
#
# HARD RULES:
#
#   1. Router does NOT execute handlers.
#   2. Router does NOT create Qbits.
#   3. Router does NOT create commands.
#   4. Router does NOT replace TrackIDs.
#   5. Router does NOT own the processing loop.
#   6. Router returns the handler selected for the Qbit.
# ==========================================================

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple


logger = logging.getLogger("QbitRouter")


__all__ = [
    "QbitRouter",
]


class QbitRouter:

    # ======================================================
    # CONSTRUCTION
    # ======================================================

    def __init__(
        self,
        *,
        default_intent: str = "system",
        default_action: str = "noop",
    ):

        self.routes: Dict[
            Tuple[str, str],
            Callable,
        ] = {}

        self.default_route = (
            str(default_intent),
            str(default_action),
        )

        self._registrations = 0

    # ======================================================
    # ROUTE REGISTRATION
    # ======================================================

    def register(
        self,
        intent: str,
        action: str,
        handler: Callable,
        *,
        replace: bool = True,
    ):

        if not isinstance(intent, str):
            raise TypeError(
                "QbitRouter intent must be str"
            )

        if not isinstance(action, str):
            raise TypeError(
                "QbitRouter action must be str"
            )

        if not callable(handler):
            raise TypeError(
                "QbitRouter handler must be callable"
            )

        key = (
            intent,
            action,
        )

        if (
            not replace
            and key in self.routes
        ):
            raise RuntimeError(
                f"QbitRouter route already registered: {key}"
            )

        self.routes[key] = handler

        self._registrations += 1

        logger.debug(
            "[QbitRouter] Route registered | "
            "intent=%s | action=%s | handler=%s",
            intent,
            action,
            getattr(
                handler,
                "__name__",
                type(handler).__name__,
            ),
        )

        return handler

    # ======================================================
    # UNREGISTER
    # ======================================================

    def unregister(
        self,
        intent: str,
        action: str,
    ):

        return self.routes.pop(
            (
                intent,
                action,
            ),
            None,
        )

    # ======================================================
    # DEFAULT ROUTE
    # ======================================================

    def set_default(
        self,
        intent: str,
        action: str,
    ):

        self.default_route = (
            str(intent),
            str(action),
        )

        return self.default_route

    # ======================================================
    # RESOLUTION
    # ======================================================

    def resolve(
        self,
        qbit: Any,
    ) -> Optional[Callable]:

        if qbit is None:
            return self.routes.get(
                self.default_route
            )

        intent = getattr(
            qbit,
            "intent",
            None,
        )

        action = getattr(
            qbit,
            "action",
            None,
        )

        # --------------------------------------------------
        # Normalize route values.
        # --------------------------------------------------

        if intent is None:
            intent = "system"

        if action is None:
            action = "noop"

        key = (
            str(intent),
            str(action),
        )

        handler = self.routes.get(
            key
        )

        if handler is not None:
            return handler

        # --------------------------------------------------
        # Default route.
        # --------------------------------------------------

        return self.routes.get(
            self.default_route
        )

    # ======================================================
    # ROUTE EXISTENCE
    # ======================================================

    def has_route(
        self,
        intent: str,
        action: str,
    ) -> bool:

        return (
            intent,
            action,
        ) in self.routes

    # ======================================================
    # ROUTE COUNT
    # ======================================================

    @property
    def route_count(self) -> int:

        return len(
            self.routes
        )

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def snapshot(self) -> Dict[str, Any]:

        return {
            "route_count": self.route_count,
            "registrations": self._registrations,
            "default_route": self.default_route,
            "routes": [
                {
                    "intent": intent,
                    "action": action,
                    "handler": getattr(
                        handler,
                        "__name__",
                        type(handler).__name__,
                    ),
                }
                for (
                    intent,
                    action,
                ), handler
                in self.routes.items()
            ],
        }