"""Download the public Polish XTB specification, without account connectivity.

Raw pages are resumable under data/generated; no live dependency is used by tests.
Run explicitly, then normalize/validate before replacing the packaged snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

URL = "https://www.xtb.com/web-api/v2/languages/pl/branches/pl/instruments"
CACHE = Path("data/generated/xtb-pages")


async def download(*, resume: bool = False) -> None:
    await asyncio.to_thread(CACHE.mkdir, parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(4)
    manifest_path = CACHE / "manifest.json"
    if manifest_path.exists() and not resume:
        raise ValueError(
            "Cache already exists: use --resume for this run or archive it for a refresh"
        )
    async with httpx.AsyncClient(timeout=45, follow_redirects=False) as client:
        initial: dict[str, Any]
        if resume and manifest_path.exists():
            initial = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            response = await client.get(URL)
            response.raise_for_status()
            initial = response.json()
            manifest_path.write_text(json.dumps(initial), encoding="utf-8")

        async def page(kind: str, number: int) -> None:
            path = CACHE / f"{kind}-{number}.json"
            if path.exists():
                return
            async with semaphore:
                for attempt in range(4):
                    try:
                        result = await client.get(URL, params={"typeSlug": kind, "page": number})
                        result.raise_for_status()
                        payload = result.json()
                        if not payload.get("instrumentsCollectionLimited", {}).get(kind):
                            raise ValueError(f"Empty page: {kind} {number}")
                        path.write_text(json.dumps(payload), encoding="utf-8")
                        break
                    except (httpx.HTTPError, ValueError):
                        if attempt == 3:
                            raise
                        await asyncio.sleep(2 ** (attempt + 1))
                await asyncio.sleep(0.15)

        for kind in initial["instrumentTypes"]:
            count = initial["instrumentCounts"][kind]
            await asyncio.gather(*(page(kind, n) for n in range(1, (count + 9) // 10 + 1)))
            print(f"{kind}: downloaded {count} advertised entries", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume", action="store_true", help="Resume the existing download manifest"
    )
    asyncio.run(download(resume=parser.parse_args().resume))
