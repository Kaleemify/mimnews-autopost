#!/usr/bin/env python3
"""
Reads Facebook app id / app secret / short token from ../.env (never printed), exchanges for a long-lived PAGE token,
picks the MIM News page and stores FB_PAGE_ID + FB_PAGE_TOKEN in the GitHub Secrets of Kaleemify/mimnews-autopost.
Run it yourself (double-click setup-facebook.bat). It prints key NAMES and the page name only, never values.
"""
import os, re, subprocess, sys
import requests

REPO = "Kaleemify/mimnews-autopost"
G = "https://graph.facebook.com/v21.0"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CANDIDATES = [os.path.join(ROOT, n) for n in (".env", ".ev", ".env.txt", ".ev.txt")]

def die(m): print("ERROR:", m); sys.exit(1)

def parse_by_shape(text):
    """Finds the three values by what they LOOK like, so the file may be written any way (KEY=VALUE, 'Token: ...', 'Client ID 123...').
    App ID = only digits (10-20); App secret = exactly 32 hex characters; token = starts with EAA and is long. Never prints a value."""
    words = re.findall(r"[A-Za-z0-9_.\-]{10,}", text)
    ids = [w for w in words if w.isdigit() and 10 <= len(w) <= 20]
    secrets = [w for w in words if re.fullmatch(r"[0-9a-f]{32}", w)]
    toks = [w for w in words if w.startswith("EA") and len(w) > 60]   # Facebook tokens start EAA..., EAG..., EAB... (depends on the app type)
    return ids, secrets, toks

path = next((p for p in CANDIDATES if os.path.exists(p)), None)
if not path: die("No credentials file found next to the Waseem folder (looked for .env and .ev).")
ids, secrets, toks = parse_by_shape(open(path, encoding="utf8", errors="replace").read())
print(f"Reading {os.path.basename(path)}: found {len(ids)} App ID, {len(secrets)} App secret, {len(toks)} token (values are never shown).")
for label, found in (("App ID (digits only, 15-16 long)", ids), ("App secret (32 letters/digits 0-9 a-f)", secrets), ("token (starts with EA, very long)", toks)):
    if len(found) != 1: die(f"expected exactly one {label} in the file, found {len(found)}.")
vals = {"id": ids[0], "secret": secrets[0], "token": toks[0]}
app_id_k, secret_k, token_k = "id", "secret", "token"

def get(path, **p):
    r = requests.get(f"{G}/{path}", params=p, timeout=60)
    if r.status_code != 200:
        try: m = r.json()["error"]["message"]
        except Exception: m = r.text[:200]
        die(f"Facebook said: {m}")
    return r.json()

long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=vals[app_id_k], client_secret=vals[secret_k], fb_exchange_token=vals[token_k])["access_token"]
pages = get("me/accounts", access_token=long_user, fields="id,name,access_token", limit=100).get("data", [])
if not pages: die("No pages returned. The token must be generated with pages_show_list and MIM News ticked in the Facebook popup.")
print("Pages:", " | ".join(f"{p['name']} ({p['id']})" for p in pages))
mim = [p for p in pages if "mim" in p["name"].lower()]
if len(pages) == 1: mim = pages
if len(mim) != 1: die("Could not pick exactly one MIM page automatically. Run refresh-facebook-token.bat and choose by number.")
page = mim[0]
chk = requests.get(f"{G}/{page['id']}/published_posts", params={"access_token": page["access_token"], "limit": 3, "fields": "id,created_time"}, timeout=60)
if chk.status_code != 200: die("Page token cannot read posts (pages_read_engagement missing?): " + chk.text[:200])
print(f"OK: can read posts of '{page['name']}' (latest {len(chk.json().get('data', []))} posts visible).")
for name, value in (("FB_PAGE_ID", page["id"]), ("FB_PAGE_TOKEN", page["access_token"])):
    r = subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, capture_output=True)
    if r.returncode: die(f"could not store {name}: {r.stderr.strip()[:200]}")
    print(f"stored secret {name}")
print(f"DONE. Now delete the file {os.path.basename(path)} (the short token and secret in it are no longer needed).")
r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/autopost.yml/dispatches", "-f", "ref=main"], capture_output=True, text=True)
print("autopost started once now; check https://mimnews.com/wp-json/mim/v1/health in 3 minutes ('ok':true)." if r.returncode == 0 else "(could not start the autopost from here; cron-job.org starts it within 15 minutes)")
