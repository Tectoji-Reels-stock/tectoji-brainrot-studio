#!/usr/bin/env python3
"""Tectoji Studio - Stage 2. Type a topic -> a new Short.
  python studio.py --topic "haunted school horror story part 1"
Series: "... part N" continues a series; "... continue" makes the next part automatically.
Uses Gemini free tier if GEMINI_API_KEY is set (never enables billing); otherwise an offline
fallback generator. Stops safely when the daily call cap or API quota is reached.
"""
import argparse, datetime, hashlib, json, os, random, re, sys, urllib.error, urllib.request
import tectoji

STATE = "state"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DAILY_CAP = int(os.environ.get("GEMINI_DAILY_MAX", "15"))
SAFE_EMOJI = list("👻💀🦇🌙🌝🔦🚪🧟🧛🐺🐱🐶🐸🐍🦉🌵🍌🍞🧦🧀🍝🥒🥔🍩🥄🧮🔑🚀🥪🎈🧲⏰🍕🍔🤡👽🤖🧠👀🦷🔥💥⭐🌍🏫🏠🚗🚌📱💻📺📞🎃😱😈🤯")
KEYWORD_EMOJI = {"school": "🏫", "house": "🏠", "ghost": "👻", "night": "🌙", "moon": "🌝", "door": "🚪",
                 "phone": "📱", "tv": "📺", "robot": "🤖", "alien": "👽", "cat": "🐱", "dog": "🐶",
                 "clown": "🤡", "bus": "🚌", "car": "🚗", "key": "🔑", "clock": "⏰", "pizza": "🍕"}
STOP = {"story", "stories", "video", "short", "horror", "scary", "funny", "brainrot", "about", "a", "the",
        "of", "and", "news", "broadcast", "breaking", "emergency"}


# ------------------------------------------------------------------ state
def jload(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def jsave(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w"), ensure_ascii=False, indent=2)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "untitled"


def parse_topic(topic):
    t = topic.strip()
    m = re.search(r"\bpart\s*(\d+)\b", t, re.I)
    part = int(m.group(1)) if m else None
    cont = bool(re.search(r"\b(continue|continued|next part)\b", t, re.I))
    clean = re.sub(r"\bpart\s*\d+\b|\b(continue|continued|next part)\b", "", t, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip(" -:,.") or t
    series = slugify(clean) if (part or cont) else None
    return dict(clean=clean, part=part, cont=cont, series=series)


def infer_style(topic):
    t = topic.lower()
    if re.search(r"analog|\bebs\b|emergency broadcast|alert system|broadcast horror|signal", t):
        return "analog"
    if re.search(r"horror|scary|ghost|haunt|creep|dark|night|curse|demon|spooky", t):
        return "horror"
    if re.search(r"news|breaking|alert|broadcast|warning|emergency|report", t):
        return "broadcast"
    return "brainrot"


def norm_words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def similarity(a, b):
    def sh(x):
        w = norm_words(x)
        return {" ".join(w[i:i + 4]) for i in range(max(1, len(w) - 3))}
    A, B = sh(a), sh(b)
    return len(A & B) / max(1, len(A | B))


def is_duplicate(text, history):
    h = hashlib.sha1(" ".join(norm_words(text)).encode()).hexdigest()
    for item in history:
        if item.get("hash") == h or similarity(text, item.get("text", "")) > 0.5:
            return True
    return False


# ------------------------------------------------------------------ quota guard
def llm_allowed(usage):
    today = datetime.date.today().isoformat()
    return os.environ.get("GEMINI_API_KEY") and usage.get(today, 0) < DAILY_CAP


def bump_usage(usage):
    today = datetime.date.today().isoformat()
    for k in [k for k in usage if k != today]:
        usage.pop(k)  # keep only today
    usage[today] = usage.get(today, 0) + 1


# ------------------------------------------------------------------ LLM
def build_prompt(topic, style, part, prev_parts):
    rules = (
        "You write 25-second vertical video scripts for an original comedy/horror Shorts channel called Tectoji. "
        "Return ONLY JSON with keys: title (max 70 chars), style (horror|broadcast|brainrot|analog), "
        "summary (one sentence of what happened), cliffhanger (one sentence, or empty if finished), "
        "(for each scene also give icon: one of door, window, tv, bed, phone, eye, house, person, lamp), "
        "hashtags (5 items, no spaces), scenes (7 or 8 items, each {text, emojis}). "
        "Each scene text is spoken aloud: max 11 words, plain English, strong hook in scene 1, "
        "a twist near the end. Total under 70 words. emojis = 1 or 2 emojis chosen ONLY from this list: "
        + "".join(SAFE_EMOJI) + ". "
        "Original characters only: no existing brands, copyrighted characters or real people. "
        "No graphic violence, gore, hate, or real-world misinformation. Absurd and funny-creepy, not disturbing."
    )
    ctx = f"Topic: {topic}\nStyle: {style}\n"
    if style == "analog":
        ctx += ("ANALOG HORROR FORMAT: a deadpan fictional emergency broadcast (call it the Tectoji Alert System, "
                "never a real agency) giving short imperative safety instructions, each one slightly more wrong "
                "and more frightening than the last (e.g. rules about doors, lights, phones, counting people). "
                "Max 8 words per scene, calm and formal, last scene implies the threat is now very close. "
                "Mention things that can be shown as simple icons: door, house, tv, phone, bed, moon, eye, lamp, person.\n")
    if style == "analog":
        ctx += ("Write it like a creepy FICTIONAL emergency broadcast: calm imperative safety instructions "
                "that get stranger, max 8 words per scene. Nothing harming children or animals, nothing graphic.\n")
    if part:
        ctx += f"This is PART {part} of a series. "
        if prev_parts:
            ctx += "Previous parts (keep the same characters and continue the story):\n"
            for p in prev_parts[-3:]:
                ctx += f"- Part {p['part']}: {p['summary']} Ended with: {p.get('cliffhanger', '')}\n"
        ctx += "End with a cliffhanger that makes people want the next part.\n"
    return rules + "\n\n" + ctx


def gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0}}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json",
                                             "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    txt = data["candidates"][0]["content"]["parts"][0]["text"]
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    return json.loads(txt)


def clean_plan(plan, style):
    scenes = []
    for s in plan.get("scenes", [])[:9]:
        text = re.sub(r"\s+", " ", str(s.get("text", ""))).strip()
        if not text:
            continue
        text = " ".join(text.split()[:16])
        ems = [e for e in s.get("emojis", []) if e in SAFE_EMOJI][:2] or ["👻"]
        icon = s.get("icon") if s.get("icon") in tectoji.ICON_NAMES else None
        scenes.append(dict(text=text, emojis=ems, icon=icon))
    if not 5 <= len(scenes) <= 9:
        return None
    tags = [re.sub(r"[^A-Za-z0-9_]", "", str(t)) for t in plan.get("hashtags", [])]
    tags = ["#" + t for t in tags if t][:6]
    if "#shorts" not in [t.lower() for t in tags]:
        tags.insert(0, "#shorts")
    st = plan.get("style") if plan.get("style") in ("horror", "broadcast", "brainrot", "analog") else style
    return dict(title=str(plan.get("title", "")).strip()[:70] or "Tectoji Short", style=st, scenes=scenes,
                summary=str(plan.get("summary", "")).strip()[:300],
                cliffhanger=str(plan.get("cliffhanger", "")).strip()[:300], tags=tags)


# ------------------------------------------------------------------ offline fallback
def fallback_plan(clean, style, seed, part):
    words = [w for w in norm_words(clean) if w not in STOP] or ["mystery"]
    phrase = " ".join(words[:3])
    emoji = next((e for k, e in KEYWORD_EMOJI.items() if k in clean.lower()), random.Random(seed).choice(SAFE_EMOJI))
    old = tectoji.OBJS
    tectoji.OBJS = [(phrase, emoji)]
    try:
        ctx, scenes, chars = tectoji.make_script(random.Random(seed), style)
    finally:
        tectoji.OBJS = old
    out = [dict(text=s["text"], emojis=s["sprites"][:2]) for s in scenes]
    title = f"{phrase.title()}" + (f" (Part {part})" if part else "")
    tags = ["#shorts", "#" + style, "#tectoji", "#funny", "#story"]
    return dict(title=title[:70], style=style, scenes=out, tags=tags,
                summary=out[0]["text"] + " " + out[-2]["text"], cliffhanger="")


# ------------------------------------------------------------------ patch tectoji with our plan
def install_plan(plan, topic_phrase, part):
    calls = {"n": 0}
    texts = [s["text"] for s in plan["scenes"]]
    if part and part > 1:
        texts[0] = f"Part {part}. " + texts[0]
    elif part == 1:
        texts[0] = "Part 1. " + texts[0]

    def make_script(rng, style):
        sc = []
        for t, s in zip(texts, plan["scenes"]):
            sc.append(dict(text=t, sprites=s["emojis"], motion=rng.choice(tectoji.MOTIONS[style]),
                           bg=rng.choice(tectoji.PAL[style]), icon=s.get("icon")))
        for _ in range(calls["n"]):  # too long for 35s: drop the longest middle scene
            if len(sc) > 5:
                i = max(range(1, len(sc) - 1), key=lambda k: len(sc[k]["text"]))
                sc.pop(i)
        calls["n"] += 1
        e0 = plan["scenes"][0]["emojis"][0]
        ctx = dict(A="", B="", O=topic_phrase, P="", S="", F="", R="")
        return ctx, sc, (("", e0), ("", e0), (topic_phrase, e0))

    def make_meta(ctx, scenes, chars, style):
        title = plan["title"] + (f" (Part {part})" if part and f"part {part}" not in plan["title"].lower() else "")
        desc = (scenes[0]["text"] + "\n\n" + plan.get("summary", "") +
                "\n\nAn original story made with AI tools. Fictional." +
                (" Not a real emergency alert." if style in ("analog", "broadcast") else "") +
                ("\nFollow for the next part!" if plan.get("cliffhanger") else "") +
                "\n\n" + " ".join(plan["tags"]))
        return dict(title=title[:100], description=desc, tags=[t[1:] for t in plan["tags"]], style=style,
                    script_hash=hashlib.sha1(" ".join(s["text"] for s in scenes).encode()).hexdigest())

    tectoji.make_script = make_script
    tectoji.make_meta = make_meta


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--style", default="auto", choices=["auto", "brainrot", "broadcast", "horror", "analog"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    tp = parse_topic(a.topic)
    style = infer_style(a.topic) if a.style == "auto" else a.style
    seed = a.seed or random.randint(1, 10 ** 6)
    history = jload(f"{STATE}/history.json", [])
    usage = jload(f"{STATE}/usage.json", {})
    series_path = f"{STATE}/series/{tp['series']}.json" if tp["series"] else None
    series = jload(series_path, dict(title=tp["clean"], parts=[])) if series_path else None

    part = tp["part"]
    if series is not None:
        have = [p["part"] for p in series["parts"]]
        if tp["cont"] and not part:
            part = (max(have) + 1) if have else 1
        if part in have:
            sys.exit(f"STOP: part {part} of '{tp['clean']}' already exists. Ask for part {max(have) + 1}.")
        if part > 1 and (part - 1) not in have:
            sys.exit(f"STOP: part {part - 1} of '{tp['clean']}' not found. Make that part first.")
    prev = series["parts"] if series else []

    plan, llm_used, note = None, False, ""
    tries = 0
    while llm_allowed(usage) and tries < 3 and plan is None:
        tries += 1
        try:
            bump_usage(usage)
            cand = clean_plan(gemini(build_prompt(a.topic if not series else tp["clean"], style, part, prev)), style)
            if cand and not is_duplicate(" ".join(s["text"] for s in cand["scenes"]), history):
                plan, llm_used = cand, True
                if a.style == "auto":
                    style = cand["style"]
        except urllib.error.HTTPError as e:
            note = f"Gemini HTTP {e.code} (quota or key problem). Using offline generator. No paid service used."
            print(note)
            if e.code in (429, 403):
                usage[datetime.date.today().isoformat()] = DAILY_CAP  # stop calling for today
            break
        except Exception as e:
            note = f"Gemini failed: {type(e).__name__}. Using offline generator."
            print(note)
    if plan is None:
        if not os.environ.get("GEMINI_API_KEY"):
            note = note or "No GEMINI_API_KEY set: using offline generator (stories are simpler, series are not truly continued)."
        elif not llm_allowed(usage) and not note:
            note = "Daily AI call cap reached: using offline generator."
        print(note)
        for k in range(20):
            cand = fallback_plan(tp["clean"], style, seed + k, part)
            if not is_duplicate(" ".join(s["text"] for s in cand["scenes"]), history):
                plan = cand
                break
        if plan is None:
            sys.exit("STOP: could not make a non-duplicate script. Try a different topic.")

    phrase = " ".join([w for w in norm_words(tp["clean"]) if w not in STOP][:3]) or tp["clean"][:20]
    install_plan(plan, phrase, part if series is not None else None)
    tectoji.build(seed, a.out, style)

    meta = jload(os.path.join(a.out, "meta.json"), {})
    script = jload(os.path.join(a.out, "script.json"), [])
    full_text = " ".join(s["text"] for s in script)
    history.append(dict(date=datetime.date.today().isoformat(), topic=a.topic, series=tp["series"], part=part,
                        title=meta.get("title"), hash=hashlib.sha1(" ".join(norm_words(full_text)).encode()).hexdigest(),
                        text=full_text))
    jsave(f"{STATE}/history.json", history[-300:])
    jsave(f"{STATE}/usage.json", usage)
    if series is not None:
        series["parts"].append(dict(part=part, summary=plan["summary"], cliffhanger=plan.get("cliffhanger", ""),
                                    title=meta.get("title")))
        jsave(series_path, series)
    meta.update(llm_used=llm_used, note=note, topic=a.topic, part=part, series=tp["series"])
    jsave(os.path.join(a.out, "meta.json"), meta)
    print("DONE:", meta.get("title"), "| ai:", llm_used, "| style:", style, "| part:", part)


if __name__ == "__main__":
    main()
