"""Facebook token health check. Prints metadata only (validity, expiry, scopes), never the token. Exits 1 (-> GitHub emails you) if invalid or expiring soon."""
import os, sys, time, requests
tok = os.environ.get("FB_PAGE_TOKEN", ""); pid = os.environ.get("FB_PAGE_ID", "")
if not tok: print("FB_PAGE_TOKEN missing"); sys.exit(1)
r = requests.get("https://graph.facebook.com/v21.0/debug_token", params={"input_token": tok, "access_token": tok}, timeout=60)
print("debug_token HTTP", r.status_code)
j = r.json()
if "data" not in j:
    print("could not inspect token:", str(j.get("error", {}).get("message", j))[:200])
    # fall back to the practical test: can we still read the page?
    t = requests.get(f"https://graph.facebook.com/v21.0/{pid}/published_posts", params={"access_token": tok, "limit": 1}, timeout=60)
    print("read page posts HTTP", t.status_code); sys.exit(0 if t.status_code == 200 else 1)
d = j["data"]
exp = d.get("expires_at", 0); dax = d.get("data_access_expires_at", 0)
print("type:", d.get("type"), "| valid:", d.get("is_valid"), "| app:", d.get("application"))
print("expires_at:", "NEVER (0)" if not exp else time.strftime("%Y-%m-%d", time.gmtime(exp)), "| data_access_expires_at:", "none" if not dax else time.strftime("%Y-%m-%d", time.gmtime(dax)))
print("scopes:", ", ".join(d.get("scopes", [])))
print("has user link (token dies if that profile loses page access):", bool(d.get("user_id")))
bad = (not d.get("is_valid")) or (exp and exp - time.time() < 14 * 86400) or (dax and dax - time.time() < 14 * 86400)
if bad: print("PROBLEM: token invalid or expiring within 14 days"); sys.exit(1)
print("OK")
