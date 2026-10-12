"""Fetch fixed public Bossa reference sources, without login or broker account access."""

from pathlib import Path

import httpx

GENERATED = Path("data/generated")
PDF_URL = (
    "https://bossa.pl/sites/b30/files/2026-07/document/"
    "Lista_wszystkich_instrumentow_zagranicznych_22-06-2026.pdf"
)


def download() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    sources = {
        "bossa-world-pdf.pdf": PDF_URL,
        "bossafx.txt": "https://bossafx.pl/oferta/instrumenty",
    }
    for category in (
        "akcje",
        "newconnect",
        "globalconnect",
        "opcje",
        "kontrakty",
        "etf",
        "obligacje",
        "certyfikaty",
    ):
        sources[f"bossa-{category}.json"] = f"https://bossa.pl/wats_api/API/market/group/{category}"
    with httpx.Client(timeout=45, follow_redirects=False) as client:
        for filename, url in sources.items():
            response = client.get(url)
            response.raise_for_status()
            if filename.endswith(".pdf") and not response.content.startswith(b"%PDF"):
                raise ValueError("Expected the dated PDF specification")
            if filename.endswith(".json"):
                response.json()
            (GENERATED / filename).write_bytes(response.content)
            print(f"Fetched public reference source: {filename}", flush=True)


if __name__ == "__main__":
    download()
