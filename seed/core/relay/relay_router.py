# ==========================================================
# FILE: relay_router.py
# PATH: SEED_ROOT/seed/core/relay/relay_router.py
# VERSION: 2.0.0
# PURPOSE: Route approved relay operations
# ==========================================================

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .relay_protocol import RelayRequest


MODULE_ID = "CORE_RELAY_ROUTER"
MODULE_VERSION = "2.0.0"


class RelayRouter:

    def __init__(self):
        self._routes: Dict[
            str,
            Callable[[RelayRequest], Any],
        ] = {}

    def register(
        self,
        operation: str,
        handler: Callable[[RelayRequest], Any],
    ) -> None:

        if not callable(handler):
            raise TypeError(
                "Relay route handler must be callable."
            )

        key = str(operation).strip().upper()

        if not key:
            raise ValueError(
                "Relay operation cannot be empty."
            )

        self._routes[key] = handler

    def unregister(
        self,
        operation: str,
    ) -> None:

        self._routes.pop(
            str(operation).strip().upper(),
            None,
        )

    def resolve(
        self,
        operation: str,
    ) -> Optional[Callable]:

        return self._routes.get(
            str(operation).strip().upper()
        )

    def route(
        self,
        request: RelayRequest,
    ) -> Any:

        handler = self.resolve(
            request.operation
        )

        if handler is None:
            raise LookupError(
                f"No relay route registered for "
                f"{request.operation}"
            )

        return handler(request)

    def operations(self) -> list[str]:
        return sorted(self._routes.keys())

    def status(self) -> dict:
        return {
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "route_count": len(self._routes),
            "routes": self.operations(),
        }