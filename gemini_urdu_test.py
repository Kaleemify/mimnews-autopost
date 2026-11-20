"""Manual test (workflow "gemini-urdu-test"): does the news writer still leave Urdu-script words in?
Uses the REAL Gemini key from the GitHub secret on 3 real, public Facebook news captions that earlier came out as raw-Urdu drafts.
Runs every sample several times with the OLD retry order (cheap "lite" model first, also on retries) and the NEW order (stronger model on retries).
Prints counts only, never the key."""
import json, os, sys
os.environ.setdefault("FB_PAGE_ID", "x"); os.environ.setdefault("FB_PAGE_TOKEN", "x"); os.environ.setdefault("MIM_KEY", "x")
import autopost as ap

RUNS = int(os.environ.get("RUNS", "4"))
samples = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "urdu_samples.json"), encoding="utf-8"))
if not ap.GEMINI_KEY: print("no GEMINI_API_KEY"); sys.exit(1)

def one(text):
    item = ap.gemini_write(text, "", "ur")
    if item is None: return "no_answer"
    if item.get("skip"): return "skip"
    return "publishable" if ap.quality_ok(item) else ("urdu_words_left" if item.get("_urdu_script") else "too_thin")

for label, model in (("OLD (lite first, also on retry)", "gemini-flash-lite-latest"), ("NEW (stronger model on retry)", "")):
    ap.GEMINI_MODEL = model
    tally = {}
    for s in samples:
        for _ in range(RUNS):
            r = one(s["text"]); tally[r] = tally.get(r, 0) + 1
    total = sum(tally.values())
    print(f"RESULT {label}: {tally.get('publishable', 0)}/{total} publishable | {tally}", flush=True)
