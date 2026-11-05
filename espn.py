"""Fetch upcoming NFL games from ESPN's public JSON feed (same data as espn.com/nfl/schedule)."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
import requests

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


@dataclass
class Team:
    city: str
    name: str          # e.g. "Chiefs"
    abbr: str          # e.g. "KC"
    color: str         # hex without '#'
    logo: str | None   # URL


@dataclass
class Game:
    id: str
    kickoff: dt.datetime   # timezone-aware UTC
    away: Team
    home: Team
    state: str             # "pre" | "in" | "post"


def _team(c: dict) -> Team:
    t = c["team"]
    return Team(
        city=t.get("location") or t.get("displayName", ""),
        name=t.get("name") or t.get("shortDisplayName") or t.get("displayName", ""),
        abbr=t.get("abbreviation", "")[:4],
        color=(t.get("color") or "1b1b1b").lstrip("#"),
        logo=t.get("logo") or (t.get("logos") or [{}])[0].get("href"),
    )


def parse_events(data: dict) -> list[Game]:
    games: list[Game] = []
    for ev in data.get("events", []):
        try:
            comp = ev["competitions"][0]
            by_side = {c["homeAway"]: c for c in comp["competitors"]}
            when = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
            games.append(Game(
                id=str(ev["id"]),
                kickoff=when.astimezone(dt.timezone.utc),
                away=_team(by_side["away"]),
                home=_team(by_side["home"]),
                state=ev.get("status", {}).get("type", {}).get("state", "pre"),
            ))
        except (KeyError, IndexError, ValueError):
            continue  # skip malformed / TBD entries
    return sorted(games, key=lambda g: g.kickoff)


def fetch_games(days_ahead: int = 2) -> list[Game]:
    today = dt.datetime.now(dt.timezone.utc).date()
    seen: dict[str, Game] = {}
    for offset in range(-1, days_ahead + 1):
        day = today + dt.timedelta(days=offset)
        r = requests.get(SCOREBOARD, params={"dates": day.strftime("%Y%m%d")}, timeout=30)
        if not r.ok:
            print(f"ESPN {day}: HTTP {r.status_code} {r.text[:200]!r} - skipped")
            continue
        for g in parse_events(r.json()):
            seen[g.id] = g
    return sorted(seen.values(), key=lambda g: g.kickoff)
