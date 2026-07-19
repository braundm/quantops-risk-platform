"""Small deterministic documentation hygiene checks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "HANDOFF.md",
    ROOT / "docs" / "progress.md",
    ROOT / "docs" / "implementation-plan.md",
    ROOT / "docs" / "risk-register.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXCLUDED_DIRECTORIES = {".git", ".venv", ".uv-cache", "node_modules"}


def markdown_documents() -> list[Path]:
    """Return repository-owned Markdown documents in deterministic order."""

    return sorted(
        document
        for document in ROOT.rglob("*.md")
        if not EXCLUDED_DIRECTORIES.intersection(document.relative_to(ROOT).parts)
    )


def main() -> int:
    """Reject missing required files and broken relative Markdown links."""

    errors: list[str] = []
    for required in REQUIRED:
        if not required.is_file():
            errors.append(f"missing required document: {required.relative_to(ROOT)}")

    documents = markdown_documents()
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_part = target.split("#", maxsplit=1)[0]
            if path_part and not (document.parent / path_part).resolve().exists():
                errors.append(f"broken link in {document.relative_to(ROOT)}: {target}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"Documentation checks passed for {len(documents)} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
