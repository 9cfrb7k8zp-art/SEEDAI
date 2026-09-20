# ========================================================================
# File: emit_wrapper.py
# Path: seed/core/emitters/emit_wrapper.py
# VERSION: 2.0.0
#
# PURPOSE:
#   Lightweight emit adapter between Qbit / Dialers and SEEDEventBus.
#
#   Rules:
#   - Safe during bootstrap
#   - No circular imports
#   - Never creates an EventBus
#   - Never replaces the authoritative EventBus
#   - Supports both attach() and attach_bus()
#   - Provides callable emission for QbitDialer
#   - Preserves publish() compatibility
#   - Telemetry failures do not crash the runtime
# ========================================================================

import logging
from typing import Optional, Any, Dict


logger = logging.getLogger("EmitWrapper")


class EmitWrapper:

    # ====================================================================
    # CONSTRUCTOR
    # ====================================================================

    def __init__(
        self,
        bus=None,
        event_bus=None,
    ):

        # --------------------------------------------------------------
        # Resolve the authoritative bus.
        #
        # Do NOT create one here.
        # --------------------------------------------------------------

        if event_bus is not None:

            self.event_bus = event_bus

        elif bus is not None:

            self.event_bus = bus

        else:

            self.event_bus = None

        # Preserve compatibility for code that checks .bus.
        self.bus = self.event_bus

    # ====================================================================
    # AUTHORITATIVE EVENTBUS ATTACHMENT
    # ====================================================================

    def attach(
        self,
        event_bus,
    ):

        if event_bus is None:

            raise ValueError(
                "EmitWrapper.attach() requires an EventBus"
            )

        self.event_bus = event_bus
        self.bus = event_bus

        logger.info(
            "[EmitWrapper] Authoritative EventBus attached | type=%s",
            type(event_bus).__name__,
        )

        return self

    # ====================================================================
    # COMPATIBILITY ALIAS
    # ====================================================================

    def attach_bus(
        self,
        event_bus,
    ):

        return self.attach(
            event_bus
        )

    # ====================================================================
    # EVENTBUS VALIDATION
    # ====================================================================

    def _get_event_bus(self):

        return self.event_bus

    # ====================================================================
    # CALLABLE EMITTER
    # ====================================================================

    def __call__(
        self,
        event,
        payload=None,
        source=None,
        **kwargs,
    ):

        return self.publish(
            event=event,
            payload=payload,
            source=source,
            **kwargs,
        )

    # ====================================================================
    # PUBLISH
    # ====================================================================

    def publish(
        self,
        event: str,
        payload: Optional[Any] = None,
        source: Optional[Any] = None,
        **kwargs,
    ):

        event_bus = self.event_bus

        if event_bus is None:

            logger.debug(
                "[EmitWrapper] Dropped event '%s' "
                "(no EventBus attached)",
                event,
            )

            return False

        if payload is None:

            payload = {}

        if source is None:

            source = "EmitWrapper"

        # --------------------------------------------------------------
        # Preferred EventBus API
        # --------------------------------------------------------------

        publish = getattr(
            event_bus,
            "publish",
            None,
        )

        if callable(
            publish
        ):

            try:

                return publish(
                    event=event,
                    payload=payload,
                    source=source,
                    **kwargs,
                )

            except TypeError:

                # ------------------------------------------------------
                # Compatibility fallback for buses that do not accept
                # keyword arguments exactly as expected.
                # ------------------------------------------------------

                try:

                    return publish(
                        event,
                        payload,
                        source,
                    )

                except Exception as exc:

                    logger.error(
                        "[EmitWrapper] "
                        "EventBus.publish failed for '%s': %s",
                        event,
                        exc,
                        exc_info=True,
                    )

                    return False

            except Exception as exc:

                logger.error(
                    "[EmitWrapper] "
                    "EventBus.publish failed for '%s': %s",
                    event,
                    exc,
                    exc_info=True,
                )

                return False

        # --------------------------------------------------------------
        # Compatibility with EventBus implementations that expose
        # emit() instead of publish().
        # --------------------------------------------------------------

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if callable(
            emit
        ):

            try:

                return emit(
                    event,
                    payload,
                    **kwargs,
                )

            except TypeError:

                try:

                    return emit(
                        event,
                        payload,
                    )

                except Exception as exc:

                    logger.error(
                        "[EmitWrapper] "
                        "EventBus.emit failed for '%s': %s",
                        event,
                        exc,
                        exc_info=True,
                    )

                    return False

            except Exception as exc:

                logger.error(
                    "[EmitWrapper] "
                    "EventBus.emit failed for '%s': %s",
                    event,
                    exc,
                    exc_info=True,
                )

                return False

        # --------------------------------------------------------------
        # No compatible EventBus API.
        # --------------------------------------------------------------

        logger.error(
            "[EmitWrapper] "
            "Authoritative EventBus has neither "
            "publish() nor emit() | type=%s",
            type(event_bus).__name__,
        )

        return False

    # ====================================================================
    # STATUS
    # ====================================================================

    @property
    def attached(self) -> bool:

        return self.event_bus is not None


# ========================================================================
# EMIT STUB
# ========================================================================
#
# Compatibility-only emitter.
#
# This does NOT create an EventBus.
# It is useful during isolated construction/testing.
# ========================================================================


class EmitStub:

    def __call__(
        self,
        event_name,
        payload=None,
        **kwargs,
    ):

        print(
            f"[EMIT STUB] "
            f"{event_name} => {payload}"
        )

        return True