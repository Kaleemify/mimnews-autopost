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

def valid_id(v): return v.isdigit() and 10 <= len(v) <= 20
def valid_secret(v): return re.fullmatch(r"[0-9a-f]{32}", v) is not None
def valid_token(v): return v.startswith("EAA") and len(v) > 60 and re.search(r"[ \t\r\n]", v) is None

def gui_inputs(hook=None):
    """A small normal window with 3 boxes (Ctrl+V and a Paste button work there; the black console window does not accept paste).
    Returns (app_id, app_secret, token), or None if no window can be opened here. Exits if the user closes it. Nothing is printed or saved."""
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception:
        return None
    root.title("New Facebook token - MIM News autopost")
    root.resizable(False, False)
    if hook is None: root.attributes("-topmost", True)
    spec = [("App ID", False, valid_id, "only digits, about 15-16 of them"),
            ("App secret", True, valid_secret, "32 letters/digits (0-9, a-f)"),
            ("Access token", True, valid_token, "starts with EAA, very long, no spaces")]
    tk.Label(root, text="Copy each value in the browser, then click 'Paste' here (or press Ctrl+V in the box).", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, padx=12, pady=(12, 6), sticky="w")
    entries, statuses = [], []
    go = tk.Button(root, text="Continue", width=14, state="disabled", font=("Segoe UI", 10, "bold"))
    result = {}

    def refresh(*_):
        allok = True
        for (name, _h, ok, why), e, st in zip(spec, entries, statuses):
            v = e.get().strip()
            if not v: st.config(text="empty", fg="#888888"); allok = False
            elif ok(v): st.config(text=f"OK ({len(v)} characters)", fg="#0a7d2a")
            else: st.config(text="not right: " + why, fg="#b00020"); allok = False
        go.config(state="normal" if allok else "disabled")

    def paste_into(e):
        try: txt = root.clipboard_get()
        except Exception: txt = ""
        e.delete(0, "end"); e.insert(0, txt.strip()); refresh()

    for i, (name, hidden, ok, why) in enumerate(spec, 1):
        tk.Label(root, text=name, width=12, anchor="w").grid(row=i * 2 - 1, column=0, padx=(12, 4), pady=(8, 0), sticky="w")
        e = tk.Entry(root, width=46, show="•" if hidden else "")
        e.grid(row=i * 2 - 1, column=1, pady=(8, 0)); e.bind("<KeyRelease>", refresh)
        e.bind("<Control-v>", lambda ev, e=e: (paste_into(e), "break")[1]); e.bind("<Shift-Insert>", lambda ev, e=e: (paste_into(e), "break")[1])
        menu = tk.Menu(root, tearoff=0); menu.add_command(label="Paste", command=lambda e=e: paste_into(e))
        e.bind("<Button-3>", lambda ev, m=menu: m.tk_popup(ev.x_root, ev.y_root))
        tk.Button(root, text="Paste", width=8, command=lambda e=e: paste_into(e)).grid(row=i * 2 - 1, column=2, padx=6, pady=(8, 0))
        st = tk.Label(root, text="empty", fg="#888888", anchor="w"); st.grid(row=i * 2, column=1, columnspan=3, sticky="w")
        entries.append(e); statuses.append(st)

    def done():
        result["v"] = tuple(e.get().strip() for e in entries); root.destroy()
    go.config(command=done); go.grid(row=7, column=1, pady=14, sticky="w")
    tk.Button(root, text="Cancel", width=10, command=root.destroy).grid(row=7, column=2, pady=14)
    entries[0].focus_set()
    if hook: hook(root, entries, go, refresh)
    else: root.mainloop()
    if "v" not in result: die("cancelled: the window was closed")
    return result["v"]

got = gui_inputs()
if got: app_id, app_secret, short = got
else:
    print("(could not open the small window; using the console way)")
    app_id = ask("App ID", "Meta app page (Settings > Basic): COPY the App ID.", valid_id, "it must be only digits, about 15-16 of them")
    app_secret = ask("App secret", "Same page: click Show next to App secret, then COPY the App secret.", valid_secret, "it must be 32 letters/digits (0-9, a-f)")
    short = ask("token", "Graph API Explorer: COPY the long Access Token from the box at the top.", valid_token, "it must start with EAA and be very long, with no spaces")

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
