"""One-off check: runs the REAL news-writing prompt through autopost.gemini_write with the real key. Prints the result only, never the key."""
import os, json
os.environ.setdefault("MIM_KEY", "unused")
import autopost as ap
print("key present:", bool(ap.GEMINI_KEY), "| length:", len(ap.GEMINI_KEY))
caption = "Sindh Education Minister ka bayan"
transcript = ("Sindh ke Wazir-e-Taleem Syed Sardar Shah ne kaha hai ke soobay ke tamam school Monday ko mamool ke mutabiq khulenge. "
              "Unhon ne kaha ke social media par chuttiyon mein izafe ka jo notification gardish kar raha hai woh jaali hai. "
              "Unhon ne walidain se appeal ki ke woh ghair tasdeeq shuda khabron par yaqeen na karen.")
item = ap.gemini_write(caption, transcript, "ur")
print("RESULT:", json.dumps(item, ensure_ascii=False)[:900])
print("quality_ok:", ap.quality_ok(item) if item else False)
raise SystemExit(0 if item else 1)
