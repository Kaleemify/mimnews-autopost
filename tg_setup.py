#!/usr/bin/env python3
"""
One-time helper for the Telegram desk. Run it yourself in a terminal:   python tg_setup.py
It asks for the bot token (hidden), shows who has messaged the bot, lets you pick the allowed people,
and stores TG_BOT_TOKEN + TG_ALLOWED_IDS in the repo's GitHub Secrets. Nothing secret is printed or saved to a file.
"""
import getpass, subprocess, sys
import requests

REPO = "Kaleemify/mimnews-autopost"

def die(m): print("ERROR:", m); sys.exit(1)
def api(token, method, **p):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=p, timeout=60)
    j = r.json()
    if not j.get("ok"): die(f"Telegram said: {j.get('description')}")
    return j["result"]
def secret(name, value):
    r = subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, capture_output=True)
    if r.returncode: die(f"could not store {name}: {r.stderr.strip()[:200]}")
    print(f"  stored secret {name}")

token = getpass.getpass("Bot token from @BotFather (hidden): ").strip()
me = api(token, "getMe"); print(f"Bot found: @{me['username']}")
input(f"\nNow open Telegram and send any message (e.g. 'hi') to @{me['username']} from EVERY phone that should be allowed.\nPress Enter when done... ")
seen = {}
for u in api(token, "getUpdates", timeout=0, limit=100):
    m = u.get("message") or {}
    f = m.get("from") or {}
    if f.get("id") and not f.get("is_bot"): seen[f["id"]] = " ".join(x for x in (f.get("first_name"), f.get("last_name"), "@" + f["username"] if f.get("username") else "") if x)
if not seen: die("Nobody has messaged the bot yet. Send a message to the bot and run this again.")
ids = list(seen)
print("\nPeople who messaged the bot:")
for i, k in enumerate(ids, 1): print(f"  {i}. {seen[k]}  (id {k})")
pick = input("\nWho may send news? Type numbers separated by commas (e.g. 1,2): ").strip()
chosen = [str(ids[int(x) - 1]) for x in pick.split(",") if x.strip()]
if not chosen: die("Nobody selected.")
secret("TG_BOT_TOKEN", token); secret("TG_ALLOWED_IDS", ",".join(chosen))
print(f"\nDone. {len(chosen)} person(s) allowed. Next: set GEMINI_API_KEY (see SETUP-TELEGRAM.md step 3).")
