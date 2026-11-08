"""One-off check: does the GEMINI_API_KEY work, and which model name answers fast? Prints status, timing and answer only, never the key."""
import json, os, time, urllib.error, urllib.request

key = os.environ.get("GEMINI_API_KEY", "")
print("key present:", bool(key), "| length:", len(key))
prompt = ('Rewrite as a short Pinglish (Roman Urdu, English letters) news item. Use ONLY these facts. '
          'Return JSON like {"title": "...", "paragraphs": ["..."]}. '
          'Facts: Sindh Education Minister Syed Sardar Shah said schools will reopen as scheduled, and the '
          'holiday-extension notification going around on social media is fake.')
ok = 0
for model in ["gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]:
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=60)
        j = json.load(r)
        print(f"MODEL {model} -> HTTP {r.status} in {time.time() - t0:.1f}s")
        print("ANSWER:", j["candidates"][0]["content"]["parts"][0]["text"].strip()[:600])
        ok += 1
    except urllib.error.HTTPError as e:
        msg = e.read().decode().replace("\n", " ").replace(key, "<key>")
        print(f"MODEL {model} -> HTTP {e.code} in {time.time() - t0:.1f}s", msg[:250])
    except Exception as e:
        print(f"MODEL {model} -> {type(e).__name__} after {time.time() - t0:.1f}s")
print("models that answered:", ok)
raise SystemExit(0 if ok else 1)
