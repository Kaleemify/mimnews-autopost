#!/usr/bin/env python3
"""
MIM News autopost: Facebook page -> website.

  check mode (--check)  : cheap. Asks Facebook for recent posts, asks the website which ones are new, prints work=true/false.
  run mode              : for each new post (oldest first, max MAX_PER_RUN):
                          video -> download -> audio -> transcript (faster-whisper) -> cover frame
                          text/photo -> use caption (+ photo)
                          -> Gemini (free tier) writes a Pinglish news item from ONLY those facts
                          -> POST to the website's /mim/v1/autopost/publish

Environment (GitHub Secrets / variables):
  FB_PAGE_ID, FB_PAGE_TOKEN   Facebook page id + page access token (required)
  MIM_KEY                     shared key for the website endpoint (required)
  MIM_URL                     default https://mimnews.com
  GEMINI_API_KEY              optional; without it items are saved as DRAFT with the raw caption/transcript
  GEMINI_MODEL                optional; default tries gemini-flash-lite-latest, gemini-flash-latest, gemini-3.5-flash-lite, gemini-3.5-flash
  WHISPER_MODEL               default small      WHISPER_LANG  optional (e.g. ur); empty = auto-detect
  WINDOW_HOURS                default 24   only posts newer than this are published; older unseen ones are ignored
  MAX_PER_RUN                 default 3
  MAX_VIDEO_MIN               default 15   longer videos: no transcript (caption only)
  MIN_TEXT_CHARS              default 30   text-only posts shorter than this are ignored
  DRY_RUN=1                   print what would happen, publish nothing, mark nothing
Never prints tokens or keys.
"""
import base64, json, os, re, subprocess, sys, tempfile, time
from datetime import datetime, timezone, timedelta
import requests

GRAPH = env_graph = __import__("os").environ.get("GRAPH_BASE") or "https://graph.facebook.com/v21.0"
CATS = ["pakistan", "crime-report", "international", "education", "breaking-news", "blog"]

def env(k, d=""):
    v = os.environ.get(k)
    return v if v not in (None, "") else d

FB_PAGE_ID = env("FB_PAGE_ID"); FB_TOKEN = env("FB_PAGE_TOKEN")
MIM_KEY = env("MIM_KEY"); MIM_URL = env("MIM_URL", "https://mimnews.com").rstrip("/")
GEMINI_KEY = env("GEMINI_API_KEY"); GEMINI_MODEL = env("GEMINI_MODEL", "")
WHISPER_MODEL = env("WHISPER_MODEL", "small"); WHISPER_LANG = env("WHISPER_LANG")
WINDOW_HOURS = float(env("WINDOW_HOURS", "24")); MAX_PER_RUN = int(env("MAX_PER_RUN", "8"))
MAX_VIDEO_MIN = float(env("MAX_VIDEO_MIN", "15")); MIN_TEXT = int(env("MIN_TEXT_CHARS", "30"))
DRY = env("DRY_RUN") == "1"

def log(*a): print(*a, flush=True)

def safe_err(e):
    """Short error text with no URLs (URLs can carry tokens)."""
    if isinstance(e, requests.HTTPError) and e.response is not None:
        try: j = e.response.json(); m = (j.get("error") or {}).get("message") or str(j)[:200]
        except Exception: m = e.response.text[:200]
        return f"HTTP {e.response.status_code}: {m}"
    return type(e).__name__ + ": " + re.sub(r"https?://\S+", "<url>", str(e))[:200]

# ------------------------------------------------------------------ website
def retry(fn, tries=4):
    """Hosts (Hostinger, Facebook) sometimes reset a connection once; try again with a pause."""
    for i in range(tries):
        try: return fn()
        except (requests.ConnectionError, requests.Timeout) as e:
            if i == tries - 1: raise
            log(f"   (network hiccup: {type(e).__name__}; retry {i + 1}/{tries - 1})")
            time.sleep(4 * (i + 1))

def mim(path, payload, timeout=120):
    for attempt in range(4):
        r = retry(lambda: requests.post(f"{MIM_URL}/wp-json/mim/v1/autopost/{path}", json=payload, headers={"X-MIM-Key": MIM_KEY, "User-Agent": "mim-autopost/1.0"}, timeout=timeout))
        if r.status_code in (502, 503, 504, 520, 521, 522, 523, 524) and attempt < 3:
            log(f"   (website busy: HTTP {r.status_code}; retry {attempt + 1}/3)"); time.sleep(10 * (attempt + 1)); continue
        break
    if r.status_code in (423, 429): return r.status_code, r.json()
    r.raise_for_status(); return r.status_code, r.json()

# ----------------------------------------------------------------- facebook
def fb_get(path, **params):
    params["access_token"] = FB_TOKEN
    r = retry(lambda: requests.get(f"{GRAPH}/{path}", params=params, timeout=60))
    r.raise_for_status(); return r.json()

def fetch_feed():
    fields = ("id,message,created_time,permalink_url,full_picture,status_type,"
              "attachments{media_type,type,target{id},media{image{src}},subattachments{media_type,target{id},media{image{src}}}}")
    return fb_get(f"{FB_PAGE_ID}/published_posts", fields=fields, limit=20).get("data", [])

def post_kind(p):
    atts = (p.get("attachments") or {}).get("data") or []
    for a in atts:
        if a.get("media_type") == "video" or a.get("type") in ("video_inline", "video_direct_response", "video_autoplay"):
            return "video", (a.get("target") or {}).get("id")
    for a in atts:
        for s in ((a.get("subattachments") or {}).get("data") or []):
            if s.get("media_type") == "video": return "video", (s.get("target") or {}).get("id")
    return ("photo" if p.get("full_picture") else "text"), None

def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)

# -------------------------------------------------------------------- media
def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)

def download(url, dest, limit_mb=500):
    n = 0
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                n += len(chunk)
                if n > limit_mb * 1048576: raise RuntimeError("video too large")
                f.write(chunk)
    return n

def duration(path):
    try: return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path]).stdout.strip())
    except Exception: return 0.0

def frame_b64(video, at):
    out = video + ".jpg"
    run(["ffmpeg", "-y", "-ss", str(max(0.5, at)), "-i", video, "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "4", out])
    with open(out, "rb") as f: return base64.b64encode(f.read()).decode()

_whisper = None
def transcribe(video):
    global _whisper
    from faster_whisper import WhisperModel
    if _whisper is None: _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    wav = video + ".wav"
    run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", wav])
    # Decode the 16 kHz mono wav ourselves: faster-whisper's own file reader (PyAV) breaks on some version combinations.
    import wave, numpy as np
    with wave.open(wav, "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, info = _whisper.transcribe(audio, language=WHISPER_LANG or None, vad_filter=True, beam_size=5)
    text = " ".join(s.text.strip() for s in segs).strip()
    return text, info.language, float(getattr(info, "language_probability", 0) or 0)

# ------------------------------------------------------------------- writing
PROMPT = """You are the desk editor of MIM News, a Pakistani news website. Write ONE short news item from the material below.

RULES (strict):
- Language: Pinglish = Roman Urdu in English letters, the way Pakistani newsrooms type it (e.g. "Karachi mein aaj ...", "wazir-e-azam ne kaha ke ..."). Names, places, numbers, dates must stay exactly as in the material.
- Write EVERYTHING in English (Latin) letters. Never output any Urdu/Arabic-script character, not even a single word such as police or discount in Urdu script. Transliterate every word.
- Use ONLY facts that appear in the material. Do NOT add details, quotes, causes, or numbers that are not there. If something is unclear, leave it out.
- No clickbait, no opinion, no emojis, no hashtags. Neutral news tone. Attribute claims ("... ke mutabiq", "... ne kaha").
- "title": 8 to 22 words, plain headline, no quotes around it.
- "paragraphs": 2 to 6 short paragraphs (1 to 3 sentences each). The first paragraph answers who/what/where/when.
- "category": exactly one of: {cats}.
- If the material is not news (greeting, advert, personal post), return {{"skip": true}}.
Return ONLY JSON: {{"title": "...", "paragraphs": ["..."], "category": "..."}}

POST CAPTION:
{caption}

VIDEO TRANSCRIPT (auto-generated, may contain mistakes; language: {lang}):
{transcript}
"""

ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")

def gemini_write(caption, transcript, lang):
    item = _gemini_call(caption, transcript, lang, "")
    if item and not item.get("skip"):
        text = " ".join([str(item.get("title", ""))] + [str(x) for x in item.get("paragraphs", [])])
        for attempt in range(2):                      # one or two corrective retries if Urdu script slipped in
            bad = ARABIC.findall(text)
            if not bad: break
            words = sorted(set(re.findall(r"\S*[؀-ۿ]\S*", text)))[:8]
            log(f"   gemini used Urdu script ({len(bad)} chars): retrying in Roman letters")
            again = _gemini_call(caption, transcript, lang, "\n\nYour previous answer contained words in Urdu script: " + ", ".join(words) + ". Rewrite the WHOLE item again using Latin letters only.")
            if not again or again.get("skip"): break
            item = again; text = " ".join([str(item.get("title", ""))] + [str(x) for x in item.get("paragraphs", [])])
        if ARABIC.search(text): item["_urdu_script"] = True
    return item

def _gemini_call(caption, transcript, lang, extra):
    if not GEMINI_KEY: return None
    body = {"contents": [{"parts": [{"text": PROMPT.format(cats=", ".join(CATS), caption=caption or "(none)", transcript=(transcript or "(none)")[:12000], lang=lang or "unknown") + extra}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    base = env('GEMINI_BASE', 'https://generativelanguage.googleapis.com/v1beta')
    # Model names are retired from time to time (gemini-2.5-* is closed to new keys). Try the configured one first, then the "latest" aliases.
    models = [m for m in dict.fromkeys([GEMINI_MODEL, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash"]) if m]
    for model in models:
        url = f"{base}/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, headers={"x-goog-api-key": GEMINI_KEY}, json=body, timeout=60)
            except (requests.ConnectionError, requests.Timeout) as e:
                log(f"   gemini {model}: {type(e).__name__}"); time.sleep(5); continue
            if r.status_code in (404, 400, 403): log(f"   gemini {model}: HTTP {r.status_code} (not usable), trying next"); break
            if r.status_code in (429, 500, 503): time.sleep(8 * (attempt + 1)); continue
            r.raise_for_status()
            try:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(txt)
            except Exception as e:
                log(f"   gemini {model}: unreadable answer ({type(e).__name__}), trying next"); break
    log("   gemini: no model answered (rate limited / unavailable)"); return None

def fallback_item(caption, transcript):
    """No LLM: raw material, ALWAYS saved as draft."""
    first = (caption or transcript or "MIM News report").strip().split("\n")[0]
    title = re.sub(r"\s+", " ", first)[:110]
    paras = [p.strip() for p in (caption or "").split("\n") if p.strip()]
    if transcript:
        sents = re.split(r"(?<=[.!?۔])\s+", transcript)
        for i in range(0, len(sents), 3): paras.append(" ".join(sents[i:i + 3]))
    return {"title": title, "paragraphs": paras[:10] or [title], "category": "blog"}

def quality_ok(item):
    if not item or item.get("skip"): return False
    t = (item.get("title") or "").strip(); ps = [p for p in (item.get("paragraphs") or []) if isinstance(p, str) and p.strip()]
    if item.get("_urdu_script"): return False
    if not (15 <= len(t) <= 170): return False
    if not ps or sum(len(p) for p in ps) < 120: return False
    if item.get("category") not in CATS: item["category"] = "blog"
    return True

# --------------------------------------------------------------------- main
def new_posts():
    feed = fetch_feed()
    ids = [p["id"] for p in feed]
    if not ids: return [], True
    code, j = mim("seen", {"ids": ids})
    if not j.get("enabled", True): log("website says autopost is switched off"); return [], False
    seen = set(j.get("seen", []))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    fresh, old = [], []
    for p in sorted(feed, key=lambda x: x["created_time"]):
        if p["id"] in seen: continue
        (fresh if parse_time(p["created_time"]) >= cutoff else old).append(p)
    if old and not DRY:
        mim("ignore", {"ids": [p["id"] for p in old]}); log(f"ignored {len(old)} older post(s) (older than {WINDOW_HOURS:g}h)")
    elif old: log(f"[dry] would ignore {len(old)} older post(s)")
    return fresh, True

def process(p):
    pid = p["id"]; kind, vid = post_kind(p); caption = (p.get("message") or "").strip()
    log(f"- {pid} [{kind}] {caption[:70]!r}")
    # Election-campaign posts are not news; skip them before spending download/transcribe minutes on them.
    low = caption.lower()
    if any(k in low for k in ("vote & support", "vote and support", "vote &amp; support", "candidate for")) or any(k in caption for k in ("ووٹ اینڈ سپورٹ", "امیدوار برائے")):
        log("   campaign post, ignored")
        if not DRY: mim("ignore", {"ids": [pid]})
        return
    if kind == "text" and len(caption) < MIN_TEXT:
        log("   too short, ignored");
        if not DRY: mim("ignore", {"ids": [pid]})
        return
    transcript, lang, image_b64 = "", "", ""
    image_url = p.get("full_picture") or ""
    status = "publish"
    if kind == "video" and vid:
        try:
            info = fb_get(vid, fields="source,length,picture,permalink_url")
            src = info.get("source"); length = float(info.get("length") or 0)
            image_url = image_url or info.get("picture") or ""
            if not src: log("   no video source link (page token permission?) -> caption only"); status = "draft"
            elif length and length / 60 > MAX_VIDEO_MIN: log(f"   video {length/60:.0f} min > {MAX_VIDEO_MIN:g}: no transcript"); status = "draft"
            elif DRY: log(f"   [dry] would download + transcribe {length:.0f}s video")
            else:
                with tempfile.TemporaryDirectory() as td:
                    path = os.path.join(td, "v.mp4"); mb = download(src, path) / 1048576
                    d = duration(path) or length; log(f"   downloaded {mb:.1f} MB, {d:.0f}s; transcribing ({WHISPER_MODEL})")
                    transcript, lang, prob = transcribe(path)
                    log(f"   transcript: {len(transcript)} chars, language={lang} ({prob:.2f})")
                    if not image_url and d: image_b64 = frame_b64(path, d * 0.15)
        except Exception as e:
            # Do not create a half-made post (no transcript) and do not mark it as handled: it is retried on the next run.
            log("   video step failed:", safe_err(e), "-> skipped, will retry next run"); return
    if DRY: log("   [dry] would write + publish"); return
    item = None
    try: item = gemini_write(caption, transcript, lang)
    except Exception as e: log("   gemini failed:", safe_err(e))
    if item and item.get("skip"):
        log("   editor said: not news -> ignored"); mim("ignore", {"ids": [pid]}); return
    if not quality_ok(item):
        item = fallback_item(caption, transcript); status = "draft"; log("   using raw text (no/failed AI) -> DRAFT")
    if kind == "video" and not transcript and not caption: log("   nothing to write from -> ignored"); mim("ignore", {"ids": [pid]}); return
    if env("FORCE_STATUS") == "draft": status = "draft"   # testing only
    payload = {"fb_id": pid, "fb_url": p.get("permalink_url") or "", "title": item["title"], "paragraphs": item["paragraphs"],
               "category": item.get("category", "blog"), "status": status, "is_video": kind == "video"}
    if image_b64: payload["image_b64"] = image_b64
    elif image_url: payload["image_url"] = image_url
    code, j = mim("publish", payload)
    log(f"   -> {j.get('status') or j}  {j.get('link', '')}  cover={j.get('has_cover')}")
    if code in (423, 429): raise SystemExit(0)

def main():
    miss = [k for k, v in (("FB_PAGE_ID", FB_PAGE_ID), ("FB_PAGE_TOKEN", FB_TOKEN), ("MIM_KEY", MIM_KEY)) if not v]
    if miss:
        if "--check" in sys.argv:   # not set up yet: stay quiet (no failing runs / emails), just flag it
            log(f"::warning::autopost is not set up yet, missing: {', '.join(miss)}")
            out = os.environ.get("GITHUB_OUTPUT")
            if out:
                with open(out, "a") as f: f.write("work=false\n")
            return
        log("missing settings:", ", ".join(miss)); sys.exit(2)
    try: fresh, enabled = new_posts()
    except Exception as e: log("check failed:", safe_err(e)); sys.exit(1)
    work = bool(fresh) and enabled
    if "--check" in sys.argv:
        log(f"new posts: {len(fresh)}")
        for p in fresh: log(f"   queue: [{post_kind(p)[0]}] {(p.get('message') or '').strip()[:70]!r} ({p['created_time'][:16]})")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f: f.write(f"work={'true' if work else 'false'}\n")
        return
    if not fresh: log("nothing new")
    for p in fresh[:MAX_PER_RUN]:
        try: process(p)
        except SystemExit: raise
        except Exception as e: log("   FAILED:", safe_err(e))
    if len(fresh) > MAX_PER_RUN: log(f"{len(fresh) - MAX_PER_RUN} more waiting for the next run")

if __name__ == "__main__":
    main()
