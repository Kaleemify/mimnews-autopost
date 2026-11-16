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
ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

def die(m): print("ERROR:", m); sys.exit(1)

if not os.path.exists(ENV): die(".env not found next to the Waseem folder.")
vals = {}
for line in open(ENV, encoding="utf8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1)
    vals[k.strip().replace("export ", "")] = v.strip().strip('"').strip("'")
print("Names found in .env:", ", ".join(vals) or "(none)")

def pick(*patterns):
    for k in vals:
        if any(re.search(p, k, re.I) for p in patterns) and vals[k]: return k
app_id_k = pick(r"APP_?ID", r"CLIENT_?ID"); secret_k = pick(r"APP_?SECRET", r"CLIENT_?SECRET", r"SECRET")
token_k = pick(r"SHORT.*TOKEN", r"ACCESS_?TOKEN", r"USER.*TOKEN", r"TOKEN")
for label, k in (("App ID", app_id_k), ("App Secret", secret_k), ("Short token", token_k)):
    if not k: die(f"Could not find {label} in .env. Rename the key to something like FB_APP_ID / FB_APP_SECRET / FB_SHORT_TOKEN.")
print(f"Using: app id = {app_id_k}, secret = {secret_k}, token = {token_k}")

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
if len(mim) != 1: die("Could not pick exactly one MIM page automatically. Run get_page_token.py and choose by number.")
page = mim[0]
chk = requests.get(f"{G}/{page['id']}/published_posts", params={"access_token": page["access_token"], "limit": 3, "fields": "id,created_time"}, timeout=60)
if chk.status_code != 200: die("Page token cannot read posts (pages_read_engagement missing?): " + chk.text[:200])
print(f"OK: can read posts of '{page['name']}' (latest {len(chk.json().get('data', []))} posts visible).")
for name, value in (("FB_PAGE_ID", page["id"]), ("FB_PAGE_TOKEN", page["access_token"])):
    r = subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, capture_output=True)
    if r.returncode: die(f"could not store {name}: {r.stderr.strip()[:200]}")
    print(f"stored secret {name}")
print("DONE. You can delete the short token and secret from .env now (they are no longer needed).")
