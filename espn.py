def fetch_games(days_ahead: int = 2) -> list[Game]:
    today = dt.datetime.now(dt.timezone.utc).date()
    seen: dict[str, Game] = {}
    for offset in range(-1, days_ahead + 1):          # yesterday .. +days_ahead (UTC/US timezone safety)
        day = today + dt.timedelta(days=offset)
        r = requests.get(SCOREBOARD, params={"dates": day.strftime("%Y%m%d")}, timeout=30)
        if not r.ok:
            print(f"ESPN {day}: HTTP {r.status_code} {r.text[:200]!r} - skipped")
            continue
        for g in parse_events(r.json()):
            seen[g.id] = g
    return sorted(seen.values(), key=lambda g: g.kickoff)
