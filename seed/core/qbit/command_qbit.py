# ==========================================================
# FILE: command_qbit.py
# PATH: SEED_ROOT/seed/core/qbit/command_qbit.py
# VERSION: 1.0.0
# ROLE: Canonical structured command/recovery Qbit factory
# AUTHORITY: Qbit carries data; QbitDialer admits commands.
# ==========================================================
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .qbit import Qbit, QbitSourceMode

class CommandQbit:
    """Builds deterministic command carriers without executing them."""

    @staticmethod
    def build(
        command: str,
        *,
        who: Any,
        what: Any,
        where: Any,
        why: str,
        when: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        track_id: Optional[str] = None,
        parent_qbit_id: Optional[str] = None,
        generation: int = 0,
        source: str = "SEED_CORE",
        mode: str = "DETERMINISTIC",
    ) -> Qbit:
        when = when or datetime.now(timezone.utc).isoformat()
        payload_data = {
            "command": command,
            "who": who,
            "what": what,
            "where": where,
            "when": when,
            "why": why,
            "track_id": track_id,
            "parent_qbit_id": parent_qbit_id,
            "generation": generation,
            "data": dict(data or {}),
        }
        qbit = Qbit.create_task(
            command=command,
            action="COMMAND",
            task_id=None,
            meta={
                "source": source,
                "schema": "COMMAND_QBIT_V1",
                "mode": mode,
                "who": who,
                "what": what,
                "where": where,
                "when": when,
                "why": why,
                "track_id": track_id,
            },
            name=f"COMMAND:{command}",
            intent=command,
            source_mode=QbitSourceMode.SYSTEM,
            source=source,
            producer="CommandQbit",
            creation_reason=why,
            upstream_source=source,
            who=who,
            what=what,
            where=where,
            when=when,
            why=why,
            track_id=track_id,
            parent_qbit_id=parent_qbit_id,
            generation=generation,
            command_type="COMMAND",
            command_data=payload_data,
        )
        qbit.payload["data"]["command_context"] = payload_data
        qbit.flags["command_qbit"] = True
        qbit.flags["execution_required"] = True
        return qbit

    @staticmethod
    async def submit(qbit: Qbit, dialer: Any) -> Any:
        """Admit the existing Qbit through the authoritative cognitive receive path."""
        if dialer is None:
            raise RuntimeError("QbitDialer unavailable")
        submit = getattr(dialer, "submit_qbit_command", None)
        if not callable(submit):
            raise RuntimeError("QbitDialer.submit_qbit_command unavailable")
        return await submit(qbit)
