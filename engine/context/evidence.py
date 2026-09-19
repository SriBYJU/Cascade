from __future__ import annotations

from typing import Any

from ..schemas import EvidencePacket


REQUIRED_PACKET_FIELDS = {
    "status", "changed_files", "validation", "evidence", "risk", "unresolved",
    "summary", "scope_deviation",
}


def parse_evidence_packet(data: dict[str, Any]) -> EvidencePacket:
    missing = REQUIRED_PACKET_FIELDS - data.keys()
    if missing:
        raise ValueError(f"malformed evidence packet; missing fields: {sorted(missing)}")
    return EvidencePacket.model_validate(data)


def compact_packet(packet: EvidencePacket, max_summary_chars: int = 1200) -> EvidencePacket:
    data = packet.model_dump(mode="json")
    if len(data["summary"]) > max_summary_chars:
        data["summary"] = data["summary"][: max_summary_chars - 1] + "…"
    return EvidencePacket.model_validate(data)
