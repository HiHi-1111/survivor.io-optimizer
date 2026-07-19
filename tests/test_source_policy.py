from optimizer.source_policy import (
    SourceAuthority,
    confidence_label,
    external_record_is_usable,
    source_authority,
)


def test_sio_is_highest_authority():
    row = {"source": "sio runtime_module_67727"}
    assert source_authority(row) == SourceAuthority.SIO_RUNTIME
    assert confidence_label(row) == "correct_sio_runtime"


def test_user_pdf_is_bible_source():
    row = {"source": "optimizer_source_reference.pdf"}
    assert source_authority(row) == SourceAuthority.USER_DISCORD_OR_PDF


def test_external_source_requires_bible_alignment():
    row = {"source": "youtube guide"}
    assert external_record_is_usable(row) is False
    row["matches_sio"] = True
    assert external_record_is_usable(row) is True
    assert confidence_label(row) == "corroborated_matches_bible"
