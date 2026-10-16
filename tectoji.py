#!/usr/bin/env python3
"""Tectoji Brainrot Studio - Stage 1: one complete sample Short, fully offline.
Script -> voice (espeak-ng) -> animation (Pillow) -> captions -> music/SFX (numpy) -> MP4 (FFmpeg).
Usage: python tectoji.py [--seed N] [--style random|brainrot|broadcast|horror] [--out out]
"""
import argparse, hashlib, json, math, os, random, shutil, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

W, H, FPS, SR = 1080, 1920, 24, 44100
MIN_S, MAX_S = 20.0, 35.0

# ---------------------------------------------------------------- content
CHARS = [("Sir Banana", "🍌"), ("Captain Toaster", "🍞"), ("Mr Sock", "🧦"),
         ("Lady Cactus", "🌵"), ("Professor Cheese", "🧀"), ("Duke Meatball", "🍝"),
         ("Baby Ghost", "👻"), ("Chef Pickle", "🥒"), ("Agent Potato", "🥔"),
         ("Queen Donut", "🍩"), ("Uncle Moon", "🌝"), ("Doctor Frog", "🐸")]
OBJS = [("glowing spoon", "🥄"), ("haunted calculator", "🧮"), ("suspicious umbrella", "☂️"),
        ("talking crayon", "🖍️"), ("forbidden bucket", "🪣"), ("shiny rock", "🪨"),
        ("angry clock", "⏰"), ("mystery key", "🔑"), ("sleepy rocket", "🚀"),
        ("golden sandwich", "🥪"), ("cursed balloon", "🎈"), ("lonely magnet", "🧲")]
PLACES = ["the school canteen", "a parking lot", "the moon", "a bus stop at 3 AM",
          "grandma's wifi router", "the cheese museum", "a very small elevator",
          "the last row of a cinema", "a bowl of soup"]
STATES = ["speaking only in compliments", "walking backwards", "allergic to Tuesdays",
          "covered in glitter", "afraid of the number seven", "singing in slow motion",
          "wearing three hats", "completely invisible on Mondays"]
FIXES = ["a loud whistle", "interpretive dancing", "a strongly worded letter",
         "two spoons and hope", "a mysterious sandwich", "pure confidence"]
RELS = ["grandfather", "landlord", "future self", "biggest fan", "evil twin", "math teacher"]

HOOKS = ["Nobody warned {A} about the {O}.", "{A} found a {O} in {P}. Big mistake.",
         "POV: {A} just woke up next to a {O}.", "This is the day {A} lost to a {O}.",
         "Stop scrolling. {A} has a {O}.", "{A} swore never to touch the {O} again."]
SETUPS = ["It started in {P}. {B} said, do not open it. {A} opened it.",
          "{B} warned everyone. Nobody listened, especially {A}.",
          "Everything was normal until the {O} blinked."]
ESCALATE = ["Then the {O} began speaking in wifi signals.", "{B} screamed, but only in lowercase.",
            "The sky turned the color of burnt toast.", "Suddenly, every clock showed banana o'clock.",
            "A crowd of pigeons arrived wearing tiny ties."]
CHAOS = ["{A} tried to fix it with {F}. It got worse.", "{B} tried {F}. The {O} laughed.",
         "Everyone panicked and started {S}."]
TWISTS = ["Then everyone was {S}. Nobody knows why.", "The whole town became {S} overnight.",
          "And that's how {A} ended up {S}."]
PUNCH = ["Turns out the {O} was {A}'s {R} all along.", "The {O} was just {B}'s {R} in disguise.",
         "Plot twist: {A} was the {O} the whole time."]
OUTROS = ["Follow for more nonsense.", "Anyway. Goodnight.", "That's all. Do not ask questions.",
          "Subscribe or the {O} comes back."]


BC_HOOKS = ["ATTENTION. A {O} has been spotted in {P}.", "BREAKING. Do not look at the {O}.",
            "Emergency broadcast. {A} has found a {O}.", "WARNING. The {O} is awake."]
BC_BEATS = ["Residents are advised to stay calm.", "Do not feed it. Do not thank it.",
            "Witnesses say {A} is now {S}.", "{B} was last seen {S}.",
            "Authorities recommend {F}.", "Do not make eye contact with the {O}.",
            "The {O} is not dangerous. It is disappointed."]
BC_TWIST = ["UPDATE. The {O} was {A}'s {R}. Stand by.", "UPDATE. Nobody is safe. Everybody is {S}."]
BC_OUT = ["This has been a broadcast. Stay tuned.", "Stay safe. Or do not. We are not your boss."]

HR_HOOKS = ["Do not look at the {O} after midnight.", "{A} found a {O} in {P}.",
            "Never answer the {O} when it whispers.", "The {O} was not there yesterday."]
HR_BEATS = ["{A} did not listen.", "It was in {P} again.", "Every night, it moved one step closer.",
            "{B} heard whispering from inside it.", "The lights flickered. Twice.",
            "Nobody remembers who bought it.", "It knows your name. It says it wrong."]
HR_TWIST = ["When the lights returned, {A} was {S}.", "Now {A} only whispers about the {O}."]
HR_OUT = ["And now it is looking at you.", "Do not turn around.", "Check behind you. Slowly."]

PAL = {"brainrot": [((255, 80, 120), (80, 40, 200)), ((255, 200, 0), (255, 60, 0)),
                    ((0, 220, 180), (20, 40, 160)), ((190, 60, 255), (255, 80, 160)),
                    ((60, 200, 60), (0, 90, 120)), ((255, 120, 0), (200, 0, 100))],
       "broadcast": [((120, 0, 0), (10, 0, 0)), ((0, 0, 70), (150, 0, 0)), ((90, 20, 0), (0, 0, 0))],
       "horror": [((10, 0, 28), (0, 40, 34)), ((30, 0, 0), (0, 0, 24)), ((0, 24, 12), (14, 0, 34))]}
MOTIONS = {"brainrot": ["bounce", "spin", "zoom", "shake", "orbit"],
           "broadcast": ["shake", "bounce", "zoom"], "horror": ["creep", "creep", "shake"]}


def make_script(rng, style="brainrot"):
    A, B = rng.sample(CHARS, 2)
    O = rng.choice(OBJS)
    ctx = dict(A=A[0], B=B[0], O=O[0], P=rng.choice(PLACES), S=rng.choice(STATES),
               F=rng.choice(FIXES), R=rng.choice(RELS))
    if style == "broadcast":
        beats = [rng.choice(BC_HOOKS)] + rng.sample(BC_BEATS, 4) + [rng.choice(BC_TWIST), rng.choice(BC_OUT)]
    elif style == "horror":
        beats = [rng.choice(HR_HOOKS)] + rng.sample(HR_BEATS, 4) + [rng.choice(HR_TWIST), rng.choice(HR_OUT)]
    else:
        beats = [rng.choice(HOOKS), rng.choice(SETUPS)]
        beats += rng.sample(ESCALATE, rng.randint(1, 2)) + [rng.choice(CHAOS)]
        beats += [rng.choice(TWISTS), rng.choice(PUNCH), rng.choice(OUTROS)]
    scenes = []
    for i, b in enumerate(beats):
        if style == "horror":
            sprites = [O[1]] if i % 2 == 0 else [A[1]]
            if i == len(beats) - 1:
                sprites = [O[1]]
        elif i == len(beats) - 1:
            sprites = [A[1], B[1]]
        else:
            sprites = [A[1], O[1]] if i % 3 != 2 else [B[1], O[1]]
        scenes.append(dict(text=b.format(**ctx), sprites=sprites,
                           motion=rng.choice(MOTIONS[style]), bg=rng.choice(PAL[style])))
    return ctx, scenes, (A, B, O)


# ---------------------------------------------------------------- voice
def tts(text, path, voice, speed, pitch):
    if shutil.which("espeak-ng"):
        for v in (voice, "en-us"):
            r = subprocess.run(["espeak-ng", "-v", v, "-s", str(speed), "-p", str(pitch),
                                "-w", path, text], capture_output=True)
            if r.returncode == 0 and os.path.exists(path):
                return True
        raise RuntimeError("espeak-ng failed")
    # Fallback (no espeak): silent audio so layout/timing can still be tested.
    n = int(len(text.split()) * 0.38 * 22050)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"\x00\x00" * n)
    return False


def read_wav(path):
    with wave.open(path) as w:
        sr, n = w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(axis=1)
    return sr, a
  # ---------------------------------------------------------------- audio
def synth_music(dur, rng):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    bpm = rng.choice([118, 128, 138, 148])
    step = 60 / bpm / 4
    root = rng.choice([110.0, 123.47, 130.81, 146.83, 164.81])
    scale = [0, 3, 5, 7, 10, 12, 15]
    pattern = [rng.choice(scale) for _ in range(16)]
    for i in range(int(dur / step)):
        s = int(i * step * SR); ln = int(step * 0.9 * SR)
        if s + ln > len(out):
            break
        f = root * 2 * 2 ** (pattern[i % 16] / 12)
        tt = np.arange(ln) / SR
        env = np.exp(-tt * 14)
        out[s:s + ln] += np.sign(np.sin(2 * np.pi * f * tt)) * env * 0.12
        if i % 4 == 0:  # bass + kick
            fb = root / 2
            out[s:s + ln] += np.sin(2 * np.pi * fb * tt) * np.exp(-tt * 5) * 0.35
            k = np.sin(2 * np.pi * (120 * np.exp(-tt * 30) + 40) * tt) * np.exp(-tt * 12) * 0.5
            out[s:s + ln] += k
        if i % 4 == 2:  # hat
            out[s:s + ln // 4] += (np.random.default_rng(i).random(ln // 4) - 0.5) * 0.08
    return out


def horror_music(dur, rng):
    t = np.arange(int(dur * SR)) / SR
    out = 0.20 * np.sin(2 * np.pi * 55 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.1 * t))
    out += 0.12 * np.sin(2 * np.pi * 58.3 * t)
    per = 60 / 68
    for i in range(int(dur / per)):
        for off in (0.0, 0.22):
            st = int((i * per + off) * SR); ln = int(0.25 * SR)
            if st + ln < len(out):
                tt = np.arange(ln) / SR
                out[st:st + ln] += np.sin(2 * np.pi * 62 * tt) * np.exp(-tt * 16) * 0.45
    for _ in range(4):
        st = int(rng.uniform(1, max(1.5, dur - 3)) * SR); ln = int(1.2 * SR)
        if st + ln < len(out):
            u = np.arange(ln) / ln
            out[st:st + ln] += np.sin(2 * np.pi * (500 + 700 * u) * u * 1.2) * np.sin(np.pi * u) * 0.05
    r = int(min(4, dur) * SR); u = np.arange(r) / r
    out[-r:] += np.sin(2 * np.pi * (200 + 1000 * u) * (np.arange(r) / SR)) * u * 0.10
    return out


def broadcast_music(dur, rng):
    t = np.arange(int(dur * SR)) / SR
    f = np.where((t % 1.2) < 0.6, 720.0, 940.0)
    ph = np.cumsum(2 * np.pi * f / SR)
    out = 0.09 * np.sin(ph) + 0.18 * np.sin(2 * np.pi * 50 * t)
    for k in range(int(dur / 2.4)):
        st = int(k * 2.4 * SR); ln = int(0.1 * SR)
        if st + ln < len(out):
            out[st:st + ln] += np.sin(2 * np.pi * 1000 * np.arange(ln) / SR) * 0.12
    return out


def add_sfx(buf, at, kind):
    s = int(at * SR)
    if kind == "pop":
        ln = int(0.14 * SR); tt = np.arange(ln) / SR
        x = np.sin(2 * np.pi * (900 * np.exp(-tt * 14) + 150) * tt) * np.exp(-tt * 18) * 0.5
    elif kind == "beep":
        ln = int(0.08 * SR); tt = np.arange(ln) / SR
        x = np.sin(2 * np.pi * 1000 * tt) * 0.3
    elif kind == "thud":
        ln = int(0.35 * SR); tt = np.arange(ln) / SR
        x = np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 9) * 0.5
    elif kind == "scare":
        ln = int(0.8 * SR); tt = np.arange(ln) / SR
        x = ((np.random.default_rng(1).random(ln) - 0.5) * 1.2 + np.sin(2 * np.pi * 150 * tt)) * np.exp(-tt * 3) * 0.9
    else:  # boom
        ln = int(0.9 * SR); tt = np.arange(ln) / SR
        x = np.sin(2 * np.pi * (90 * np.exp(-tt * 4) + 30) * tt) * np.exp(-tt * 4) * 0.8
    e = min(len(buf), s + ln)
    if e > s:
        buf[s:e] += x[:e - s]


# ---------------------------------------------------------------- visuals
def find_font(cands, size):
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


FONT_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
EMOJI_FONT = ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
              "/usr/share/fonts/noto/NotoColorEmoji.ttf"]


def emoji_sprite(ch, size=420):
    f = ImageFont.truetype(next(p for p in EMOJI_FONT if os.path.exists(p)), 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox() or (0, 0, 160, 160))
    r = size / max(im.size)
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)


def make_bg(c1, c2):
    y = np.linspace(0, 1, H * 2, dtype=np.float32)  # 2 periods tall, rolled for motion
    m = (0.5 + 0.5 * np.sin(2 * np.pi * y * 2))[:, None, None]
    a = np.array(c1, np.float32)[None, None, :]; b = np.array(c2, np.float32)[None, None, :]
    return (a * m + b * (1 - m)).astype(np.uint8).repeat(W, axis=1)[:, :W]


def paste_center(img, sp, cx, cy, scale=1.0, angle=0.0):
    if scale != 1.0:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BICUBIC)
    if angle:
        sp = sp.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)), sp)


def wrap_words(words, font, maxw, draw):
    lines, cur = [], []
    for w in words:
        t = " ".join(cur + [w])
        if cur and draw.textlength(t, font=font) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    return lines + ([cur] if cur else [])


def darken(sp, f):
    r, g, bb, al = sp.split()
    rgb = ImageEnhance.Brightness(Image.merge("RGB", (r, g, bb))).enhance(f)
    return Image.merge("RGBA", (*rgb.split(), al))


def vignette():
    y, x = np.ogrid[:H, :W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    a = np.clip((d - 0.45) / 0.9, 0, 1) ** 1.5 * 235
    arr = np.zeros((H, W, 4), np.uint8); arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def scanlines():
    arr = np.zeros((H, W, 4), np.uint8); arr[::4, :, 3] = 70
    return Image.fromarray(arr, "RGBA")


def render_frames(scenes, bounds, total, ff_stdin, rng, style, ctx):
    bright = 0.55 if style == "horror" else 1.0
    sprites = {}
    for s in scenes:
        for ch in s["sprites"]:
            if ch not in sprites:
                sp = emoji_sprite(ch)
                sprites[ch] = darken(sp, bright) if bright < 1 else sp
    pool = {"brainrot": ["✨", "💥", "⭐", "🔥", "💫"], "broadcast": ["🚨", "⚠"],
            "horror": ["🦇", "💀", "👻"]}[style]
    ndec = {"brainrot": 8, "broadcast": 5, "horror": 4}[style]
    decor = {d: emoji_sprite(d, 110) for d in pool}
    if style == "horror":
        decor = {d: darken(v, 0.5) for d, v in decor.items()}
    deco = [(rng.choice(pool), rng.random(), rng.random(), 0.3 + rng.random() * 0.6) for _ in range(ndec)]
    font = find_font(FONT_BOLD, 78 if style != "brainrot" else 84)
    small = find_font(FONT_BOLD, 44); banner = find_font(FONT_BOLD, 62)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    bgs = [make_bg(*s["bg"]) for s in scenes]
    vig = vignette() if style == "horror" else None
    scan = scanlines() if style == "broadcast" else None
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    roll = {"brainrot": 260, "broadcast": 120, "horror": 40}[style]
    accent = {"brainrot": (255, 235, 0), "broadcast": (255, 40, 40), "horror": (200, 0, 0)}[style]
    hi = {"brainrot": (255, 235, 0), "broadcast": (255, 220, 0), "horror": (255, 70, 70)}[style]
    stroke = {"brainrot": (0, 0, 0), "broadcast": (0, 0, 0), "horror": (90, 0, 0)}[style]
    ticker = f"   STAY CALM  *  DO NOT FEED THE {ctx['O'].upper()}  *  FICTIONAL COMEDY BROADCAST  *  "
    tw = int(tmp.textlength(ticker, font=small))
    nf = int(total * FPS); si = 0
    for f in range(nf):
        t = f / FPS
        while si < len(scenes) - 1 and t >= bounds[si + 1]:
            si += 1
        sc = scenes[si]; lt = t - bounds[si]
        bg = np.roll(bgs[si], int(t * roll), axis=0)[:H]
        img = Image.fromarray(bg).convert("RGBA")
        for d, x, y0, sp in deco:
            yy = (y0 - t * sp * 0.25) % 1.0
            paste_center(img, decor[d], x * W, yy * H, 1.0, (t * 90 * sp) % 360)
        pop = min(1.0, lt / 0.18); pop = 1 - (1 - pop) ** 3
        m = sc["motion"]; sl = sc["sprites"]; n = len(sl)
        for k, ch in enumerate(sl):
            bx = W * (0.5 if n == 1 else (0.30 if k == 0 else 0.70)); by = H * 0.30
            base = 1.25 if n == 1 else 0.8
            sc_, ang, ox, oy = 1.0, 0.0, 0.0, 0.0
            ph = t * 6 + k * 1.7
            if m == "bounce": oy = -abs(math.sin(ph)) * 230
            elif m == "spin": ang = (t * 220 * (1 if k == 0 else -1)) % 360
            elif m == "zoom": sc_ = 0.8 + 0.35 * math.sin(ph)
            elif m == "shake": ox = math.sin(t * 70 + k) * 28; oy = math.cos(t * 83) * 18
            elif m == "orbit": ox = math.cos(ph) * 120; oy = math.sin(ph) * 120
            elif m == "creep":
                sc_ = 0.75 + 0.6 * min(1.0, lt / max(0.5, bounds[si + 1] - bounds[si]))
                ox = math.sin(t * 9) * 5
            paste_center(img, sprites[ch], bx + ox, by + oy, sc_ * pop * base, ang)
        if style == "horror":
            fl = 0.0
            if (int(t * 12) * 7919) % 11 == 0: fl = 0.35
            img = Image.blend(img, black, min(0.9, 0.25 + fl))
            img.alpha_composite(vig)
            if si == len(scenes) - 1 and lt < 0.25:
                img = Image.blend(img, Image.new("RGBA", (W, H), (255, 255, 255, 255)), 0.7)
        if style == "broadcast":
            a = int(60 * max(0, math.sin(t * 6)))
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 0, 0, a)))
            img.alpha_composite(scan)
        # captions
        words = sc["text"].split()
        tot_c = sum(len(w) + 1 for w in words); acc = 0; cur = 0
        for i, w in enumerate(words):
            if lt >= (acc / tot_c) * sc["_vdur"]:
                cur = i
            acc += len(w) + 1
        d = ImageDraw.Draw(img, "RGBA")
        shown = [w.lower() for w in words] if style == "horror" else words
        lines = wrap_words(shown, font, W - 140, tmp)
        y0 = int(H * (0.66 if style == "horror" else 0.58))
        if style == "broadcast":
            d.rectangle((40, y0 - 25, W - 40, y0 + len(lines) * 108 + 10), fill=(0, 0, 0, 200))
        y = y0; idx = 0
        for ln in lines:
            lw = tmp.textlength(" ".join(ln), font=font); x = (W - lw) / 2
            for w in ln:
                col = hi if idx == cur else (255, 255, 255)
                sw = 0 if style == "broadcast" else 9
                d.text((x, y), w, font=font, fill=col, stroke_width=sw, stroke_fill=stroke)
                x += tmp.textlength(w + " ", font=font); idx += 1
            y += 108
        if style == "broadcast":
            if int(t * 2) % 2 == 0:
                d.rectangle((0, 40, W, 170), fill=(210, 0, 0, 255))
                d.text((W / 2, 105), "EMERGENCY BROADCAST", font=banner, fill=(255, 255, 255), anchor="mm")
            d.rectangle((0, H - 230, W, H - 160), fill=(0, 0, 0, 230))
            off = int(t * 260) % tw
            for rep in range(3):
                d.text((-off + rep * tw, H - 195), ticker, font=small, fill=(255, 220, 0))
        d.rectangle((0, 0, int(W * t / total), 12), fill=accent + (255,))  # progress bar
        d.text((W / 2, H - 80), "TECTOJI", font=small, fill=(255, 255, 255, 150),
               anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
        ff_stdin.write(img.convert("RGB").tobytes())
      # ---------------------------------------------------------------- metadata
def make_meta(ctx, scenes, chars, style):
    A, B, O = chars
    hook = scenes[0]["text"]
    if style == "broadcast":
        title = f"BREAKING: {O[0]} spotted in {ctx['P']} {O[1]}"
        tags = ["#shorts", "#breakingnews", "#absurd", "#funny", "#tectoji", "#comedy"]
        note = "A fictional comedy broadcast. None of this is real news."
    elif style == "horror":
        title = f"Do not look at the {O[0]} {O[1]}"
        tags = ["#shorts", "#horror", "#creepy", "#scary", "#tectoji", "#spooky"]
        note = "An original absurd horror mini-story."
    else:
        title = f"{A[0]} vs the {O[0]} {A[1]}{O[1]}"
        tags = ["#shorts", "#brainrot", "#absurd", "#funny", "#tectoji", "#comedy"]
        note = "An original absurdist mini-story from Tectoji."
    if len(title) > 90:
        title = title[:87] + "..."
    desc = (f"{hook}\n\n{note} Script, animation and voice are generated with automated tools.\n\n"
            + " ".join(tags))
    return dict(title=title, description=desc, tags=[t[1:] for t in tags], style=style,
                script_hash=hashlib.sha1(" ".join(s["text"] for s in scenes).encode()).hexdigest())


# ---------------------------------------------------------------- main
def build(seed, out, style):
    if style == "random":
        style = ["brainrot", "broadcast", "horror"][seed % 3]
    os.makedirs(out, exist_ok=True)
    tmpd = os.path.join(out, "tmp"); os.makedirs(tmpd, exist_ok=True)
    for attempt in range(25):
        rng = random.Random(seed * 1000 + attempt)
        ctx, scenes, chars = make_script(rng, style)
        if style == "horror":
            voice = rng.choice(["en-us+whisper", "en-us+m2"]); speed, pitch = rng.randint(125, 140), rng.randint(10, 30)
        elif style == "broadcast":
            voice = rng.choice(["en-us+m7", "en-gb+m4"]); speed, pitch = rng.randint(150, 165), rng.randint(20, 40)
        else:
            voice = rng.choice(["en-us+m3", "en-us+f3", "en-gb+m7", "en-us+m4"])
            speed, pitch = rng.randint(165, 190), rng.randint(40, 75)
        real = True
        for i, s in enumerate(scenes):
            p = os.path.join(tmpd, f"v{i}.wav")
            real = tts(s["text"], p, voice, speed, pitch)
            sr, a = read_wav(p); s["_wav"] = a; s["_sr"] = sr
            s["_vdur"] = len(a) / sr if len(a) else 1.5
        starts, t = [], 0.0
        for s in scenes:
            starts.append(t); t += max(s["_vdur"] + 0.45, 1.6)
        total = t + 0.6
        if MIN_S <= total <= MAX_S:
            break
    else:
        total = min(max(total, MIN_S), MAX_S)
    if total < MIN_S:
        total = MIN_S
    bounds = starts + [total]
    print(f"style={style} seed={seed} attempt={attempt} voice={voice} real_tts={real} duration={total:.1f}s")

    # audio mix
    mus = {"horror": horror_music, "broadcast": broadcast_music}.get(style, synth_music)
    buf = mus(total, rng) * 0.55
    sfx = {"horror": "thud", "broadcast": "beep"}.get(style, "pop")
    last = "scare" if style == "horror" else "boom"
    n = len(buf)
    for i, s in enumerate(scenes):
        add_sfx(buf, starts[i], sfx)
        a = np.interp(np.arange(int(len(s["_wav"]) * SR / s["_sr"])) / SR * s["_sr"],
                      np.arange(len(s["_wav"])), s["_wav"]) if len(s["_wav"]) else np.zeros(1)
        st = int((starts[i] + 0.1) * SR); e = min(n, st + len(a))
        if e > st:
            buf[st:e] += a[:e - st] * 1.0
    add_sfx(buf, total - 0.9, last)
    buf = np.clip(buf / max(1.0, np.abs(buf).max()) * 0.95, -1, 1)
    wpath = os.path.join(tmpd, "mix.wav")
    with wave.open(wpath, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())

    # video
    mp4 = os.path.join(out, "short.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wpath, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    render_frames(scenes, bounds, total, pr.stdin, rng, style, ctx)
    pr.stdin.close()
    if pr.wait() != 0:
        sys.exit("ffmpeg failed")

    meta = make_meta(ctx, scenes, chars, style)
    meta.update(duration_s=round(total, 1), seed=seed, real_tts=real)
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), ensure_ascii=False, indent=2)
    json.dump([dict(text=s["text"], motion=s["motion"]) for s in scenes],
              open(os.path.join(out, "script.json"), "w"), ensure_ascii=False, indent=2)
    shutil.rmtree(tmpd, ignore_errors=True)
    print("OK:", mp4, "|", meta["title"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="out")
    ap.add_argument("--style", default="random", choices=["random", "brainrot", "broadcast", "horror"])
    a = ap.parse_args()
    build(a.seed, a.out, a.style)
