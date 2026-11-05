"""Build a 6s 9:16 reel: base video + team overlay (logos, names, kickoff time) via Pillow + ffmpeg."""
from __future__ import annotations
import io, subprocess
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(draw, text, max_w, start, min_size=26):
    s = start
    while s > min_size and draw.textlength(text, font=font(s)) > max_w:
        s -= 2
    return font(s)


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def get_logo(team, size: int) -> Image.Image:
    """Logo on a white disc; falls back to a coloured disc with the abbreviation."""
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(disc)
    d.ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255, 245))
    logo = None
    if team.logo:
        try:
            r = requests.get(team.logo, timeout=20)
            r.raise_for_status()
            logo = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception as e:
            print(f"  logo download failed for {team.abbr}: {e}")
    if logo:
        pad = int(size * 0.14)
        logo.thumbnail((size - 2 * pad, size - 2 * pad))
        disc.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    else:
        d.ellipse((6, 6, size - 7, size - 7), fill=hex_rgb(team.color) + (255,))
        f = fit(d, team.abbr, size - 30, 64)
        d.text((size / 2, size / 2), team.abbr, font=f, fill="white", anchor="mm")
    return disc


def make_overlay(game, kickoff_text: str, out_png: Path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # top gradient for readability
    for y in range(0, 460):
        a = int(200 * (1 - y / 460) ** 1.4)
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))

    # tag
    d.text((W / 2, 62), "NFL  •  GAME DAY", font=font(30), fill=(255, 255, 255, 235), anchor="mm")

    logo_size = 150
    for team, cx in ((game.away, 150), (game.home, W - 150)):
        img.alpha_composite(get_logo(team, logo_size), (cx - logo_size // 2, 110))
        d.text((cx, 285), team.city.upper(), font=fit(d, team.city.upper(), 270, 24, 16),
               fill=(255, 255, 255, 215), anchor="mm")
        d.text((cx, 325), team.name.upper(), font=fit(d, team.name.upper(), 290, 46),
               fill=(255, 255, 255, 255), anchor="mm")
        # team colour underline
        d.rectangle((cx - 90, 360, cx + 90, 368), fill=hex_rgb(team.color) + (255,))

    # kickoff pill (centre, over the stadium, clear of Reels UI at the very bottom)
    f = font(34)
    tw = d.textlength(kickoff_text, font=f)
    x0, x1, y0, y1 = W / 2 - tw / 2 - 34, W / 2 + tw / 2 + 34, 870, 940
    d.rounded_rectangle((x0, y0, x1, y1), radius=35, fill=(0, 0, 0, 175))
    d.text((W / 2, (y0 + y1) / 2), kickoff_text, font=f, fill="white", anchor="mm")

    img.save(out_png)


def render_reel(game, kickoff_text: str, base_video: Path, out_mp4: Path, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    png = work / f"overlay_{game.id}.png"
    make_overlay(game, kickoff_text, png)
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-i", str(base_video),
        "-loop", "1", "-framerate", "24", "-i", str(png),
        "-filter_complex",
        "[1:v]format=rgba,fade=t=in:st=0.3:d=0.7:alpha=1[ov];"
        "[0:v][ov]overlay=0:0:shortest=1,format=yuv420p[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-t", "6", "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    return out_mp4
