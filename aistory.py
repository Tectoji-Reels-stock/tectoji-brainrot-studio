#!/usr/bin/env python3
"""Tectoji AI Story - Hindi horror Shorts made only from AI images + AI voice.
  python aistory.py --topic "haunted haveli 3 rules story part 1"
Images : Cloudflare Workers AI (FLUX.1 schnell), free plan, capped per day. No paid fallback.
Voice  : Piper neural TTS (Hindi, open source).
Motion : slow zoom/pan (Ken Burns) + grain, flicker, vignette, rendered by FFmpeg.
If AI images/voice are unavailable the run STOPS, unless ALLOW_PLACEHOLDER=1 (non-AI test mode).
"""
import argparse, base64, datetime, hashlib, io, json, math, os, random, re, shutil, subprocess, sys
import urllib.error, urllib.request, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import tectoji, studio

W, H, FPS, SR = tectoji.W, tectoji.H, tectoji.FPS, tectoji.SR
ALLOW = os.environ.get("ALLOW_PLACEHOLDER") == "1"
CF_DAILY = int(os.environ.get("CF_IMAGES_PER_DAY", "12"))
PIPER_MODEL = os.environ.get("PIPER_MODEL", "models/hi_IN-rohan-medium.onnx")
STYLE_SUFFIX = (", cinematic dark horror photograph, moody low-key lighting, volumetric fog, "
                "vertical 9:16 composition, subject centered, highly detailed, no text, no watermark")
HI_FONTS = ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]

SAMPLE = dict(
    title="सुनसान हवेली के तीन नियम", summary="A challenge to stay one night in an abandoned haveli with three rules.",
    cliffhanger="A fourth rule was found on the gate.", tags=["#shorts", "#horrorstory", "#hindihorror", "#bhoot", "#tectoji"],
    scenes=[
        ("सुनसान हवेली में रात बिताने की शर्त थी।", "abandoned old Indian haveli gate at night, full moon, thick fog"),
        ("गेट पर लिखा था, तीन नियम मानो, वरना सूरज नहीं देख पाओगे।", "rusted iron gate with faded carved stone wall, dark courtyard beyond"),
        ("पहला नियम. आँगन में पायल की आवाज़ आए, तो पीछे मत देखना।", "empty stone courtyard at night, two old anklets lying on the ground, mist"),
        ("दूसरा नियम. लाल साड़ी वाली औरत दिखे, तो उससे आँख मत मिलाना।", "silhouette of a woman in a red saree under a dark stone arch, face hidden in shadow"),
        ("तीसरा नियम. जब सारी बत्तियाँ बुझ जाएँ, तो अपना नाम मत बोलना।", "dark narrow stone corridor, a single dying oil lamp, long shadows"),
        ("आधी रात को आँगन में पायल छनकने लगी।", "moonlit courtyard, faint ghostly mist swirling near the ground"),
        ("मैंने नियम तोड़ दिया। मैं पीछे मुड़ गया।", "view from behind a man looking back into a dark empty hall, dim cold light"),
        ("वहाँ कोई नहीं था, बस मेरी अपनी परछाई मुस्कुरा रही थी।", "a long stretched shadow on a stone wall, cold moonlight, eerie"),
        ("सुबह लोगों ने हवेली खोली। मैं नहीं मिला, पर गेट पर चौथा नियम लिखा था।", "old haveli gate at dawn, grey light, fog, empty courtyard")])


def hindi_font(size):
    for p in HI_FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ------------------------------------------------------------------ script (Gemini, Hindi)
def hindi_prompt(topic, part, prev):
    p = ("तुम एक हिंदी हॉरर शॉर्ट्स चैनल के लेखक हो। Return ONLY JSON: {title (Hindi, max 60 chars), summary (English, one sentence), "
         "cliffhanger (Hindi or empty), hashtags (5, no spaces, mix Hindi/English), scenes: 8 to 10 items each {hi, img}}. "
         "hi = one narration line in simple spoken Hindi (Devanagari), max 14 words, strong hook first, scary twist near the end. "
         "Total under 110 words. img = an English image prompt for that scene (place, mood, lighting; NO text in image, "
         "no gore, no real people or real places by name, characters only as silhouettes or seen from behind). "
         "Original story only, fictional, safe for general audience.\n\nTopic: " + topic + "\n")
    if part:
        p += f"This is PART {part} of a series.\n"
        for x in (prev or [])[-3:]:
            p += f"- Part {x['part']}: {x['summary']} Ended with: {x.get('cliffhanger', '')}\n"
        p += "Continue the same story and characters. End with a cliffhanger.\n"
    return p


def clean_hindi_plan(plan):
    sc = []
    for s in plan.get("scenes", [])[:10]:
        hi = re.sub(r"\s+", " ", str(s.get("hi", ""))).strip()
        img = re.sub(r"\s+", " ", str(s.get("img", ""))).strip()[:300]
        if hi and img and re.search(r"[\u0900-\u097F]", hi):
            sc.append((" ".join(hi.split()[:16]), img))
    if not 6 <= len(sc) <= 10:
        return None
    tags = ["#" + re.sub(r"[^\w]", "", str(t)) for t in plan.get("hashtags", [])]
    tags = [t for t in tags if len(t) > 1][:6]
    if "#shorts" not in [t.lower() for t in tags]:
        tags.insert(0, "#shorts")
    return dict(title=str(plan.get("title", "")).strip()[:70] or "डरावनी कहानी", summary=str(plan.get("summary", ""))[:300],
                cliffhanger=str(plan.get("cliffhanger", ""))[:300], tags=tags, scenes=sc)


# ------------------------------------------------------------------ AI image (Cloudflare FLUX)
def cf_image(prompt):
    acct, tok = os.environ["CF_ACCOUNT_ID"], os.environ["CF_API_TOKEN"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    req = urllib.request.Request(url, json.dumps({"prompt": prompt, "steps": 6}).encode(),
                                 {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return Image.open(io.BytesIO(base64.b64decode(data["result"]["image"]))).convert("RGB")


def placeholder_image(seed):
    """NON-AI test image (only with ALLOW_PLACEHOLDER=1)."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, 1344)[:, None, None]
    base = np.array([10, 14, 24]) * (1 - y) + np.array([30, 10, 10]) * y
    im = Image.fromarray(np.broadcast_to(base, (1344, 768, 3)).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse((520, 150, 640, 270), fill=(200, 200, 190))
    d.polygon([(200, 1344), (200, 600), (384, 450), (568, 600), (568, 1344)], fill=(6, 6, 8))
    d.rectangle((340, 900, 430, 1344), fill=(24, 18, 12))
    return im


def get_images(scenes, cf_state, seed):
    imgs, ai = [], 0
    have_key = os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_API_TOKEN")
    for i, (_, p) in enumerate(scenes):
        im = None
        today = datetime.date.today().isoformat()
        if have_key and cf_state.get(today, 0) < CF_DAILY:
            for attempt in range(2):
                try:
                    cf_state[today] = cf_state.get(today, 0) + 1
                    im = cf_image(p + STYLE_SUFFIX); ai += 1
                    break
                except urllib.error.HTTPError as e:
                    print(f"image {i}: Cloudflare HTTP {e.code}")
                    if e.code in (429, 403, 401):
                        cf_state[today] = CF_DAILY  # quota/permission problem: stop calling today
                        break
                except Exception as e:
                    print(f"image {i}: {type(e).__name__}")
        if im is None:
            if not ALLOW:
                sys.exit("STOP: AI image not available (missing Cloudflare keys or free quota used up). "
                         "No paid service was used. Try again tomorrow, or set ALLOW_PLACEHOLDER=1 to test with non-AI images.")
            im = placeholder_image(seed + i)
        imgs.append(im)
    return imgs, ai


# ------------------------------------------------------------------ AI voice (Piper Hindi)
def piper_tts(text, path):
    if not os.path.exists(PIPER_MODEL):
        return False
    for cmd in (["python3", "-m", "piper", "-m", PIPER_MODEL, "-f", path],
                ["python3", "-m", "piper", "--model", PIPER_MODEL, "--output_file", path],
                ["piper", "--model", PIPER_MODEL, "--output_file", path]):
        try:
            r = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=120)
            if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 1000:
                return True
        except Exception:
            continue
    return False


def hindi_tts(text, path):
    if piper_tts(text, path):
        return "piper"
    if not ALLOW:
        sys.exit("STOP: Hindi AI voice (Piper) is not available. No fallback voice used.")
    if shutil.which("espeak-ng") and subprocess.run(["espeak-ng", "-v", "hi", "-s", "120", "-w", path, text],
                                                    capture_output=True).returncode == 0:
        return "espeak"
    n = int(len(text.split()) * 0.45 * 22050)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\x00\x00" * n)
    return "silent"


# ------------------------------------------------------------------ render
def cover_9x16(im, bw, bh):
    iw, ih = im.size
    tr = bw / bh
    if iw / ih > tr:
        nw = int(ih * tr); im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / tr); im = im.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return im.resize((bw, bh), Image.LANCZOS)


def render(scenes, imgs, starts, total, ff, rng):
    BW, BH = int(W * 1.3), int(H * 1.3)
    bases = [cover_9x16(im, BW, BH) for im in imgs]
    motions = [(rng.choice([1.0, 1.28]), rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in scenes]
    font = hindi_font(76)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    vig = tectoji.vignette(); nr = np.random.default_rng(5)
    nf = int(total * FPS); si = 0
    for f in range(nf):
        t = f / FPS
        while si < len(scenes) - 1 and t >= starts[si + 1]:
            si += 1
        end = starts[si + 1] if si + 1 < len(starts) else total
        dur = end - starts[si]; lt = t - starts[si]; p = lt / dur
        z0, px, py = motions[si]
        z = 1.0 + 0.28 * (p if z0 == 1.0 else 1 - p)
        ww, wh = BW / z, BH / z
        x0 = (BW - ww) * (0.5 + 0.5 * px * (p - 0.5) * 2 * 0.8)
        y0 = (BH - wh) * (0.5 + 0.5 * py * (p - 0.5) * 2 * 0.8)
        img = bases[si].resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + ww, y0 + wh))
        img = ImageEnhance.Brightness(img).enhance(0.82 + (0.18 if (int(t * 9) * 7919) % 17 else -0.1))
        img = img.convert("RGBA"); img.alpha_composite(vig)
        # captions: 2-3 word chunks, centered
        words = scenes[si][0].split()
        chunks = [" ".join(words[i:i + 3]) for i in range(0, len(words), 3)]
        vd = scenes[si + 0][2] if len(scenes[si]) > 2 else dur
        k = min(len(chunks) - 1, int(max(0.0, lt - 0.2) / max(0.3, vd) * len(chunks)))
        d = ImageDraw.Draw(img)
        d.text((W / 2, H * 0.52), chunks[k], font=font, fill=(245, 245, 245, 255), anchor="mm",
               stroke_width=8, stroke_fill=(0, 0, 0, 255))
        g = (nr.random((H // 6, W // 6)) > 0.95)
        arr = np.zeros((H // 6, W // 6, 4), np.uint8); arr[..., :3] = 255; arr[..., 3] = g * 22
        img.alpha_composite(Image.fromarray(arr, "RGBA").resize((W, H), Image.NEAREST))
        fade = min(1.0, lt / 0.3, (dur - lt) / 0.25)
        if fade < 1.0:
            img = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), img, max(0.0, fade))
        ff.write(img.convert("RGB").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    seed = a.seed or random.randint(1, 10 ** 6)
    rng = random.Random(seed)
    tp = studio.parse_topic(a.topic)
    S = studio.STATE
    history = studio.jload(f"{S}/history.json", [])
    usage = studio.jload(f"{S}/usage.json", {})
    cf_state = studio.jload(f"{S}/cf_usage.json", {})
    sp = f"{S}/series/{tp['series']}.json" if tp["series"] else None
    series = studio.jload(sp, dict(title=tp["clean"], parts=[])) if sp else None
    part = tp["part"]
    if series is not None:
        have = [x["part"] for x in series["parts"]]
        if tp["cont"] and not part:
            part = (max(have) + 1) if have else 1
        if part in have:
            sys.exit(f"STOP: part {part} already exists.")
        if part > 1 and (part - 1) not in have:
            sys.exit(f"STOP: part {part - 1} not found. Make that part first.")
    prev = series["parts"] if series else []

    plan, llm = None, False
    for _ in range(2):
        if plan or not studio.llm_allowed(usage):
            break
        try:
            studio.bump_usage(usage)
            c = clean_hindi_plan(studio.gemini(hindi_prompt(tp["clean"], part, prev)))
            if c and not studio.is_duplicate(" ".join(s[0] for s in c["scenes"]), history):
                plan, llm = c, True
        except urllib.error.HTTPError as e:
            print(f"Gemini HTTP {e.code}")
            usage[datetime.date.today().isoformat()] = studio.DAILY_CAP
        except Exception as e:
            print("Gemini failed:", type(e).__name__)
    if plan is None:
        if studio.is_duplicate(" ".join(s[0] for s in SAMPLE["scenes"]), history):
            sys.exit("STOP: no new Hindi script (Gemini key missing or quota used up). Add GEMINI_API_KEY or try tomorrow.")
        plan = dict(SAMPLE); print("Using built-in sample story (no Gemini script).")
    scenes = [[hi, img] for hi, img in plan["scenes"]]

    os.makedirs(a.out, exist_ok=True); tmpd = os.path.join(a.out, "tmp"); os.makedirs(tmpd, exist_ok=True)
    imgs, ai_n = get_images([(s[0], s[1]) for s in scenes], cf_state, seed)
    voice_kind, starts, t = None, [], 0.0
    wavs = []
    for i, s in enumerate(scenes):
        text = ("भाग %d। " % part if (part and i == 0) else "") + s[0]
        wp = os.path.join(tmpd, f"v{i}.wav")
        voice_kind = hindi_tts(text, wp)
        sr, arr = tectoji.read_wav(wp); vd = len(arr) / sr if len(arr) else 2.0
        wavs.append((sr, arr)); s.append(vd)
        starts.append(t); t += max(vd + 0.7, 3.0)
    total = min(t + 0.8, 59.0)
    starts = [min(x, total - 1) for x in starts]

    buf = tectoji.horror_music(total, rng) * 0.5
    for i, (sr, arr) in enumerate(wavs):
        tectoji.add_sfx(buf, starts[i], "thud")
        if len(arr):
            v = np.interp(np.arange(int(len(arr) * SR / sr)) / SR * sr, np.arange(len(arr)), arr)
            st = int((starts[i] + 0.2) * SR); e = min(len(buf), st + len(v))
            if e > st:
                buf[st:e] += v[:e - st] * 1.3
    tectoji.add_sfx(buf, total - 0.9, "scare")
    buf = np.clip(buf / max(1.0, np.abs(buf).max()) * 0.95, -1, 1)
    wpath = os.path.join(tmpd, "mix.wav")
    with wave.open(wpath, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype(np.int16).tobytes())
    mp4 = os.path.join(a.out, "short.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", wpath, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    render([tuple(s) for s in scenes], imgs, starts, total, pr.stdin, rng)
    pr.stdin.close()
    if pr.wait() != 0:
        sys.exit("ffmpeg failed")

    title = plan["title"] + (f" (भाग {part})" if part else "")
    desc = (scenes[0][0] + "\n\n" + plan.get("summary", "") +
            "\n\nकाल्पनिक कहानी। AI से बनी तस्वीरें और आवाज़ (AI-generated visuals and voice). Fictional story." +
            "\n\n" + " ".join(plan["tags"]))
    meta = dict(title=title[:100], description=desc, tags=[t[1:] for t in plan["tags"]], language="hi",
                contains_synthetic_media=True, duration_s=round(total, 1), ai_images=f"{ai_n}/{len(scenes)}",
                voice=voice_kind, llm_script=llm, part=part, series=tp["series"], topic=a.topic, seed=seed)
    studio.jsave(os.path.join(a.out, "meta.json"), meta)
    full = " ".join(s[0] for s in scenes)
    history.append(dict(date=datetime.date.today().isoformat(), topic=a.topic, series=tp["series"], part=part, title=title,
                        hash=hashlib.sha1(" ".join(studio.norm_words(full)).encode()).hexdigest(), text=full))
    studio.jsave(f"{S}/history.json", history[-300:]); studio.jsave(f"{S}/usage.json", usage)
    studio.jsave(f"{S}/cf_usage.json", cf_state)
    if series is not None:
        series["parts"].append(dict(part=part, summary=plan.get("summary", ""), cliffhanger=plan.get("cliffhanger", ""), title=title))
        studio.jsave(sp, series)
    shutil.rmtree(tmpd, ignore_errors=True)
    print("DONE:", title, "| AI images:", meta["ai_images"], "| voice:", voice_kind, "|", meta["duration_s"], "s")


if __name__ == "__main__":
    main()
