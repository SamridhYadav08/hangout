"""smoke_test.py - run after starting/deploying:  python smoke_test.py http://localhost:8000
Checks health, page, assets, session minting and the security headers (stdlib only)."""
import json, sys, urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def get(path, **kw):
    req = urllib.request.Request(base + path, **kw)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, {k.title(): v for k, v in r.headers.items()}, r.read()   # header names arrive lower-case from uvicorn


ok = True
def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name)


s, h, b = get("/health");                       check("/health", s == 200 and json.loads(b)["ok"])
s, h, b = get("/");                             check("index page", s == 200 and b"Hangout" in b)
check("CSP header", "default-src 'self'" in h.get("Content-Security-Policy", ""))
for p in ("/css/base_theme.css", "/js/main_router.js", "/js/chess.js", "/js/photobooth.js", "/js/car.js", "/js/duel.js",
          "/js/bouquet.js", "/js/notes.js", "/heart.png", "/wallpaper.jpg"):
    s, h, b = get(p);                           check(p, s == 200 and len(b) > 100)
req = urllib.request.Request(base + "/api/session", data=b'{"name":"Smoke Test"}', headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=20) as r:
    check("/api/session mints a token", r.status == 200 and "token" in json.loads(r.read()))
sys.exit(0 if ok else 1)
