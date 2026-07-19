"""Source authority rules for the Survivor.io optimizer."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Mapping


class SourceAuthority(IntEnum):
    UNKNOWN = 0
    EXTERNAL_CORROBORATION = 1
    USER_DISCORD_OR_PDF = 2
    SIO_RUNTIME = 3


SOURCE_AUTHORITY_LABELS = {
    SourceAuthority.SIO_RUNTIME: "sio_runtime_bible",
    SourceAuthority.USER_DISCORD_OR_PDF: "user_discord_or_pdf_bible",
    SourceAuthority.EXTERNAL_CORROBORATION: "external_corroboration",
    SourceAuthority.UNKNOWN: "unknown",
}


def source_authority(record: Mapping[str, Any]) -> SourceAuthority:
    source = str(record.get("source") or record.get("source_type") or "").lower()
    if any(token in source for token in ("sio", "exp0", "webpack", "runtime_module")):
        return SourceAuthority.SIO_RUNTIME
    if any(token in source for token in ("discord", "optimizer_source_reference", "source_database_map", "user_pdf")):
        return SourceAuthority.USER_DISCORD_OR_PDF
    if any(token in source for token in ("youtube", "reddit", "bilibili", "douyin", "tieba", "game8", "community")):
        return SourceAuthority.EXTERNAL_CORROBORATION
    return SourceAuthority.UNKNOWN


def external_record_is_usable(record: Mapping[str, Any]) -> bool:
    """External facts are usable only after they align with a Bible source."""
    if source_authority(record) != SourceAuthority.EXTERNAL_CORROBORATION:
        return True
    return bool(record.get("matches_sio") or record.get("matches_user_bible"))


def confidence_label(record: Mapping[str, Any]) -> str:
    authority = source_authority(record)
    if authority == SourceAuthority.SIO_RUNTIME:
        return "correct_sio_runtime"
    if authority == SourceAuthority.USER_DISCORD_OR_PDF:
        return "correct_user_bible"
    if authority == SourceAuthority.EXTERNAL_CORROBORATION and external_record_is_usable(record):
        return "corroborated_matches_bible"
    return "unknown"
