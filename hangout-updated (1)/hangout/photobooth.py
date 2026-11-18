"""photobooth.py - Interactive 4-stage peer-to-peer Photo Booth.
Video flows peer-to-peer over WebRTC (DTLS-SRTP encrypted); the server only relays
small handshake messages and coordinates shared session timing for locked rooms.
"""
import asyncio
import json
import math
import time
from core import config, partner_of

NAME = "Photo Booth"
SLUG = "photobooth"
KINDS = {"offer", "answer", "ice"}
FILTERS = {"none", "grayscale", "sepia", "vintage", "softpink", "contrast"}
PAPERS = {"classic", "blossom", "polaroid", "film", "retro", "midnight", "hearts"}


# ============================================================================
# 1. SERVER EVENTS
# ============================================================================
def setup(sio, auth, rooms):
    fast_auth = getattr(auth, "fast", auth)
    active_sessions = {}

    def _room_and_peer(pid):
        room_id = rooms.by_player.get(pid)
        room = rooms.rooms.get(room_id)
        peer = partner_of(rooms, pid)
        if not room or not getattr(room, "locked", False) or not peer:
            return None, None, None
        return room_id, room, peer

    def _cancel_session(room_id):
        task = active_sessions.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    @sio.on("rtc:ready")
    @auth
    async def ready(sid, sess, data):
        pid = sess["pid"]
        _, room, peer = _room_and_peer(pid)
        if not room or not peer:
            return
        await sio.emit("rtc:servers", {"iceServers": config.ice_servers()}, to=sid)
        await sio.emit("rtc:ready", {"role": room.players[pid]["role"]}, to=peer["sid"])

    @sio.on("rtc:signal")
    @fast_auth
    async def signal(sid, sess, data):
        pid = sess["pid"]
        _, room, peer = _room_and_peer(pid)
        if not room or not peer or not isinstance(data, dict) or data.get("kind") not in KINDS:
            return
        if len(json.dumps(data.get("data"), default=str)) > 20000:
            return
        await sio.emit("rtc:signal", {"kind": data["kind"], "data": data.get("data")}, to=peer["sid"])

    @sio.on("photo:snap")
    @auth
    async def snap(sid, sess, data):
        _, room, _ = _room_and_peer(sess["pid"])
        if room:
            for p in room.players.values():
                await sio.emit("photo:go", {}, to=p["sid"])

    @sio.on("photo:start")
    @auth
    async def photo_start(sid, sess, data):
        pid = sess["pid"]
        room_id, room, peer = _room_and_peer(pid)
        if not room or not peer:
            return
        if room_id in active_sessions and not active_sessions[room_id].done():
            return  # Guard against double starts

        payload = data if isinstance(data, dict) else {}
        flt = payload.get("filter") if payload.get("filter") in FILTERS else "none"
        only_index = payload.get("shotIndex")
        if isinstance(only_index, int) and 0 <= only_index < 6:
            indices = [only_index]
        else:
            indices = [0, 1, 2, 3, 4, 5]

        session_id = f"{room_id}_{int(time.time() * 1000)}"

        async def _run_session():
            try:
                sids = [p["sid"] for p in room.players.values()]
                for target_sid in sids:
                    await sio.emit(
                        "photo:start",
                        {
                            "sessionId": session_id,
                            "indices": indices,
                            "total": 6,
                            "filter": flt,
                            "serverTs": int(time.time() * 1000),
                        },
                        to=target_sid,
                    )
                await asyncio.sleep(0.35)

                for pos, shot_idx in enumerate(indices):
                    for count in (3, 2, 1):
                        _, cur_room, cur_peer = _room_and_peer(pid)
                        if not cur_room or not cur_peer:
                            if cur_room:
                                for p in cur_room.players.values():
                                    await sio.emit("photo:cancel", {"reason": "Partner left the booth."}, to=p["sid"])
                            return
                        for p in cur_room.players.values():
                            await sio.emit(
                                "photo:shot",
                                {
                                    "sessionId": session_id,
                                    "index": shot_idx,
                                    "step": pos + 1,
                                    "steps": len(indices),
                                    "total": 6,
                                    "phase": "countdown",
                                    "count": count,
                                    "serverTs": int(time.time() * 1000),
                                },
                                to=p["sid"],
                            )
                        await asyncio.sleep(0.75)

                    _, cur_room, cur_peer = _room_and_peer(pid)
                    if not cur_room or not cur_peer:
                        if cur_room:
                            for p in cur_room.players.values():
                                await sio.emit("photo:cancel", {"reason": "Partner left the booth."}, to=p["sid"])
                        return
                    for p in cur_room.players.values():
                        await sio.emit(
                            "photo:shot",
                            {
                                "sessionId": session_id,
                                "index": shot_idx,
                                "step": pos + 1,
                                "steps": len(indices),
                                "total": 6,
                                "phase": "snap",
                                "count": 0,
                                "serverTs": int(time.time() * 1000),
                            },
                            to=p["sid"],
                        )
                    await asyncio.sleep(0.95)

                _, cur_room, _ = _room_and_peer(pid)
                if cur_room:
                    for p in cur_room.players.values():
                        await sio.emit(
                            "photo:shot",
                            {
                                "sessionId": session_id,
                                "phase": "done",
                                "total": 6,
                                "serverTs": int(time.time() * 1000),
                            },
                            to=p["sid"],
                        )
            except asyncio.CancelledError:
                pass
            finally:
                if active_sessions.get(room_id) is task:
                    active_sessions.pop(room_id, None)

        task = asyncio.create_task(_run_session())
        active_sessions[room_id] = task

    @sio.on("photo:cancel")
    @auth
    async def photo_cancel(sid, sess, data):
        pid = sess["pid"]
        room_id, room, _ = _room_and_peer(pid)
        if not room:
            return
        _cancel_session(room_id)
        reason = "Session cancelled."
        if isinstance(data, dict) and data.get("reason") == "left":
            reason = "Partner stepped out of the booth."
        for p in room.players.values():
            await sio.emit("photo:cancel", {"reason": reason}, to=p["sid"])

    @sio.on("photo:share")
    @auth
    async def photo_share(sid, sess, data):
        pid = sess["pid"]
        _, room, peer = _room_and_peer(pid)
        if not room or not peer or not isinstance(data, dict):
            return
        raw = json.dumps(data, default=str)
        if len(raw) > 15000:
            return
        paper = data.get("paper") if data.get("paper") in PAPERS else "classic"
        stickers = data.get("stickers") if isinstance(data.get("stickers"), list) else []
        clean_stickers = []
        for s in stickers[:40]:
            if not (isinstance(s, dict) and isinstance(s.get("type"), str)):
                continue
            try:
                x, y = float(s.get("x", 600)), float(s.get("y", 900))
                sc, rot = float(s.get("scale", 1.0)), float(s.get("rot", 0.0))
            except (TypeError, ValueError):
                continue
            if not all(map(math.isfinite, (x, y, sc, rot))):
                continue
            clean_stickers.append({
                "type": s["type"][:24],
                "x": max(-2000.0, min(4000.0, x)),
                "y": max(-2000.0, min(4000.0, y)),
                "scale": max(0.25, min(3.0, sc)),
                "rot": max(-360.0, min(360.0, rot)),
                "flip": bool(s.get("flip", False)),
            })
        await sio.emit(
            "photo:share",
            {"paper": paper, "stickers": clean_stickers},
            to=peer["sid"],
        )


# ============================================================================
# 2. CSS (Strict CSP: zero inline styles, all styling via classes)
# ============================================================================
CSS = r'''
.pb-shell {
  position: relative;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  color: #fff6fa;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Georgia, serif;
  user-select: none;
  -webkit-user-select: none;
}
.pb-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: rgba(26, 12, 24, 0.78);
  border: 1px solid rgba(255, 194, 218, 0.25);
  border-radius: 14px;
}
.pb-topbar-left, .pb-topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.pb-stage-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255, 182, 211, 0.16);
  color: #ffd6e7;
  border: 1px solid rgba(255, 182, 211, 0.35);
}
.pb-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 0.85rem;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(20, 10, 18, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f8dce8;
}
.pb-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 8px #f59e0b;
}
.pb-dot.is-ok {
  background: #34d399;
  box-shadow: 0 0 10px #34d399;
}
.pb-dot.is-err {
  background: #f87171;
  box-shadow: 0 0 10px #f87171;
}
.pb-btn {
  appearance: none;
  border: 1px solid rgba(255, 200, 222, 0.4);
  background: linear-gradient(180deg, #3b1c32 0%, #24101e 100%);
  color: #fff5f9;
  font-size: 0.9rem;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.pb-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #ff9ec4;
  box-shadow: 0 4px 14px rgba(255, 120, 172, 0.25);
}
.pb-btn:active:not(:disabled) {
  transform: translateY(0);
}
.pb-btn:focus-visible, .pb-enter-btn:focus-visible, .pb-chip:focus-visible, .pb-sticker-btn:focus-visible {
  outline: 3px solid #ff9ec4;
  outline-offset: 2px;
}
.pb-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.pb-btn-primary {
  background: linear-gradient(180deg, #ff6fa5 0%, #d93870 100%);
  border-color: #ffc2da;
  color: #fff;
  box-shadow: 0 4px 16px rgba(217, 56, 112, 0.45);
}
.pb-btn-primary:hover:not(:disabled) {
  box-shadow: 0 6px 22px rgba(255, 111, 165, 0.65);
}
.pb-btn-danger {
  background: linear-gradient(180deg, #7f1d32 0%, #4c0d1b 100%);
  border-color: rgba(252, 165, 165, 0.5);
}

/* STAGE 1: OUTDOOR GARDEN SCENE */
.pb-garden-stage {
  position: relative;
  width: 100%;
  min-height: 540px;
  aspect-ratio: 16 / 10;
  max-height: 78vh;
  border-radius: 20px;
  overflow: hidden;
  border: 2px solid rgba(255, 206, 226, 0.35);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.55);
  background: linear-gradient(180deg, #1b1026 0%, #3d1e3d 32%, #8c4268 64%, #f2a6c0 88%, #ffe4ee 100%);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
}
.pb-garden-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  transition: transform 0.65s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.65s ease;
  transform-origin: 50% 56%;
}
.pb-garden-stage.is-entering .pb-garden-svg {
  transform: scale(2.35);
  opacity: 0.15;
}
.pb-curtain-door {
  transition: transform 0.45s cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: 430px 260px;
}
.pb-garden-stage.is-entering .pb-curtain-door {
  transform: scaleX(0.18);
}
.pb-bulb-a {
  animation: pbBulbPulse 1.6s infinite alternate ease-in-out;
}
.pb-bulb-b {
  animation: pbBulbPulse 1.6s 0.8s infinite alternate ease-in-out;
}
@keyframes pbBulbPulse {
  0% { opacity: 0.55; }
  100% { opacity: 1; }
}
.pb-petal {
  animation: pbPetalDrift 9s linear infinite;
  transform-box: fill-box;
  transform-origin: center;
}
.pb-petal-1 { animation-duration: 8.5s; animation-delay: -1s; }
.pb-petal-2 { animation-duration: 10.2s; animation-delay: -3.5s; }
.pb-petal-3 { animation-duration: 7.8s; animation-delay: -5.2s; }
.pb-petal-4 { animation-duration: 11.4s; animation-delay: -2.1s; }
.pb-petal-5 { animation-duration: 9.6s; animation-delay: -6.8s; }
.pb-petal-6 { animation-duration: 8.9s; animation-delay: -4.3s; }
@keyframes pbPetalDrift {
  0% { transform: translate(0px, -30px) rotate(0deg); opacity: 0; }
  15% { opacity: 0.92; }
  85% { opacity: 0.92; }
  100% { transform: translate(-110px, 480px) rotate(260deg); opacity: 0; }
}
.pb-enter-wrap {
  position: relative;
  z-index: 5;
  margin-bottom: 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.pb-enter-btn {
  appearance: none;
  cursor: pointer;
  border: 2px solid #ffd8ea;
  border-radius: 999px;
  padding: 13px 38px;
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #fff;
  background: linear-gradient(180deg, #ff5c99 0%, #b81d58 100%);
  box-shadow: 0 0 22px rgba(255, 92, 153, 0.85), 0 8px 24px rgba(0, 0, 0, 0.5), inset 0 2px 4px rgba(255, 255, 255, 0.45);
  animation: pbEnterGlow 2s infinite alternate ease-in-out;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.pb-enter-btn:hover {
  transform: scale(1.05) translateY(-2px);
  box-shadow: 0 0 32px rgba(255, 130, 180, 1), 0 10px 28px rgba(0, 0, 0, 0.6);
}
@keyframes pbEnterGlow {
  0% { box-shadow: 0 0 16px rgba(255, 92, 153, 0.65), 0 6px 20px rgba(0, 0, 0, 0.5); }
  100% { box-shadow: 0 0 34px rgba(255, 148, 194, 1), 0 8px 26px rgba(0, 0, 0, 0.6); }
}
.pb-enter-sub {
  font-size: 0.82rem;
  color: #ffeaf3;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.85);
  background: rgba(24, 10, 20, 0.62);
  padding: 3px 12px;
  border-radius: 999px;
}

/* STAGE 2 & 3: BOOTH INTERIOR & VERTICAL CAMERAS */
.pb-interior {
  position: relative;
  border-radius: 20px;
  overflow: hidden;
  padding: 18px 16px 20px;
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 214, 170, 0.22) 0%, transparent 58%),
    repeating-linear-gradient(90deg, #4b1127 0px, #681836 22px, #3c0c1e 44px);
  border: 2px solid rgba(255, 205, 224, 0.35);
  box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.75), 0 16px 40px rgba(0, 0, 0, 0.5);
}
.pb-light-strip {
  height: 10px;
  max-width: 680px;
  margin: 0 auto 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, #ffe2b8, #fff8eb, #ffd1e6, #fff8eb, #ffe2b8);
  box-shadow: 0 0 24px rgba(255, 236, 209, 0.9), 0 0 45px rgba(255, 168, 208, 0.65);
}
.pb-cam-window {
  position: relative;
  max-width: 760px;
  margin: 0 auto;
  padding: 14px;
  border-radius: 18px;
  background: linear-gradient(180deg, #1b0e18 0%, #11080f 100%);
  border: 3px solid #e6c8d5;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.65), inset 0 0 18px rgba(255, 196, 220, 0.15);
}
.pb-vids-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: stretch;
}
.pb-vid-card {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 12px;
  overflow: hidden;
  background: #1a0d17;
  border: 1px solid rgba(255, 200, 222, 0.3);
}
.pb-vid-card video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pb-vid-local {
  transform: scaleX(-1);
}
.pb-vid-remote {
  transform: none;
}
.pb-vid-badge {
  position: absolute;
  left: 10px;
  bottom: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  background: rgba(15, 6, 13, 0.76);
  color: #ffe6f1;
  border: 1px solid rgba(255, 200, 222, 0.3);
  pointer-events: none;
}
.pb-partner-wait {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 16px;
  background: radial-gradient(circle, rgba(46, 20, 38, 0.88) 0%, rgba(19, 8, 16, 0.94) 100%);
  color: #ffd7e8;
  font-size: 0.92rem;
  gap: 10px;
}
.pb-partner-wait.is-hidden {
  display: none;
}
.pb-cam-error {
  margin: 10px auto;
  max-width: 520px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(110, 18, 38, 0.88);
  border: 1px solid #fca5a5;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.pb-cam-error.is-hidden {
  display: none;
}

/* FILTERS (Live preview classes; canvas export uses Safari-safe pixel math) */
.pb-flt-none { filter: none; -webkit-filter: none; }
.pb-flt-grayscale { filter: grayscale(1); -webkit-filter: grayscale(1); }
.pb-flt-sepia { filter: sepia(0.95); -webkit-filter: sepia(0.95); }
.pb-flt-vintage { filter: sepia(0.55) contrast(1.12) saturate(1.25); -webkit-filter: sepia(0.55) contrast(1.12) saturate(1.25); }
.pb-flt-softpink { filter: saturate(1.28) hue-rotate(-14deg) brightness(1.07); -webkit-filter: saturate(1.28) hue-rotate(-14deg) brightness(1.07); }
.pb-flt-contrast { filter: contrast(1.42) saturate(1.1); -webkit-filter: contrast(1.42) saturate(1.1); }

/* PROGRESS FILM DOTS & COUNTDOWN OVERLAY */
.pb-film-progress {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 14px 0 10px;
  flex-wrap: wrap;
}
.pb-film-dot {
  width: 34px;
  height: 26px;
  border-radius: 6px;
  background: rgba(24, 10, 20, 0.8);
  border: 2px solid rgba(255, 198, 222, 0.35);
  display: grid;
  place-items: center;
  font-size: 0.78rem;
  font-weight: 700;
  color: #f3bfd4;
  transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}
.pb-film-dot.is-active {
  border-color: #fff;
  background: #ff5c99;
  color: #fff;
  transform: scale(1.12);
}
.pb-film-dot.is-done {
  border-color: #ffd0e3;
  background: #a32658;
  color: #fff;
}
.pb-countdown-layer {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
  z-index: 15;
}
.pb-countdown-num {
  font-size: clamp(4.5rem, 12vw, 7.5rem);
  font-weight: 900;
  color: #fff;
  text-shadow: 0 6px 28px rgba(0, 0, 0, 0.9), 0 0 32px rgba(255, 105, 168, 0.95);
  transform: scale(1);
  transition: transform 0.2s ease;
}
.pb-flash-layer {
  position: absolute;
  inset: 0;
  background: #ffffff;
  opacity: 0;
  pointer-events: none;
  z-index: 20;
  transition: opacity 0.28s ease-out;
}
.pb-flash-layer.is-flashing {
  opacity: 0.96;
  transition: none;
}
.pb-develop-overlay {
  position: absolute;
  inset: 0;
  z-index: 25;
  background: rgba(18, 7, 15, 0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #ffe8f2;
  font-size: 1.25rem;
  font-weight: 700;
}
.pb-develop-overlay.is-hidden {
  display: none;
}
.pb-develop-strip-icon {
  width: 54px;
  height: 82px;
  border-radius: 6px;
  background: #fff;
  border: 3px solid #ff9ec4;
  animation: pbDevelopBounce 0.9s infinite alternate ease-in-out;
}
@keyframes pbDevelopBounce {
  0% { transform: translateY(-8px) rotate(-3deg); }
  100% { transform: translateY(8px) rotate(3deg); }
}

.pb-controls-bar {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.pb-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: center;
}
.pb-chip {
  appearance: none;
  border: 1px solid rgba(255, 198, 222, 0.35);
  background: rgba(25, 10, 21, 0.82);
  color: #fce2ed;
  padding: 6px 13px;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}
.pb-chip:hover {
  border-color: #ff9ec4;
}
.pb-chip.is-active {
  background: #ff5c99;
  border-color: #fff;
  color: #fff;
  box-shadow: 0 0 12px rgba(255, 92, 153, 0.5);
}
.pb-stool-bar {
  margin: 14px auto 0;
  width: 220px;
  height: 16px;
  border-radius: 999px;
  background: linear-gradient(180deg, #d98aa8 0%, #8a3858 100%);
  border: 2px solid #f7c6d9;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.6);
}

/* STAGE 4: STUDIO EDITOR (PAPER + STICKERS + EXPORT) */
.pb-studio {
  display: grid;
  grid-template-columns: minmax(290px, 460px) minmax(280px, 1fr);
  gap: 18px;
  align-items: start;
  background: rgba(23, 10, 20, 0.84);
  border: 1px solid rgba(255, 198, 222, 0.3);
  border-radius: 20px;
  padding: 16px;
}
.pb-preview-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.pb-canvas-wrap {
  position: relative;
  width: 100%;
  max-width: 430px;
  aspect-ratio: 2 / 3;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 14px 38px rgba(0, 0, 0, 0.65);
  border: 2px solid rgba(255, 210, 228, 0.4);
  background: #120810;
  touch-action: none;
}
.pb-preview-canvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
}
.pb-preview-canvas:active {
  cursor: grabbing;
}
.pb-editor-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.pb-panel {
  background: rgba(38, 16, 33, 0.78);
  border: 1px solid rgba(255, 198, 222, 0.24);
  border-radius: 14px;
  padding: 12px 14px;
}
.pb-panel-title {
  font-size: 0.86rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #ffb8d5;
  margin: 0 0 9px;
}
.pb-sticker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(52px, 1fr));
  gap: 8px;
}
.pb-sticker-btn {
  appearance: none;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  border: 1px solid rgba(255, 202, 224, 0.3);
  background: rgba(20, 8, 18, 0.75);
  padding: 6px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: transform 0.14s ease, border-color 0.14s ease, background 0.14s ease;
}
.pb-sticker-btn:hover {
  transform: scale(1.08);
  border-color: #ff9ec4;
  background: rgba(255, 111, 165, 0.18);
}
.pb-sticker-btn svg {
  width: 100%;
  height: 100%;
  display: block;
}
.pb-slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 0.85rem;
  color: #ffe3ef;
}
.pb-slider-row label {
  min-width: 68px;
  font-weight: 600;
}
.pb-slider-row input[type="range"] {
  flex: 1;
  accent-color: #ff5c99;
}
.pb-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pb-retake-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.pb-is-hidden {
  display: none !important;
}

@media (max-width: 820px) {
  .pb-studio {
    grid-template-columns: 1fr;
  }
  .pb-canvas-wrap {
    max-width: 360px;
  }
}
@media (max-width: 520px) {
  .pb-garden-stage {
    min-height: 440px;
    aspect-ratio: 4 / 5;
  }
  .pb-vids-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .pb-enter-btn {
    padding: 11px 28px;
    font-size: 1.04rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  .pb-petal, .pb-bulb-a, .pb-bulb-b, .pb-enter-btn, .pb-develop-strip-icon {
    animation: none !important;
  }
  .pb-garden-svg, .pb-curtain-door {
    transition: none !important;
  }
}
'''


# ============================================================================
# 3. CLIENT JAVASCRIPT
# ============================================================================
JS = r'''"use strict";
window.Features = window.Features || {};
window.Features["Photo Booth"] = (() => {
  const H = window.Hang;
  let inited = false;
  let uidCounter = 0;
  const nextUid = () => "pb" + (++uidCounter) + "_";

  // Hardware & WebRTC state
  let stream = null;
  let pc = null;
  let ice = null;
  let role = null;
  let offered = false;
  let replied = false;
  let partnerConnected = false;
  let pendingCandidates = [];
  let signalChain = Promise.resolve();

  // UI & Session state
  let stage = 1; // 1: Outside, 2: Inside/Camera, 3: Session Countdown, 4: Paper & Stickers
  let activeSessionId = null;
  let localFallbackTimer = null;
  let audioCtx = null;
  let shots = [null, null, null, null, null, null];
  let currentShotIndex = -1;
  let selectedFilter = "none";
  let selectedPaper = "classic";
  let stickers = [];
  let selectedStickerId = null;
  let stickerSeq = 1;
  let dragMode = null; // "move" | "resize" | "rotate"
  let dragStart = null;
  let activePointers = new Map();
  let pinchStart = null;

  // DOM references
  let rootEl = null;
  let stagePillEl = null;
  let statusDotEl = null;
  let statusTextEl = null;
  let stage1El = null;
  let stage2El = null;
  let stage4El = null;
  let vl = null;
  let vr = null;
  let partnerWaitEl = null;
  let camErrorEl = null;
  let camErrorMsgEl = null;
  let countdownEl = null;
  let flashEl = null;
  let developEl = null;
  let filmDots = [];
  let startBtnEl = null;
  let cancelSessionBtnEl = null;
  let previewCanvas = null;
  let sizeInputEl = null;
  let rotInputEl = null;
  let stickerToolsWrapEl = null;

  const FILTER_LIST = [
    { id: "none", label: "None" },
    { id: "grayscale", label: "B&W" },
    { id: "sepia", label: "Sepia" },
    { id: "vintage", label: "Vintage" },
    { id: "softpink", label: "Soft Pink" },
    { id: "contrast", label: "High Contrast" }
  ];

  const PAPER_LIST = [
    { id: "classic", label: "Classic White" },
    { id: "blossom", label: "Pink Blossom" },
    { id: "polaroid", label: "Polaroid Cards" },
    { id: "film", label: "Film Strip" },
    { id: "retro", label: "Retro Cream" },
    { id: "midnight", label: "Dark Midnight" },
    { id: "hearts", label: "Heart Grid" }
  ];

  // ==========================================================================
  // 3A. SCENE ART (SVG Blossom Garden + Vintage Booth + ENTER Sign)
  // ==========================================================================
  function buildGardenSceneSVG() {
    const p = nextUid();
    const bulbCoords = [];
    for (let i = 0; i < 9; i++) {
      bulbCoords.push({ x: 374 + i * 31.5, y: 150, cls: i % 2 === 0 ? "pb-bulb-a" : "pb-bulb-b" });
    }
    const bulbsSvg = bulbCoords.map((b) =>
      `<circle cx="${b.x}" cy="${b.y}" r="5.5" fill="#fffbe0" stroke="#f59e0b" stroke-width="1.5" class="${b.cls}"/>`
    ).join("");

    const petalsData = [
      { cx: 160, cy: 60, r: -25, s: 1.0, cls: "pb-petal pb-petal-1" },
      { cx: 310, cy: 40, r: 15, s: 0.85, cls: "pb-petal pb-petal-2" },
      { cx: 520, cy: 30, r: 45, s: 1.1, cls: "pb-petal pb-petal-3" },
      { cx: 710, cy: 55, r: -15, s: 0.9, cls: "pb-petal pb-petal-4" },
      { cx: 860, cy: 45, r: 30, s: 1.05, cls: "pb-petal pb-petal-5" },
      { cx: 940, cy: 85, r: -40, s: 0.8, cls: "pb-petal pb-petal-6" },
      { cx: 240, cy: 110, r: 20, s: 0.75, cls: "pb-petal pb-petal-3" },
      { cx: 640, cy: 95, r: -30, s: 0.95, cls: "pb-petal pb-petal-1" },
      { cx: 430, cy: 75, r: 12, s: 0.85, cls: "pb-petal pb-petal-5" },
      { cx: 790, cy: 120, r: -22, s: 0.9, cls: "pb-petal pb-petal-2" }
    ];
    const petalsSvg = petalsData.map((pt) =>
      `<g class="${pt.cls}">
        <path d="M ${pt.cx} ${pt.cy} C ${pt.cx - 8 * pt.s} ${pt.cy - 10 * pt.s}, ${pt.cx - 12 * pt.s} ${pt.cy + 4 * pt.s}, ${pt.cx} ${pt.cy + 12 * pt.s} C ${pt.cx + 12 * pt.s} ${pt.cy + 4 * pt.s}, ${pt.cx + 8 * pt.s} ${pt.cy - 10 * pt.s}, ${pt.cx} ${pt.cy} Z" fill="#ffb8d2" opacity="0.9"/>
      </g>`
    ).join("");

    return `
    <svg class="pb-garden-svg" viewBox="0 0 1000 620" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="${p}sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#1c102b"/>
          <stop offset="34%" stop-color="#442048"/>
          <stop offset="68%" stop-color="#9e4c74"/>
          <stop offset="92%" stop-color="#f5acc5"/>
          <stop offset="100%" stop-color="#ffe8f0"/>
        </linearGradient>
        <radialGradient id="${p}sun" cx="0.32" cy="0.24" r="0.45">
          <stop offset="0%" stop-color="#fff6d6" stop-opacity="0.95"/>
          <stop offset="35%" stop-color="#ffb6d2" stop-opacity="0.48"/>
          <stop offset="100%" stop-color="#ffb6d2" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="${p}grass" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#43304f"/>
          <stop offset="38%" stop-color="#2c243b"/>
          <stop offset="100%" stop-color="#191324"/>
        </linearGradient>
        <linearGradient id="${p}path" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#e3c6d4"/>
          <stop offset="100%" stop-color="#9a7489"/>
        </linearGradient>
        <linearGradient id="${p}cabFront" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#fff9f5"/>
          <stop offset="60%" stop-color="#ffeef4"/>
          <stop offset="100%" stop-color="#f5cedd"/>
        </linearGradient>
        <linearGradient id="${p}cabSide" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#ebbfd2"/>
          <stop offset="100%" stop-color="#b87491"/>
        </linearGradient>
        <linearGradient id="${p}pinkPanel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ff9ec3"/>
          <stop offset="100%" stop-color="#d95b8a"/>
        </linearGradient>
        <linearGradient id="${p}curtain" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#9e1946"/>
          <stop offset="25%" stop-color="#cc2960"/>
          <stop offset="50%" stop-color="#7c1034"/>
          <stop offset="75%" stop-color="#bf2458"/>
          <stop offset="100%" stop-color="#6b0d2c"/>
        </linearGradient>
      </defs>

      <!-- Sky & Upper-Left Sun Glow -->
      <rect width="1000" height="620" fill="url(#${p}sky)"/>
      <circle cx="310" cy="150" r="260" fill="url(#${p}sun)"/>
      <circle cx="310" cy="150" r="52" fill="#fff7df" opacity="0.75"/>

      <!-- Distant Hills & Far Parallax Blossom Layer -->
      <path d="M 0 430 Q 220 365 480 415 T 1000 395 L 1000 500 L 0 500 Z" fill="#5e3258" opacity="0.7"/>
      <g opacity="0.65">
        <circle cx="120" cy="310" r="85" fill="#e58eb2"/>
        <circle cx="215" cy="290" r="95" fill="#f0a3c2"/>
        <circle cx="310" cy="325" r="75" fill="#df82a8"/>
        <circle cx="720" cy="315" r="88" fill="#e58eb2"/>
        <circle cx="825" cy="285" r="98" fill="#f2a8c6"/>
        <circle cx="915" cy="320" r="80" fill="#dc7ea4"/>
      </g>

      <!-- Mid-ground Cherry Blossom Trees (Left & Right) -->
      <!-- Left Tree -->
      <path d="M 130 475 C 145 390, 140 320, 105 245 C 80 195, 35 160, 10 140 L 0 165 C 35 190, 75 230, 92 290 C 65 265, 30 255, 0 255 L 0 280 C 35 280, 72 295, 98 335 C 102 390, 92 440, 75 475 Z" fill="#3a1b2d"/>
      <path d="M 122 300 C 165 250, 225 225, 290 215 L 285 235 C 228 248, 175 275, 132 325 Z" fill="#3a1b2d"/>
      <g>
        <circle cx="70" cy="180" r="78" fill="#ffaec9"/>
        <circle cx="165" cy="165" r="86" fill="#ffc4d9"/>
        <circle cx="255" cy="195" r="72" fill="#ff9ebb"/>
        <circle cx="125" cy="230" r="74" fill="#ffd9e6"/>
        <circle cx="220" cy="235" r="64" fill="#ffbad2"/>
        <circle cx="40" cy="245" r="65" fill="#ff9ec0"/>
      </g>

      <!-- Right Tree -->
      <path d="M 875 475 C 860 395, 862 320, 895 240 C 920 190, 955 155, 995 135 L 1000 165 C 962 185, 925 225, 908 280 C 938 260, 970 250, 1000 250 L 1000 278 C 960 280, 925 295, 902 335 C 896 392, 908 440, 925 475 Z" fill="#341728"/>
      <path d="M 880 295 C 835 245, 775 215, 710 205 L 716 225 C 772 238, 825 268, 870 320 Z" fill="#341728"/>
      <g>
        <circle cx="930" cy="175" r="82" fill="#ffaec9"/>
        <circle cx="830" cy="160" r="90" fill="#ffc4d9"/>
        <circle cx="740" cy="195" r="72" fill="#ff9ebb"/>
        <circle cx="875" cy="225" r="76" fill="#ffd9e6"/>
        <circle cx="775" cy="235" r="64" fill="#ffbad2"/>
        <circle cx="960" cy="245" r="68" fill="#ff9ec0"/>
      </g>

      <!-- Garden Lawn & Stone Path -->
      <path d="M 0 445 Q 500 415 1000 445 L 1000 620 L 0 620 Z" fill="url(#${p}grass)"/>
      <path d="M 425 458 L 575 458 L 690 620 L 310 620 Z" fill="url(#${p}path)" opacity="0.88"/>
      <ellipse cx="500" cy="495" rx="75" ry="10" fill="#fff0f6" opacity="0.45"/>
      <ellipse cx="500" cy="532" rx="95" ry="13" fill="#fff0f6" opacity="0.45"/>
      <ellipse cx="500" cy="575" rx="120" ry="16" fill="#fff0f6" opacity="0.45"/>

      <!-- Booth Ground Cast Shadow (Light from upper-left -> shadow to lower-right) -->
      <ellipse cx="525" cy="466" rx="175" ry="26" fill="#0d0612" opacity="0.65"/>

      <!-- ================================================================== -->
      <!-- VINTAGE PHOTO BOOTH CABINET (Centerpiece)                          -->
      <!-- ================================================================== -->
      <g id="${p}booth">
        <!-- 3D Right Side Depth Wall -->
        <path d="M 612 135 L 656 156 L 656 452 L 612 465 Z" fill="url(#${p}cabSide)" stroke="#7a425b" stroke-width="2"/>
        <!-- Roof Cap 3D -->
        <path d="M 342 135 Q 477 108 612 135 L 656 156 Q 515 132 342 135 Z" fill="#f7c8dc"/>

        <!-- Main Rounded Front Cabinet -->
        <rect x="342" y="122" width="270" height="343" rx="22" ry="22" fill="url(#${p}cabFront)" stroke="#e5a4bf" stroke-width="3"/>

        <!-- Upper-Left Highlight Bevel -->
        <path d="M 346 320 L 346 144 Q 346 125 366 125 L 580 125" fill="none" stroke="#ffffff" stroke-width="4" opacity="0.85" stroke-linecap="round"/>

        <!-- Marquee Header Sign ("PHOTO") -->
        <rect x="358" y="136" width="238" height="54" rx="12" ry="12" fill="#3a1228" stroke="#ffbad4" stroke-width="2.5"/>
        <rect x="364" y="142" width="226" height="42" rx="8" ry="8" fill="#591839" stroke="#ff85b3" stroke-width="1.5"/>
        <text x="477" y="176" text-anchor="middle" fill="#fff7e6" font-family="Georgia, serif" font-size="30" font-weight="900" letter-spacing="7">PHOTO</text>
        ${bulbsSvg}

        <!-- Booth Curtain Opening (Left Side of Front Face) -->
        <rect x="364" y="204" width="142" height="236" rx="10" ry="10" fill="#170914" stroke="#c98aa5" stroke-width="3"/>
        <!-- Warm Interior Glow & Stool inside Booth -->
        <rect x="370" y="210" width="130" height="14" rx="5" fill="#ffefc2" opacity="0.85"/>
        <ellipse cx="435" cy="245" rx="58" ry="32" fill="#ff9ec4" opacity="0.18"/>
        <!-- Stool inside doorway -->
        <rect x="429" y="388" width="12" height="48" fill="#8c7a84"/>
        <path d="M 405 436 L 465 436" stroke="#c4b2bc" stroke-width="5" stroke-linecap="round"/>
        <ellipse cx="435" cy="386" rx="32" ry="9" fill="#d94b7d" stroke="#ffd2e2" stroke-width="2"/>

        <!-- Velvet Curtain (Animates open when entering) -->
        <g class="pb-curtain-door">
          <path d="M 366 206 L 486 206 C 478 265, 456 305, 424 338 C 442 372, 448 410, 444 438 L 366 438 Z" fill="url(#${p}curtain)"/>
          <!-- Gold Tie-back Cord -->
          <path d="M 366 334 Q 402 344 426 336" fill="none" stroke="#fbbf24" stroke-width="4" stroke-linecap="round"/>
          <circle cx="424" cy="342" r="5" fill="#fbbf24"/>
        </g>

        <!-- Right Side Control Panel (Coin Slot, "4 for $2" Plaque, Chute) -->
        <rect x="518" y="204" width="78" height="236" rx="10" ry="10" fill="url(#${p}pinkPanel)" stroke="#b8436e" stroke-width="2"/>

        <!-- Vintage "4 FOR $2" Enamel Plaque -->
        <rect x="526" y="216" width="62" height="52" rx="6" ry="6" fill="#fff8ee" stroke="#47172c" stroke-width="2"/>
        <text x="557" y="236" text-anchor="middle" fill="#b81d58" font-family="Georgia, serif" font-size="12" font-weight="900">4 FOR $2</text>
        <text x="557" y="250" text-anchor="middle" fill="#47172c" font-family="sans-serif" font-size="7.5" font-weight="700">6 POSES</text>
        <text x="557" y="261" text-anchor="middle" fill="#47172c" font-family="sans-serif" font-size="7" font-weight="700">INSTANT</text>

        <!-- Metallic Coin Plate & Slot -->
        <rect x="532" y="282" width="50" height="58" rx="6" ry="6" fill="#e2d5dc" stroke="#785e6c" stroke-width="1.8"/>
        <rect x="554" y="293" width="6" height="18" rx="2" fill="#291521"/>
        <circle cx="557" cy="324" r="6" fill="#b89fa9" stroke="#5e4653" stroke-width="1.5"/>
        <text x="557" y="290" text-anchor="middle" fill="#4a3340" font-family="sans-serif" font-size="6.5" font-weight="700">COINS</text>

        <!-- Photo Strip Delivery Chute + Sample Strip Peeking Out -->
        <rect x="530" y="356" width="54" height="62" rx="6" ry="6" fill="#291220" stroke="#f5b8d0" stroke-width="1.8"/>
        <rect x="544" y="366" width="26" height="44" rx="2" fill="#ffffff" transform="rotate(6 557 388)"/>
        <rect x="548" y="370" width="18" height="10" fill="#ff8ab5" transform="rotate(6 557 388)"/>
        <rect x="548" y="383" width="18" height="10" fill="#ff8ab5" transform="rotate(6 557 388)"/>
        <rect x="548" y="396" width="18" height="10" fill="#ff8ab5" transform="rotate(6 557 388)"/>

        <!-- Base Plinth -->
        <rect x="334" y="454" width="328" height="16" rx="6" ry="6" fill="#4a2038" stroke="#ffbad4" stroke-width="1.5"/>
      </g>

      <!-- Foreground Overhanging Blossom Branches & Fallen Petals -->
      <g>
        <circle cx="35" cy="45" r="62" fill="#ffc4d9" opacity="0.92"/>
        <circle cx="115" cy="25" r="55" fill="#ffd9e6" opacity="0.9"/>
        <circle cx="960" cy="40" r="64" fill="#ffc4d9" opacity="0.92"/>
        <circle cx="885" cy="22" r="52" fill="#ffd9e6" opacity="0.9"/>
        <!-- Fallen petals on grass -->
        <ellipse cx="260" cy="510" rx="7" ry="3.5" fill="#ffb8d2"/>
        <ellipse cx="295" cy="545" rx="6" ry="3" fill="#ffd4e4"/>
        <ellipse cx="350" cy="495" rx="6.5" ry="3" fill="#ffb8d2"/>
        <ellipse cx="670" cy="520" rx="7" ry="3.5" fill="#ffb8d2"/>
        <ellipse cx="725" cy="555" rx="6" ry="3" fill="#ffd4e4"/>
        <ellipse cx="635" cy="565" rx="6.5" ry="3" fill="#ffb8d2"/>
      </g>

      <!-- Animated Drifting Petals -->
      ${petalsSvg}
    </svg>`;
  }

  // ==========================================================================
  // 3B. WEBAUDIO SHUTTER & COUNTDOWN SOUNDS (Zero external audio files)
  // ==========================================================================
  function getAudioCtx() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioCtx && audioCtx.state === "suspended") {
      audioCtx.resume().catch(() => {});
    }
    return audioCtx;
  }

  function playBeep(freq = 660, duration = 0.09) {
    try {
      const ctx = getAudioCtx();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration);
    } catch (_) {}
  }

  function playShutterSound() {
    try {
      const ctx = getAudioCtx();
      if (!ctx) return;
      const now = ctx.currentTime;
      // White noise burst for mechanical shutter curtain
      const bufferSize = Math.floor(ctx.sampleRate * 0.085);
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.022));
      }
      const noise = ctx.createBufferSource();
      noise.buffer = buffer;

      const filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.setValueAtTime(1600, now);

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.42, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.08);

      noise.connect(filter);
      filter.connect(gain);
      gain.connect(ctx.destination);
      noise.start(now);

      // Second mechanical mirror clack
      const osc = ctx.createOscillator();
      const clickGain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(240, now + 0.045);
      osc.frequency.exponentialRampToValueAtTime(75, now + 0.095);
      clickGain.gain.setValueAtTime(0.28, now + 0.045);
      clickGain.gain.exponentialRampToValueAtTime(0.001, now + 0.095);
      osc.connect(clickGain);
      clickGain.connect(ctx.destination);
      osc.start(now + 0.045);
      osc.stop(now + 0.098);
    } catch (_) {}
  }

  // ==========================================================================
  // 3C. CAMERA & WEBRTC (Strict signal queue + hardware kill-switch)
  // ==========================================================================
  function stopHardware() {
    if (localFallbackTimer) {
      clearTimeout(localFallbackTimer);
      localFallbackTimer = null;
    }
    activeSessionId = null;
    if (stream) {
      stream.getTracks().forEach((t) => {
        try { t.stop(); } catch (_) {}
      });
      stream = null;
    }
    if (pc) {
      try { pc.ontrack = null; pc.onicecandidate = null; pc.onconnectionstatechange = null; pc.close(); } catch (_) {}
      pc = null;
    }
    if (vl) vl.srcObject = null;
    if (vr) vr.srcObject = null;
    offered = false;
    replied = false;
    partnerConnected = false;
    pendingCandidates = [];
    updateStatusUI("Camera off · Outside booth", "idle");
  }

  function updateStatusUI(text, state) {
    if (statusTextEl) statusTextEl.textContent = text;
    if (statusDotEl) {
      statusDotEl.className = "pb-dot" + (state === "ok" ? " is-ok" : state === "err" ? " is-err" : "");
    }
    if (partnerWaitEl) {
      if (partnerConnected) {
        partnerWaitEl.classList.add("is-hidden");
      } else {
        partnerWaitEl.classList.remove("is-hidden");
        partnerWaitEl.textContent = text;
      }
    }
  }

  function markPartnerConnected() {
    partnerConnected = true;
    updateStatusUI("Partner connected · Ready!", "ok");
  }

  function makePc() {
    if (pc) return pc;
    pc = new RTCPeerConnection({ iceServers: (ice && ice.iceServers) || [] });
    if (stream) {
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));
    }
    pc.ontrack = (e) => {
      if (vr && e.streams && e.streams[0]) {
        vr.srcObject = e.streams[0];
        markPartnerConnected();
      }
    };
    pc.onicecandidate = (e) => {
      if (e.candidate) {
        SocketClient.emit("rtc:signal", { kind: "ice", data: e.candidate });
      }
    };
    pc.onconnectionstatechange = () => {
      if (!pc) return;
      const st = pc.connectionState;
      if (st === "connected") {
        markPartnerConnected();
      } else if (st === "connecting") {
        if (!partnerConnected) updateStatusUI("Connecting to partner...", "idle");
      } else if (st === "disconnected" || st === "failed" || st === "closed") {
        partnerConnected = false;
        updateStatusUI("Waiting for partner to reconnect...", "idle");
      }
    };
    pc.oniceconnectionstatechange = () => {
      if (!pc) return;
      if (pc.iceConnectionState === "connected" || pc.iceConnectionState === "completed") {
        markPartnerConnected();
      }
    };
    return pc;
  }

  async function flushPendingCandidates(p) {
    while (pendingCandidates.length > 0) {
      const c = pendingCandidates.shift();
      try {
        await p.addIceCandidate(c);
      } catch (_) {}
    }
  }

  async function createAndSendOffer() {
    if (offered || !stream) return;
    offered = true;
    updateStatusUI("Connecting to partner...", "idle");
    const p = makePc();
    const off = await p.createOffer();
    await p.setLocalDescription(off);
    SocketClient.emit("rtc:signal", { kind: "offer", data: p.localDescription });
  }

  async function requestVerticalCamera() {
    if (camErrorEl) camErrorEl.classList.add("is-hidden");
    updateStatusUI("Asking for camera permission...", "idle");
    try {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 720 },
            height: { ideal: 960 },
            aspectRatio: { ideal: 0.75 },
            facingMode: "user"
          },
          audio: false
        });
      } catch (_) {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
      if (vl) {
        vl.srcObject = stream;
      }
      updateStatusUI("Waiting for partner to enter the booth...", "idle");
      SocketClient.emit("rtc:ready");
    } catch (err) {
      const msg = (err && err.message) ? err.message : "Permission denied or no camera found.";
      updateStatusUI("Camera unavailable", "err");
      if (camErrorMsgEl) camErrorMsgEl.textContent = "Camera error: " + msg;
      if (camErrorEl) camErrorEl.classList.remove("is-hidden");
    }
  }

  // ==========================================================================
  // 3D. SAFARI-COMPATIBLE PIXEL FILTER & MIRRORED PORTRAIT CAPTURE
  // ==========================================================================
  function applyPixelFilter(ctx, w, h, filterName) {
    if (!filterName || filterName === "none") return;
    const imgData = ctx.getImageData(0, 0, w, h);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      let r = d[i], g = d[i + 1], b = d[i + 2];
      if (filterName === "grayscale") {
        const y = 0.299 * r + 0.587 * g + 0.114 * b;
        r = g = b = y;
      } else if (filterName === "sepia") {
        const nr = r * 0.393 + g * 0.769 + b * 0.189;
        const ng = r * 0.349 + g * 0.686 + b * 0.168;
        const nb = r * 0.272 + g * 0.534 + b * 0.131;
        r = nr; g = ng; b = nb;
      } else if (filterName === "vintage") {
        const nr = r * 0.52 + g * 0.54 + b * 0.14 + 14;
        const ng = r * 0.26 + g * 0.68 + b * 0.14 + 6;
        const nb = r * 0.18 + g * 0.38 + b * 0.44 - 8;
        r = (nr - 128) * 1.12 + 128;
        g = (ng - 128) * 1.08 + 128;
        b = (nb - 128) * 1.02 + 128;
      } else if (filterName === "softpink") {
        r = r * 1.14 + 18;
        g = g * 0.98 + 6;
        b = b * 1.08 + 14;
      } else if (filterName === "contrast") {
        const f = 1.42;
        r = (r - 128) * f + 128;
        g = (g - 128) * f + 128;
        b = (b - 128) * f + 128;
      }
      d[i] = r < 0 ? 0 : r > 255 ? 255 : r;
      d[i + 1] = g < 0 ? 0 : g > 255 ? 255 : g;
      d[i + 2] = b < 0 ? 0 : b > 255 ? 255 : b;
    }
    ctx.putImageData(imgData, 0, 0);
  }

  function drawVideoCoverPortrait(ctx, videoEl, dx, dy, dw, dh, mirrored) {
    const vw = (videoEl && videoEl.videoWidth) || 0;
    const vh = (videoEl && videoEl.videoHeight) || 0;
    if (!vw || !vh) {
      // Charming fallback silhouette when partner video is not yet active
      ctx.save();
      ctx.fillStyle = "#2b1323";
      ctx.fillRect(dx, dy, dw, dh);
      ctx.fillStyle = "#6e3554";
      ctx.beginPath();
      ctx.arc(dx + dw * 0.5, dy + dh * 0.38, dw * 0.18, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(dx + dw * 0.5, dy + dh * 0.86, dw * 0.34, Math.PI, 0, false);
      ctx.fill();
      ctx.restore();
      return;
    }
    const targetAspect = dw / dh;
    const srcAspect = vw / vh;
    let sx = 0, sy = 0, sw = vw, sh = vh;
    if (srcAspect > targetAspect) {
      sw = vh * targetAspect;
      sx = (vw - sw) * 0.5;
    } else {
      sh = vw / targetAspect;
      sy = (vh - sh) * 0.5;
    }
    ctx.save();
    if (mirrored) {
      // Fixed mirrored coordinate transform: translate to the frame's right edge (dx + dw, dy), then scale(-1, 1)
      ctx.translate(dx + dw, dy);
      ctx.scale(-1, 1);
      ctx.drawImage(videoEl, sx, sy, sw, sh, 0, 0, dw, dh);
    } else {
      ctx.drawImage(videoEl, sx, sy, sw, sh, dx, dy, dw, dh);
    }
    ctx.restore();
  }

  function captureCombinedFrame(shotIdx) {
    const c = document.createElement("canvas");
    c.width = 720;
    c.height = 480;
    const x = c.getContext("2d");
    x.fillStyle = "#180b14";
    x.fillRect(0, 0, 720, 480);

    // Left half (0..360): local player portrait (3:4), mirrored accurately
    drawVideoCoverPortrait(x, vl, 0, 0, 360, 480, true);
    // Right half (360..720): partner portrait (3:4), unmirrored
    drawVideoCoverPortrait(x, vr, 360, 0, 360, 480, false);

    // Divider line
    x.fillStyle = "rgba(255,255,255,0.22)";
    x.fillRect(359, 0, 2, 480);

    // Apply Safari-safe pixel filter directly to captured ImageData
    applyPixelFilter(x, 720, 480, selectedFilter);

    shots[shotIdx] = c;
  }

  // ==========================================================================
  // 3E. STAGE 3: 6-PHOTO SESSION FLOW
  // ==========================================================================
  function refreshFilmDots(activeIndex) {
    for (let i = 0; i < 6; i++) {
      const dot = filmDots[i];
      if (!dot) continue;
      dot.className = "pb-film-dot" +
        (i === activeIndex ? " is-active" : shots[i] ? " is-done" : "");
    }
  }

  function triggerFlash() {
    if (!flashEl) return;
    flashEl.classList.add("is-flashing");
    setTimeout(() => {
      if (flashEl) flashEl.classList.remove("is-flashing");
    }, 90);
  }

  function setFilterSelection(flt) {
    if (!FILTER_LIST.some((f) => f.id === flt)) return;
    selectedFilter = flt;
    const cls = "pb-flt-" + flt;
    if (vl) vl.className = "pb-vid-local " + cls;
    if (vr) vr.className = "pb-vid-remote " + cls;
    if (rootEl) {
      rootEl.querySelectorAll("[data-filter-id]").forEach((btn) => {
        if (btn.getAttribute("data-filter-id") === flt) btn.classList.add("is-active");
        else btn.classList.remove("is-active");
      });
    }
  }

  function startSessionRequest(singleShotIndex = null) {
    if (!stream) {
      requestVerticalCamera();
      return;
    }
    getAudioCtx();
    const payload = { filter: selectedFilter };
    if (typeof singleShotIndex === "number" && singleShotIndex >= 0 && singleShotIndex < 6) {
      payload.shotIndex = singleShotIndex;
    } else {
      shots = [null, null, null, null, null, null];
      refreshFilmDots(-1);
    }
    SocketClient.emit("photo:start", payload);

    // Local fallback if testing solo without a second socket partner in locked room
    if (localFallbackTimer) clearTimeout(localFallbackTimer);
    localFallbackTimer = setTimeout(() => {
      if (!activeSessionId && stage !== 3) {
        const indices = typeof singleShotIndex === "number" ? [singleShotIndex] : [0, 1, 2, 3, 4, 5];
        runLocalFallbackSession(indices);
      }
    }, 700);
  }

  function runLocalFallbackSession(indices) {
    const sid = "local_" + Date.now();
    onSessionStart({ sessionId: sid, indices, filter: selectedFilter });
    let delay = 250;
    indices.forEach((idx) => {
      [3, 2, 1].forEach((cnt) => {
        setTimeout(() => {
          if (activeSessionId !== sid) return;
          onSessionShot({ sessionId: sid, index: idx, phase: "countdown", count: cnt });
        }, delay);
        delay += 720;
      });
      setTimeout(() => {
        if (activeSessionId !== sid) return;
        onSessionShot({ sessionId: sid, index: idx, phase: "snap", count: 0 });
      }, delay);
      delay += 920;
    });
    setTimeout(() => {
      if (activeSessionId !== sid) return;
      onSessionShot({ sessionId: sid, phase: "done" });
    }, delay);
  }

  function onSessionStart(data) {
    if (localFallbackTimer) {
      clearTimeout(localFallbackTimer);
      localFallbackTimer = null;
    }
    activeSessionId = data.sessionId || "shared";
    if (data.filter) setFilterSelection(data.filter);
    if (Array.isArray(data.indices) && data.indices.length === 6) {
      shots = [null, null, null, null, null, null];
    }
    switchStage(3);
    if (startBtnEl) startBtnEl.disabled = true;
    if (cancelSessionBtnEl) cancelSessionBtnEl.classList.remove("pb-is-hidden");
    refreshFilmDots(Array.isArray(data.indices) ? data.indices[0] : 0);
  }

  function onSessionShot(data) {
    if (!activeSessionId) return;
    if (data.phase === "countdown") {
      currentShotIndex = data.index;
      refreshFilmDots(currentShotIndex);
      if (countdownEl) countdownEl.textContent = String(data.count);
      playBeep(data.count === 1 ? 880 : 620, 0.08);
    } else if (data.phase === "snap") {
      currentShotIndex = data.index;
      if (countdownEl) countdownEl.textContent = "";
      triggerFlash();
      playShutterSound();
      captureCombinedFrame(currentShotIndex);
      refreshFilmDots(currentShotIndex);
    } else if (data.phase === "done") {
      activeSessionId = null;
      if (countdownEl) countdownEl.textContent = "";
      if (cancelSessionBtnEl) cancelSessionBtnEl.classList.add("pb-is-hidden");
      if (startBtnEl) startBtnEl.disabled = false;
      if (developEl) developEl.classList.remove("is-hidden");
      setTimeout(() => {
        if (developEl) developEl.classList.add("is-hidden");
        if (stage === 3 || stage === 2) {
          switchStage(4);
        }
      }, 1300);
    }
  }

  function onSessionCancel(data) {
    if (localFallbackTimer) {
      clearTimeout(localFallbackTimer);
      localFallbackTimer = null;
    }
    activeSessionId = null;
    if (countdownEl) countdownEl.textContent = "";
    if (developEl) developEl.classList.add("is-hidden");
    if (cancelSessionBtnEl) cancelSessionBtnEl.classList.add("pb-is-hidden");
    if (startBtnEl) startBtnEl.disabled = false;
    if (stage === 3) switchStage(2);
    if (data && data.reason && H && H.toast) {
      H.toast(data.reason);
    }
  }

  // ==========================================================================
  // 3F. STICKERS CATALOG (14 Inline SVG Stickers + Cached Canvas Images)
  // ==========================================================================
  const STICKER_DEFS = [
    {
      id: "heart", label: "Heart",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M60 104 C20 76 10 48 22 28 C34 10 54 18 60 32 C66 18 86 10 98 28 C110 48 100 76 60 104 Z" fill="#ff3b7a" stroke="#ffffff" stroke-width="6" stroke-linejoin="round"/><path d="M34 34 C28 42 30 54 36 60" fill="none" stroke="#ffc2da" stroke-width="5" stroke-linecap="round"/></svg>`
    },
    {
      id: "star", label: "Star",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><polygon points="60,10 74,42 109,46 82,70 90,104 60,86 30,104 38,70 11,46 46,42" fill="#fbbf24" stroke="#ffffff" stroke-width="6" stroke-linejoin="round"/><polygon points="60,22 69,45 93,48 75,64 80,88 60,75 40,88 45,64 27,48 51,45" fill="#fde68a"/></svg>`
    },
    {
      id: "blossom", label: "Blossom",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><g stroke="#ffffff" stroke-width="4"><ellipse cx="60" cy="28" rx="18" ry="22" fill="#ff9ec4"/><ellipse cx="90" cy="50" rx="18" ry="22" transform="rotate(72 90 50)" fill="#ffb3d1"/><ellipse cx="79" cy="86" rx="18" ry="22" transform="rotate(144 79 86)" fill="#ff9ec4"/><ellipse cx="41" cy="86" rx="18" ry="22" transform="rotate(216 41 86)" fill="#ffb3d1"/><ellipse cx="30" cy="50" rx="18" ry="22" transform="rotate(288 30 50)" fill="#ff9ec4"/></g><circle cx="60" cy="58" r="12" fill="#fde047" stroke="#f59e0b" stroke-width="3"/></svg>`
    },
    {
      id: "petals", label: "Petals",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M38 22 C20 26 20 54 44 62 C56 44 52 20 38 22 Z" fill="#ff85b3" stroke="#ffffff" stroke-width="4"/><path d="M84 36 C68 42 70 70 94 74 C104 56 98 32 84 36 Z" fill="#ffb3d1" stroke="#ffffff" stroke-width="4"/><path d="M46 74 C30 82 36 106 60 106 C68 90 60 68 46 74 Z" fill="#ff9ec4" stroke="#ffffff" stroke-width="4"/></svg>`
    },
    {
      id: "bow", label: "Bow",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M56 56 L28 104 L46 98 L54 110 L62 64 Z" fill="#e11d74" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"/><path d="M64 56 L92 104 L74 98 L66 110 L58 64 Z" fill="#e11d74" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"/><path d="M56 54 C14 22 10 82 56 62 Z" fill="#ff6ea7" stroke="#ffffff" stroke-width="5" stroke-linejoin="round"/><path d="M64 54 C106 22 110 82 64 62 Z" fill="#ff6ea7" stroke="#ffffff" stroke-width="5" stroke-linejoin="round"/><circle cx="60" cy="58" r="11" fill="#ff9ec4" stroke="#ffffff" stroke-width="4"/></svg>`
    },
    {
      id: "sparkles", label: "Sparkles",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M48 12 Q48 44 16 44 Q48 44 48 76 Q48 44 80 44 Q48 44 48 12 Z" fill="#fef08a" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"/><path d="M88 54 Q88 74 68 74 Q88 74 88 94 Q88 74 108 74 Q88 74 88 54 Z" fill="#fbcfe8" stroke="#ffffff" stroke-width="3.5" stroke-linejoin="round"/><path d="M30 72 Q30 88 14 88 Q30 88 30 104 Q30 88 46 88 Q30 88 30 72 Z" fill="#a5f3fc" stroke="#ffffff" stroke-width="3.5" stroke-linejoin="round"/></svg>`
    },
    {
      id: "smiley", label: "Smiley",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><circle cx="60" cy="60" r="46" fill="#fde047" stroke="#ffffff" stroke-width="6"/><circle cx="44" cy="48" r="6" fill="#291521"/><circle cx="76" cy="48" r="6" fill="#291521"/><ellipse cx="32" cy="62" rx="8" ry="5" fill="#fb7185"/><ellipse cx="88" cy="62" rx="8" ry="5" fill="#fb7185"/><path d="M38 66 Q60 88 82 66" fill="none" stroke="#291521" stroke-width="6" stroke-linecap="round"/></svg>`
    },
    {
      id: "cherries", label: "Cherries",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M40 78 Q52 38 72 22 Q68 48 82 80" fill="none" stroke="#16a34a" stroke-width="6" stroke-linecap="round"/><path d="M70 22 C88 14 104 28 86 38 C74 44 68 30 70 22 Z" fill="#4ade80" stroke="#ffffff" stroke-width="3"/><circle cx="38" cy="84" r="20" fill="#e11d48" stroke="#ffffff" stroke-width="5"/><circle cx="82" cy="86" r="20" fill="#be123c" stroke="#ffffff" stroke-width="5"/><circle cx="32" cy="78" r="5" fill="#fecdd3"/><circle cx="76" cy="80" r="5" fill="#fecdd3"/></svg>`
    },
    {
      id: "love", label: "LOVE",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect x="8" y="32" width="104" height="56" rx="28" fill="#ff5c99" stroke="#ffffff" stroke-width="6"/><text x="60" y="69" text-anchor="middle" fill="#ffffff" font-family="Georgia, serif" font-size="30" font-weight="900" letter-spacing="2">LOVE</text></svg>`
    },
    {
      id: "bestie", label: "BESTIE",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect x="6" y="34" width="108" height="52" rx="26" fill="#a855f7" stroke="#ffffff" stroke-width="6"/><text x="60" y="67" text-anchor="middle" fill="#fef08a" font-family="sans-serif" font-size="22" font-weight="900" letter-spacing="1.5">BESTIE</text></svg>`
    },
    {
      id: "xoxo", label: "XOXO",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect x="8" y="34" width="104" height="52" rx="16" fill="#fb7185" stroke="#ffffff" stroke-width="6"/><text x="60" y="68" text-anchor="middle" fill="#ffffff" font-family="Georgia, serif" font-size="26" font-weight="900" letter-spacing="2">XOXO</text></svg>`
    },
    {
      id: "camera", label: "Camera",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect x="30" y="22" width="26" height="14" rx="4" fill="#f472b6" stroke="#ffffff" stroke-width="4"/><rect x="16" y="32" width="88" height="64" rx="14" fill="#fbcfe8" stroke="#ffffff" stroke-width="6"/><circle cx="60" cy="64" r="20" fill="#3b1c32" stroke="#ffffff" stroke-width="5"/><circle cx="60" cy="64" r="9" fill="#ff6fa5"/><circle cx="86" cy="46" r="5" fill="#fef08a"/></svg>`
    },
    {
      id: "moon", label: "Moon",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M76 18 C42 22 24 58 44 88 C60 110 92 104 100 88 C72 92 54 68 62 42 C66 30 72 22 76 18 Z" fill="#fde047" stroke="#ffffff" stroke-width="5" stroke-linejoin="round"/><polygon points="88,28 91,36 100,37 93,43 95,52 88,47 81,52 83,43 76,37 85,36" fill="#fef08a"/></svg>`
    },
    {
      id: "crown", label: "Crown",
      svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><path d="M16 88 L24 36 L48 60 L60 26 L72 60 L96 36 L104 88 Z" fill="#fbbf24" stroke="#ffffff" stroke-width="6" stroke-linejoin="round"/><circle cx="60" cy="72" r="6" fill="#e11d48"/><circle cx="38" cy="74" r="5" fill="#ec4899"/><circle cx="82" cy="74" r="5" fill="#ec4899"/></svg>`
    }
  ];

  const stickerImages = {};
  function preloadStickerImages() {
    STICKER_DEFS.forEach((def) => {
      if (stickerImages[def.id]) return;
      const img = new Image();
      img.onload = () => {
        if (stage === 4) renderPreview();
      };
      img.src = "data:image/svg+xml;utf8," + encodeURIComponent(def.svg);
      stickerImages[def.id] = img;
    });
  }

  // ==========================================================================
  // 3G. PAPER TEMPLATES & UNIFIED HIGH-RES CANVAS RENDERER (1200 x 1800)
  // ==========================================================================
  function getGridSlots(paper) {
    // Returns 6 slots {x, y, w, h, rot} in 1200 x 1800 canonical coordinates
    if (paper === "film") {
      const slots = [];
      for (let i = 0; i < 6; i++) {
        const col = i % 2;
        const row = Math.floor(i / 2);
        slots.push({
          x: col === 0 ? 130 : 620,
          y: 135 + row * 485,
          w: 450,
          h: 340,
          rot: 0
        });
      }
      return slots;
    }
    if (paper === "polaroid") {
      const angles = [-0.032, 0.028, 0.022, -0.026, -0.02, 0.03];
      const slots = [];
      for (let i = 0; i < 6; i++) {
        const col = i % 2;
        const row = Math.floor(i / 2);
        slots.push({
          x: col === 0 ? 95 : 625,
          y: 115 + row * 490,
          w: 480,
          h: 345,
          rot: angles[i]
        });
      }
      return slots;
    }
    const slots = [];
    for (let i = 0; i < 6; i++) {
      const col = i % 2;
      const row = Math.floor(i / 2);
      slots.push({
        x: col === 0 ? 78 : 618,
        y: 120 + row * 480,
        w: 504,
        h: 378,
        rot: 0
      });
    }
    return slots;
  }

  function drawRoundedRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function drawHeartPath(ctx, cx, cy, w, h) {
    const topY = cy - h * 0.32;
    const botY = cy + h * 0.48;
    ctx.beginPath();
    ctx.moveTo(cx, botY);
    ctx.bezierCurveTo(cx - w * 0.56, cy + h * 0.14, cx - w * 0.54, cy - h * 0.46, cx - w * 0.25, cy - h * 0.46);
    ctx.bezierCurveTo(cx - w * 0.08, cy - h * 0.46, cx, topY, cx, topY);
    ctx.bezierCurveTo(cx, topY, cx + w * 0.08, cy - h * 0.46, cx + w * 0.25, cy - h * 0.46);
    ctx.bezierCurveTo(cx + w * 0.54, cy - h * 0.46, cx + w * 0.56, cy + h * 0.14, cx, botY);
    ctx.closePath();
  }

  function drawBlossomFlowerOnCanvas(ctx, cx, cy, r) {
    ctx.save();
    ctx.translate(cx, cy);
    for (let i = 0; i < 5; i++) {
      ctx.save();
      ctx.rotate((i * Math.PI * 2) / 5);
      ctx.fillStyle = i % 2 === 0 ? "#ffb3d1" : "#ffc8df";
      ctx.beginPath();
      ctx.ellipse(0, -r * 0.65, r * 0.42, r * 0.58, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    ctx.fillStyle = "#fde047";
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.26, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function renderPaperToCanvas(canvas, includeSelectionUI) {
    const W = 1200;
    const H = 1800;
    if (canvas.width !== W) canvas.width = W;
    if (canvas.height !== H) canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.save();
    ctx.clearRect(0, 0, W, H);

    const dateStr = new Date().toLocaleDateString();
    const footerText = "us \u00b7 " + dateStr;

    // 1. Paper Background & Border Art
    if (selectedPaper === "classic") {
      ctx.fillStyle = "#faf8f6";
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#e2dce0";
      ctx.lineWidth = 6;
      ctx.strokeRect(32, 32, W - 64, H - 64);
    } else if (selectedPaper === "blossom") {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, "#ffe4ef");
      g.addColorStop(0.5, "#ffc8df");
      g.addColorStop(1, "#ffafd0");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 8;
      ctx.strokeRect(36, 36, W - 72, H - 72);
      [
        [75, 70, 34], [1125, 70, 34], [70, 1720, 36], [1125, 1720, 36],
        [600, 62, 28], [62, 600, 26], [1138, 600, 26], [62, 1080, 26], [1138, 1080, 26]
      ].forEach(([bx, by, br]) => drawBlossomFlowerOnCanvas(ctx, bx, by, br));
    } else if (selectedPaper === "polaroid") {
      const g = ctx.createLinearGradient(0, 0, W, H);
      g.addColorStop(0, "#f3e7ee");
      g.addColorStop(1, "#e2cedb");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    } else if (selectedPaper === "film") {
      ctx.fillStyle = "#121216";
      ctx.fillRect(0, 0, W, H);
      // Sprocket holes along left and right edges
      ctx.fillStyle = "#f4f4f6";
      for (let y = 45; y < H - 45; y += 64) {
        drawRoundedRect(ctx, 32, y, 42, 30, 6);
        ctx.fill();
        drawRoundedRect(ctx, W - 74, y, 42, 30, 6);
        ctx.fill();
      }
      ctx.fillStyle = "#f59e0b";
      ctx.font = "bold 20px monospace";
      for (let i = 0; i < 6; i++) {
        const row = Math.floor(i / 2);
        const col = i % 2;
        ctx.fillText("0" + (i + 1) + "A", col === 0 ? 135 : 625, 122 + row * 485);
      }
    } else if (selectedPaper === "retro") {
      ctx.fillStyle = "#f6ebd8";
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#b85d3b";
      ctx.lineWidth = 8;
      ctx.strokeRect(34, 34, W - 68, H - 68);
      ctx.strokeStyle = "#d99b52";
      ctx.lineWidth = 4;
      ctx.strokeRect(48, 48, W - 96, H - 96);
    } else if (selectedPaper === "midnight") {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, "#0c1024");
      g.addColorStop(0.55, "#191738");
      g.addColorStop(1, "#29183e");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth = 5;
      ctx.strokeRect(38, 38, W - 76, H - 76);
      // Gold stars
      ctx.fillStyle = "#fde68a";
      for (let i = 0; i < 38; i++) {
        const sx = (i * 197 + 63) % (W - 80) + 40;
        const sy = (i * 283 + 47) % (H - 80) + 40;
        ctx.beginPath();
        ctx.arc(sx, sy, (i % 3) + 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (selectedPaper === "hearts") {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, "#fff0f5");
      g.addColorStop(1, "#ffd6e6");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "#ff6fa5";
      ctx.lineWidth = 6;
      ctx.setLineDash([16, 12]);
      ctx.strokeRect(36, 36, W - 72, H - 72);
      ctx.setLineDash([]);
    }

    // 2. Render the 6 Photo Frames
    const slots = getGridSlots(selectedPaper);
    for (let i = 0; i < 6; i++) {
      const s = slots[i];
      const shotCanvas = shots[i];
      ctx.save();
      if (selectedPaper === "polaroid") {
        ctx.translate(s.x + s.w * 0.5, s.y + s.h * 0.5);
        ctx.rotate(s.rot);
        ctx.shadowColor = "rgba(0,0,0,0.22)";
        ctx.shadowBlur = 18;
        ctx.shadowOffsetY = 8;
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(-s.w * 0.5 - 22, -s.h * 0.5 - 22, s.w + 44, s.h + 92);
        ctx.shadowColor = "transparent";
        if (shotCanvas) {
          ctx.drawImage(shotCanvas, -s.w * 0.5, -s.h * 0.5, s.w, s.h);
        } else {
          ctx.fillStyle = "#2b1623";
          ctx.fillRect(-s.w * 0.5, -s.h * 0.5, s.w, s.h);
        }
        // Washi tape accent at top of polaroid
        ctx.fillStyle = "rgba(255, 168, 205, 0.72)";
        ctx.fillRect(-55, -s.h * 0.5 - 32, 110, 24);
      } else if (selectedPaper === "hearts") {
        const cx = s.x + s.w * 0.5;
        const cy = s.y + s.h * 0.5;
        drawHeartPath(ctx, cx, cy, s.w * 1.02, s.h * 1.05);
        ctx.save();
        ctx.clip();
        if (shotCanvas) {
          ctx.drawImage(shotCanvas, s.x, s.y, s.w, s.h);
        } else {
          ctx.fillStyle = "#381829";
          ctx.fillRect(s.x, s.y, s.w, s.h);
        }
        ctx.restore();
        drawHeartPath(ctx, cx, cy, s.w * 1.02, s.h * 1.05);
        ctx.strokeStyle = "#ff4785";
        ctx.lineWidth = 8;
        ctx.stroke();
      } else {
        drawRoundedRect(ctx, s.x, s.y, s.w, s.h, 14);
        ctx.save();
        ctx.clip();
        if (shotCanvas) {
          ctx.drawImage(shotCanvas, s.x, s.y, s.w, s.h);
        } else {
          ctx.fillStyle = "#2a1421";
          ctx.fillRect(s.x, s.y, s.w, s.h);
        }
        ctx.restore();

        // Frame border + Retro quartz date stamp
        drawRoundedRect(ctx, s.x, s.y, s.w, s.h, 14);
        ctx.lineWidth = 5;
        ctx.strokeStyle =
          selectedPaper === "midnight" ? "#fbbf24" :
          selectedPaper === "blossom" ? "#ffffff" :
          selectedPaper === "retro" ? "#c27849" :
          selectedPaper === "film" ? "#2e2e36" : "#e5dce0";
        ctx.stroke();

        if (selectedPaper === "retro") {
          ctx.fillStyle = "#ff6b2b";
          ctx.font = "bold 21px monospace";
          ctx.fillText("'" + String(new Date().getFullYear()).slice(-2) + " " + String(new Date().getMonth() + 1).padStart(2, "0") + " " + String(new Date().getDate()).padStart(2, "0"), s.x + s.w - 135, s.y + s.h - 18);
        }
      }
      ctx.restore();
    }

    // 3. Footer / Caption Area
    ctx.save();
    ctx.textAlign = "center";
    if (selectedPaper === "midnight" || selectedPaper === "film") {
      ctx.fillStyle = "#fde68a";
      ctx.font = "italic 600 44px Georgia, serif";
      ctx.fillText(footerText, W * 0.5, 1685);
      ctx.fillStyle = "rgba(255, 240, 200, 0.7)";
      ctx.font = "600 22px sans-serif";
      ctx.fillText("BLOSSOM GARDEN PHOTO BOOTH", W * 0.5, 1732);
    } else if (selectedPaper === "blossom" || selectedPaper === "hearts") {
      ctx.fillStyle = "#9e1946";
      ctx.font = "italic 700 46px Georgia, serif";
      ctx.fillText(footerText, W * 0.5, 1685);
      ctx.fillStyle = "#c93b6b";
      ctx.font = "700 22px sans-serif";
      ctx.fillText("CHERRY BLOSSOM MEMORIES", W * 0.5, 1732);
    } else {
      ctx.fillStyle = "#361928";
      ctx.font = "italic 700 44px Georgia, serif";
      ctx.fillText(footerText, W * 0.5, 1685);
      ctx.fillStyle = "#7a5266";
      ctx.font = "600 21px sans-serif";
      ctx.fillText("PHOTO BOOTH \u00b7 SIX POSES", W * 0.5, 1730);
    }
    ctx.restore();

    // 4. Stickers Layer (clamped to paper bounds)
    const baseSize = 150;
    stickers.forEach((st) => {
      const img = stickerImages[st.type];
      if (!img || !img.complete) return;
      const sz = baseSize * st.scale;
      ctx.save();
      ctx.translate(st.x, st.y);
      ctx.rotate((st.rot * Math.PI) / 180);
      if (st.flip) ctx.scale(-1, 1);
      ctx.drawImage(img, -sz * 0.5, -sz * 0.5, sz, sz);
      ctx.restore();
    });

    // 5. Interactive Selection Handles (Preview only, omitted on PNG export)
    if (includeSelectionUI && selectedStickerId) {
      const sel = stickers.find((s) => s.id === selectedStickerId);
      if (sel) {
        const sz = baseSize * sel.scale;
        const half = sz * 0.5;
        ctx.save();
        ctx.translate(sel.x, sel.y);
        ctx.rotate((sel.rot * Math.PI) / 180);

        ctx.strokeStyle = "#ff3b82";
        ctx.lineWidth = 4;
        ctx.setLineDash([10, 6]);
        ctx.strokeRect(-half, -half, sz, sz);
        ctx.setLineDash([]);

        // Top Rotate Handle
        ctx.beginPath();
        ctx.moveTo(0, -half);
        ctx.lineTo(0, -half - 44);
        ctx.stroke();
        ctx.fillStyle = "#fbbf24";
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(0, -half - 44, 18, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Bottom-Right Resize Handle
        ctx.fillStyle = "#ff3b82";
        ctx.beginPath();
        ctx.arc(half, half, 18, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.restore();
      }
    }

    ctx.restore();
  }

  function renderPreview() {
    if (!previewCanvas) return;
    renderPaperToCanvas(previewCanvas, true);
  }

  // ==========================================================================
  // 3H. STICKER MANIPULATION & POINTER EVENTS
  // ==========================================================================
  function clampSticker(st) {
    const pad = Math.min(220, 65 * st.scale);
    st.x = Math.max(pad, Math.min(1200 - pad, st.x));
    st.y = Math.max(pad, Math.min(1800 - pad, st.y));
    st.scale = Math.max(0.3, Math.min(2.8, st.scale));
  }

  function syncStickerInspector() {
    const sel = stickers.find((s) => s.id === selectedStickerId);
    if (!stickerToolsWrapEl) return;
    if (!sel) {
      stickerToolsWrapEl.classList.add("pb-is-hidden");
      return;
    }
    stickerToolsWrapEl.classList.remove("pb-is-hidden");
    if (sizeInputEl) sizeInputEl.value = String(sel.scale);
    if (rotInputEl) rotInputEl.value = String(Math.round(sel.rot));
  }

  function addSticker(type) {
    const offset = (stickers.length % 5) * 36 - 72;
    const st = {
      id: "st_" + (++stickerSeq),
      type,
      x: 600 + offset,
      y: 860 + offset,
      scale: 1.0,
      rot: 0,
      flip: false
    };
    clampSticker(st);
    stickers.push(st);
    selectedStickerId = st.id;
    syncStickerInspector();
    renderPreview();
  }

  function canvasCoordsFromEvent(e) {
    const rect = previewCanvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 1200;
    const y = ((e.clientY - rect.top) / rect.height) * 1800;
    return { x, y };
  }

  function localCoordsForSticker(px, py, st) {
    const dx = px - st.x;
    const dy = py - st.y;
    const rad = (-st.rot * Math.PI) / 180;
    return {
      lx: dx * Math.cos(rad) - dy * Math.sin(rad),
      ly: dx * Math.sin(rad) + dy * Math.cos(rad)
    };
  }

  function bindCanvasPointerEvents() {
    if (!previewCanvas) return;
    const baseSize = 150;

    previewCanvas.addEventListener("pointerdown", (e) => {
      previewCanvas.setPointerCapture(e.pointerId);
      const pt = canvasCoordsFromEvent(e);
      activePointers.set(e.pointerId, pt);

      if (activePointers.size === 2 && selectedStickerId) {
        const sel = stickers.find((s) => s.id === selectedStickerId);
        if (sel) {
          const pts = Array.from(activePointers.values());
          const d = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) || 1;
          const ang = Math.atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x);
          pinchStart = { dist: d, angle: ang, scale: sel.scale, rot: sel.rot };
          dragMode = "pinch";
          return;
        }
      }

      // Check handles of currently selected sticker first
      if (selectedStickerId) {
        const sel = stickers.find((s) => s.id === selectedStickerId);
        if (sel) {
          const half = (baseSize * sel.scale) * 0.5;
          const { lx, ly } = localCoordsForSticker(pt.x, pt.y, sel);
          if (Math.hypot(lx - 0, ly - (-half - 44)) <= 34) {
            dragMode = "rotate";
            dragStart = { sticker: sel };
            return;
          }
          if (Math.hypot(lx - half, ly - half) <= 34) {
            dragMode = "resize";
            dragStart = { sticker: sel };
            return;
          }
        }
      }

      // Hit-test stickers from top to bottom
      let hit = null;
      for (let i = stickers.length - 1; i >= 0; i--) {
        const st = stickers[i];
        const half = (baseSize * st.scale) * 0.54;
        const { lx, ly } = localCoordsForSticker(pt.x, pt.y, st);
        if (Math.abs(lx) <= half && Math.abs(ly) <= half) {
          hit = st;
          break;
        }
      }

      if (hit) {
        selectedStickerId = hit.id;
        dragMode = "move";
        dragStart = { sticker: hit, ox: pt.x - hit.x, oy: pt.y - hit.y };
      } else {
        selectedStickerId = null;
        dragMode = null;
        dragStart = null;
      }
      syncStickerInspector();
      renderPreview();
    });

    previewCanvas.addEventListener("pointermove", (e) => {
      if (!activePointers.has(e.pointerId)) return;
      const pt = canvasCoordsFromEvent(e);
      activePointers.set(e.pointerId, pt);

      if (dragMode === "pinch" && pinchStart && activePointers.size === 2 && selectedStickerId) {
        const sel = stickers.find((s) => s.id === selectedStickerId);
        if (sel) {
          const pts = Array.from(activePointers.values());
          const d = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) || 1;
          const ang = Math.atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x);
          sel.scale = pinchStart.scale * (d / pinchStart.dist);
          sel.rot = pinchStart.rot + ((ang - pinchStart.angle) * 180) / Math.PI;
          clampSticker(sel);
          syncStickerInspector();
          renderPreview();
        }
        return;
      }

      if (!dragMode || !dragStart || !dragStart.sticker) return;
      const st = dragStart.sticker;
      if (dragMode === "move") {
        st.x = pt.x - dragStart.ox;
        st.y = pt.y - dragStart.oy;
        clampSticker(st);
      } else if (dragMode === "resize") {
        const dist = Math.hypot(pt.x - st.x, pt.y - st.y);
        st.scale = dist / (baseSize * 0.707);
        clampSticker(st);
      } else if (dragMode === "rotate") {
        const angle = Math.atan2(pt.y - st.y, pt.x - st.x);
        st.rot = ((angle * 180) / Math.PI) + 90;
        if (st.rot > 180) st.rot -= 360;
      }
      syncStickerInspector();
      renderPreview();
    });

    const endPtr = (e) => {
      activePointers.delete(e.pointerId);
      if (activePointers.size < 2) pinchStart = null;
      if (activePointers.size === 0) {
        dragMode = null;
        dragStart = null;
      }
    };
    previewCanvas.addEventListener("pointerup", endPtr);
    previewCanvas.addEventListener("pointercancel", endPtr);
  }

  // ==========================================================================
  // 3I. HIGH-RESOLUTION EXPORT (1200 x 1800 PNG)
  // ==========================================================================
  function downloadHighResPNG() {
    const outCanvas = document.createElement("canvas");
    outCanvas.width = 1200;
    outCanvas.height = 1800;
    renderPaperToCanvas(outCanvas, false);

    const triggerDownload = (url) => {
      const a = document.createElement("a");
      a.href = url;
      a.download = "photobooth-" + selectedPaper + ".png";
      document.body.appendChild(a);
      a.click();
      a.remove();
    };

    if (outCanvas.toBlob) {
      outCanvas.toBlob((blob) => {
        if (!blob) {
          triggerDownload(outCanvas.toDataURL("image/png"));
          return;
        }
        const url = URL.createObjectURL(blob);
        triggerDownload(url);
        setTimeout(() => URL.revokeObjectURL(url), 10000);
      }, "image/png");
    } else {
      triggerDownload(outCanvas.toDataURL("image/png"));
    }
  }

  // ==========================================================================
  // 3J. STAGE NAVIGATION & FULL UI CONSTRUCTION
  // ==========================================================================
  function switchStage(nextStage) {
    stage = nextStage;
    if (!stage1El || !stage2El || !stage4El) return;

    if (stage === 1) {
      stopHardware();
      stage1El.classList.remove("pb-is-hidden", "is-entering");
      stage2El.classList.add("pb-is-hidden");
      stage4El.classList.add("pb-is-hidden");
      if (stagePillEl) stagePillEl.textContent = "Stage 1 · Blossom Garden";
    } else if (stage === 2 || stage === 3) {
      stage1El.classList.add("pb-is-hidden");
      stage2El.classList.remove("pb-is-hidden");
      stage4El.classList.add("pb-is-hidden");
      if (stagePillEl) {
        stagePillEl.textContent = stage === 2 ? "Stage 2 · Inside Booth" : "Stage 3 · Taking 6 Photos";
      }
      if (!stream) {
        requestVerticalCamera();
      }
    } else if (stage === 4) {
      stage1El.classList.add("pb-is-hidden");
      stage2El.classList.add("pb-is-hidden");
      stage4El.classList.remove("pb-is-hidden");
      if (stagePillEl) stagePillEl.textContent = "Stage 4 · Paper & Stickers";
      renderPreview();
    }
  }

  function handleBackButton() {
    if (activeSessionId) {
      SocketClient.emit("photo:cancel", { reason: "left" });
    }
    // Always invoke the hardware kill-switch so camera tracks are ended immediately on Back
    stopHardware();
    if (stage !== 1) {
      switchStage(1);
    }
  }

  function buildBoothDOM(container) {
    container.replaceChildren();
    preloadStickerImages();

    rootEl = H.el("div", "pb-shell");

    // Top Navigation & Status Bar
    const topbar = H.el("div", "pb-topbar");
    const topLeft = H.el("div", "pb-topbar-left");
    const backBtn = H.el("button", "pb-btn", "\u2190 Back");
    backBtn.type = "button";
    backBtn.setAttribute("aria-label", "Back and stop camera");
    backBtn.onclick = handleBackButton;

    stagePillEl = H.el("span", "pb-stage-pill", "Stage 1 · Blossom Garden");
    topLeft.append(backBtn, stagePillEl);

    const topRight = H.el("div", "pb-topbar-right");
    const statusPill = H.el("div", "pb-status-pill");
    statusDotEl = H.el("span", "pb-dot");
    statusTextEl = H.el("span", "", "Camera off · Outside booth");
    statusPill.append(statusDotEl, statusTextEl);
    topRight.append(statusPill);
    topbar.append(topLeft, topRight);

    // ------------------------------------------------------------------------
    // STAGE 1: Outdoor Blossom Garden & Vintage Booth
    // ------------------------------------------------------------------------
    stage1El = H.el("div", "pb-garden-stage");
    stage1El.innerHTML = buildGardenSceneSVG();

    const enterWrap = H.el("div", "pb-enter-wrap");
    const enterBtn = H.el("button", "pb-enter-btn", "ENTER");
    enterBtn.type = "button";
    enterBtn.setAttribute("aria-label", "Enter the Photo Booth");
    const enterSub = H.el("span", "pb-enter-sub", "Step inside with your partner · 6 vertical photos");
    enterBtn.onclick = () => {
      getAudioCtx();
      const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduceMotion) {
        switchStage(2);
      } else {
        stage1El.classList.add("is-entering");
        setTimeout(() => switchStage(2), 460);
      }
    };
    enterWrap.append(enterBtn, enterSub);
    stage1El.append(enterWrap);

    // ------------------------------------------------------------------------
    // STAGE 2 & 3: Inside the Booth (Vertical Camera + 6-Shot Session)
    // ------------------------------------------------------------------------
    stage2El = H.el("div", "pb-interior pb-is-hidden");
    const lightStrip = H.el("div", "pb-light-strip");
    const camWindow = H.el("div", "pb-cam-window");

    // Camera Permission Error Box with Retry
    camErrorEl = H.el("div", "pb-cam-error is-hidden");
    camErrorMsgEl = H.el("span", "", "Camera access is required.");
    const retryCamBtn = H.el("button", "pb-btn pb-btn-primary", "Retry Camera");
    retryCamBtn.type = "button";
    retryCamBtn.onclick = () => requestVerticalCamera();
    camErrorEl.append(camErrorMsgEl, retryCamBtn);

    // Dual Vertical Portrait Videos
    const vidsGrid = H.el("div", "pb-vids-grid");
    const localCard = H.el("div", "pb-vid-card");
    vl = H.el("video", "pb-vid-local pb-flt-none");
    vl.autoplay = true;
    vl.muted = true;
    vl.playsInline = true;
    const localBadge = H.el("span", "pb-vid-badge", "You");
    localCard.append(vl, localBadge);

    const remoteCard = H.el("div", "pb-vid-card");
    vr = H.el("video", "pb-vid-remote pb-flt-none");
    vr.autoplay = true;
    vr.playsInline = true;
    vr.onloadeddata = () => markPartnerConnected();
    partnerWaitEl = H.el("div", "pb-partner-wait", "Waiting for partner to enter the booth...");
    const remoteBadge = H.el("span", "pb-vid-badge", "Partner");
    remoteCard.append(vr, partnerWaitEl, remoteBadge);

    vidsGrid.append(localCard, remoteCard);

    // Countdown, White Flash & Developing Overlays
    const countdownLayer = H.el("div", "pb-countdown-layer");
    countdownEl = H.el("div", "pb-countdown-num", "");
    countdownLayer.append(countdownEl);

    flashEl = H.el("div", "pb-flash-layer");

    developEl = H.el("div", "pb-develop-overlay is-hidden");
    const devIcon = H.el("div", "pb-develop-strip-icon");
    const devText = H.el("div", "", "Developing your photos...");
    developEl.append(devIcon, devText);

    camWindow.append(camErrorEl, vidsGrid, countdownLayer, flashEl, developEl);

    // Progress Film Dots (1/6 ... 6/6)
    const filmRow = H.el("div", "pb-film-progress");
    filmDots = [];
    for (let i = 0; i < 6; i++) {
      const dot = H.el("div", "pb-film-dot", (i + 1) + "/6");
      filmDots.push(dot);
      filmRow.append(dot);
    }

    // Filter Picker & Start / Back Controls
    const controlsBar = H.el("div", "pb-controls-bar");
    const filterRow = H.el("div", "pb-chip-row");
    FILTER_LIST.forEach((f) => {
      const chip = H.el("button", "pb-chip" + (f.id === selectedFilter ? " is-active" : ""), f.label);
      chip.type = "button";
      chip.setAttribute("data-filter-id", f.id);
      chip.onclick = () => setFilterSelection(f.id);
      filterRow.append(chip);
    });

    const actionRow = H.el("div", "pb-action-row");
    startBtnEl = H.el("button", "pb-btn pb-btn-primary", "Start (6 Photos)");
    startBtnEl.type = "button";
    startBtnEl.onclick = () => startSessionRequest(null);

    cancelSessionBtnEl = H.el("button", "pb-btn pb-btn-danger pb-is-hidden", "Cancel Session");
    cancelSessionBtnEl.type = "button";
    cancelSessionBtnEl.onclick = () => {
      SocketClient.emit("photo:cancel", {});
      onSessionCancel({ reason: "Session cancelled." });
    };

    const interiorBackBtn = H.el("button", "pb-btn", "Back");
    interiorBackBtn.type = "button";
    interiorBackBtn.onclick = handleBackButton;

    actionRow.append(startBtnEl, cancelSessionBtnEl, interiorBackBtn);
    controlsBar.append(filterRow, actionRow);

    const stoolBar = H.el("div", "pb-stool-bar");
    stage2El.append(lightStrip, camWindow, filmRow, controlsBar, stoolBar);

    // ------------------------------------------------------------------------
    // STAGE 4: Paper Templates, Stickers & High-Res Export
    // ------------------------------------------------------------------------
    stage4El = H.el("div", "pb-studio pb-is-hidden");

    const previewCol = H.el("div", "pb-preview-col");
    const canvasWrap = H.el("div", "pb-canvas-wrap");
    previewCanvas = H.el("canvas", "pb-preview-canvas");
    previewCanvas.width = 1200;
    previewCanvas.height = 1800;
    canvasWrap.append(previewCanvas);
    const hintText = H.el("div", "pb-enter-sub", "Drag stickers to move · Drag handles or use sliders to resize & rotate");
    previewCol.append(canvasWrap, hintText);

    const editorCol = H.el("div", "pb-editor-col");

    // Paper Picker Panel
    const paperPanel = H.el("div", "pb-panel");
    paperPanel.append(H.el("div", "pb-panel-title", "1. Choose Booth Paper"));
    const paperRow = H.el("div", "pb-chip-row");
    PAPER_LIST.forEach((pItem) => {
      const btn = H.el("button", "pb-chip" + (pItem.id === selectedPaper ? " is-active" : ""), pItem.label);
      btn.type = "button";
      btn.setAttribute("data-paper-id", pItem.id);
      btn.onclick = () => {
        selectedPaper = pItem.id;
        paperRow.querySelectorAll(".pb-chip").forEach((b) => {
          if (b.getAttribute("data-paper-id") === pItem.id) b.classList.add("is-active");
          else b.classList.remove("is-active");
        });
        renderPreview();
      };
      paperRow.append(btn);
    });
    paperPanel.append(paperRow);

    // Sticker Tray Panel
    const stickerPanel = H.el("div", "pb-panel");
    stickerPanel.append(H.el("div", "pb-panel-title", "2. Add Stickers (Tap to Place)"));
    const stickerGrid = H.el("div", "pb-sticker-grid");
    STICKER_DEFS.forEach((def) => {
      const sBtn = H.el("button", "pb-sticker-btn");
      sBtn.type = "button";
      sBtn.title = "Add " + def.label;
      sBtn.setAttribute("aria-label", "Add " + def.label + " sticker");
      sBtn.innerHTML = def.svg;
      sBtn.onclick = () => addSticker(def.id);
      stickerGrid.append(sBtn);
    });
    stickerPanel.append(stickerGrid);

    // Selected Sticker Inspector Controls
    stickerToolsWrapEl = H.el("div", "pb-panel pb-is-hidden");
    stickerToolsWrapEl.append(H.el("div", "pb-panel-title", "Selected Sticker Controls"));

    const sizeRow = H.el("div", "pb-slider-row");
    const sizeLbl = H.el("label", "", "Size");
    sizeInputEl = H.el("input");
    sizeInputEl.type = "range";
    sizeInputEl.min = "0.3";
    sizeInputEl.max = "2.8";
    sizeInputEl.step = "0.05";
    sizeInputEl.value = "1";
    sizeInputEl.oninput = () => {
      const sel = stickers.find((s) => s.id === selectedStickerId);
      if (sel) {
        sel.scale = parseFloat(sizeInputEl.value);
        clampSticker(sel);
        renderPreview();
      }
    };
    sizeRow.append(sizeLbl, sizeInputEl);

    const rotRow = H.el("div", "pb-slider-row");
    const rotLbl = H.el("label", "", "Rotate");
    rotInputEl = H.el("input");
    rotInputEl.type = "range";
    rotInputEl.min = "-180";
    rotInputEl.max = "180";
    rotInputEl.step = "1";
    rotInputEl.value = "0";
    rotInputEl.oninput = () => {
      const sel = stickers.find((s) => s.id === selectedStickerId);
      if (sel) {
        sel.rot = parseFloat(rotInputEl.value);
        renderPreview();
      }
    };
    rotRow.append(rotLbl, rotInputEl);

    const stBtns = H.el("div", "pb-action-row");
    const frontBtn = H.el("button", "pb-btn", "Bring to Front");
    frontBtn.type = "button";
    frontBtn.onclick = () => {
      const idx = stickers.findIndex((s) => s.id === selectedStickerId);
      if (idx >= 0) {
        const [item] = stickers.splice(idx, 1);
        stickers.push(item);
        renderPreview();
      }
    };

    const flipBtn = H.el("button", "pb-btn", "Flip");
    flipBtn.type = "button";
    flipBtn.onclick = () => {
      const sel = stickers.find((s) => s.id === selectedStickerId);
      if (sel) {
        sel.flip = !sel.flip;
        renderPreview();
      }
    };

    const dupBtn = H.el("button", "pb-btn", "Duplicate");
    dupBtn.type = "button";
    dupBtn.onclick = () => {
      const sel = stickers.find((s) => s.id === selectedStickerId);
      if (sel) {
        const copy = {
          id: "st_" + (++stickerSeq),
          type: sel.type,
          x: sel.x + 42,
          y: sel.y + 42,
          scale: sel.scale,
          rot: sel.rot,
          flip: sel.flip
        };
        clampSticker(copy);
        stickers.push(copy);
        selectedStickerId = copy.id;
        syncStickerInspector();
        renderPreview();
      }
    };

    const delBtn = H.el("button", "pb-btn pb-btn-danger", "Delete Sticker");
    delBtn.type = "button";
    delBtn.onclick = () => {
      stickers = stickers.filter((s) => s.id !== selectedStickerId);
      selectedStickerId = null;
      syncStickerInspector();
      renderPreview();
    };

    stBtns.append(frontBtn, flipBtn, dupBtn, delBtn);
    stickerToolsWrapEl.append(sizeRow, rotRow, stBtns);

    // Retake & Export Panel
    const exportPanel = H.el("div", "pb-panel");
    exportPanel.append(H.el("div", "pb-panel-title", "3. Finish, Retake or Download"));
    const mainExportRow = H.el("div", "pb-action-row");

    const downloadBtn = H.el("button", "pb-btn pb-btn-primary", "Download PNG");
    downloadBtn.type = "button";
    downloadBtn.onclick = downloadHighResPNG;

    const shareBtn = H.el("button", "pb-btn", "Send to Partner");
    shareBtn.type = "button";
    shareBtn.onclick = () => {
      SocketClient.emit("photo:share", { paper: selectedPaper, stickers });
      if (H && H.toast) H.toast("Sent your paper & stickers to your partner!");
    };

    const clearStickersBtn = H.el("button", "pb-btn", "Clear Stickers");
    clearStickersBtn.type = "button";
    clearStickersBtn.onclick = () => {
      stickers = [];
      selectedStickerId = null;
      syncStickerInspector();
      renderPreview();
    };

    const retakeAllBtn = H.el("button", "pb-btn", "Retake All 6");
    retakeAllBtn.type = "button";
    retakeAllBtn.onclick = () => {
      switchStage(2);
      startSessionRequest(null);
    };

    const stage4BackBtn = H.el("button", "pb-btn", "Back");
    stage4BackBtn.type = "button";
    stage4BackBtn.onclick = handleBackButton;

    mainExportRow.append(downloadBtn, shareBtn, clearStickersBtn, retakeAllBtn, stage4BackBtn);

    // Single-shot Retake Buttons (Retake #1 .. #6)
    const retakeSub = H.el("div", "pb-retake-grid");
    for (let i = 0; i < 6; i++) {
      const rBtn = H.el("button", "pb-chip", "Retake #" + (i + 1));
      rBtn.type = "button";
      rBtn.onclick = () => {
        switchStage(2);
        startSessionRequest(i);
      };
      retakeSub.append(rBtn);
    }

    exportPanel.append(mainExportRow, retakeSub);
    editorCol.append(paperPanel, stickerPanel, stickerToolsWrapEl, exportPanel);
    stage4El.append(previewCol, editorCol);

    bindCanvasPointerEvents();

    rootEl.append(topbar, stage1El, stage2El, stage4El);
    container.append(rootEl);
  }

  // ==========================================================================
  // 3K. MODULE CONTRACT: open() AND init()
  // ==========================================================================
  async function open() {
    stopHardware();
    const o = H.overlay("Photo Booth", () => {
      if (activeSessionId) SocketClient.emit("photo:cancel", { reason: "left" });
      stopHardware();
    });
    buildBoothDOM(o.box);
    switchStage(1);
  }

  function init() {
    if (inited) return;
    inited = true;

    window.addEventListener("pagehide", stopHardware);
    window.addEventListener("beforeunload", stopHardware);

    SocketClient.on("rtc:servers", (d) => {
      ice = d;
    });

    SocketClient.on("rtc:ready", (d) => {
      role = d && d.role === "white" ? "black" : "white";
      if (!stream) return;
      if (role === "white") {
        createAndSendOffer();
      } else if (!replied) {
        replied = true;
        SocketClient.emit("rtc:ready");
      }
    });

    // Strict promise chain + pending ICE candidate queue so ICE never drops before offer is applied
    SocketClient.on("rtc:signal", (m) => {
      signalChain = signalChain.then(() => handleSignal(m)).catch(() => {});
    });

    async function handleSignal(msg) {
      if (!stream || !msg) return;
      const { kind, data } = msg;
      const p = makePc();
      try {
        if (kind === "offer") {
          await p.setRemoteDescription(data);
          await flushPendingCandidates(p);
          const ans = await p.createAnswer();
          await p.setLocalDescription(ans);
          SocketClient.emit("rtc:signal", { kind: "answer", data: p.localDescription });
        } else if (kind === "answer") {
          await p.setRemoteDescription(data);
          await flushPendingCandidates(p);
        } else if (kind === "ice" && data) {
          if (p.remoteDescription && p.remoteDescription.type) {
            await p.addIceCandidate(data);
          } else {
            pendingCandidates.push(data);
          }
        }
      } catch (_) {}
    }

    SocketClient.on("photo:go", () => {
      if (stream) startSessionRequest(null);
    });

    SocketClient.on("photo:start", (d) => {
      if (stream) onSessionStart(d || {});
    });

    SocketClient.on("photo:shot", (d) => {
      if (stream) onSessionShot(d || {});
    });

    SocketClient.on("photo:cancel", (d) => {
      onSessionCancel(d || {});
    });

    SocketClient.on("photo:share", (d) => {
      if (!d || typeof d !== "object") return;
      if (PAPER_LIST.some((p) => p.id === d.paper)) {
        selectedPaper = d.paper;
        if (rootEl) {
          rootEl.querySelectorAll("[data-paper-id]").forEach((b) => {
            if (b.getAttribute("data-paper-id") === selectedPaper) b.classList.add("is-active");
            else b.classList.remove("is-active");
          });
        }
      }
      if (Array.isArray(d.stickers)) {
        stickers = d.stickers
          .filter((s) => s && STICKER_DEFS.some((def) => def.id === s.type))
          .map((s) => ({
            id: "st_" + (++stickerSeq),
            type: s.type,
            x: Number(s.x) || 600,
            y: Number(s.y) || 900,
            scale: Number(s.scale) || 1,
            rot: Number(s.rot) || 0,
            flip: Boolean(s.flip)
          }));
        selectedStickerId = null;
        syncStickerInspector();
      }
      if (stage === 4) renderPreview();
      if (H && H.toast) H.toast("Partner shared their decorated photo strip!");
    });
  }

  return { init, open };
})();
'''