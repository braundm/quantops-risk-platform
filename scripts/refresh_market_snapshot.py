"""Explicitly refresh the checked-in market-price fixture; no transactions are imported."""

import json

from quantops_api.application.market_snapshot import SNAPSHOT_PATH, fetch_market_snapshot

if __name__ == "__main__":
    snapshot = fetch_market_snapshot()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Saved sourced prices through {snapshot['as_of']}; ownership remains simulated.")
