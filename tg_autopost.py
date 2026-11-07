#!/usr/bin/env python3
"""
MIM News Telegram desk -> website.

Reporters / editors send a text, photo, video or voice note to the MIM News Telegram bot.
This job reads those messages (only from allowed Telegram user ids), then for each one:
  video  -> transcript (faster-whisper) + cover frame + compressed copy hosted on the site
  voice  -> transcript
  photo  -> cover image
  text   -> as is
-> Gemini writes a Pinglish news item from ONLY those facts -> published on the website -> the sender gets the link back in Telegram.

  --check   cheap: are there new messages from allowed senders?   (writes work=true/false for GitHub Actions)
  (no flag) process them.

Environment: TG_BOT_TOKEN, TG_ALLOWED_IDS (comma separated numeric user ids), MIM_KEY, MIM_URL, GEMINI_API_KEY, WHISPER_MODEL, WHISPER_LANG
Message tips for senders: start a message with  "draft:"  to save it as a draft instead of publishing.
Never prints tokens or keys.
"""
import base64, os, re, sys, tempfile, time
import requests
import autopost as ap

TOKEN = ap.env("TG_BOT_TOKEN"); ALLOWED = {x.strip() for x in ap.env("TG_ALLOWED_IDS").split(",") if x.strip()}
BASE = ap.env("TG_BASE", "https://api.telegram.org"); ID_PREFIX = ap.env("TG_ID_PREFIX", "tg:")
MAX_ITEMS = int(ap.env("MAX_PER_RUN", "5")); LIMIT_MB = 20   # Telegram bots can download files up to 20 MB
log = ap.log

def api(method, **params):
    r = ap.retry(lambda: requests.post(f"{BASE}/bot{TOKEN}/{method}", json=params, timeout=60))
    try: j = r.json()
    except Exception: r.raise_for_status(); return {}
    if not j.get("ok"): raise RuntimeError(f"telegram {method}: {j.get('description', 'error')[:150]}")
    return j.get("result")

def say(chat_id, text):
    try: api("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)
    except Exception as e: log("   (could not reply:", ap.safe_err(e) + ")")

def tg_download(file_id, dest):
    info = api("getFile", file_id=file_id)
    path = info["file_path"]; n = 0
    with requests.get(f"{BASE}/file/bot{TOKEN}/{path}", stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for c in r.iter_content(1 << 20): n += len(c); f.write(c)
    return n

# ---------------------------------------------------------------- reading updates
def media_of(m):
    """-> (kind, file_id, size) of the main attachment of a Telegram message."""
    if m.get("video"): v = m["video"]; return "video", v["file_id"], v.get("file_size", 0)
    if m.get("animation"): v = m["animation"]; return "video", v["file_id"], v.get("file_size", 0)
    if m.get("video_note"): v = m["video_note"]; return "video", v["file_id"], v.get("file_size", 0)
    if m.get("voice"): v = m["voice"]; return "audio", v["file_id"], v.get("file_size", 0)
    if m.get("audio"): v = m["audio"]; return "audio", v["file_id"], v.get("file_size", 0)
    d = m.get("document")
    if d and (d.get("mime_type") or "").startswith("video/"): return "video", d["file_id"], d.get("file_size", 0)
    if d and (d.get("mime_type") or "").startswith("audio/"): return "audio", d["file_id"], d.get("file_size", 0)
    if m.get("photo"): ph = sorted(m["photo"], key=lambda x: x.get("file_size", 0) or x.get("width", 0))[-1]; return "photo", ph["file_id"], ph.get("file_size", 0)
    return None, None, 0

def collect():
    """-> (items in order, all updates). One item per message, albums merged."""
    ups = api("getUpdates", timeout=0, limit=100, allowed_updates=["message", "channel_post"])
    items, groups = [], {}
    for u in ups:
        m = u.get("message") or u.get("channel_post")
        if not m: continue
        sender = str((m.get("from") or {}).get("id") or (m.get("sender_chat") or {}).get("id") or "")
        if sender not in ALLOWED: continue                       # silently ignore strangers
        text = (m.get("text") or m.get("caption") or "").strip()
        if text.startswith("/"): continue                        # /start etc.
        kind, fid, size = media_of(m)
        if not kind and not text: continue
        key = ("g", m["chat"]["id"], m["media_group_id"]) if m.get("media_group_id") else None
        if key and key in groups:
            g = groups[key]; g["text"] = g["text"] or text; g["uids"].append(u["update_id"])
            if (g["kind"] in (None, "photo")) and kind in ("video", "audio"): g.update(kind=kind, fid=fid, size=size)
            continue
        it = {"id": f"{ID_PREFIX}{m['chat']['id']}:{m['message_id']}", "chat": m["chat"]["id"], "text": text, "kind": kind, "fid": fid, "size": size, "uids": [u["update_id"]],
              "photo_fid": fid if kind == "photo" else None}
        if key: groups[key] = it
        items.append(it)
    return items, ups

# ------------------------------------------------------------------- processing
def compress(src, dst):
    ap.run(["ffmpeg", "-y", "-i", src, "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", dst])

def upload_video(path, name):
    with open(path, "rb") as f: data = f.read()
    r = ap.retry(lambda: requests.post(f"{ap.MIM_URL}/wp-json/mim/v1/autopost/media", data=data, timeout=300,
                 headers={"X-MIM-Key": ap.MIM_KEY, "X-Filename": name, "Content-Type": "video/mp4", "User-Agent": "mim-autopost/1.0"}))
    r.raise_for_status(); return r.json()["url"]

def handle(it):
    """Returns the text to send back to the sender."""
    caption = it["text"]; force_draft = False
    if re.match(r"(?i)^\s*draft\s*:", caption): force_draft = True; caption = re.sub(r"(?i)^\s*draft\s*:\s*", "", caption)
    kind, transcript, lang, image_b64, video_url, notes = it["kind"], "", "", "", "", []
    log(f"- {it['id']} [{kind or 'text'}] {caption[:70]!r}")
    if not kind and len(caption) < ap.MIN_TEXT: return "Khabar bohat chhoti hai (kam az kam 30 harf). Poori khabar likh kar bhejein."
    status = "draft" if force_draft else "publish"
    try:
        if kind in ("video", "audio"):
            if it["size"] and it["size"] > LIMIT_MB * 1048576:
                notes.append(f"{kind} {LIMIT_MB} MB se bari hai, Telegram bot use nahi utha sakta. Chhoti karke bhejein."); status = "draft"
            else:
                with tempfile.TemporaryDirectory() as td:
                    src = os.path.join(td, "in.bin"); tg_download(it["fid"], src)
                    d = ap.duration(src)
                    if d and d / 60 > ap.MAX_VIDEO_MIN: notes.append(f"{kind} {ap.MAX_VIDEO_MIN:g} minute se lambi hai, transcript nahi bana."); status = "draft"
                    else:
                        log(f"   downloaded, {d:.0f}s; transcribing ({ap.WHISPER_MODEL})")
                        transcript, lang, prob = ap.transcribe(src); log(f"   transcript: {len(transcript)} chars, language={lang} ({prob:.2f})")
                    if kind == "video":
                        image_b64 = ap.frame_b64(src, max(0.5, (d or 6) * 0.15)); out = os.path.join(td, "web.mp4"); compress(src, out)
                        video_url = upload_video(out, re.sub(r"[^A-Za-z0-9]+", "-", it["id"]))
                        log("   video hosted on the site")
        if it.get("photo_fid") and not image_b64:
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "p.jpg"); tg_download(it["photo_fid"], p)
                with open(p, "rb") as f: image_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        log("   media step failed:", ap.safe_err(e)); notes.append("Media (video/photo) process nahi ho saka."); status = "draft"
    if kind and not caption and not transcript: return "Is mein se khabar nahi nikal saka (na caption, na awaaz). Caption ke saath dobara bhejein."
    item = None
    try: item = ap.gemini_write(caption, transcript, lang)
    except Exception as e: log("   gemini failed:", ap.safe_err(e))
    if item and item.get("skip"): return "Editor AI ne ise khabar nahi samjha, isliye publish nahi kiya. Zyada tafseel likh kar bhejein."
    if not ap.quality_ok(item):
        item = ap.fallback_item(caption, transcript); status = "draft"; notes.append("AI text nahi bana saka, kaccha text draft mein rakha.")
    if ap.env("FORCE_STATUS") == "draft": status = "draft"
    payload = {"fb_id": it["id"], "title": item["title"], "paragraphs": item["paragraphs"], "category": item.get("category", "blog"), "status": status}
    if video_url: payload["video_url"] = video_url
    if image_b64: payload["image_b64"] = image_b64
    code, j = ap.mim("publish", payload)
    log(f"   -> {j.get('status') or j}  {j.get('link', '')}")
    if code in (423, 429): return "Website ne abhi naya post nahi liya (switch off ya limit). Baad mein try karein."
    head = "Publish ho gayi:" if j.get("status") == "publish" else "Draft mein save hui (admin check kar ke publish karega):"
    return head + " " + j.get("link", "") + ("\n" + "\n".join("- " + n for n in notes) if notes else "")

def main():
    miss = [k for k, v in (("TG_BOT_TOKEN", TOKEN), ("TG_ALLOWED_IDS", ALLOWED), ("MIM_KEY", ap.MIM_KEY)) if not v]
    check = "--check" in sys.argv; out = os.environ.get("GITHUB_OUTPUT")
    def result(work):
        if check and out:
            with open(out, "a") as f: f.write(f"work={'true' if work else 'false'}\n")
    if miss:
        if check: log(f"::warning::telegram desk is not set up yet, missing: {', '.join(miss)}"); result(False); return
        log("missing settings:", ", ".join(miss)); sys.exit(2)
    try:
        items, ups = collect()
        ids = [i["id"] for i in items]
        seen, enabled = set(), True
        if ids: _, j = ap.mim("seen", {"ids": ids}); seen = set(j.get("seen", [])); enabled = j.get("enabled", True)
    except Exception as e: log("check failed:", ap.safe_err(e)); sys.exit(1)
    todo = [i for i in items if i["id"] not in seen]
    if check: log(f"new messages: {len(todo)}"); result(bool(todo) and enabled); return
    if not enabled and todo: log("website says autopost is switched off"); return
    handled, done_uids, stopped_early = 0, [], False
    for it in items:
        if it["id"] in seen: done_uids += it["uids"]; continue
        if handled >= MAX_ITEMS: stopped_early = True; break
        try: reply = handle(it)
        except SystemExit: raise
        except Exception as e: log("   FAILED:", ap.safe_err(e)); reply = "Process karte hue masla aaya. Dobara bhejein."
        handled += 1; done_uids += it["uids"]
        say(it["chat"], reply)
    if not todo: log("nothing new")
    if stopped_early: log("more messages waiting for the next run")
    if ups:   # tell Telegram what we have handled; strangers' messages and /commands are dropped with them
        if stopped_early: last = max(done_uids)
        else: last = max(u["update_id"] for u in ups)
        api("getUpdates", offset=last + 1, timeout=0, limit=1)

if __name__ == "__main__":
    main()
