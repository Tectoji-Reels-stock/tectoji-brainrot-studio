#!/usr/bin/env python3
"""Pixazo image-to-video (AI video clip from an AI image). OPT-IN, capped, never loops on errors.
Default model: ltx-2-3-transition (cheapest documented LTX image-to-video on Pixazo; billed per second from your Pixazo balance).
Check the price on pixazo.ai/models/ltx before enabling. A 402 (no balance) or 401/403/429 stops video for the run.
"""
import json, os, time, urllib.error, urllib.request

MODEL = os.environ.get("PIXAZO_VIDEO_MODEL", "ltx-2-3-transition")
POLL_S = float(os.environ.get("PIXAZO_POLL_SECONDS", "25"))
TIMEOUT_S = float(os.environ.get("PIXAZO_VIDEO_TIMEOUT", "1500"))
BASE = "https://gateway.pixazo.ai"


class VideoStop(Exception):
    """Key/balance/rate problem: stop making video clips for this run."""


def _hdr():
    return {"Ocp-Apim-Subscription-Key": os.environ["PIXAZO_API_KEY"], "Content-Type": "application/json"}


def animate(image_url, prompt, seed, out_path):
    body = {"prompt": prompt, "first_image": image_url, "duration": 5, "resolution": "low",
            "aspect_ratio": "9:16", "seed": int(seed) % 2147483647}
    try:
        req = urllib.request.Request(f"{BASE}/{MODEL}/v1/image-to-video", json.dumps(body).encode(), _hdr())
        with urllib.request.urlopen(req, timeout=60) as r:
            rid = json.load(r)["request_id"]
        t0 = time.time()
        while time.time() - t0 < TIMEOUT_S:
            time.sleep(POLL_S)
            st = urllib.request.Request(f"{BASE}/v2/requests/status/{rid}", headers=_hdr())
            with urllib.request.urlopen(st, timeout=60) as r:
                d = json.load(r)
            s = d.get("status")
            if s == "COMPLETED":
                url = d["output"]["media_url"][0]
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
                    open(out_path, "wb").write(r.read())
                return out_path
            if s not in ("QUEUED", "PROCESSING"):
                raise RuntimeError(f"video failed: {d.get('error')}")
        raise TimeoutError("video took too long")
    except urllib.error.HTTPError as e:
        if e.code in (401, 402, 403, 429):
            raise VideoStop(f"Pixazo HTTP {e.code} (key, balance or rate limit)")
        raise
