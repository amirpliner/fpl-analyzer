#!/usr/bin/env python3
"""Learns real price-change thresholds from price_history.json, per
PLAN.md's "כייל את הסף רטרואקטיבית" requirement: for every player whose
cost_change_event flips to nonzero in some snapshot, looks at their
net-transfer share from the PRIOR snapshot (before the change landed)
and uses that distribution to set the rise/fall thresholds instead of
guessing.

Writes data/price_threshold.json, read by price_alerts.py. If no price
changes have happened yet (true for the whole preseason so far -
prices are frozen), leaves the provisional defaults in place and says
so clearly instead of calibrating against nothing.

Usage: python3 scripts/calibrate_price_threshold.py
"""
import json
import os

from price_alerts import DEFAULT_RISE_THRESHOLD_PCT, DEFAULT_FALL_THRESHOLD_PCT

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def main():
    price_history = load("price_history.json")
    bootstrap = load("bootstrap.json")
    if not price_history or not bootstrap:
        print("calibrate: missing price_history.json or bootstrap.json, run fetch_data.py first")
        return

    total_players = bootstrap.get("total_players") or 1
    rise_samples, fall_samples = [], []

    for i in range(1, len(price_history)):
        prev_snap, cur_snap = price_history[i - 1], price_history[i]
        for pid, cur in cur_snap["players"].items():
            if cur["cost_change_event"] == 0:
                continue
            prev = prev_snap["players"].get(pid)
            if not prev:
                continue
            net = prev["transfers_in_event"] - prev["transfers_out_event"]
            pct = round(net / total_players * 100, 3)
            (rise_samples if cur["cost_change_event"] > 0 else fall_samples).append(pct)

    if not rise_samples and not fall_samples:
        print("calibrate: no price changes recorded yet in price_history.json "
              "(expected pre-season - FPL freezes prices until close to the "
              "season). Keeping provisional defaults "
              f"(rise >= {DEFAULT_RISE_THRESHOLD_PCT}%, fall <= {DEFAULT_FALL_THRESHOLD_PCT}%). "
              "Re-run once real price changes start happening.")
        save("price_threshold.json", {
            "rise_threshold_pct": DEFAULT_RISE_THRESHOLD_PCT,
            "fall_threshold_pct": DEFAULT_FALL_THRESHOLD_PCT,
            "calibrated": False,
            "sample_size": 0,
        })
        return

    # Conservative: the lowest net-transfer share that actually preceded a
    # real rise/fall, so the threshold doesn't over-promise.
    rise_threshold = min(rise_samples) if rise_samples else DEFAULT_RISE_THRESHOLD_PCT
    fall_threshold = max(fall_samples) if fall_samples else DEFAULT_FALL_THRESHOLD_PCT

    print(f"calibrate: {len(rise_samples)} rise samples, {len(fall_samples)} fall samples")
    print(f"  rise threshold: {rise_threshold}%, fall threshold: {fall_threshold}%")

    save("price_threshold.json", {
        "rise_threshold_pct": rise_threshold,
        "fall_threshold_pct": fall_threshold,
        "calibrated": True,
        "sample_size": len(rise_samples) + len(fall_samples),
    })


if __name__ == "__main__":
    main()
