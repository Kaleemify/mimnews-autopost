#!/usr/bin/env python3
"""
One-time helper: turns a short Facebook user token into a long-lived PAGE token and stores it
(and the page id) directly in this repo's GitHub Secrets. Nothing secret is printed or written to a file.

Run it yourself in a terminal (inside the repo folder):   python get_page_token.py
You will be asked for: App ID, App Secret, and a short-lived user token from Graph API Explorer.
"""
import getpass, re, subprocess, sys
import requests

G = "https://graph.facebook.com/v21.0"
REPO = "Kaleemify/mimnews-autopost"   # always this repo, whatever folder the script is started from

def die(msg): print("ERROR:", msg); sys.exit(1)

def get(path, **p):
    r = requests.get(f"{G}/{path}", params=p, timeout=60)
    if r.status_code != 200:
        try: m = r.json()["error"]["message"]
        except Exception: m = r.text[:200]
        die(f"Facebook said: {m}")
    return r.json()

def gh_secret(name, value):
    r = subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, capture_output=True)
    if r.returncode != 0: die(f"could not store {name}: {r.stderr.strip()[:200]}")
    print(f"  stored secret {name}")

def clipboard():
    try: return subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ""

def ask(label, how, ok, why):
    """Reads the value from the clipboard (paste into this window does not work for hidden boxes). Never prints the value."""
    for attempt in range(1, 6):
        print(); print(">>> " + how)
        input("    Then press Enter here... ")
        v = clipboard()
        if ok(v):
            print(f"    got the {label} ({len(v)} characters). It is not shown on the screen.")
            return v
        print(f"    That does not look like the {label}: {why}. Copy it again.")
        if attempt == 3:
            v = getpass.getpass(f"    Or type/paste the {label} here (hidden, nothing appears): ").strip()
            if ok(v): return v
    die(f"could not get a valid {label}")

app_id = ask("App ID", "Meta app page (Settings > Basic): COPY the App ID (click its copy icon or select + Ctrl+C).",
             lambda v: v.isdigit() and 10 <= len(v) <= 20, "it must be only digits, about 15-16 of them")
app_secret = ask("App secret", "Same page: click Show next to App secret, then COPY the App secret.",
                 lambda v: re.fullmatch(r"[0-9a-f]{32}", v) is not None, "it must be 32 letters/digits (0-9, a-f)")
short = ask("token", "Graph API Explorer: after Generate Access Token, COPY the long Access Token from the box at the top.",
            lambda v: v.startswith("EAA") and len(v) > 60 and not re.search(r"\s", v), "it must start with EAA and be very long, with no spaces")

print("Exchanging for a long-lived token...")
long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id, client_secret=app_secret, fb_exchange_token=short)["access_token"]

pages = get("me/accounts", access_token=long_user, fields="id,name,access_token", limit=100).get("data", [])
if not pages: die("No pages found. Make sure you are an ADMIN of the page and ticked pages_show_list when generating the token.")
print("\nPages you manage:")
for i, p in enumerate(pages, 1): print(f"  {i}. {p['name']}  (id {p['id']})")
mim = [i for i, p in enumerate(pages, 1) if "mim" in p["name"].lower()]
if len(pages) == 1: n = 1
elif len(mim) == 1: n = mim[0]; print(f"\nUsing page {n} (the only one with MIM in its name).")
else: n = int(input("\nWhich number is the MIM News page? ").strip())
page = pages[n - 1]

# sanity check: can this token read the page's posts?
chk = requests.get(f"{G}/{page['id']}/published_posts", params={"access_token": page["access_token"], "limit": 1, "fields": "id,created_time"}, timeout=60)
if chk.status_code != 200: die("Token cannot read posts: " + chk.text[:200] + "\nAdd the permission pages_read_engagement and try again.")
print(f"OK - can read posts of '{page['name']}'.")

gh_secret("FB_PAGE_ID", page["id"])
gh_secret("FB_PAGE_TOKEN", page["access_token"])
print("\nDone. Page tokens made from a long-lived user token do not expire (unless you change your Facebook password or remove the app).")
