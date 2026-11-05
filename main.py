"""NFL reel bot: every run, post a team-specific reel for games kicking off in 4-5 hours."""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path
from zoneinfo import ZoneInfo

import espn, render, facebook

ROOT = Path(__file__).parent
STATE = ROOT / "posted.json"
BASE_VIDEO = ROOT / "assets" / "base.mp4"


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def kickoff_text(g, tz: ZoneInfo) -> str:
    t = g.kickoff.astimezone(tz)
    return t.strftime("%a, %b %d  •  %I:%M %p %Z").upper().replace(" 0", " ")


def caption(g, tz: ZoneInfo) -> str:
    t = g.kickoff.astimezone(tz).strftime("%a %b %d, %I:%M %p %Z").replace(" 0", " ")
    tags = " ".join("#" + re.sub(r"\W", "", x.name) for x in (g.away, g.home))
    return (f"🏈 {g.away.city} {g.away.name} vs {g.home.city} {g.home.name}\n"
            f"⏰ Kickoff: {t}\n"
            f"Who's taking this one? Drop your pick 👇\n\n"
            f"#NFL #GameDay {tags}")


MOCK = {"events": [{
    "id": "mock1", "date": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=4.5)).strftime("%Y-%m-%dT%H:%MZ"),
    "status": {"type": {"state": "pre"}},
    "competitions": [{"competitors": [
        {"homeAway": "home", "team": {"location": "Los Angeles", "name": "Rams", "abbreviation": "LAR", "color": "003594",
                                      "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png"}},
        {"homeAway": "away", "team": {"location": "Seattle", "name": "Seahawks", "abbreviation": "SEA", "color": "002244",
                                      "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png"}}]}]}]}


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render videos but do not post")
    ap.add_argument("--mock", action="store_true", help="use a built-in sample game (no network for schedule)")
    ap.add_argument("--all-upcoming", action="store_true", help="ignore the 4-5h window (for testing renders)")
    a = ap.parse_args()

    tz = ZoneInfo(os.environ.get("DISPLAY_TZ", "America/New_York"))
    lo = float(os.environ.get("POST_MIN_HOURS", 4))
    hi = float(os.environ.get("POST_MAX_HOURS", 5))
    cap = int(os.environ.get("MAX_POSTS_PER_RUN", 10))

    games = espn.parse_events(MOCK) if a.mock else espn.fetch_games()
    posted = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)

    due = []
    for g in games:
        hrs = (g.kickoff - now).total_seconds() / 3600
        if g.state != "pre" or g.id in posted:
            continue
        if a.all_upcoming or lo <= hrs <= hi:
            due.append(g)
    print(f"{len(games)} games fetched, {len(due)} due now")

    count = 0
    for g in due:
        if cap and count >= cap:
            print("per-run cap reached; remaining games wait for the next run")
            break
        label = f"{g.away.abbr} @ {g.home.abbr}"
        print(f"→ {label}")
        out = render.render_reel(g, kickoff_text(g, tz), BASE_VIDEO,
                                 ROOT / "out" / f"{g.id}_{g.away.abbr}_{g.home.abbr}.mp4", ROOT / "out" / "tmp")
        if a.dry_run:
            print(f"  rendered {out} (dry run, not posted)")
            continue
        vid = facebook.post_reel(str(out), caption(g, tz), os.environ["FB_PAGE_ID"],
                                 os.environ["FB_PAGE_TOKEN"], os.environ.get("FB_GRAPH_VERSION", "v23.0"))
        posted[g.id] = {"game": label, "fb_video_id": vid, "posted_at": now.isoformat()}
        STATE.write_text(json.dumps(posted, indent=2))   # save after each post so a crash can't duplicate
        print(f"  posted reel {vid}")
        count += 1


if __name__ == "__main__":
    sys.exit(main())
