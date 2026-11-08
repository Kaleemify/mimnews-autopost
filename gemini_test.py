"""One-off check: does the GEMINI_API_KEY work, and which model name answers? Prints status and the answer only, never the key."""
import json, os, urllib.error, urllib.request

key = os.environ.get("GEMINI_API_KEY", "")
print("key present:", bool(key), "| length:", len(key))
prompt = ('Rewrite as a short Pinglish (Roman Urdu, English letters) news item. Use ONLY these facts. '
          'Return JSON like {"title": "...", "paragraphs": ["..."]}. '
          'Facts: Sindh Education Minister Syed Sardar Shah said schools will reopen as scheduled, and the '
          'holiday-extension notification going around on social media is fake.')
for model in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash"]:
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        r = urllib.request.urlopen(req, timeout=90)
        j = json.load(r)
        print("MODEL", model, "-> HTTP", r.status)
        print("ANSWER:", j["candidates"][0]["content"]["parts"][0]["text"].strip()[:600])
        break
    except urllib.error.HTTPError as e:
        msg = e.read().decode().replace("\n", " ").replace(key, "<key>")
        print("MODEL", model, "-> HTTP", e.code, msg[:300])
