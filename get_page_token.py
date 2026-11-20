#!/usr/bin/env python3
"""
One-time helper: turns a short Facebook user token into a long-lived PAGE token and stores it
(and the page id) directly in this repo's GitHub Secrets. Nothing secret is printed or written to a file.

Run it yourself in a terminal (inside the repo folder):   python get_page_token.py
You will be asked for: App ID, App Secret, and a short-lived user token from Graph API Explorer.
"""
import getpass, subprocess, sys
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

app_id = input("App ID: ").strip()
app_secret = getpass.getpass("App Secret (hidden): ").strip()
short = getpass.getpass("Short-lived user token from Graph API Explorer (hidden): ").strip()

print("Exchanging for a long-lived token...")
long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id, client_secret=app_secret, fb_exchange_token=short)["access_token"]

pages = get("me/accounts", access_token=long_user, fields="id,name,access_token", limit=100).get("data", [])
if not pages: die("No pages found. Make sure you are an ADMIN of the page and ticked pages_show_list when generating the token.")
print("\nPages you manage:")
for i, p in enumerate(pages, 1): print(f"  {i}. {p['name']}  (id {p['id']})")
n = int(input("\nWhich number is the MIM News page? ").strip())
page = pages[n - 1]

# sanity check: can this token read the page's posts?
chk = requests.get(f"{G}/{page['id']}/published_posts", params={"access_token": page["access_token"], "limit": 1, "fields": "id,created_time"}, timeout=60)
if chk.status_code != 200: die("Token cannot read posts: " + chk.text[:200] + "\nAdd the permission pages_read_engagement and try again.")
print(f"OK - can read posts of '{page['name']}'.")

gh_secret("FB_PAGE_ID", page["id"])
gh_secret("FB_PAGE_TOKEN", page["access_token"])
print("\nDone. Page tokens made from a long-lived user token do not expire (unless you change your Facebook password or remove the app).")
