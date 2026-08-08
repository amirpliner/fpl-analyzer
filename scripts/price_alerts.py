"""Price-rise/fall alerts. FPL doesn't publish the real price-change
algorithm, so this is a heuristic built from net transfer volume
(normalized by total managers, from bootstrap's total_players) and its
velocity between price_history.json snapshots.

KNOWN LIMITATION: the thresholds below are provisional defaults, not
calibrated - see calibrate_price_threshold.py, which learns real
thresholds from price_history.json once actual price changes have
happened (confirmed: zero so far this preseason - prices are frozen
until close to the season). Every alert is tagged "provisional" vs
"calibrated" so the UI can be honest about which it's showing.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_RISE_THRESHOLD_PCT = 0.6
DEFAULT_FALL_THRESHOLD_PCT = -0.6


def net_transfers_pct(player, total_players):
    net = (player.get("transfers_in_event") or 0) - (player.get("transfers_out_event") or 0)
    if not total_players:
        return 0.0
    return round(net / total_players * 100, 3)


def velocity(player_id, price_history):
    """Change in net-transfer share between the last two snapshots -
    positive means momentum is accelerating toward a rise."""
    if len(price_history) < 2:
        return None
    pid = str(player_id)
    recent = [snap["players"].get(pid) for snap in price_history[-2:]]
    if not all(recent):
        return None
    net_a = recent[0]["transfers_in_event"] - recent[0]["transfers_out_event"]
    net_b = recent[1]["transfers_in_event"] - recent[1]["transfers_out_event"]
    return net_b - net_a


def load_thresholds():
    path = os.path.join(DATA_DIR, "price_threshold.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("rise_threshold_pct", DEFAULT_RISE_THRESHOLD_PCT),
            data.get("fall_threshold_pct", DEFAULT_FALL_THRESHOLD_PCT),
            data.get("calibrated", False),
        )
    return DEFAULT_RISE_THRESHOLD_PCT, DEFAULT_FALL_THRESHOLD_PCT, False


def build_price_alerts(players, price_history, total_players):
    rise_th, fall_th, calibrated = load_thresholds()
    alerts = []
    for p in players:
        pct = net_transfers_pct(p, total_players)
        if pct >= rise_th:
            direction = "rising"
        elif pct <= fall_th:
            direction = "falling"
        else:
            continue
        alerts.append({
            "id": p["id"],
            "name": p["name"],
            "team": p["team"],
            "net_transfers_pct": pct,
            "velocity": velocity(p["id"], price_history),
            "direction": direction,
            "confidence": "calibrated" if calibrated else "provisional",
        })
    alerts.sort(key=lambda a: abs(a["net_transfers_pct"]), reverse=True)
    return {
        "alerts": alerts,
        "rise_threshold_pct": rise_th,
        "fall_threshold_pct": fall_th,
        "calibrated": calibrated,
    }
