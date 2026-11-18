"""car_race.py - 3D Beach Buggy & Smash Karts Edition.
Preserves full compatibility with Hang framework, SocketClient, and server-authoritative lap/ring checks.
"""
import math, time
from core import partner_of

NAME = "Car Race"
SLUG = "car"

# Huge 3.5x Serpentine Circuit Constants (Shared with JS Client)
CX, CY = 1800.0, 1200.0
RX, RY = 1250.0, 800.0
TRACK_HALF_WIDTH = 175.0
LAP_OPTIONS = (3, 5, 8, 10)   # allowed lap counts (must match the JS)
TRACKS = (1.0, 1.8, 2.6)      # circuit length multipliers: Sprint Cove, Grand Circuit, Volcano Marathon (must match the JS)
MAX_SPEED = 780.0  # Accommodates Nitro, Hyper Warp, and Boost Pads without rubber-banding
START_X, START_Y = 3300.0, 1200.0  # theta = 0 centerline (track_center(0).x = 3300; the old 3075 was off the road)
FX_TYPES = {"tnt", "missile", "triple"}

races = {}   # room code -> {"go": timestamp, "p": {pid: {...}}}


def track_center(ang, k=1.0):
    """Centerline (x, y) at angle `ang` for the serpentine circuit scaled by k."""
    wave = 1.0 + 0.14 * math.cos(2.0 * ang) - 0.10 * math.sin(3.0 * ang) + 0.06 * math.cos(5.0 * ang)
    return (CX + math.cos(ang) * RX * wave) * k, (CY + math.sin(ang) * RY * wave) * k


def track_angle(x, y, k=1.0):
    return math.atan2((y - CY * k) / (RY * k), (x - CX * k) / (RX * k))


def in_ring(x, y, k=1.0):
    """Server-authoritative boundary check with a generous off-road shoulder."""
    tx, ty = track_center(track_angle(x, y, k), k)
    return math.hypot(x - tx, y - ty) <= (TRACK_HALF_WIDTH + 145.0)


def setup(sio, auth, rooms):
    @sio.on("race:start")
    @auth
    async def start(sid, sess, data):
        code = rooms.by_player.get(sess["pid"])
        room = rooms.rooms.get(code)
        if not room or not room.locked or (code in races and time.time() < races[code]["go"] + 3):
            return
        go = time.time() + 3
        d = data if isinstance(data, dict) else {}
        tr, nl = d.get("track"), d.get("laps")
        ti = tr if isinstance(tr, int) and 0 <= tr < len(TRACKS) else 1
        laps_total = nl if isinstance(nl, int) and nl in LAP_OPTIONS else 3
        k = TRACKS[ti]
        p = {}
        for pid, pl in room.players.items():
            sx = START_X * k - 32.0 if pl["role"] == "white" else START_X * k + 32.0
            sy = START_Y * k
            ang0 = track_angle(sx, sy, k)
            p[pid] = {
                "x": float(sx),
                "y": float(sy),
                "t": go,
                "ang": ang0,
                "prog": ang0,   # laps tick exactly at the line
                "laps": 0
            }
        races[code] = {"go": go, "p": p, "k": k, "laps": laps_total}
        for pl in room.players.values():
            await sio.emit("race:go", {"role": pl["role"], "ms": 3000, "track": ti, "laps": laps_total}, to=pl["sid"])

    @sio.on("race:pos")
    @auth.fast
    async def pos(sid, sess, data):
        code = rooms.by_player.get(sess["pid"])
        r = races.get(code)
        room = rooms.rooms.get(code)
        if not r or not room or not isinstance(data, dict) or sess["pid"] not in r["p"]:
            return
        now = time.time()
        if now < r["go"]:
            return
        try:
            x, y, a = float(data["x"]), float(data["y"]), float(data["a"])
            z = float(data.get("z", 0.0))
            car_idx = int(data.get("carIdx", 0))
            char_idx = int(data.get("charIdx", 0))
        except (KeyError, TypeError, ValueError):
            return
        if not all(map(math.isfinite, (x, y, a, z))) or not in_ring(x, y, r["k"]):
            return
        s = r["p"][sess["pid"]]
        dt = min(max(now - s["t"], 0.02), 0.6)
        if math.hypot(x - s["x"], y - s["y"]) > MAX_SPEED * dt + 85.0:  # Anti-teleport check
            return await sio.emit("race:fix", {"x": s["x"], "y": s["y"]}, to=sid)
        ang = track_angle(x, y, r["k"])
        d = (ang - s["ang"] + math.pi) % (2 * math.pi) - math.pi
        s.update(x=x, y=y, t=now, ang=ang, prog=s["prog"] + d)
        laps = max(0, int(-s["prog"] / (2 * math.pi)))
        if laps != s["laps"]:
            s["laps"] = laps
            await sio.emit("race:lap", {"laps": laps}, to=sid)
        peer = partner_of(rooms, sess["pid"])
        if peer:
            await sio.emit("race:opp", {
                "x": x, "y": y, "z": z, "a": a, "g": 1 if data.get("g") else 0,
                "carIdx": car_idx, "charIdx": char_idx,
                "laps": s["laps"], "prog": s["prog"]
            }, to=peer["sid"])
        if laps >= r["laps"]:
            races.pop(code, None)
            for pl in room.players.values():
                await sio.emit("race:over", {"winner": sess["name"]}, to=pl["sid"])

    @sio.on("race:fx")
    @auth.fast
    async def fx(sid, sess, data):
        """Relays weapons (missile, triple rockets, TNT) to the partner. Only validated numbers are forwarded."""
        peer = partner_of(rooms, sess["pid"])
        if not peer or not isinstance(data, dict) or not isinstance(data.get("type"), str) or data["type"] not in FX_TYPES:
            return
        try:
            x, y, a = float(data["x"]), float(data["y"]), float(data["a"])
        except (KeyError, TypeError, ValueError):
            return
        if all(map(math.isfinite, (x, y, a))):
            await sio.emit("race:fx", {"type": data["type"], "x": x, "y": y, "a": a}, to=peer["sid"])

# ==============================================================================
# EMBEDDED CSS (Arcade Neon Beach Buggy / Smash Karts UI)
# ==============================================================================
CSS = r'''
.bb-wrap {
  position: relative;
  width: min(920px, 96vw);
  height: min(600px, 84vh);
  background: #090514;
  border: 4px solid #ff1493;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 0 35px rgba(255, 20, 147, 0.45);
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  color: #fff;
}
.bb-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.bb-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px;
}
.bb-hidden {
  display: none !important;
}
.bb-interactive {
  pointer-events: auto;
}
.bb-title {
  text-align: center;
  font-size: clamp(1.5rem, 3.2vw, 2.4rem);
  font-weight: 900;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #ffd700;
  text-shadow: 0 0 14px #ff1493, 0 4px 0 #000;
}
.bb-sub {
  text-align: center;
  font-size: 0.8rem;
  color: #00f0ff;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-top: -6px;
}
.bb-garage-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.bb-card {
  background: rgba(14, 8, 26, 0.9);
  border: 2px solid #ff1493;
  border-radius: 14px;
  padding: 10px 14px;
  width: 245px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.6);
}
.bb-card-hdr {
  font-size: 0.72rem;
  color: #ffd700;
  text-transform: uppercase;
  letter-spacing: 1px;
  text-align: center;
  margin-bottom: 4px;
  font-weight: 800;
}
.bb-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.bb-arrow {
  background: #ff1493;
  color: #fff;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-weight: 900;
  cursor: pointer;
  transition: transform 0.12s, background 0.15s;
}
.bb-arrow:hover {
  background: #ffd700;
  color: #000;
  transform: scale(1.1);
}
.bb-name {
  font-size: 1.05rem;
  font-weight: 800;
  color: #fff;
}
.bb-desc {
  font-size: 0.7rem;
  color: #00f0ff;
  text-align: center;
  margin-top: 2px;
}
.bb-stat {
  margin: 5px 0;
  font-size: 0.72rem;
}
.bb-stat-lbl {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
  color: #ddd;
  font-weight: 600;
}
.bb-bar-bg {
  height: 7px;
  background: #231733;
  border-radius: 4px;
  overflow: hidden;
}
.bb-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #ff1493, #00f0ff, #ffd700);
  transition: width 0.25s;
}
.bb-btn-main {
  background: linear-gradient(135deg, #ffd700, #ff1493);
  color: #000;
  border: 2px solid #fff;
  padding: 13px 28px;
  border-radius: 32px;
  font-size: 1.05rem;
  font-weight: 900;
  text-transform: uppercase;
  cursor: pointer;
  box-shadow: 0 0 22px rgba(255, 215, 0, 0.65);
  margin: 4px;
  transition: transform 0.15s;
}
.bb-btn-main:hover {
  transform: scale(1.06);
}
/* HUD */
.bb-hud-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.bb-metrics {
  display: flex;
  gap: 14px;
  background: rgba(14, 8, 26, 0.88);
  border: 2px solid #ffd700;
  border-radius: 12px;
  padding: 6px 14px;
  align-items: center;
}
.bb-m-box {
  text-align: center;
}
.bb-m-lbl {
  font-size: 0.65rem;
  color: #ffd700;
  text-transform: uppercase;
  font-weight: 800;
}
.bb-m-val {
  font-size: 1.2rem;
  font-weight: 900;
}
.bb-pu-slot {
  width: 78px;
  height: 78px;
  background: radial-gradient(circle, rgba(40,18,68,0.95), rgba(14,8,26,0.95));
  border: 3px solid #00f0ff;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 0 18px rgba(0, 240, 255, 0.55);
  transition: transform 0.12s;
}
.bb-pu-slot:active {
  transform: scale(0.92);
}
.bb-pu-icon {
  font-size: 1.9rem;
  line-height: 1;
}
.bb-pu-name {
  font-size: 0.62rem;
  color: #ffd700;
  font-weight: 800;
  text-transform: uppercase;
  margin-top: 3px;
  text-align: center;
}
.bb-minimap {
  background: rgba(14, 8, 26, 0.88);
  border: 2px solid #ff1493;
  border-radius: 12px;
  padding: 5px;
}
.bb-center-msg {
  position: absolute;
  top: 38%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: clamp(2.2rem, 5vw, 3.8rem);
  font-weight: 900;
  color: #ffd700;
  text-shadow: 0 0 22px #ff1493, 0 4px 0 #000;
  text-align: center;
  pointer-events: none;
}
.bb-feed {
  position: absolute;
  top: 96px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.95rem;
  font-weight: 900;
  color: #00f0ff;
  text-shadow: 0 2px 4px #000;
  pointer-events: none;
  text-align: center;
}
.bb-center{text-align:center}.bb-hint{font-size:.75rem;color:#ddd;font-weight:600}.bb-unit{font-size:.72rem;font-weight:800}.bb-h{color:#ffd700;margin:0 0 14px}.bb-res{white-space:pre-line;margin-bottom:12px;font-weight:700;line-height:1.5}
.bb-sel{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:8px;background:rgba(16,10,24,.88);border:2px solid #ff1493;border-radius:12px;padding:6px 10px}.bb-sel-v{min-width:150px;text-align:center}.bb-sel-v small{display:block;font-size:.62rem;color:#ffd700;letter-spacing:1px}.bb-sel-v b{font-size:.95rem}
.bb-hud-bot {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
.bb-speedo {
  background: rgba(14, 8, 26, 0.88);
  border: 2px solid #00f0ff;
  border-radius: 12px;
  padding: 6px 16px;
  text-align: right;
}
.bb-spd-num {
  font-size: 1.7rem;
  font-weight: 900;
  color: #ffd700;
}
.bb-touch {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 8px;
}
.bb-t-grp {
  display: flex;
  gap: 8px;
}
.bb-t-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255, 20, 147, 0.4);
  border: 2px solid #ffd700;
  color: #fff;
  font-weight: 900;
  font-size: 1.15rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.bb-t-btn:active {
  background: #ffd700;
  color: #000;
}
.bb-modal {
  position: absolute;
  inset: 0;
  background: rgba(8, 4, 16, 0.86);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.bb-modal-box {
  background: #140a24;
  border: 3px solid #ffd700;
  border-radius: 18px;
  padding: 24px;
  width: 320px;
  text-align: center;
  box-shadow: 0 0 30px rgba(255, 20, 147, 0.5);
}
'''


# ==============================================================================
# EMBEDDED JAVASCRIPT (Lag-Free 3D Engine + Smash Karts Obstacles & Tracks)
# ==============================================================================
JS = r'''"use strict";
window.Features = window.Features || {};
window.Features["Car Race"] = (() => {
  const H = Hang;

  // Shared Circuit Geometry (Matches Python Server `track_center` & `in_ring`)
  // Same serpentine layout at three lengths (k scales the whole circuit). Must match TRACKS / LAP_OPTIONS in car_race.py.
  const TRACKS = [{ name: "Sprint Cove", tag: "Short", k: 1 }, { name: "Grand Circuit", tag: "Long", k: 1.8 }, { name: "Volcano Marathon", tag: "Epic", k: 2.6 }];
  const LAP_OPTIONS = [3, 5, 8, 10];
  const TRACK_HALF_WIDTH = 175;
  let trackIdx = 1, lapIdx = 0, K = 1, CX = 0, CY = 0, RX = 0, RY = 0, START_X = 0, START_Y = 0, LAPS = 3;
  function applyTrack(i) { trackIdx = i; K = TRACKS[i].k; CX = 1800 * K; CY = 1200 * K; RX = 1250 * K; RY = 800 * K; START_X = 3300 * K; START_Y = 1200 * K; }
  applyTrack(trackIdx);
  const POWERUP_RESPAWN_TIME = 40.0;   // seconds until a power-up box comes back
  const GHOST_AFTER_HIT = 3.0;         // seconds of see-through invincibility after you get hit (includes the spin-out)

  function getTrackCenter(ang) {
    const wave = 1.0 + 0.14 * Math.cos(2.0 * ang) - 0.10 * Math.sin(3.0 * ang) + 0.06 * Math.cos(5.0 * ang);
    return {
      x: CX + Math.cos(ang) * RX * wave,
      y: CY + Math.sin(ang) * RY * wave
    };
  }

  function getTrackTangent(ang) {
    const d = 0.005;
    const p1 = getTrackCenter(ang - d);
    const p2 = getTrackCenter(ang + d);
    const dx = p2.x - p1.x, dy = p2.y - p1.y;
    const len = Math.hypot(dx, dy) || 1;
    // Counter-clockwise racing direction means decreasing `ang`
    return { tx: -dx / len, ty: -dy / len, nx: -dy / len, ny: dx / len };
  }

  // 4 Iconic Drivers
  const CHARACTERS = [
    { name: "Rez", desc: "Cyber Drift Specialist", skin: 0xffccaa, suit: 0xff1493, hat: 0xffd700, style: "visor" },
    { name: "Bella", desc: "Lagoon Speed Queen", skin: 0xe0a882, suit: 0x00f0ff, hat: 0xff66b2, style: "sunhat" },
    { name: "Tiki", desc: "Volcano Tiki Guardian", skin: 0x8b5a2b, suit: 0x32cd32, hat: 0xff4500, style: "crown" },
    { name: "Boney", desc: "Smash Kart Skeleton", skin: 0xf2f2f2, suit: 0x9b59b6, hat: 0xffd700, style: "crown" }
  ];

  // 4 Custom Karts / Buggies
  const CARS = [
    { name: "Sandstorm", color: 0xff1493, accent: 0xffd700, maxSpd: 440, acc: 460, hnd: 2.85, sSpd: 85, sAcc: 88, sHnd: 92, monster: false },
    { name: "Skull Crusher", color: 0x222230, accent: 0xff3300, maxSpd: 470, acc: 390, hnd: 2.35, sSpd: 96, sAcc: 74, sHnd: 74, monster: true },
    { name: "Wave Rider", color: 0x00f0ff, accent: 0xff1493, maxSpd: 425, acc: 520, hnd: 3.25, sSpd: 80, sAcc: 98, sHnd: 96, monster: false },
    { name: "Solar Apex", color: 0xffd700, accent: 0x111111, maxSpd: 455, acc: 480, hnd: 2.75, sSpd: 92, sAcc: 90, sHnd: 86, monster: false }
  ];

  // 6 Beach Buggy & Smash Karts Weapons
  const POWERUPS = [
    { id: "nitro", name: "Hyper Nitro", icon: "🔥", wFront: 18, wBack: 35 },
    { id: "missile", name: "Homing Missile", icon: "🚀", wFront: 12, wBack: 40 },
    { id: "triple", name: "Triple Rockets", icon: "☄️", wFront: 10, wBack: 30 },
    { id: "tnt", name: "Drop TNT Crate", icon: "🧨", wFront: 40, wBack: 8 },
    { id: "hammer", name: "Smash Hammer", icon: "🔨", wFront: 20, wBack: 28 },
    { id: "shield", name: "Energy Shield", icon: "🛡️", wFront: 32, wBack: 18 },
    { id: "warp", name: "Lightning Warp", icon: "⚡", wFront: 5, wBack: 38 }
  ];

  let inited = false;
  let threeLoaded = false;
  let raf = 0;
  let state = "HOME"; // HOME, COUNTDOWN, RACING, PAUSED, OVER
  let charIdx = 0, carIdx = 0;
  let role = "white";
  let keys = {};
  let lastSend = 0, tPrev = 0, raceTimer = 0, worldTime = 0;

  // Game Entities
  let me = null, netOpp = null, aiRacers = [];
  let powerupBoxes = [], boostPads = [], jumpRamps = [];
  let obstacles = [], pendulums = [], boulders = [], projectiles = [], explosions = [];
  let serverLaps = 0, standings = [], cdTimer = 0, closed = false, ro = null;
  const clearKeys = () => { keys = {}; };
  const disposeScene = (s) => { if (s) s.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) [].concat(o.material).forEach((m) => m.dispose()); }); };
  function syncSel() {
    const r = document.getElementById("bb-root"); if (!r) return;
    r.querySelector("#bb-t-name").textContent = `${TRACKS[trackIdx].name} · ${TRACKS[trackIdx].tag}`;
    r.querySelector("#bb-l-val").textContent = LAP_OPTIONS[lapIdx];
  }
  function rebuildScene() { disposeScene(scene); buildTrackScene(); refreshGaragePreview(); }
  const angDiff = (a, b) => { let d = (a - b) % (2 * Math.PI); if (d > Math.PI) d -= 2 * Math.PI; if (d < -Math.PI) d += 2 * Math.PI; return d; };
  let trackOutlinePts = [];

  // Cached Three.js Objects (Zero GC allocation in loop)
  let renderer, scene, camera, garageGroup, previewMesh, mmCanvas, mmCtx;
  let tmpVec1, tmpVec2;
  let sharedBoxGeo, sharedMissileGeo, sharedCrateMat, sharedTntMat, sharedShockGeo;

  // DOM Elements
  let uiHome, uiHud, uiPause, uiOver, elCenterMsg, elFeedMsg, elPuIcon, elPuName;
  let elPos, elLap, elTime, elSpd;

  // Web Audio Synth for Arcade Sound Effects
  const Sfx = {
    ctx: null,
    tone(f, type, dur, vol = 0.1, slide = null) {
      try {
        if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        if (this.ctx.state === "suspended") this.ctx.resume();
        const o = this.ctx.createOscillator(), g = this.ctx.createGain();
        o.type = type;
        o.frequency.setValueAtTime(f, this.ctx.currentTime);
        if (slide) o.frequency.exponentialRampToValueAtTime(slide, this.ctx.currentTime + dur);
        g.gain.setValueAtTime(vol, this.ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
        o.connect(g);
        g.connect(this.ctx.destination);
        o.start();
        o.stop(this.ctx.currentTime + dur);
      } catch (e) {}
    },
    pickup() { this.tone(540, "sine", 0.13, 0.12, 980); },
    boost() { this.tone(180, "sawtooth", 0.45, 0.14, 660); },
    jump() { this.tone(260, "triangle", 0.28, 0.14, 580); },
    boom() { this.tone(95, "square", 0.42, 0.2, 28); },
    smash() { this.tone(150, "sawtooth", 0.25, 0.18, 55); }
  };

  function showFeed(txt) {
    if (!elFeedMsg) return;
    elFeedMsg.textContent = txt;
    clearTimeout(elFeedMsg._t);
    elFeedMsg._t = setTimeout(() => { if (elFeedMsg) elFeedMsg.textContent = ""; }, 2200);
  }

  function loadThreeJS() {
    if (window.THREE) { threeLoaded = true; return Promise.resolve(); }
    return new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js";
      s.onload = () => { threeLoaded = true; resolve(); };
      s.onerror = () => resolve();
      document.head.appendChild(s);
    });
  }

  // ============================================================================
  // 3D PROCEDURAL MODELS (Drivers, Karts, Track, Obstacles)
  // ============================================================================
  function buildDriverMesh(cCfg) {
    const g = new THREE.Group();
    const torso = new THREE.Mesh(
      new THREE.CylinderGeometry(3.2, 4.0, 8, 8),
      new THREE.MeshLambertMaterial({ color: cCfg.suit })
    );
    torso.position.y = 4;
    g.add(torso);

    const head = new THREE.Mesh(
      new THREE.SphereGeometry(3.8, 10, 10),
      new THREE.MeshLambertMaterial({ color: cCfg.skin })
    );
    head.position.y = 10;
    g.add(head);

    const visor = new THREE.Mesh(
      new THREE.BoxGeometry(5.5, 1.8, 3.2),
      new THREE.MeshLambertMaterial({ color: 0x111111 })
    );
    visor.position.set(0, 10.2, 2.5);
    g.add(visor);

    const hatMat = new THREE.MeshLambertMaterial({ color: cCfg.hat });
    if (cCfg.style === "sunhat") {
      const brim = new THREE.Mesh(new THREE.CylinderGeometry(7, 7, 0.6, 10), hatMat);
      brim.position.y = 12.8;
      g.add(brim);
    } else if (cCfg.style === "crown") {
      const crown = new THREE.Mesh(new THREE.ConeGeometry(3.8, 5, 6), hatMat);
      crown.position.y = 14;
      g.add(crown);
    } else {
      const helm = new THREE.Mesh(new THREE.SphereGeometry(4.1, 10, 8, 0, Math.PI * 2, 0, Math.PI * 0.55), hatMat);
      helm.position.y = 10.3;
      g.add(helm);
    }
    return g;
  }

  function buildBuggyMesh(carCfg, charCfg) {
    const root = new THREE.Group();
    const bodyMat = new THREE.MeshLambertMaterial({ color: carCfg.color });
    const accMat = new THREE.MeshLambertMaterial({ color: carCfg.accent });
    const tireMat = new THREE.MeshLambertMaterial({ color: 0x181818 });

    // Kart Main Chassis & Roll Cage
    const chassis = new THREE.Mesh(new THREE.BoxGeometry(17, 5, 29), bodyMat);
    chassis.position.y = 5.5;
    root.add(chassis);

    const nose = new THREE.Mesh(new THREE.BoxGeometry(13, 3.8, 10), accMat);
    nose.position.set(0, 5.0, 15);
    root.add(nose);

    const bumper = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 16, 8), accMat);
    bumper.rotation.z = Math.PI / 2;
    bumper.position.set(0, 4.5, 20.5);
    root.add(bumper);

    // Dual Exhaust Pipes & Rear Wing
    const wing = new THREE.Mesh(new THREE.BoxGeometry(20, 1.2, 5), accMat);
    wing.position.set(0, 13, -13);
    root.add(wing);

    const pipeGeo = new THREE.CylinderGeometry(1.4, 1.8, 7, 6);
    pipeGeo.rotateX(Math.PI / 3);
    const pL = new THREE.Mesh(pipeGeo, accMat);
    pL.position.set(-5, 9, -15);
    const pR = pL.clone();
    pR.position.x = 5;
    root.add(pL, pR);

    // Nitro Flame Cones (Visible when boosting)
    const flameMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    const flameGeo = new THREE.ConeGeometry(2.4, 11, 6);
    flameGeo.rotateX(-Math.PI / 2);
    const flames = new THREE.Group();
    const f1 = new THREE.Mesh(flameGeo, flameMat);
    f1.position.set(-5, 8.5, -21);
    const f2 = f1.clone();
    f2.position.x = 5;
    flames.add(f1, f2);
    flames.visible = false;
    root.add(flames);
    root.userData.flames = flames;

    // 4 Off-Road Wheels
    const wRad = carCfg.monster ? 6.0 : 4.5;
    const wGeo = new THREE.CylinderGeometry(wRad, wRad, 4.2, 10);
    wGeo.rotateZ(Math.PI / 2);
    const wheels = [];
    [[-10.2, wRad, 10.5], [10.2, wRad, 10.5], [-10.2, wRad, -10.5], [10.2, wRad, -10.5]].forEach(([wx, wy, wz]) => {
      const w = new THREE.Mesh(wGeo, tireMat);
      w.position.set(wx, wy, wz);
      root.add(w);
      wheels.push(w);
    });
    root.userData.wheels = wheels;

    if (charCfg) {
      const drv = buildDriverMesh(charCfg);
      drv.position.set(0, 6.5, -1);
      root.add(drv);
    }

    // Energy Shield Sphere
    const sh = new THREE.Mesh(
      new THREE.SphereGeometry(21, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0x00f0ff, wireframe: true, transparent: true, opacity: 0.42 })
    );
    sh.position.y = 8;
    sh.visible = false;
    root.add(sh);
    root.userData.shield = sh;

    // Smash Hammer Attachment (Visible when Hammer power-up active)
    const hammerGroup = new THREE.Group();
    const hShaft = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 26, 6), new THREE.MeshLambertMaterial({ color: 0x8b4513 }));
    hShaft.rotation.x = Math.PI / 2;
    hShaft.position.z = 13;
    const hHead = new THREE.Mesh(new THREE.CylinderGeometry(6, 6, 16, 8), new THREE.MeshLambertMaterial({ color: 0xffd700 }));
    hHead.rotation.z = Math.PI / 2;
    hHead.position.z = 26;
    hammerGroup.add(hShaft, hHead);
    hammerGroup.position.set(0, 14, 0);
    hammerGroup.visible = false;
    root.add(hammerGroup);
    root.userData.hammer = hammerGroup;

    return root;
  }

  function buildTrackScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b162c);
    scene.fog = new THREE.FogExp2(0x0b162c, 0.00045);

    tmpVec1 = new THREE.Vector3();
    tmpVec2 = new THREE.Vector3();
    sharedBoxGeo = new THREE.BoxGeometry(16, 16, 16);
    sharedMissileGeo = new THREE.ConeGeometry(4.5, 18, 8);
    sharedMissileGeo.rotateX(Math.PI / 2);
    sharedCrateMat = new THREE.MeshLambertMaterial({ color: 0xd35400 });
    sharedTntMat = new THREE.MeshLambertMaterial({ color: 0xe74c3c });
    sharedShockGeo = new THREE.RingGeometry(4, 52, 20);
    sharedShockGeo.rotateX(-Math.PI / 2);

    // High-Performance Lighting (No expensive shadow maps)
    scene.add(new THREE.HemisphereLight(0xffd89b, 0x191654, 0.85));
    const sun = new THREE.DirectionalLight(0xfff0cc, 0.9);
    sun.position.set(CX + 600, 1200, CY - 500);
    scene.add(sun);

    // Tropical Ocean & Sandy Island Floor
    const ocean = new THREE.Mesh(
      new THREE.PlaneGeometry(9000 * K, 9000 * K),
      new THREE.MeshLambertMaterial({ color: 0x006994 })
    );
    ocean.rotation.x = -Math.PI / 2;
    ocean.position.set(CX, -4, CY);
    scene.add(ocean);

    const island = new THREE.Mesh(
      new THREE.PlaneGeometry(5400 * K, 4200 * K),
      new THREE.MeshLambertMaterial({ color: 0x2c1b3d })
    );
    island.rotation.x = -Math.PI / 2;
    island.position.set(CX, -0.6, CY);
    scene.add(island);

    // Central Volcano Landmark with Lava Glow
    const volcano = new THREE.Mesh(
      new THREE.ConeGeometry(420, 380, 16, 1, true),
      new THREE.MeshLambertMaterial({ color: 0x3b232e })
    );
    volcano.position.set(CX, 185, CY);
    scene.add(volcano);

    const lavaCrater = new THREE.Mesh(
      new THREE.CircleGeometry(140, 16),
      new THREE.MeshBasicMaterial({ color: 0xff4500 })
    );
    lavaCrater.rotation.x = -Math.PI / 2;
    lavaCrater.position.set(CX, 355, CY);
    scene.add(lavaCrater);

    // Build Serpentine Road Ribbon + Red/White Arcade Rumble Curbs
    const segs = Math.round(280 * K);
    const roadPos = [], roadCol = [], roadIdx = [];
    const curbPos = [], curbCol = [], curbIdx = [];
    trackOutlinePts = [];

    for (let i = 0; i <= segs; i++) {
      const ang = (i / segs) * Math.PI * 2;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      trackOutlinePts.push(c);

      const ix = c.x - t.nx * TRACK_HALF_WIDTH;
      const iz = c.y - t.ny * TRACK_HALF_WIDTH;
      const ox = c.x + t.nx * TRACK_HALF_WIDTH;
      const oz = c.y + t.ny * TRACK_HALF_WIDTH;

      roadPos.push(ix, 0.3, iz, ox, 0.3, oz);
      // Varied biome asphalt tinting along the track
      const stripe = (Math.floor(i / 2) % 2 === 0);
      const rCol = stripe ? new THREE.Color(0x3a2d4c) : new THREE.Color(0x302440);
      roadCol.push(rCol.r, rCol.g, rCol.b, rCol.r, rCol.g, rCol.b);

      // Outer & Inner Red/White Curbs
      const cWidth = 18;
      const cix = ix - t.nx * cWidth, ciz = iz - t.ny * cWidth;
      const cox = ox + t.nx * cWidth, coz = oz + t.ny * cWidth;
      curbPos.push(cix, 0.8, ciz, ix, 0.8, iz, ox, 0.8, oz, cox, 0.8, coz);
      const isRed = (i % 2 === 0);
      const kCol = isRed ? new THREE.Color(0xff1493) : new THREE.Color(0xffd700);
      for (let k = 0; k < 4; k++) curbCol.push(kCol.r, kCol.g, kCol.b);

      if (i < segs) {
        const b = i * 2;
        roadIdx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2);
        const cb = i * 4;
        curbIdx.push(
          cb, cb + 1, cb + 4, cb + 1, cb + 5, cb + 4,
          cb + 2, cb + 3, cb + 6, cb + 3, cb + 7, cb + 6
        );
      }
    }

    const rGeo = new THREE.BufferGeometry();
    rGeo.setAttribute("position", new THREE.Float32BufferAttribute(roadPos, 3));
    rGeo.setAttribute("color", new THREE.Float32BufferAttribute(roadCol, 3));
    rGeo.setIndex(roadIdx);
    rGeo.computeVertexNormals();
    scene.add(new THREE.Mesh(rGeo, new THREE.MeshLambertMaterial({ vertexColors: true })));

    const cGeo = new THREE.BufferGeometry();
    cGeo.setAttribute("position", new THREE.Float32BufferAttribute(curbPos, 3));
    cGeo.setAttribute("color", new THREE.Float32BufferAttribute(curbCol, 3));
    cGeo.setIndex(curbIdx);
    cGeo.computeVertexNormals();
    scene.add(new THREE.Mesh(cGeo, new THREE.MeshBasicMaterial({ vertexColors: true })));

    // Start / Finish Checkered Line & Grand Arch at ang = 0 (START_X, START_Y)
    const sLine = new THREE.Mesh(
      new THREE.PlaneGeometry(TRACK_HALF_WIDTH * 2, 24),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    sLine.rotation.x = -Math.PI / 2;
    sLine.position.set(START_X, 0.6, START_Y);
    scene.add(sLine);

    const pillarMat = new THREE.MeshLambertMaterial({ color: 0xff1493 });
    const pL = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 95, 8), pillarMat);
    pL.position.set(START_X - TRACK_HALF_WIDTH, 47, START_Y);
    const pR = pL.clone();
    pR.position.set(START_X + TRACK_HALF_WIDTH, 47, START_Y);
    const banner = new THREE.Mesh(
      new THREE.BoxGeometry(TRACK_HALF_WIDTH * 2 + 24, 20, 10),
      new THREE.MeshLambertMaterial({ color: 0xffd700 })
    );
    banner.position.set(START_X, 92, START_Y);
    scene.add(pL, pR, banner);

    // Tropical Palm Trees & Tiki Pillars along the Circuit
    const trunkMat = new THREE.MeshLambertMaterial({ color: 0x784820 });
    const leafMat = new THREE.MeshLambertMaterial({ color: 0x2ecc71 });
    const trunkGeo = new THREE.CylinderGeometry(3, 5, 52, 6);
    const leafGeo = new THREE.ConeGeometry(26, 18, 6);
    const n64 = Math.round(64 * K);
    for (let i = 0; i < n64; i++) {
      const ang = (i / n64) * Math.PI * 2;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const side = (i % 2 === 0) ? 1 : -1;
      const dist = TRACK_HALF_WIDTH + 65 + (i % 3) * 35;
      const tx = c.x + t.nx * side * dist;
      const tz = c.y + t.ny * side * dist;

      const tree = new THREE.Group();
      tree.position.set(tx, 0, tz);
      const tr = new THREE.Mesh(trunkGeo, trunkMat);
      tr.position.y = 26;
      const lf = new THREE.Mesh(leafGeo, leafMat);
      lf.position.y = 54;
      tree.add(tr, lf);
      scene.add(tree);
    }

    // 1. Spawn Mystery Power-Up Item Boxes (10 clusters x 3 boxes = 30 boxes)
    powerupBoxes = [];
    const itemBoxMat = new THREE.MeshLambertMaterial({ color: 0xff1493, emissive: 0x550033 });
    const nBox = Math.round(10 * K);
    for (let i = 0; i < nBox; i++) {
      const ang = ((i + 0.5) / nBox) * Math.PI * 2;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      [-85, 0, 85].forEach(offset => {
        const bx = c.x + t.nx * offset;
        const bz = c.y + t.ny * offset;
        const m = new THREE.Mesh(sharedBoxGeo, itemBoxMat);
        m.position.set(bx, 12, bz);
        scene.add(m);
        powerupBoxes.push({ mesh: m, x: bx, y: bz, active: true, timer: 0 });
      });
    }

    // 2. Spawn Glowing Cyan Chevron Boost Pads (10 Pads)
    boostPads = [];
    const padGeo = new THREE.PlaneGeometry(42, 64);
    padGeo.rotateX(-Math.PI / 2);
    const padMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    const nPad = Math.round(10 * K);
    for (let i = 0; i < nPad; i++) {
      const ang = (i / nPad) * Math.PI * 2 + 0.18;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const offset = (i % 2 === 0 ? 55 : -55);
      const px = c.x + t.nx * offset;
      const pz = c.y + t.ny * offset;
      const pad = new THREE.Mesh(padGeo, padMat);
      pad.position.set(px, 0.8, pz);
      const heading = Math.atan2(t.ty, t.tx);
      pad.rotation.y = Math.PI / 2 - heading;
      scene.add(pad);
      boostPads.push({ x: px, y: pz, radius: 34 });
    }

    // 3. Spawn Jump Ramps (6 Ramps around the track)
    jumpRamps = [];
    const rampGeo = new THREE.BoxGeometry(50, 14, 46);
    const rampMat = new THREE.MeshLambertMaterial({ color: 0xff9900 });
    const nRamp = Math.round(6 * K);
    for (let i = 0; i < nRamp; i++) {
      const ang = (i / nRamp) * Math.PI * 2 + 0.35;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const heading = Math.atan2(t.ty, t.tx);
      const ramp = new THREE.Mesh(rampGeo, rampMat);
      ramp.position.set(c.x, 3, c.y);
      ramp.rotation.y = Math.PI / 2 - heading;
      ramp.rotation.x = -0.22;
      scene.add(ramp);
      jumpRamps.push({ x: c.x, y: c.y, radius: 34 });
    }

    // 4. Spawn Destructible Crates & Explosive TNT Barrels (24 Obstacles)
    obstacles = [];
    const crateGeo = new THREE.BoxGeometry(18, 18, 18);
    const barrelGeo = new THREE.CylinderGeometry(10, 10, 22, 10);
    const nObs = Math.round(24 * K);
    for (let i = 0; i < nObs; i++) {
      const ang = (i / nObs) * Math.PI * 2 + 0.11;
      if (Math.abs(ang) < 0.2 || Math.abs(ang - Math.PI * 2) < 0.2) continue; // Keep start clear
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const offset = ((i * 73) % 220) - 110;
      const ox = c.x + t.nx * offset;
      const oz = c.y + t.ny * offset;
      const isTnt = (i % 3 === 0);
      const m = new THREE.Mesh(isTnt ? barrelGeo : crateGeo, isTnt ? sharedTntMat : sharedCrateMat);
      m.position.set(ox, isTnt ? 11 : 9, oz);
      scene.add(m);
      obstacles.push({
        type: isTnt ? "tnt" : "crate",
        mesh: m, x: ox, y: oz, radius: 18,
        active: true, timer: 0
      });
    }

    // 5. Spawn Giant Swinging Pendulum Hammers (4 Smash Gates)
    pendulums = [];
    const archMat = new THREE.MeshLambertMaterial({ color: 0x8e44ad });
    const hammerMat = new THREE.MeshLambertMaterial({ color: 0xffd700 });
    const nPend = Math.round(4 * K);
    for (let i = 0; i < nPend; i++) {
      const ang = (i / nPend) * Math.PI * 2 + 0.78;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const heading = Math.atan2(t.ty, t.tx);

      const gate = new THREE.Group();
      gate.position.set(c.x, 0, c.y);
      gate.rotation.y = Math.PI / 2 - heading;

      const postL = new THREE.Mesh(new THREE.CylinderGeometry(6, 6, 110, 8), archMat);
      postL.position.set(-TRACK_HALF_WIDTH + 10, 55, 0);
      const postR = postL.clone();
      postR.position.x = TRACK_HALF_WIDTH - 10;
      const topBeam = new THREE.Mesh(new THREE.BoxGeometry(TRACK_HALF_WIDTH * 2, 10, 10), archMat);
      topBeam.position.set(0, 110, 0);
      gate.add(postL, postR, topBeam);

      const pivot = new THREE.Group();
      pivot.position.set(0, 108, 0);
      const rod = new THREE.Mesh(new THREE.CylinderGeometry(2.5, 2.5, 92, 6), archMat);
      rod.position.y = -46;
      const bob = new THREE.Mesh(new THREE.CylinderGeometry(16, 16, 36, 10), hammerMat);
      bob.position.y = -92;
      pivot.add(rod, bob);
      gate.add(pivot);
      scene.add(gate);

      pendulums.push({
        cx: c.x, cy: c.y, nx: t.nx, ny: t.ny,
        pivot, phase: i * 1.5, hx: c.x, hy: c.y
      });
    }

    // 6. Spawn Rolling Canyon Boulders (4 Boulders rolling across the road)
    boulders = [];
    const boulderGeo = new THREE.DodecahedronGeometry(22, 1);
    const boulderMat = new THREE.MeshLambertMaterial({ color: 0x7f8c8d });
    const nBoul = Math.round(4 * K);
    for (let i = 0; i < nBoul; i++) {
      const ang = (i / nBoul) * Math.PI * 2 + 1.15;
      const c = getTrackCenter(ang);
      const t = getTrackTangent(ang);
      const m = new THREE.Mesh(boulderGeo, boulderMat);
      m.position.set(c.x, 22, c.y);
      scene.add(m);
      boulders.push({
        cx: c.x, cy: c.y, nx: t.nx, ny: t.ny,
        mesh: m, phase: i * 2.1, x: c.x, y: c.y
      });
    }

    // High-Altitude Garage Showcase Platform
    garageGroup = new THREE.Group();
    garageGroup.position.set(CX, 900, CY);
    scene.add(garageGroup);
    const ped = new THREE.Mesh(
      new THREE.CylinderGeometry(28, 32, 4, 24),
      new THREE.MeshLambertMaterial({ color: 0x221138 })
    );
    garageGroup.add(ped);
    const gLight = new THREE.PointLight(0xffffff, 1.4, 200);
    gLight.position.set(0, 50, 40);
    garageGroup.add(gLight);
  }

  function refreshGaragePreview() {
    if (!garageGroup) return;
    if (previewMesh) garageGroup.remove(previewMesh);
    previewMesh = buildBuggyMesh(CARS[carIdx], CHARACTERS[charIdx]);
    previewMesh.position.y = 2.0;
    garageGroup.add(previewMesh);

    const root = document.getElementById("bb-root");
    if (!root) return;
    root.querySelector("#bb-c-name").textContent = CHARACTERS[charIdx].name;
    root.querySelector("#bb-c-desc").textContent = CHARACTERS[charIdx].desc;
    root.querySelector("#bb-v-name").textContent = CARS[carIdx].name;
    root.querySelector("#bb-b-spd").style.width = CARS[carIdx].sSpd + "%";
    root.querySelector("#bb-b-acc").style.width = CARS[carIdx].sAcc + "%";
    root.querySelector("#bb-b-hnd").style.width = CARS[carIdx].sHnd + "%";
  }

  // ============================================================================
  // RACER INITIALIZATION, SMASH KARTS WEAPONS & EXPLOSIONS
  // ============================================================================
  function spawnExplosion(x, y, colorHex = 0xff4500) {
    const m = new THREE.Mesh(
      sharedShockGeo,
      new THREE.MeshBasicMaterial({ color: colorHex, side: THREE.DoubleSide, transparent: true, opacity: 0.9 })
    );
    m.position.set(x, 4, y);
    scene.add(m);
    explosions.push({ mesh: m, life: 0.45, maxLife: 0.45 });
  }

  function createRacerObj(x, y, cIdx, chIdx, isMe, name) {
    const cfg = CARS[cIdx % CARS.length];
    const ch = CHARACTERS[chIdx % CHARACTERS.length];
    const mesh = buildBuggyMesh(cfg, ch);
    scene.add(mesh);
    // materials of the car + driver (not shield/flames/hammer) that fade during ghost mode
    const skip = new Set(), ghostMats = [];
    [mesh.userData.shield, mesh.userData.flames, mesh.userData.hammer].forEach((g) => g && g.traverse((o) => skip.add(o)));
    mesh.traverse((o) => { if (o.material && !skip.has(o) && !ghostMats.includes(o.material)) { o.material.transparent = true; ghostMats.push(o.material); } });
    return {
      x, y, z: 0, vz: 0,
      a: -Math.PI / 2, v: 0,
      tx: x, ty: y, ta: -Math.PI / 2, // Network interpolation targets
      carIdx: cIdx, charIdx: chIdx, cfg, name, isMe,
      mesh,
      ang: Math.atan2((y - CY) / RY, (x - CX) / RX),
      prog: Math.atan2((y - CY) / RY, (x - CX) / RX), laps: 0, rank: 1,
      pu: null, boostT: 0, shieldT: 0, spinT: 0, hammerT: 0, ghostT: 0, ghostMats: ghostMats,
      aiLaneOffset: (Math.random() - 0.5) * 160
    };
  }

  function clearRacers() {
    if (me && me.mesh) scene.remove(me.mesh);
    if (netOpp && netOpp.mesh) scene.remove(netOpp.mesh);
    aiRacers.forEach(b => scene.remove(b.mesh));
    projectiles.forEach(p => scene.remove(p.mesh));
    explosions.forEach(ex => scene.remove(ex.mesh));
    aiRacers = []; projectiles = []; explosions = []; netOpp = null;
  }

  function spawnRaceEntities(startRole) {
    clearRacers();
    role = startRole || "white";
    const startX = role === "white" ? START_X - 32 : START_X + 32;
    me = createRacerObj(startX, START_Y, carIdx, charIdx, true, CHARACTERS[charIdx].name + " (You)");
    serverLaps = 0;

    // Spawn 5 Aggressive Smash Karts AI Bots
    for (let i = 1; i <= 5; i++) {
      const bCar = (carIdx + i) % CARS.length;
      const bChar = (charIdx + i) % CHARACTERS.length;
      const laneX = START_X + ((i % 3) - 1) * 55;
      const rowY = START_Y + Math.floor((i + 1) / 2) * 45;
      const bot = createRacerObj(laneX, rowY, bCar, bChar, false, CHARACTERS[bChar].name + " [Bot]");
      bot.aiLaneOffset = ((i % 3) - 1) * 65;
      aiRacers.push(bot);
    }

    powerupBoxes.forEach(b => { b.active = true; b.timer = 0; b.mesh.visible = true; });
    obstacles.forEach(o => { o.active = true; o.timer = 0; o.mesh.visible = true; });
    updatePuSlot();
  }

  function pickWeightedPowerup(rank, total) {
    const ratio = (rank - 1) / Math.max(1, total - 1);
    const weights = POWERUPS.map(p => p.wFront * (1 - ratio) + p.wBack * ratio);
    let sum = weights.reduce((a, b) => a + b, 0), r = Math.random() * sum;
    for (let i = 0; i < POWERUPS.length; i++) {
      r -= weights[i];
      if (r <= 0) return POWERUPS[i];
    }
    return POWERUPS[0];
  }

  function updatePuSlot() {
    if (!elPuIcon || !elPuName) return;
    if (me && me.pu) {
      elPuIcon.textContent = me.pu.icon;
      elPuName.textContent = me.pu.name;
    } else {
      elPuIcon.textContent = "—";
      elPuName.textContent = "Ready";
    }
  }

  function updateGhostVisual(r) {
    const on = r.ghostT > 0;
    if (!on && !r._gh) return;
    const op = on ? 0.2 + 0.25 * (0.5 + 0.5 * Math.sin(worldTime * 24)) : 1;   // flickering see-through car
    for (let i = 0; i < r.ghostMats.length; i++) r.ghostMats[i].opacity = op;
    r._gh = on;
  }

  function hitRacer(target, attackerName, weaponName) {
    if (target.ghostT > 0) return;   // ghost mode: nothing can hit you
    if (target.shieldT > 0) {
      target.shieldT = 0;
      if (target.isMe) showFeed("🛡️ Shield Blocked Attack!");
      return;
    }
    target.spinT = 1.05;
    target.ghostT = GHOST_AFTER_HIT;
    target.v *= 0.25;
    target.vz = 145; // Launch into the air on impact!
    spawnExplosion(target.x, target.y, 0xff1493);
    if (target.isMe || (attackerName && attackerName.includes("(You)"))) {
      Sfx.boom();
      showFeed(`💥 ${attackerName || "Hazard"} hit ${target.name} with ${weaponName}!`);
    }
  }

  function activatePowerup(racer) {
    if (!racer || !racer.pu || state !== "RACING") return;
    const pu = racer.pu;
    racer.pu = null;
    if (racer.isMe) updatePuSlot();

    if (pu.id === "nitro") {
      racer.boostT = 3.2;
      if (racer.isMe) { Sfx.boost(); showFeed("🔥 Hyper Nitro Activated!"); }
    } else if (pu.id === "warp") {
      racer.boostT = 5.0;
      racer.shieldT = 5.0;
      if (racer.isMe) { Sfx.boost(); showFeed("⚡ Lightning Warp Engaged!"); }
    } else if (pu.id === "shield") {
      racer.shieldT = 7.0;
      if (racer.isMe) { Sfx.pickup(); showFeed("🛡️ Energy Shield Online!"); }
    } else if (pu.id === "hammer") {
      racer.hammerT = 5.5;
      racer.boostT = Math.max(racer.boostT, 2.5);
      if (racer.isMe) { Sfx.smash(); showFeed("🔨 Smash Hammer Equipped! Ram Opponents!"); }
    } else if (pu.id === "tnt") {
      const tx = racer.x - Math.cos(racer.a) * 32;
      const ty = racer.y - Math.sin(racer.a) * 32;
      spawnHazard("tnt", tx, ty, racer.a, racer);
      if (racer.isMe) {
        Sfx.pickup();
        if (window.SocketClient) SocketClient.emit("race:fx", { type: "tnt", x: tx, y: ty, a: racer.a });
      }
    } else if (pu.id === "missile") {
      if (racer.isMe) Sfx.boost();
      spawnHazard("missile", racer.x, racer.y, racer.a, racer);
      if (racer.isMe && window.SocketClient) {
        SocketClient.emit("race:fx", { type: "missile", x: racer.x, y: racer.y, a: racer.a });
      }
    } else if (pu.id === "triple") {
      if (racer.isMe) Sfx.boost();
      [-0.18, 0, 0.18].forEach(spread => {
        spawnHazard("missile", racer.x, racer.y, racer.a + spread, racer);
      });
      if (racer.isMe && window.SocketClient) {
        SocketClient.emit("race:fx", { type: "triple", x: racer.x, y: racer.y, a: racer.a });
      }
    }
  }

  function spawnHazard(type, x, y, a, owner) {
    if (type === "triple") {
      [-0.18, 0, 0.18].forEach(s => spawnHazard("missile", x, y, a + s, owner));
      return;
    }
    if (type === "tnt") {
      const m = new THREE.Mesh(sharedBoxGeo, sharedTntMat);
      m.position.set(x, 8, y);
      scene.add(m);
      projectiles.push({ type: "tnt", x, y, a, mesh: m, owner, life: 22 });
    } else if (type === "missile") {
      const m = new THREE.Mesh(
        sharedMissileGeo,
        new THREE.MeshBasicMaterial({ color: 0xff1493 })
      );
      m.position.set(x, 8, y);
      scene.add(m);
      projectiles.push({ type: "missile", x, y, a, speed: 680, mesh: m, owner, life: 4.5 });
    }
  }

  // ============================================================================
  // PHYSICS, JUMP RAMPS, OBSTACLES & AI LOOP
  // ============================================================================
  function stepRacerPhysics(r, ctrl, dt, allRacers) {
    if (r.boostT > 0) r.boostT -= dt;
    if (r.shieldT > 0) r.shieldT -= dt;
    if (r.hammerT > 0) r.hammerT -= dt;
    if (r.ghostT > 0) r.ghostT -= dt;
    updateGhostVisual(r);

    r.mesh.userData.shield.visible = r.shieldT > 0;
    r.mesh.userData.flames.visible = r.boostT > 0;
    r.mesh.userData.hammer.visible = r.hammerT > 0;
    if (r.hammerT > 0) {
      r.mesh.userData.hammer.rotation.y = Math.sin(worldTime * 16) * 1.1;
    }

    // Vertical Jump & Gravity Physics
    if (r.z > 0 || r.vz !== 0) {
      r.z += r.vz * dt;
      r.vz -= 460 * dt; // Gravity
      if (r.z <= 0) { r.z = 0; r.vz = 0; }
    }

    if (r.spinT > 0) {
      r.spinT -= dt;
      r.v *= 0.93;
      r.x += Math.cos(r.a) * r.v * dt;
      r.y += Math.sin(r.a) * r.v * dt;
      r.mesh.position.set(r.x, r.z, r.y);
      r.mesh.rotation.y += dt * 16;
      return;
    }

    let maxV = r.cfg.maxSpd;
    let acc = r.cfg.acc;
    if (r.boostT > 0) { maxV *= 1.38; acc *= 1.65; }

    if (ctrl.up) r.v = Math.min(r.v + acc * dt, maxV);
    else if (ctrl.dn) r.v = Math.max(r.v - 520 * dt, -140);
    else r.v *= Math.pow(0.45, dt * 2);

    const driftMult = ctrl.drift ? 1.42 : 1.0;
    const speedFactor = Math.min(1.15, Math.max(0.35, Math.abs(r.v) / 280));
    r.a += ((ctrl.r ? 1 : 0) - (ctrl.l ? 1 : 0)) * r.cfg.hnd * driftMult * dt * speedFactor * (r.v >= -1 ? 1 : -1);

    const nx = r.x + Math.cos(r.a) * r.v * dt;
    const ny = r.y + Math.sin(r.a) * r.v * dt;

    // Smooth Serpentine Boundary Check & Wall Sliding (Zero abrupt freezing!)
    const ang = Math.atan2((ny - CY) / RY, (nx - CX) / RX);
    const tc = getTrackCenter(ang);
    const dx = nx - tc.x, dy = ny - tc.y;
    const distFromCenter = Math.hypot(dx, dy);

    if (distFromCenter <= TRACK_HALF_WIDTH) {
      r.x = nx; r.y = ny;
    } else if (distFromCenter <= TRACK_HALF_WIDTH + 48) {
      // Off-road sand shoulder: slight drag, full control
      r.x = nx; r.y = ny;
      if (r.boostT <= 0) r.v *= (1 - 0.55 * dt);
    } else {
      // Smoothly slide along outer barrier wall
      const maxDist = TRACK_HALF_WIDTH + 46;
      const ux = dx / (distFromCenter || 1), uy = dy / (distFromCenter || 1);
      r.x = tc.x + ux * maxDist;
      r.y = tc.y + uy * maxDist;
      r.v *= 0.94;
    }

    // Check Boost Pads
    for (let i = 0; i < boostPads.length; i++) {
      const bp = boostPads[i];
      if (Math.hypot(r.x - bp.x, r.y - bp.y) < bp.radius && r.z < 12) {
        if (r.boostT < 1.2 && r.isMe) Sfx.boost();
        r.boostT = Math.max(r.boostT, 1.6);
      }
    }

    // Check Jump Ramps
    for (let i = 0; i < jumpRamps.length; i++) {
      const jr = jumpRamps[i];
      if (Math.hypot(r.x - jr.x, r.y - jr.y) < jr.radius && r.z < 5 && r.v > 180) {
        r.vz = 195;
        r.boostT = Math.max(r.boostT, 1.1);
        if (r.isMe) Sfx.jump();
      }
    }

    // Smash Hammer Melee Collisions
    if (r.hammerT > 0) {
      for (let i = 0; i < allRacers.length; i++) {
        const other = allRacers[i];
        if (other !== r && other.spinT <= 0 && other.ghostT <= 0 && Math.hypot(r.x - other.x, r.y - other.y) < 42) {
          hitRacer(other, r.name, "Smash Hammer");
        }
      }
    }

    // Track angular progress (CCW around CX, CY)
    const d = angDiff(ang, r.ang);
    r.ang = ang;
    r.prog += d;
    r.laps = Math.max(0, Math.floor(-r.prog / (2 * Math.PI)));

    // Sync 3D Mesh & Wheel Spin
    r.mesh.position.set(r.x, r.z, r.y);
    r.mesh.rotation.y = Math.PI / 2 - r.a;
    r.mesh.rotation.x = r.z > 0 ? -r.vz * 0.0012 : 0;
    const wheels = r.mesh.userData.wheels;
    if (wheels) {
      for (let i = 0; i < wheels.length; i++) wheels[i].rotation.x += r.v * dt * 0.08;
    }
  }

  function computeAISteer(bot) {
    // Look ahead counter-clockwise along the serpentine centerline
    const targetAng = bot.ang - 0.16;
    const tc = getTrackCenter(targetAng);
    const tang = getTrackTangent(targetAng);
    const tx = tc.x + tang.nx * bot.aiLaneOffset;
    const ty = tc.y + tang.ny * bot.aiLaneOffset;

    const desiredA = Math.atan2(ty - bot.y, tx - bot.x);
    const diff = angDiff(desiredA, bot.a);

    if (bot.pu && Math.random() < 0.03) activatePowerup(bot);
    return { up: true, dn: false, l: diff < -0.06, r: diff > 0.06, drift: Math.abs(diff) > 0.38 };
  }

  function drawMinimap(allRacers) {
    if (!mmCtx) return;
    mmCtx.clearRect(0, 0, 136, 94);
    const sx = 136 / (2 * CX), sy = 94 / (2 * CY);

    mmCtx.save();
    mmCtx.scale(sx, sy);

    // Draw Serpentine Track Ribbon
    mmCtx.strokeStyle = "#483460";
    mmCtx.lineWidth = TRACK_HALF_WIDTH * 2 + 120 * (K - 1);
    mmCtx.lineCap = "round";
    mmCtx.lineJoin = "round";
    mmCtx.beginPath();
    for (let i = 0; i < trackOutlinePts.length; i++) {
      const p = trackOutlinePts[i];
      if (i === 0) mmCtx.moveTo(p.x, p.y);
      else mmCtx.lineTo(p.x, p.y);
    }
    mmCtx.closePath();
    mmCtx.stroke();

    // Start Line
    mmCtx.fillStyle = "#ffffff";
    mmCtx.fillRect(START_X - TRACK_HALF_WIDTH, START_Y - 18, TRACK_HALF_WIDTH * 2, 36);

    // Racers
    for (let i = 0; i < allRacers.length; i++) {
      const r = allRacers[i];
      mmCtx.fillStyle = r.isMe ? "#ff1493" : (r === netOpp ? "#ffd700" : "#00f0ff");
      mmCtx.beginPath();
      mmCtx.arc(r.x, r.y, (r.isMe ? 85 : 62) * Math.sqrt(K), 0, 7);
      mmCtx.fill();
    }
    mmCtx.restore();
  }

  function loop(t) {
    const dt = Math.min((t - tPrev) / 1000 || 0.016, 0.05);
    tPrev = t;
    worldTime += dt;

    if (state === "HOME") {
      if (previewMesh) previewMesh.rotation.y += dt * 0.95;
      camera.position.set(CX, 922, CY + 62);
      camera.lookAt(CX, 908, CY);
      camera.fov = 50;
      camera.updateProjectionMatrix();
    } else if (state === "COUNTDOWN" || state === "RACING" || state === "OVER") {
      const allRacers = [me, ...aiRacers];
      if (netOpp) allRacers.push(netOpp);

      // Animate Pendulum Smash Hammers & Rolling Boulders
      for (let i = 0; i < pendulums.length; i++) {
        const pd = pendulums[i];
        const swing = Math.sin(worldTime * 2.4 + pd.phase) * 1.05;
        pd.pivot.rotation.z = swing;
        const offset = Math.sin(swing) * 92;
        pd.hx = pd.cx + pd.nx * offset;
        pd.hy = pd.cy + pd.ny * offset;
      }

      for (let i = 0; i < boulders.length; i++) {
        const bd = boulders[i];
        const slide = Math.sin(worldTime * 1.6 + bd.phase) * (TRACK_HALF_WIDTH - 25);
        bd.x = bd.cx + bd.nx * slide;
        bd.y = bd.cy + bd.ny * slide;
        bd.mesh.position.set(bd.x, 22, bd.y);
        bd.mesh.rotation.z += dt * 4;
        bd.mesh.rotation.x += dt * 2;
      }

      // Animate Explosions
      for (let i = explosions.length - 1; i >= 0; i--) {
        const ex = explosions[i];
        ex.life -= dt;
        if (ex.life <= 0) {
          scene.remove(ex.mesh);
          explosions.splice(i, 1);
        } else {
          const prog = 1 - ex.life / ex.maxLife;
          const sc = 0.3 + prog * 2.2;
          ex.mesh.scale.set(sc, sc, sc);
          ex.mesh.material.opacity = 1 - prog;
        }
      }

      if (state === "RACING") {
        raceTimer += dt;
        const myCtrl = {
          up: keys.w || keys.arrowup,
          dn: keys.s || keys.arrowdown,
          l: keys.a || keys.arrowleft,
          r: keys.d || keys.arrowright,
          drift: keys.shift
        };
        stepRacerPhysics(me, myCtrl, dt, allRacers);
        for (let i = 0; i < aiRacers.length; i++) {
          stepRacerPhysics(aiRacers[i], computeAISteer(aiRacers[i]), dt, allRacers);
        }

        // Smooth Network Opponent Interpolation
        if (netOpp) {
          if (netOpp.ghostT > 0) netOpp.ghostT -= dt;
          if (netOpp.spinT > 0) netOpp.spinT -= dt;
          updateGhostVisual(netOpp);
          netOpp.x += (netOpp.tx - netOpp.x) * Math.min(1, dt * 12);
          netOpp.y += (netOpp.ty - netOpp.y) * Math.min(1, dt * 12);
          netOpp.a += angDiff(netOpp.ta, netOpp.a) * Math.min(1, dt * 12);
          netOpp.mesh.position.set(netOpp.x, netOpp.z || 0, netOpp.y);
          netOpp.mesh.rotation.y = Math.PI / 2 - netOpp.a;
        }

        // Emit position to server
        if (t - lastSend > 50 && window.SocketClient) {
          lastSend = t;
          SocketClient.emit("race:pos", { x: me.x, y: me.y, z: me.z, a: me.a, carIdx, charIdx, g: me.ghostT > 0 ? 1 : 0 });
        }

        // Power-Up Box Pickups & Respawn
        for (let i = 0; i < powerupBoxes.length; i++) {
          const b = powerupBoxes[i];
          if (b.active) {
            b.mesh.rotation.y += dt * 2.6;
            b.mesh.rotation.x += dt * 1.4;
            for (let j = 0; j < allRacers.length; j++) {
              const r = allRacers[j];
              if (!r.pu && Math.hypot(r.x - b.x, r.y - b.y) < 30) {
                r.pu = pickWeightedPowerup(r.rank, allRacers.length);
                b.active = false;
                b.timer = POWERUP_RESPAWN_TIME;
                b.mesh.visible = false;
                if (r.isMe) { Sfx.pickup(); updatePuSlot(); }
              }
            }
          } else {
            b.timer -= dt;
            if (b.timer <= 0) { b.active = true; b.mesh.visible = true; }
          }
        }

        // Destructible Crates & Explosive TNT Barrel Collisions
        for (let i = 0; i < obstacles.length; i++) {
          const ob = obstacles[i];
          if (ob.active) {
            for (let j = 0; j < allRacers.length; j++) {
              const r = allRacers[j];
              if (r.z < 20 && !(ob.type === "tnt" && r.ghostT > 0) && Math.hypot(r.x - ob.x, r.y - ob.y) < ob.radius + 14) {
                ob.active = false;
                ob.timer = 18.0;
                ob.mesh.visible = false;
                if (ob.type === "tnt") {
                  hitRacer(r, "Track Hazard", "TNT Barrel");
                } else {
                  // Wooden Crate gives a quick mini-boost or item!
                  spawnExplosion(ob.x, ob.y, 0xffd700);
                  if (r.isMe) Sfx.smash();
                  if (!r.pu) {
                    r.pu = pickWeightedPowerup(r.rank, allRacers.length);
                    if (r.isMe) updatePuSlot();
                  }
                }
                break;
              }
            }
          } else {
            ob.timer -= dt;
            if (ob.timer <= 0) { ob.active = true; ob.mesh.visible = true; }
          }
        }

        // Pendulum & Rolling Boulder Collisions
        for (let j = 0; j < allRacers.length; j++) {
          const r = allRacers[j];
          if (r.spinT > 0 || r.ghostT > 0) continue;
          for (let i = 0; i < pendulums.length; i++) {
            const pd = pendulums[i];
            if (Math.hypot(r.x - pd.hx, r.y - pd.hy) < 30) {
              hitRacer(r, "Arena Trap", "Pendulum Hammer");
            }
          }
          for (let i = 0; i < boulders.length; i++) {
            const bd = boulders[i];
            if (r.z < 26 && Math.hypot(r.x - bd.x, r.y - bd.y) < 34) {
              hitRacer(r, "Canyon Trap", "Rolling Boulder");
            }
          }
        }

        // Update Projectiles (Homing Missiles & Dropped TNT Crates)
        for (let i = projectiles.length - 1; i >= 0; i--) {
          const p = projectiles[i];
          p.life -= dt;
          if (p.life <= 0) { scene.remove(p.mesh); projectiles.splice(i, 1); continue; }
          if (p.type === "missile") {
            // Home in on closest racer in front cone
            let bestTgt = null, bestDist = 750;
            for (let j = 0; j < allRacers.length; j++) {
              const cand = allRacers[j];
              if (cand === p.owner || cand.ghostT > 0) continue;
              const d = Math.hypot(cand.x - p.x, cand.y - p.y);
              if (d < bestDist) { bestDist = d; bestTgt = cand; }
            }
            if (bestTgt) {
              const dAng = Math.atan2(bestTgt.y - p.y, bestTgt.x - p.x);
              const diff = angDiff(dAng, p.a);
              p.a += Math.sign(diff) * Math.min(Math.abs(diff), dt * 4.2);
            }
            p.x += Math.cos(p.a) * p.speed * dt;
            p.y += Math.sin(p.a) * p.speed * dt;
            p.mesh.position.set(p.x, 8, p.y);
            p.mesh.rotation.y = Math.PI / 2 - p.a;
          } else {
            p.mesh.rotation.y += dt * 2;
          }

          for (let j = 0; j < allRacers.length; j++) {
            const r = allRacers[j];
            if (r !== p.owner && r.ghostT <= 0 && r.z < 22 && Math.hypot(r.x - p.x, r.y - p.y) < 28) {
              hitRacer(r, p.owner ? p.owner.name : "Racer", p.type === "missile" ? "Homing Missile" : "TNT Crate");
              scene.remove(p.mesh);
              projectiles.splice(i, 1);
              break;
            }
          }
        }

        // Standings & Solo Win Check
        allRacers.sort((a, b) => a.prog - b.prog);
        for (let i = 0; i < allRacers.length; i++) allRacers[i].rank = i + 1;
        standings = allRacers;
        const displayLaps = Math.max(serverLaps, me.laps);
        if (allRacers[0].laps >= LAPS || displayLaps >= LAPS) finishRace();

        // Update Cached HUD DOM Nodes
        if (elPos) {
          elPos.textContent = `${me.rank}/${allRacers.length}`;
          elLap.textContent = `${Math.min(displayLaps + 1, LAPS)}/${LAPS}`;
          elTime.textContent = raceTimer.toFixed(1) + "s";
          elSpd.textContent = Math.round(Math.abs(me.v) * 0.45);
        }
      }

      // Zero-GC Third-Person Chase Camera following `me`
      if (me) {
        const camBack = 92, camUp = 44;
        tmpVec1.set(
          me.x - Math.cos(me.a) * camBack,
          camUp + me.z * 0.65,
          me.y - Math.sin(me.a) * camBack
        );
        camera.position.lerp(tmpVec1, Math.min(1, dt * 10));
        const targetFov = me.boostT > 0 ? 78 : 62;
        if (Math.abs(camera.fov - targetFov) > 0.2) {
          camera.fov += (targetFov - camera.fov) * Math.min(1, dt * 6);
          camera.updateProjectionMatrix();
        }
        tmpVec2.set(me.x + Math.cos(me.a) * 55, 10 + me.z * 0.4, me.y + Math.sin(me.a) * 55);
        camera.lookAt(tmpVec2);
      }

      drawMinimap(allRacers);
    }

    if (renderer && scene && camera) renderer.render(scene, camera);
    raf = requestAnimationFrame(loop);
  }

  // ============================================================================
  // UI TRANSITIONS & SOCKET HANDLERS
  // ============================================================================
  function beginCountdown(startRole, ms) {
    spawnRaceEntities(startRole);
    uiHome.classList.add("bb-hidden");
    uiPause.classList.add("bb-hidden");
    uiOver.classList.add("bb-hidden");
    uiHud.classList.remove("bb-hidden");
    state = "COUNTDOWN";
    raceTimer = 0;

    let count = Math.round((ms || 3000) / 1000);
    elCenterMsg.textContent = count;
    Sfx.pickup();
    clearInterval(cdTimer);
    const iv = cdTimer = setInterval(() => {
      count--;
      if (count > 0) {
        elCenterMsg.textContent = count;
        Sfx.pickup();
      } else if (count === 0) {
        elCenterMsg.textContent = "SMASH & GO!";
        Sfx.boost();
        state = "RACING";
      } else {
        elCenterMsg.textContent = "";
        clearInterval(iv);
      }
    }, 1000);
  }

  function finishRace(winnerName) {
    if (state === "OVER") return;
    state = "OVER";
    uiOver.classList.remove("bb-hidden");
    const msg = uiOver.querySelector("#bb-over-msg"), list = uiOver.querySelector("#bb-over-list");
    const w = (standings[0] && standings[0].name) || winnerName || "Someone";
    if (msg) msg.textContent = `🏆 ${w} wins!`;
    if (list) list.textContent = standings.map((r, i) => `${i + 1}. ${r.name}`).join("\n");
  }

  const kd = (e) => {
    const k = e.key.toLowerCase();
    keys[k] = true;
    if (e.key.startsWith("Arrow") || e.code === "Space") e.preventDefault();
    if (e.code === "Space" && me) activatePowerup(me);
  };
  const ku = (e) => { keys[e.key.toLowerCase()] = false; };

  async function open() {
    const o = H.overlay("Car Race", () => {
      closed = true; clearInterval(cdTimer); cancelAnimationFrame(raf);
      removeEventListener("keydown", kd); removeEventListener("keyup", ku); removeEventListener("blur", clearKeys);
      if (ro) ro.disconnect();
      if (renderer) { renderer.dispose(); renderer.forceContextLoss(); }
      renderer = scene = me = netOpp = null; aiRacers = []; projectiles = []; explosions = []; keys = {}; state = "HOME";
    });
    closed = false;

    const wrap = H.el("div", "bb-wrap");
    wrap.id = "bb-root";
    wrap.innerHTML = `
      <canvas class="bb-canvas" id="bb-webgl"></canvas>

      <!-- 1. GARAGE HOME SCREEN -->
      <div class="bb-layer" id="bb-home">
        <div>
          <div class="bb-title">Beach Buggy Smash 3D</div>
          <div class="bb-sub">Volcano Circuit &bull; Smash Karts Weapons &bull; 3 Laps</div>
        </div>
        <div class="bb-garage-bar bb-interactive">
          <div class="bb-card">
            <div class="bb-card-hdr">Select Driver</div>
            <div class="bb-nav">
              <button class="bb-arrow" id="bb-prev-c">&#9664;</button>
              <div class="bb-name" id="bb-c-name">Rez</div>
              <button class="bb-arrow" id="bb-next-c">&#9654;</button>
            </div>
            <div class="bb-desc" id="bb-c-desc">Cyber Drift Specialist</div>
          </div>

          <div class="bb-center">
            <div class="bb-sel"><button class="bb-arrow" id="bb-prev-t">&#9664;</button><div class="bb-sel-v"><small>TRACK</small><b id="bb-t-name">Grand Circuit</b></div><button class="bb-arrow" id="bb-next-t">&#9654;</button></div>
            <div class="bb-sel"><button class="bb-arrow" id="bb-prev-l">&#9664;</button><div class="bb-sel-v"><small>LAPS</small><b id="bb-l-val">3</b></div><button class="bb-arrow" id="bb-next-l">&#9654;</button></div>
            <button class="bb-btn-main" id="bb-start-btn">Start Race</button>
          </div>

          <div class="bb-card">
            <div class="bb-card-hdr">Select Kart</div>
            <div class="bb-nav">
              <button class="bb-arrow" id="bb-prev-v">&#9664;</button>
              <div class="bb-name" id="bb-v-name">Sandstorm</div>
              <button class="bb-arrow" id="bb-next-v">&#9654;</button>
            </div>
            <div class="bb-stat"><div class="bb-stat-lbl"><span>Top Speed</span></div><div class="bb-bar-bg"><div class="bb-bar-fill" id="bb-b-spd"></div></div></div>
            <div class="bb-stat"><div class="bb-stat-lbl"><span>Acceleration</span></div><div class="bb-bar-bg"><div class="bb-bar-fill" id="bb-b-acc"></div></div></div>
            <div class="bb-stat"><div class="bb-stat-lbl"><span>Handling &amp; Drift</span></div><div class="bb-bar-bg"><div class="bb-bar-fill" id="bb-b-hnd"></div></div></div>
          </div>
        </div>
      </div>

      <!-- 2. RACE HUD -->
      <div class="bb-layer bb-hidden" id="bb-hud">
        <div class="bb-hud-top">
          <div class="bb-metrics bb-interactive">
            <div class="bb-m-box"><div class="bb-m-lbl">Pos</div><div class="bb-m-val" id="bb-h-pos">1/6</div></div>
            <div class="bb-m-box"><div class="bb-m-lbl">Lap</div><div class="bb-m-val" id="bb-h-lap">1/3</div></div>
            <div class="bb-m-box"><div class="bb-m-lbl">Time</div><div class="bb-m-val" id="bb-h-time">0.0s</div></div>
            <button class="bb-arrow" id="bb-pause-btn" title="Pause">||</button>
          </div>

          <div class="bb-pu-slot bb-interactive" id="bb-pu-btn" title="SPACE or Tap to Fire Weapon">
            <div class="bb-pu-icon" id="bb-pu-i">—</div>
            <div class="bb-pu-name" id="bb-pu-n">Ready</div>
          </div>

          <div class="bb-minimap">
            <canvas id="bb-mm" width="136" height="94"></canvas>
          </div>
        </div>

        <div class="bb-feed" id="bb-feed-msg"></div>
        <div class="bb-center-msg" id="bb-center-msg"></div>

        <div>
          <div class="bb-touch bb-interactive">
            <div class="bb-t-grp">
              <div class="bb-t-btn" data-k="arrowleft">&#9664;</div>
              <div class="bb-t-btn" data-k="arrowright">&#9654;</div>
            </div>
            <div class="bb-t-grp">
              <div class="bb-t-btn" id="bb-t-pu">🚀</div>
              <div class="bb-t-btn" data-k="arrowdown">B</div>
              <div class="bb-t-btn" data-k="arrowup">▲</div>
            </div>
          </div>
          <div class="bb-hud-bot">
            <div class="bb-hint">WASD / Arrows &bull; SPACE: Fire Weapon &bull; SHIFT: Power-Drift</div>
            <div class="bb-speedo"><span class="bb-spd-num" id="bb-h-spd">0</span> <span class="bb-unit">KM/H</span></div>
          </div>
        </div>
      </div>

      <!-- 3. PAUSE MODAL -->
      <div class="bb-modal bb-hidden bb-interactive" id="bb-pause">
        <div class="bb-modal-box">
          <h3 class="bb-h">RACE PAUSED</h3>
          <button class="bb-btn-main" id="bb-res-btn">Resume</button><br/>
          <button class="bb-btn-main" id="bb-home-btn">Garage</button>
        </div>
      </div>

      <!-- 4. FINISH MODAL -->
      <div class="bb-modal bb-hidden bb-interactive" id="bb-over">
        <div class="bb-modal-box">
          <h3 class="bb-h" id="bb-over-msg">Race Complete!</h3><div class="bb-res" id="bb-over-list"></div>
          <button class="bb-btn-main" id="bb-again-btn">Race Again</button><br/>
          <button class="bb-btn-main" id="bb-over-home-btn">Garage</button>
        </div>
      </div>
    `;
    o.box.append(wrap);

    await loadThreeJS();
    if (closed) return;
    if (!window.THREE) { o.box.replaceChildren(H.el("p", "", "Couldn't load the 3D engine. Check your connection and reopen Car Race.")); return; }

    const cv = wrap.querySelector("#bb-webgl");
    renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setSize(wrap.clientWidth, wrap.clientHeight, false);
    camera = new THREE.PerspectiveCamera(62, wrap.clientWidth / wrap.clientHeight, 2, 3400);
    ro = new ResizeObserver(() => { if (!renderer) return; renderer.setSize(wrap.clientWidth, wrap.clientHeight, false); camera.aspect = wrap.clientWidth / wrap.clientHeight; camera.updateProjectionMatrix(); });
    ro.observe(wrap);

    mmCanvas = wrap.querySelector("#bb-mm");
    mmCtx = mmCanvas.getContext("2d");

    uiHome = wrap.querySelector("#bb-home");
    uiHud = wrap.querySelector("#bb-hud");
    uiPause = wrap.querySelector("#bb-pause");
    uiOver = wrap.querySelector("#bb-over");
    elCenterMsg = wrap.querySelector("#bb-center-msg");
    elFeedMsg = wrap.querySelector("#bb-feed-msg");
    elPuIcon = wrap.querySelector("#bb-pu-i");
    elPuName = wrap.querySelector("#bb-pu-n");
    elPos = wrap.querySelector("#bb-h-pos");
    elLap = wrap.querySelector("#bb-h-lap");
    elTime = wrap.querySelector("#bb-h-time");
    elSpd = wrap.querySelector("#bb-h-spd");

    buildTrackScene();
    state = "HOME";
    refreshGaragePreview();

    // Wire Garage Controls
    const pickTrack = (d) => { applyTrack((trackIdx + d + TRACKS.length) % TRACKS.length); rebuildScene(); syncSel(); };
    const pickLaps = (d) => { lapIdx = (lapIdx + d + LAP_OPTIONS.length) % LAP_OPTIONS.length; LAPS = LAP_OPTIONS[lapIdx]; syncSel(); };
    wrap.querySelector("#bb-prev-t").onclick = () => pickTrack(-1);
    wrap.querySelector("#bb-next-t").onclick = () => pickTrack(1);
    wrap.querySelector("#bb-prev-l").onclick = () => pickLaps(-1);
    wrap.querySelector("#bb-next-l").onclick = () => pickLaps(1);
    syncSel();
    wrap.querySelector("#bb-prev-c").onclick = () => { charIdx = (charIdx + 3) % 4; refreshGaragePreview(); };
    wrap.querySelector("#bb-next-c").onclick = () => { charIdx = (charIdx + 1) % 4; refreshGaragePreview(); };
    wrap.querySelector("#bb-prev-v").onclick = () => { carIdx = (carIdx + 3) % 4; refreshGaragePreview(); };
    wrap.querySelector("#bb-next-v").onclick = () => { carIdx = (carIdx + 1) % 4; refreshGaragePreview(); };

    const triggerStart = () => {
      if (window.SocketClient) SocketClient.emit("race:start", { charIdx, carIdx, track: trackIdx, laps: LAP_OPTIONS[lapIdx] });
    };
    wrap.querySelector("#bb-start-btn").onclick = triggerStart;
    wrap.querySelector("#bb-again-btn").onclick = triggerStart;

    wrap.querySelector("#bb-pause-btn").onclick = () => { if (state === "RACING") { state = "PAUSED"; uiPause.classList.remove("bb-hidden"); } };
    wrap.querySelector("#bb-res-btn").onclick = () => { state = "RACING"; uiPause.classList.add("bb-hidden"); };
    const goHome = () => {
      state = "HOME";
      uiPause.classList.add("bb-hidden");
      uiOver.classList.add("bb-hidden");
      uiHud.classList.add("bb-hidden");
      uiHome.classList.remove("bb-hidden");
    };
    wrap.querySelector("#bb-home-btn").onclick = goHome;
    wrap.querySelector("#bb-over-home-btn").onclick = goHome;
    wrap.querySelector("#bb-pu-btn").onclick = () => { if (me) activatePowerup(me); };
    wrap.querySelector("#bb-t-pu").ontouchstart = (e) => { e.preventDefault(); if (me) activatePowerup(me); };

    wrap.querySelectorAll("[data-k]").forEach(btn => {
      const k = btn.getAttribute("data-k");
      btn.ontouchstart = (e) => { e.preventDefault(); keys[k] = true; };
      btn.ontouchend = (e) => { e.preventDefault(); keys[k] = false; };
    });

    addEventListener("keydown", kd);
    addEventListener("keyup", ku);
    addEventListener("blur", clearKeys);
    tPrev = performance.now();
    raf = requestAnimationFrame(loop);
  }

  const init = () => {
    if (inited) return;
    inited = true;

    SocketClient.on("race:go", (d) => {
      if (!renderer) return;
      if (Number.isInteger(d.track) && TRACKS[d.track] && d.track !== trackIdx) { applyTrack(d.track); rebuildScene(); }   // follow the track the starter picked
      if (LAP_OPTIONS.includes(d.laps)) { lapIdx = LAP_OPTIONS.indexOf(d.laps); LAPS = d.laps; }
      syncSel();
      beginCountdown(d.role, d.ms);
    });

    SocketClient.on("race:opp", (d) => {
      if (!scene || state !== "RACING") return;
      if (!netOpp) {
        netOpp = createRacerObj(d.x, d.y, d.carIdx || 0, d.charIdx || 1, false, "Partner");
      }
      netOpp.tx = d.x; netOpp.ty = d.y; netOpp.ta = d.a;
      netOpp.z = d.z || 0;
      if (d.g) netOpp.ghostT = Math.max(netOpp.ghostT || 0, 0.35);
      netOpp.prog = d.prog || 0;
      netOpp.laps = Math.max(0, Math.floor(-netOpp.prog / (2 * Math.PI)));
    });

    SocketClient.on("race:lap", (d) => { serverLaps = d.laps; });

    SocketClient.on("race:fix", (d) => {
      if (me) { me.x = d.x; me.y = d.y; me.v *= 0.5; }
    });

    SocketClient.on("race:fx", (d) => {
      if (scene && state === "RACING") spawnHazard(d.type, d.x, d.y, d.a, netOpp);
    });

    SocketClient.on("race:over", (d) => {
      finishRace(d.winner);
    });
  };

  return { init, open };
})();'''