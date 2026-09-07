"""Builds data/news_feed.json: FPL's own official per-player `news`
text (the same field analysis.py's injury_flag() already trusts for
the user's own squad) as a chronological feed, plus this gameweek's
most net-transferred-in players ("hot"). Pure transform, no I/O -
matches build_static.py's style.
"""

NEWS_FEED_LIMIT = 20
HOT_PLAYERS_LIMIT = 10


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_news_feed(bootstrap):
    items = []
    for p in bootstrap["elements"]:
        if not p.get("news"):
            continue
        items.append({
            "id": p["id"],
            "web_name": p["web_name"],
            "team": p["team"],
            "news": p["news"],
            "news_added": p.get("news_added"),
            "chance_of_playing_next_round": p.get("chance_of_playing_next_round"),
        })
    items.sort(key=lambda x: x["news_added"] or "", reverse=True)
    news = items[:NEWS_FEED_LIMIT]

    def net_transfers(p):
        return (p.get("transfers_in_event") or 0) - (p.get("transfers_out_event") or 0)

    hot_players = [
        {
            "id": p["id"],
            "web_name": p["web_name"],
            "team": p["team"],
            "net_transfers": net_transfers(p),
            "form": _num(p["form"]),
            "owned": _num(p["selected_by_percent"]),
        }
        for p in sorted(bootstrap["elements"], key=net_transfers, reverse=True)[:HOT_PLAYERS_LIMIT]
        if net_transfers(p) > 0
    ]

    return {"news": news, "hot_players": hot_players}
