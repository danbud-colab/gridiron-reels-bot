"""Fully generated 6s 9:16 animated reel (no base video): team-colour diagonal split,
logos slide in, VS slam + flash, names, kickoff pill. Frames piped from Pillow to ffmpeg."""
from __future__ import annotations
import math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFilter
from render import W, H, font, fit, hex_rgb, get_logo

FPS, DUR = 24, 6.0


def ease_out(x):  # cubic
    x = max(0, min(1, x)); return 1 - (1 - x) ** 3


def back_out(x):  # overshoot
    x = max(0, min(1, x)); c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def seg(t, a, b):
    return max(0.0, min(1.0, (t - a) / (b - a)))


def dist(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def background(away_c, home_c):
    if dist(away_c, home_c) < 90:               # near-identical colours → lighten home side
        home_c = shade(home_c, 1.9) if sum(home_c) < 450 else shade(home_c, 0.55)
    img = Image.new("RGB", (W, H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    a_poly = [(0, 0), (W * 0.70, 0), (W * 0.30, H), (0, H)]
    h_poly = [(W * 0.70, 0), (W, 0), (W, H), (W * 0.30, H)]
    d.polygon(a_poly, fill=shade(away_c, 0.8))
    d.polygon(h_poly, fill=shade(home_c, 0.8))
    # vertical darkening gradient + vignette
    shade_layer = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade_layer)
    for y in range(H):
        sd.line([(0, y), (W, y)], fill=int(150 * abs(y - H * 0.5) / (H * 0.5)) ** 1 if False else int(140 * (abs(y - H / 2) / (H / 2)) ** 1.6))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade_layer)
    d = ImageDraw.Draw(img)
    # diagonal stripes along the split
    for off, w, a in ((0, 14, 255), (-34, 5, 160), (34, 5, 160)):
        d.line([(W * 0.70 + off, 0), (W * 0.30 + off, H)], fill=(a, a, a), width=w)
    # subtle yard-line texture
    for i in range(-4, 12):
        y = i * 140
        d.line([(0, y), (W, y + 90)], fill=(255, 255, 255), width=1)
    img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), 0.0)
    return img


def text_layer(size, items):
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for text, f, y, fill in items:
        d.text((size[0] / 2, y), text, font=f, fill=fill, anchor="mm")
    return lay


def with_alpha(layer, a):
    if a >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return out


def paste_center(canvas, layer, cx, cy, alpha=1.0, scale=1.0):
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BILINEAR)
    layer = with_alpha(layer, alpha)
    canvas.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


def render_animated(game, kickoff_text: str, out_mp4: Path, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    away_c, home_c = hex_rgb(game.away.color), hex_rgb(game.home.color)
    bg = background(away_c, home_c)

    LS = 250
    away_logo, home_logo = get_logo(game.away, LS), get_logo(game.home, LS)
    # soft shadow behind logos
    shadow = Image.new("RGBA", (LS + 80, LS + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((40, 52, LS + 40, LS + 52), fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))

    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    def name_block(team):
        city, name = team.city.upper(), team.name.upper()
        return text_layer((420, 130), [
            (city, fit(tmp, city, 380, 30, 18), 28, (255, 255, 255, 220)),
            (name, fit(tmp, name, 340, 70, 30), 82, (255, 255, 255, 255))])
    away_name, home_name = name_block(game.away), name_block(game.home)

    vs = text_layer((300, 150), [("VS", font(112), 75, (255, 255, 255, 255))])
    # outline/glow for VS
    glow = vs.filter(ImageFilter.GaussianBlur(10))
    vs_full = Image.new("RGBA", vs.size, (0, 0, 0, 0)); vs_full.alpha_composite(glow); vs_full.alpha_composite(vs)

    tag = text_layer((560, 60), [("NFL  •  GAME DAY", font(32), 30, (255, 255, 255, 235))])
    f = font(34); tw = tmp.textlength(kickoff_text, font=f)
    pill = Image.new("RGBA", (int(tw + 90), 78), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle((0, 0, pill.width - 1, 77), radius=39, fill=(0, 0, 0, 190), outline=(255, 255, 255, 200), width=2)
    pd.text((pill.width / 2, 39), kickoff_text, font=f, fill="white", anchor="mm")

    AWAY_XY, HOME_XY, VS_XY = (200, 260), (525, 725), (360, 575)
    ffmpeg = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        # synthesized audio: whoosh in, bass thump on the VS hit
        "-f", "lavfi", "-i", "anoisesrc=d=6:c=pink:a=0.35,highpass=f=700,lowpass=f=7000,"
                              "afade=t=in:st=0.15:d=0.7,afade=t=out:st=0.85:d=0.3",
        "-f", "lavfi", "-i", "aevalsrc='if(gte(t,1.0),0.9*sin(2*PI*55*t)*exp(-7*(t-1.0)),0)':d=6:s=44100",
        "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:normalize=0,volume=0.9[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-t", str(DUR), "-movflags", "+faststart", str(out_mp4)]
    p = subprocess.Popen(ffmpeg, stdin=subprocess.PIPE)
    try:
        for i in range(int(FPS * DUR)):
            t = i / FPS
            fr = bg.copy().convert("RGBA")
            # tag
            paste_center(fr, tag, W * 0.30, 70, alpha=seg(t, 0.1, 0.6))
            # logos slide in from the sides
            ea, eh = ease_out(seg(t, 0.15, 0.85)), ease_out(seg(t, 0.35, 1.05))
            pulse = 1 + 0.02 * math.sin(t * 3.2)
            ax = AWAY_XY[0] - (1 - ea) * 420; hx = HOME_XY[0] + (1 - eh) * 420
            paste_center(fr, shadow, ax, AWAY_XY[1], alpha=ea)
            paste_center(fr, away_logo, ax, AWAY_XY[1], alpha=ea, scale=pulse)
            paste_center(fr, shadow, hx, HOME_XY[1], alpha=eh)
            paste_center(fr, home_logo, hx, HOME_XY[1], alpha=eh, scale=pulse)
            # names rise in
            na, nh = ease_out(seg(t, 0.8, 1.4)), ease_out(seg(t, 0.95, 1.55))
            paste_center(fr, away_name, AWAY_XY[0], 435 + (1 - na) * 30, alpha=na)
            paste_center(fr, home_name, HOME_XY[0], 900 + (1 - nh) * 30, alpha=nh)
            # VS slam
            vp = seg(t, 1.0, 1.35)
            if vp > 0:
                paste_center(fr, vs_full, VS_XY[0], VS_XY[1], alpha=min(1, vp * 3), scale=0.6 + 0.4 * back_out(vp) + 0.8 * (1 - ease_out(vp)) * 0)
            # impact flash
            if 1.0 <= t < 1.35:
                flash = int(100 * (1 - seg(t, 1.0, 1.35)))
                fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, flash)))
            # kickoff pill slides up
            ka = ease_out(seg(t, 1.8, 2.4))
            paste_center(fr, pill, W / 2, 1008 + (1 - ka) * 50, alpha=ka)
            # tiny end fade-out for clean loop
            if t > DUR - 0.25:
                fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * seg(t, DUR - 0.25, DUR)))))
            p.stdin.write(fr.convert("RGB").tobytes())
        p.stdin.close()
    finally:
        p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg failed")
    return out_mp4
