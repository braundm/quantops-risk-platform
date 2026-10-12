from __future__ import annotations

from pathlib import Path

from scripts.security_scan import MAXIMUM_FILE_BYTES, scan_paths


def test_clean_text_and_binary_are_accepted(tmp_path: Path) -> None:
    text = tmp_path / "safe.txt"
    text.write_text("synthetic fixture without credentials\n", encoding="utf-8")
    binary = tmp_path / "image.bin"
    binary.write_bytes(b"\x00\x01\x02")

    assert scan_paths((text, binary), tmp_path) == ()


def test_private_key_and_token_are_reported_without_secret_value(tmp_path: Path) -> None:
    key = "-----BEGIN " + "PRIVATE KEY-----"
    token = "gh" + "p_" + ("A" * 36)
    unsafe = tmp_path / "unsafe.txt"
    unsafe.write_text(f"{key}\n{token}\n", encoding="utf-8")

    findings = scan_paths((unsafe,), tmp_path)

    assert [finding.code for finding in findings] == ["private_key", "github_classic_token"]
    assert all(token not in finding.render() for finding in findings)


def test_sensitive_filename_and_large_file_are_rejected(tmp_path: Path) -> None:
    environment = tmp_path / ".env"
    environment.write_text("PLACEHOLDER=true\n", encoding="utf-8")
    oversized = tmp_path / "oversized.bin"
    oversized.write_bytes(b"x" * (MAXIMUM_FILE_BYTES + 1))

    findings = scan_paths((environment, oversized), tmp_path)

    assert [finding.code for finding in findings] == [
        "disallowed_sensitive_filename",
        f"file_exceeds_{MAXIMUM_FILE_BYTES}_bytes",
    ]


def test_large_catalog_exception_still_scans_for_secrets(tmp_path: Path) -> None:
    catalog = tmp_path / "apps/api/quantops_api/data/broker_catalog.json"
    catalog.parent.mkdir(parents=True)
    token = "gh" + "p_" + ("A" * 36)
    catalog.write_text(" " * MAXIMUM_FILE_BYTES + token, encoding="utf-8")

    findings = scan_paths((catalog,), tmp_path)

    assert [finding.code for finding in findings] == ["github_classic_token"]
    assert all(token not in finding.render() for finding in findings)
