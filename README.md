# NFL Reel Bot (ESPN → video → Facebook Page Reel)

Every 30 min a GitHub Action runs `main.py`:
1. Pulls the NFL schedule from ESPN (JSON feed behind espn.com/nfl/schedule)
2. Picks games kicking off in 4–5 hours that aren't posted yet (`posted.json`)
3. Renders a 6s 9:16 reel: your base video + both team logos/names + kickoff time
4. Publishes it to your Facebook Page as a Reel

## Setup
1. Facebook: create an app (developers.facebook.com), add yourself as admin of the Page, generate a
   **long-lived Page access token** with `pages_show_list, pages_read_engagement, pages_manage_posts`
   (Graph API Explorer → exchange for long-lived → GET /me/accounts for the Page token). Note the Page ID.
2. Push this folder to a GitHub repo. Settings → Secrets → Actions: add `FB_PAGE_ID`, `FB_PAGE_TOKEN`.
3. Change `DISPLAY_TZ` in `.github/workflows/post.yml` if you want another timezone on the video.
4. Actions tab → "NFL reel bot" → Run workflow to test.

## Local testing
    pip install -r requirements.txt   # and have ffmpeg installed
    python main.py --mock --dry-run              # render a sample, no posting
    python main.py --all-upcoming --dry-run      # render real upcoming games (needs internet)
    cp .env.example .env && python main.py       # real run

Swap the base video: replace `assets/base.mp4` (keep 9:16, 3-90s).
