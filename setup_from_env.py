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
def soft(path, **p):
    """Like get() but never stops the script: returns {} on any error."""
    try:
        r = requests.get(f"{G}/{path}", params=p, timeout=60)
        return r.json() if r.status_code == 200 else {"_error": (r.json().get("error") or {}).get("message", "")[:160]}
    except Exception as e: return {"_error": type(e).__name__}

pages = get("me/accounts", access_token=long_user, fields="id,name,access_token", limit=100).get("data", [])
if not pages:
    # Explain WHY (prints permission names and page ids only, never a token or secret).
    d = soft("debug_token", input_token=long_user, access_token=f"{vals[app_id_k]}|{vals[secret_k]}").get("data", {})
    gs = {g.get("scope"): g.get("target_ids", []) for g in d.get("granular_scopes", [])}
    print("\n--- WHY NO PAGES? (what Facebook says about this token) ---")
    print("token valid:", d.get("is_valid"), "| type:", d.get("type"), "| scopes granted:", ", ".join(d.get("scopes", [])) or "(none)")
    for need in ("pages_show_list", "pages_read_engagement"):
        print(f"  {need}: " + ("granted" if need in d.get("scopes", []) else "NOT granted") + (f" | pages chosen in the popup: {len(gs[need])} {gs[need]}" if need in gs else " | no page was chosen in the popup"))
    me = soft("me", access_token=long_user, fields="id,name")
    print("token belongs to the Facebook profile:", me.get("name", me.get("_error")))
    # The popup chose a page, but /me/accounts is empty: this happens when the page is reached through a business portfolio / task-based access.
    # Then Facebook can still hand out the page token when we ask for the page by its id.
    for pid in sorted({t for ids in gs.values() for t in ids}):
        pg = soft(pid, access_token=long_user, fields="id,name,access_token")
        print(f"asking Facebook for page {pid} directly ->", pg.get("name") or pg.get("_error") or "no answer", "| token for it:", "yes" if pg.get("access_token") else "no")
        if pg.get("access_token"): pages.append(pg)
    biz = soft("me/businesses", access_token=long_user, fields="id,name").get("data")
    print("business portfolios visible (needs business_management):", [b.get("name") for b in biz] if biz else "none/not allowed")
    if biz:
        for b in biz:
            for edge in ("owned_pages", "client_pages"):
                found = soft(f"{b['id']}/{edge}", access_token=long_user, fields="id,name,access_token", limit=100).get("data", [])
                for pg in found:
                    if pg.get("access_token"): pages.append(pg)
        if pages: print("found page(s) through the business portfolio:", ", ".join(p["name"] for p in pages))
    if not pages:
        print("\nMEANING: if 'no page was chosen' -> in the Facebook popup tick MIM News (Edit settings / choose pages) and make a NEW token.")
        print("         if a page WAS chosen but still nothing -> this profile has no role on the page any more: the client must give it Full control (Meta Business Suite > Settings > Pages > People).")
        die("No pages returned for this token (see the explanation above).")
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
