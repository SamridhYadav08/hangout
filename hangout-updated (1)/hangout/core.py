"""core.py - shared engine: settings, security (JWT, rate limits), data checks, rooms. Other files import from here."""
import asyncio, os, secrets, time, types, uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import wraps

import jwt
from pydantic import BaseModel, Field

# ======================= SETTINGS =======================

# Set JWT_SECRET in your host's env vars so sessions survive restarts.
JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
JWT_ALG = "HS256"
TOKEN_TTL = 6 * 3600
JWT_ISSUER = "hangout"
ROOM_TTL = 6 * 3600
RECONNECT_GRACE = 60  # seconds a player may drop before the room is wiped

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no I, L, O, 0, 1
CODE_LEN = 6
JOIN_FAILS_MAX = 5
JOIN_LOCK_SECONDS = 300
MAX_PAYLOAD = 64 * 1024

# Comma-separated list, e.g. "https://myhangout.onrender.com". Empty = same-origin only.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]


def ice_servers():
    servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
    url = os.environ.get("TURN_URL")
    if url:  # optional relay for networks where direct P2P fails
        servers.append({"urls": [url], "username": os.environ.get("TURN_USER", ""),
                        "credential": os.environ.get("TURN_CRED", "")})
    return servers

config = types.SimpleNamespace(**{k: v for k, v in globals().items() if k.isupper()}, ice_servers=ice_servers)

# ======================= SECURITY =======================
def create_token(name: str) -> str:
    now = int(time.time())
    claims = {"pid": uuid.uuid4().hex, "name": name, "iat": now, "nbf": now - 5, "iss": config.JWT_ISSUER, "exp": now + config.TOKEN_TTL}
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALG)


def verify_token(token: str):
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALG],
                          issuer=config.JWT_ISSUER, options={"require": ["exp", "iss", "pid", "name"]})
    except jwt.PyJWTError:
        return None


def new_room_code(taken) -> str:
    while True:
        code = "".join(secrets.choice(config.CODE_ALPHABET) for _ in range(config.CODE_LEN))
        if code not in taken:
            return code


def format_code(code: str) -> str:
    return f"{code[:3]}-{code[3:]}"


def normalize_code(raw) -> str:
    return str(raw).upper().replace("-", "").replace(" ", "")[:12]


class RateLimiter:
    def __init__(self, limit: int, window: int):
        self.limit, self.window, self.hits = limit, window, defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, q = time.time(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(self.hits) > 2000:   # keep memory flat: forget keys that have gone quiet
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > self.window]:
                if k != key:
                    del self.hits[k]
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class LockoutTracker:
    def __init__(self, max_fails: int, lock_seconds: int):
        self.max, self.lock, self.fails = max_fails, lock_seconds, {}

    def locked(self, key: str) -> bool:
        n, t = self.fails.get(key, (0, 0))
        if n >= self.max and time.time() - t < self.lock:
            return True
        if n >= self.max:
            self.fails.pop(key, None)
        return False

    def fail(self, key: str):
        if len(self.fails) > 2000:
            now = time.time()
            self.fails = {k: v for k, v in self.fails.items() if now - v[1] < self.lock}
        n, _ = self.fails.get(key, (0, 0))
        self.fails[key] = (n + 1, time.time())

    def reset(self, key: str):
        self.fails.pop(key, None)


event_limiter = RateLimiter(40, 10)


fast_limiter = RateLimiter(300, 10)   # movement/position events (~20 per second)


def authed(sio):
    """Socket auth decorator: verified session + per-player rate limit. Use @auth.fast for movement events."""
    def make(limiter):
        def deco(fn):
            @wraps(fn)
            async def wrapper(sid, data=None):
                sess = await sio.get_session(sid)
                if not sess or not limiter.allow(sess["pid"]):
                    await sio.emit("room:error", {"message": "Slow down a little."}, to=sid)
                    return
                return await fn(sid, sess, data)
            return wrapper
        return deco
    deco = make(event_limiter)
    deco.fast = make(fast_limiter)
    return deco

# ======================= BASIC INPUT CHECKS =======================
class NameIn(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9 ]{2,20}$")


class JoinIn(BaseModel):
    code: str = Field(pattern=r"^[A-HJKMNP-Z2-9]{6}$")



# ======================= ROOMS =======================
@dataclass
class Room:
    code: str
    players: dict = field(default_factory=dict)  # pid -> {name, sid, role}
    locked: bool = False
    created: float = field(default_factory=time.time)


class RoomManager:
    def __init__(self):
        self.rooms = {}
        self.by_player = {}
        self._timers = {}

    def create(self, pid, name, sid):
        if pid in self.by_player:
            raise ValueError("You are already in a room.")
        code = new_room_code(self.rooms)
        room = Room(code)
        room.players[pid] = {"name": name, "sid": sid, "role": "white"}
        self.rooms[code], self.by_player[pid] = room, code
        return room

    def join(self, code, pid, name, sid):
        room = self.rooms.get(code)
        if (pid in self.by_player or not room or room.locked or len(room.players) >= 2
                or time.time() - room.created > config.ROOM_TTL):
            raise ValueError("Room unavailable")
        room.players[pid] = {"name": name, "sid": sid, "role": "black"}
        room.locked = True  # lock rule: exactly two players
        self.by_player[pid] = code
        return room

    def reattach(self, pid, sid):
        room = self.rooms.get(self.by_player.get(pid))
        if not room:
            return None
        timer = self._timers.pop(pid, None)
        if timer:
            timer.cancel()
        room.players[pid]["sid"] = sid
        return room

    def schedule_wipe(self, pid, sid, on_wipe):
        room = self.rooms.get(self.by_player.get(pid))
        if not room or room.players[pid]["sid"] != sid:
            return

        async def wait():
            await asyncio.sleep(config.RECONNECT_GRACE)
            await self.close(room.code, on_wipe)

        self._timers[pid] = asyncio.create_task(wait())

    async def close(self, code, on_wipe):
        room = self.rooms.pop(code, None)
        if not room:
            return
        for pid in room.players:
            self.by_player.pop(pid, None)
            t = self._timers.pop(pid, None)
            if t and t is not asyncio.current_task():
                t.cancel()
        await on_wipe(room)


def partner_of(rooms, pid):
    """The other player in a locked 2-player room, or None."""
    room = rooms.rooms.get(rooms.by_player.get(pid))
    if not room or not room.locked:
        return None
    return next((v for k, v in room.players.items() if k != pid), None)
