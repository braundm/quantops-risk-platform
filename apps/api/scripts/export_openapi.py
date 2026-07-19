"""Export the deterministic OpenAPI document for client generation or compatibility checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quantops_api.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional destination; stdout is used when omitted",
    )
    arguments = parser.parse_args()
    document = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        sys.stdout.write(document)
        return
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(document, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
