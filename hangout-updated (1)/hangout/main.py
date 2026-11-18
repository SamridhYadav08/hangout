"""main.py - the server. Run:  uvicorn main:asgi --reload   then open http://localhost:8000"""
from urllib.parse import urlparse
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError
import socketio
from socketio.exceptions import ConnectionRefusedError

from core import (config, JoinIn, NameIn, RoomManager, LockoutTracker, RateLimiter, authed,
                  create_token, format_code, normalize_code, verify_token)
import website
from pathlib import Path
WALLPAPER = Path(__file__).parent / "wallpaper.jpg"   # keep wallpaper.jpg next to main.py
import bouquet, notes, chess_game, photobooth, car_race, dress_duel   # <- one file per option
FEATURES = [bouquet, notes, chess_game, photobooth, car_race, dress_duel]   # <- add or remove options here

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=config.ALLOWED_ORIGINS or None,
                           max_http_buffer_size=config.MAX_PAYLOAD)
rooms = RoomManager()
session_limit = RateLimiter(10, 60)
join_lock = LockoutTracker(config.JOIN_FAILS_MAX, config.JOIN_LOCK_SECONDS)
auth = authed(sio)

CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' wss: ws:; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Frame-Options": "DENY",
        "X-Permitted-Cross-Domain-Policies": "none",
    })
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def client_ip(forwarded, fallback):
    return forwarded.split(",")[0].strip() if forwarded else (fallback or "unknown")


@app.get("/health")
async def health():
    return {"ok": True, "rooms": len(rooms.rooms)}


@app.post("/api/session")
async def session(body: NameIn, request: Request):
    origin = request.headers.get("origin")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    if origin and origin not in config.ALLOWED_ORIGINS and urlparse(origin).netloc != host:  # block cross-site session minting
        raise HTTPException(403, "Forbidden origin")
    ip = client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None)
    if not session_limit.allow(ip):
        raise HTTPException(429, "Too many requests")
    return {"token": create_token(body.name.strip())}


@app.get("/api/ice")
async def ice(authorization: str = Header("")):
    if not verify_token(authorization.removeprefix("Bearer ").strip()):
        raise HTTPException(401, "Unauthorized")
    return {"iceServers": config.ice_servers()}


async def sync_room(room):
    code = format_code(room.code)
    if not room.locked:
        for p in room.players.values():
            await sio.emit("room:created", {"code": code}, to=p["sid"])
        return
    for pid, p in room.players.items():
        other = next(v for k, v in room.players.items() if k != pid)
        await sio.emit("room:ready", {"code": code, "role": p["role"], "partner": other["name"]}, to=p["sid"])


async def on_wipe(room):
    sids = {p["sid"] for p in room.players.values()}
    for f in FEATURES:   # drop per-room game state so memory doesn't grow
        for name in ("games", "races"):
            getattr(f, name, {}).pop(room.code, None)
        stale = getattr(f, "pending", None)   # unopened gifts / notes addressed to this room
        if isinstance(stale, dict):
            for gid in [g for g, v in stale.items() if v.get("to") in sids or v.get("from") in room.players or v.get("sender") in room.players]:
                stale.pop(gid, None)
    for p in room.players.values():
        await sio.emit("room:closed", {}, to=p["sid"])


@sio.event
async def connect(sid, environ, auth_data):
    token = auth_data.get("token", "") if isinstance(auth_data, dict) else ""
    claims = verify_token(token)
    if not claims:
        raise ConnectionRefusedError("unauthorized")
    ip = client_ip(environ.get("HTTP_X_FORWARDED_FOR"), environ.get("REMOTE_ADDR"))
    await sio.save_session(sid, {"pid": claims["pid"], "name": claims["name"], "ip": ip})
    room = rooms.reattach(claims["pid"], sid)
    if room:
        await sio.enter_room(sid, room.code)
        await sync_room(room)


@sio.event
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid)
    except KeyError:
        return
    rooms.schedule_wipe(sess["pid"], sid, on_wipe)


@sio.on("room:create")
@auth
async def on_create(sid, sess, data):
    try:
        room = rooms.create(sess["pid"], sess["name"], sid)
    except ValueError as e:
        return await sio.emit("room:error", {"message": str(e)}, to=sid)
    await sio.enter_room(sid, room.code)
    await sync_room(room)


@sio.on("room:join")
@auth
async def on_join(sid, sess, data):
    ip = sess["ip"]
    if join_lock.locked(ip):
        return await sio.emit("room:error", {"message": "Too many attempts. Try again in a few minutes."}, to=sid)
    raw = data.get("code", "") if isinstance(data, dict) else ""
    try:
        code = JoinIn(code=normalize_code(raw)).code
        room = rooms.join(code, sess["pid"], sess["name"], sid)
    except (ValidationError, ValueError):
        join_lock.fail(ip)
        return await sio.emit("room:error", {"message": "Room unavailable. Check the code."}, to=sid)
    join_lock.reset(ip)
    await sio.enter_room(sid, room.code)
    await sync_room(room)




# ======================= FEATURES + WEBSITE =======================
for feature in FEATURES:
    feature.setup(sio, auth, rooms)

FILES = dict(website.ASSETS)
for feature in FEATURES:
    FILES[f"css/{feature.SLUG}.css"] = feature.CSS
    FILES[f"js/{feature.SLUG}.js"] = feature.JS


@app.get("/heart.png")
async def heart():
    p = Path(__file__).parent / "heart.png"
    if not p.exists():
        raise HTTPException(404)
    return Response(p.read_bytes(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/wallpaper.jpg")
async def wallpaper():
    if not WALLPAPER.exists():
        raise HTTPException(404)
    return Response(WALLPAPER.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


INDEX_HTML = website.page(FEATURES)   # built once at startup


@app.get("/favicon.ico")
async def favicon():
    return await heart()


@app.get("/")
async def index():
    return Response(INDEX_HTML, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


@app.get("/{kind}/{name}")
async def asset(kind: str, name: str):
    key = f"{kind}/{name}"
    if key not in FILES:
        raise HTTPException(404)
    return Response(FILES[key], media_type="text/css; charset=utf-8" if kind == "css" else "application/javascript; charset=utf-8",
                    headers={"Cache-Control": "no-cache"})


asgi = socketio.ASGIApp(sio, other_asgi_app=app)
