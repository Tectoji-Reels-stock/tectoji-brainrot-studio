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

AN_HOOKS = ["This is not a test.", "Attention. Stay where you are.", "This is an emergency broadcast.",
            "Do not change the channel.", "Warning. The {O} has entered your area."]
AN_BEATS = ["Lock all your doors now.", "Close every window. Close the curtains.",
            "Do not look at the television.", "Find a quiet place to hide.",
            "If someone knocks, do not answer.", "Turn off your phone. It can hear you.",
            "Do not look outside. It is already there.", "It copies the voice of someone you know.",
            "Do not count the people in your house.", "Turn off all the lights."]
AN_TWIST = ["This broadcast is coming from inside your house.", "This message is playing in your room."]
AN_OUT = ["Do not turn around.", "It is watching you too.", "End of broadcast. Sleep well."]

PAL = {"brainrot": [((255, 80, 120), (80, 40, 200)), ((255, 200, 0), (255, 60, 0)),
                    ((0, 220, 180), (20, 40, 160)), ((190, 60, 255), (255, 80, 160)),
                    ((60, 200, 60), (0, 90, 120)), ((255, 120, 0), (200, 0, 100))],
       "broadcast": [((120, 0, 0), (10, 0, 0)), ((0, 0, 70), (150, 0, 0)), ((90, 20, 0), (0, 0, 0))],
       "horror": [((10, 0, 28), (0, 40, 34)), ((30, 0, 0), (0, 0, 24)), ((0, 24, 12), (14, 0, 34))],
       "analog": [((6, 6, 6), (24, 0, 0))]}
MOTIONS = {"brainrot": ["bounce", "spin", "zoom", "shake", "orbit"],
           "broadcast": ["shake", "bounce", "zoom"], "horror": ["creep", "creep", "shake"], "analog": ["creep"]}


def make_script(rng, style="brainrot"):
    A, B = rng.sample(CHARS, 2)
    O = rng.choice(OBJS)
    ctx = dict(A=A[0], B=B[0], O=O[0], P=rng.choice(PLACES), S=rng.choice(STATES),
               F=rng.choice(FIXES), R=rng.choice(RELS))
    if style == "broadcast":
        beats = [rng.choice(BC_HOOKS)] + rng.sample(BC_BEATS, 4) + [rng.choice(BC_TWIST), rng.choice(BC_OUT)]
    elif style == "analog":
        beats = [rng.choice(AN_HOOKS)] + rng.sample(AN_BEATS, 4) + [rng.choice(AN_TWIST), rng.choice(AN_OUT)]
    elif style == "horror":
        beats = [rng.choice(HR_HOOKS)] + rng.sample(HR_BEATS, 4) + [rng.choice(HR_TWIST), rng.choice(HR_OUT)]
    else:
        beats = [rng.choice(HOOKS), rng.choice(SETUPS)]
        beats += rng.sample(ESCALATE, rng.randint(1, 2)) + [rng.choice(CHAOS)]
        beats += [rng.choice(TWISTS), rng.choice(PUNCH), rng.choice(OUTROS)]
    scenes = []
    for i, b in enumerate(beats):
        if style == "analog":
            sprites = [O[1]]
        elif style == "horror":
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


def analog_music(dur, rng):
    t = np.arange(int(dur * SR)) / SR
    out = 0.16 * np.sin(2 * np.pi * 60 * t) + 0.07 * np.sin(2 * np.pi * 120 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t))
    nz = np.random.default_rng(3).random(len(t)) - 0.5
    k = 8
    nz = np.convolve(nz, np.ones(k) / k, mode="same")
    out += nz * 0.10
    vib = np.sin(2 * np.pi * 330 * t + 4 * np.sin(2 * np.pi * 5 * t))
    out += vib * 0.025 * (np.sin(2 * np.pi * 0.12 * t) > 0.4)
    for j in range(int(dur / 3.2)):
        st = int((1.0 + j * 3.2) * SR); ln = int(0.15 * SR)
        if st + ln < len(out):
            out[st:st + ln] += np.sin(2 * np.pi * 760 * np.arange(ln) / SR) * 0.09
    r = int(min(5, dur) * SR); u = np.arange(r) / r
    out[-r:] += np.sin(2 * np.pi * (150 + 750 * u) * (np.arange(r) / SR)) * u * 0.10
    return out


def radio_fx(a):
    a = np.round(np.tanh(a * 2.0) * 20) / 20
    return a + (np.random.default_rng(5).random(len(a)) - 0.5) * 0.02


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
    elif kind == "static":
        ln = int(0.25 * SR); tt = np.arange(ln) / SR
        x = (np.random.default_rng(int(at * 100)).random(ln) - 0.5) * np.exp(-tt * 9) * 0.7
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


ICON_WORDS = [("door", "door"), ("knock", "door"), ("window", "window"), ("curtain", "window"),
              ("outside", "window"), ("television", "tv"), ("tv", "tv"), ("channel", "tv"),
              ("broadcast", "tv"), ("hide", "bed"), ("sleep", "bed"), ("quiet", "bed"),
              ("phone", "phone"), ("hear", "phone"), ("look", "eye"), ("watch", "eye"),
              ("turn around", "eye"), ("house", "house"), ("home", "house"), ("room", "house"),
              ("light", "lamp"), ("dark", "lamp")]


ICON_NAMES = ["door", "window", "tv", "bed", "phone", "eye", "house", "person", "lamp"]


def icon_for(text):
    t = text.lower()
    for k, v in ICON_WORDS:
        if k in t:
            return v
    return "person"


def draw_person(d, cx, top, h, col):
    r = h * 0.11
    d.ellipse((cx - r, top, cx + r, top + 2 * r), fill=col)
    d.rounded_rectangle((cx - h * 0.16, top + 2.3 * r, cx + h * 0.16, top + h * 0.62), int(h * 0.06), fill=col)
    d.rectangle((cx - h * 0.14, top + h * 0.58, cx - h * 0.02, top + h), fill=col)
    d.rectangle((cx + h * 0.02, top + h * 0.58, cx + h * 0.14, top + h), fill=col)
    d.rectangle((cx - h * 0.26, top + 2.4 * r, cx - h * 0.19, top + h * 0.55), fill=col)
    d.rectangle((cx + h * 0.19, top + 2.4 * r, cx + h * 0.26, top + h * 0.55), fill=col)


def draw_icon(name, S=520):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = (190, 190, 190, 255); k = (0, 0, 0, 255); lw = 14
    if name == "door":
        d.rectangle((150, 40, 370, 480), outline=g, width=lw)
        d.polygon([(150, 40), (250, 70), (250, 450), (150, 480)], fill=g)
        d.ellipse((222, 250, 238, 266), fill=k)
    elif name == "window":
        d.rectangle((110, 80, 410, 440), outline=g, width=lw)
        d.line((260, 80, 260, 440), fill=g, width=lw); d.line((110, 260, 410, 260), fill=g, width=lw)
    elif name == "tv":
        d.line((200, 60, 260, 130), fill=g, width=10); d.line((330, 50, 270, 130), fill=g, width=10)
        d.rounded_rectangle((70, 130, 450, 420), 28, fill=g)
        d.rounded_rectangle((100, 160, 380, 390), 18, fill=(15, 15, 15, 255))
        d.ellipse((400, 200, 430, 230), fill=k); d.ellipse((400, 260, 430, 290), fill=k)
    elif name == "bed":
        d.rectangle((70, 300, 450, 360), fill=g); d.rectangle((70, 200, 110, 420), fill=g)
        d.rectangle((410, 260, 450, 420), fill=g); d.rounded_rectangle((120, 230, 220, 300), 18, fill=g)
    elif name == "phone":
        d.rounded_rectangle((170, 60, 350, 460), 30, outline=g, width=lw)
        d.ellipse((245, 410, 275, 440), outline=g, width=8)
    elif name == "eye":
        d.ellipse((60, 190, 460, 330), outline=g, width=lw)
        d.ellipse((220, 200, 300, 320), fill=(150, 0, 0, 255)); d.ellipse((248, 238, 272, 282), fill=k)
    elif name == "house":
        d.polygon([(60, 230), (260, 70), (460, 230)], outline=g, width=lw)
        d.rectangle((110, 230, 410, 440), outline=g, width=lw); d.rectangle((230, 330, 290, 440), fill=g)
    elif name == "lamp":
        d.polygon([(190, 120), (330, 120), (380, 260), (140, 260)], fill=g)
        d.rectangle((250, 260, 270, 420), fill=g); d.rectangle((190, 420, 330, 440), fill=g)
    else:
        draw_person(d, S // 2, 60, 400, g)
    return im


def draw_entity():
    im = Image.new("RGBA", (260, 900), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = (135, 0, 0, 255)
    d.ellipse((100, 0, 160, 80), fill=c)
    d.rounded_rectangle((105, 85, 155, 560), 20, fill=c)
    d.rectangle((85, 100, 100, 640), fill=c); d.rectangle((160, 100, 175, 640), fill=c)
    d.rectangle((108, 540, 128, 900), fill=c); d.rectangle((132, 540, 152, 900), fill=c)
    return im


def render_analog(scenes, bounds, total, ff, rng, ctx):
    mono = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"] + FONT_BOLD
    f_logo, f_sub, f_cap, f_big = (find_font(mono, z) for z in (170, 36, 58, 110))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    icons, ents = {}, []
    ent = draw_entity(); last = max(1, len(scenes) - 1)
    for i, s in enumerate(scenes):
        s["icon"] = s.get("icon") or icon_for(s["text"])
        if s["icon"] not in icons:
            icons[s["icon"]] = draw_icon(s["icon"])
        prog = i / last; es = 0.35 + 0.95 * prog
        e = ent.resize((int(ent.width * es), int(ent.height * es)), Image.BICUBIC)
        al = e.getchannel("A").point(lambda v, p=prog: int(v * (0.25 + 0.75 * p)))
        e.putalpha(al); ents.append((e, es))
    scan, vig = scanlines(), vignette()
    nprng = np.random.default_rng(7)
    nf = int(total * FPS); si = 0
    for f in range(nf):
        t = f / FPS
        while si < len(scenes) - 1 and t >= bounds[si + 1]:
            si += 1
        sc = scenes[si]; lt = t - bounds[si]; prog = si / last
        img = Image.new("RGBA", (W, H), (6, 6, 6, 255)); d = ImageDraw.Draw(img)
        flick = 1.0 if (int(t * 10) * 7919) % 13 else 0.45
        d.text((W / 2, 230), "TAS", font=f_logo, fill=(int(200 * flick), 0, 0, 255), anchor="mm")
        d.text((W / 2, 345), "TECTOJI ALERT SYSTEM", font=f_sub, fill=(170, 170, 170, 255), anchor="mm")
        pop = min(1.0, lt / 0.2)
        paste_center(img, icons[sc["icon"]], W * 0.40, H * 0.43, 1.25 * max(0.2, pop), 0)
        e, es = ents[si]
        jit = math.sin(t * 31) * 4 if prog > 0.6 else 0
        paste_center(img, e, W * 0.82 + jit, H * 0.66 - e.height / 2, 1.0, 0)
        words = sc["text"].upper().split()
        tot_c = sum(len(w) + 1 for w in words); acc = 0; cur = 0
        for i, w in enumerate(words):
            if lt >= (acc / tot_c) * sc["_vdur"]:
                cur = i
            acc += len(w) + 1
        d = ImageDraw.Draw(img)
        lines = wrap_words(words, f_cap, W - 160, tmp); y = int(H * 0.72); idx = 0
        for ln in lines:
            lw = tmp.textlength(" ".join(ln), font=f_cap); x = (W - lw) / 2
            for w in ln:
                d.text((x, y), w, font=f_cap, fill=(230, 30, 30, 255) if idx == cur else (225, 225, 225, 255))
                x += tmp.textlength(w + " ", font=f_cap); idx += 1
            y += 82
        d.text((W / 2, H - 80), "FICTIONAL  *  NOT A REAL ALERT", font=f_sub, fill=(120, 120, 120, 255), anchor="mm")
        d.rectangle((0, 0, int(W * t / total), 8), fill=(136, 0, 0, 255))
        if lt < 0.18 or (int(t * 7) * 104729) % 29 == 0:
            arr = np.array(img.convert("RGB"))
            for _ in range(6):
                y0 = int(nprng.integers(0, H - 80)); hh = int(nprng.integers(10, 70))
                arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], int(nprng.integers(-80, 80)), axis=1)
            img = Image.fromarray(arr).convert("RGBA")
        noise = Image.fromarray(nprng.integers(0, 70, (H // 4, W // 4), dtype=np.uint8), "L").resize((W, H)).convert("RGBA")
        img = Image.blend(img, noise, 0.10)
        img.alpha_composite(scan); img.alpha_composite(vig)
        if si == len(scenes) - 1 and lt < 0.3:
            img = Image.blend(img, Image.new("RGBA", (W, H), (150, 0, 0, 255)), 0.5)
        if t > total - 0.9:
            blk = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), noise, 0.7)
            ImageDraw.Draw(blk).text((W / 2, H / 2), "SIGNAL LOST", font=f_big, fill=(190, 0, 0, 255), anchor="mm")
            img = blk
        ff.write(img.convert("RGB").tobytes())


def render_frames(scenes, bounds, total, ff_stdin, rng, style, ctx):
    if style == "analog":
        return render_analog(scenes, bounds, total, ff_stdin, rng, ctx)
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
    elif style == "analog":
        title = f"EMERGENCY BROADCAST: {hook[:50]}"
        tags = ["#shorts", "#analoghorror", "#emergencybroadcast", "#creepy", "#horror", "#tectoji"]
        note = "An original fictional analog horror broadcast. Not a real emergency alert."
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
        style = ["brainrot", "broadcast", "horror", "analog"][seed % 4]
    os.makedirs(out, exist_ok=True)
    tmpd = os.path.join(out, "tmp"); os.makedirs(tmpd, exist_ok=True)
    for attempt in range(25):
        rng = random.Random(seed * 1000 + attempt)
        ctx, scenes, chars = make_script(rng, style)
        if style == "analog":
            voice = rng.choice(["en-us+m7", "en-us+m2"]); speed, pitch = rng.randint(120, 135), rng.randint(5, 20)
        elif style == "horror":
            voice = rng.choice(["en-us+whisper", "en-us+m2"]); speed, pitch = rng.randint(125, 140), rng.randint(10, 30)
        elif style == "broadcast":
            voice = rng.choice(["en-us+m7", "en-gb+m4"]); speed, pitch = rng.randint(150, 165), rng.randint(20, 40)
        else:
            voice = rng.choice(["en-us+m3", "en-us+f3", "en-gb+m7", "en-us+m4"])
            speed, pitch = rng.randint(165, 190), rng.randint(40, 75)
        real = True
        for i, s in enumerate(scenes):
            p = os.path.join(tmpd, f"v{i}.wav")
            real = tts(s["text"].lower() if style == "analog" else s["text"], p, voice, speed, pitch)
            sr, a = read_wav(p); s["_wav"] = a; s["_sr"] = sr
            s["_vdur"] = len(a) / sr if len(a) else 1.5
        starts, t = [], 0.0
        for s in scenes:
            starts.append(t); t += max(s["_vdur"] + 0.45, 2.4 if style == "analog" else 1.6)
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
    mus = {"horror": horror_music, "broadcast": broadcast_music, "analog": analog_music}.get(style, synth_music)
    buf = mus(total, rng) * 0.55
    sfx = {"horror": "thud", "broadcast": "beep", "analog": "static"}.get(style, "pop")
    last = "scare" if style in ("horror", "analog") else "boom"
    n = len(buf)
    for i, s in enumerate(scenes):
        add_sfx(buf, starts[i], sfx)
        a = np.interp(np.arange(int(len(s["_wav"]) * SR / s["_sr"])) / SR * s["_sr"],
                      np.arange(len(s["_wav"])), s["_wav"]) if len(s["_wav"]) else np.zeros(1)
        if style == "analog":
            a = radio_fx(a)
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
    ap.add_argument("--style", default="random", choices=["random", "brainrot", "broadcast", "horror", "analog"])
    a = ap.parse_args()
    build(a.seed, a.out, a.style)
