"""bouquet.py - Bouquet Builder: server rules (40 flowers, 1 paper, 3 decorations) + its screen (JS/CSS) in one file."""
import secrets, uuid
from typing import Annotated, Dict, List
from pydantic import BaseModel, Field, ValidationError, field_validator
from core import partner_of

NAME = "Bouquet Builder"   # must match the dashboard card label
SLUG = "bouquet"           # becomes js/bouquet.js and css/bouquet.css

FLOWERS = {"red_rose", "sunflower", "pink_peony", "white_lily", "lavender",
           "blue_hydrangea", "tulip", "babys_breath"}
PAPERS = {"kraft_vintage", "pastel_pink_silk", "midnight_gold", "botanical_newspaper"}
DECORS = {"satin_bow", "fairy_lights", "pearl_pins", "gold_butterflies",
          "dried_eucalyptus", "lace_ribbon"}



class BouquetPayload(BaseModel):
    flowers: Dict[str, Annotated[int, Field(strict=True, ge=0, le=40)]]
    paper_id: str
    decorations: List[str] = Field(max_length=3)

    @field_validator("flowers")
    @classmethod
    def _flowers(cls, v):
        if not set(v) <= FLOWERS:
            raise ValueError("Unknown flower")
        total = sum(v.values())
        if not 1 <= total <= 40:
            raise ValueError(f"Total flowers must be 1-40 (got {total})")
        return v

    @field_validator("paper_id")
    @classmethod
    def _paper(cls, v):
        if v not in PAPERS:
            raise ValueError("Unknown paper")
        return v

    @field_validator("decorations")
    @classmethod
    def _decor(cls, v):
        if len(set(v)) != len(v) or not set(v) <= DECORS:
            raise ValueError("Invalid decorations")
        return v



BACKGROUNDS = ["Golden Hour Meadow", "Starlight Balcony", "Sakura Garden", "Cozy Rain Window"]
pending = {}  # gift_id -> {to, payload, bg, sender}


def setup(sio, auth, rooms):
    """Called once by main.py: adds this feature's socket events."""

    @sio.on("gift:send")
    @auth
    async def on_gift_send(sid, sess, data):
        peer = partner_of(rooms, sess["pid"])
        try:
            payload = BouquetPayload(**(data.get("payload") or {}))
        except (ValidationError, TypeError, AttributeError):
            return await sio.emit("gift:error", {"message": "Invalid bouquet."}, to=sid)
        if not peer or len([g for g in pending.values() if g["sender"] == sess["pid"]]) >= 3:
            return await sio.emit("gift:error", {"message": "Can't send right now."}, to=sid)
        gid = uuid.uuid4().hex
        pending[gid] = {"to": peer["sid"], "payload": payload.model_dump(), "bg": secrets.choice(BACKGROUNDS), "sender": sess["pid"]}
        await sio.emit("gift:incoming", {"gift_id": gid, "sender_name": sess["name"], "gift_type": "BOUQUET"}, to=peer["sid"])
        await sio.emit("gift:sent", {}, to=sid)

    @sio.on("gift:respond")
    @auth
    async def on_gift_respond(sid, sess, data):
        gid = data.get("gift_id") if isinstance(data, dict) else None
        g = pending.get(gid) if isinstance(gid, str) else None
        if not g or g["to"] != sid:
            return
        pending.pop(gid)
        if data.get("accepted") is True:
            await sio.emit("gift:open", {"payload": g["payload"], "bg": g["bg"]}, to=sid)


CSS = r'''
.bq-ov{position:fixed;inset:0;z-index:25;background:radial-gradient(circle at 18% 12%,#fff3f7 0%,#f9eef4 48%,#efe6f0 100%);color:var(--ink,#2b1d28);overflow-y:auto;padding:20px;display:flex;flex-direction:column;align-items:center;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.bq-wrap{width:min(1220px,100%);display:flex;flex-direction:column;gap:16px}
.bq-hdr{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;background:rgba(255,255,255,.78);backdrop-filter:blur(10px);border:1px solid rgba(214,150,178,.35);border-radius:18px;padding:12px 18px;box-shadow:0 6px 20px rgba(70,30,50,.06)}
.bq-title-grp{display:flex;align-items:baseline;gap:12px}
.bq-title-grp h2{margin:0;font-size:1.45rem;color:#3b1c2e;letter-spacing:-.02em}
.bq-badge{font-size:.85rem;font-weight:700;padding:4px 11px;border-radius:999px;background:#fce4ee;color:#b83260;border:1px solid #f4bdd4}
.bq-hdr-acts{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bq-btn{border:1px solid rgba(184,50,96,.25);border-radius:999px;background:#fff;color:#54233c;padding:7px 15px;font-size:.86rem;font-weight:600;cursor:pointer;transition:transform .15s ease,background .15s ease,box-shadow .15s ease}
.bq-btn:hover:not(:disabled){background:#fdf0f5;transform:translateY(-1px);box-shadow:0 4px 10px rgba(184,50,96,.12)}
.bq-btn:disabled{opacity:.4;cursor:not-allowed}
.bq-btn-pri{background:linear-gradient(135deg,#d94676,#b02a57);color:#fff;border-color:transparent;padding:8px 20px;font-size:.92rem;font-weight:700;box-shadow:0 6px 16px rgba(184,50,96,.28)}
.bq-btn-pri:hover:not(:disabled){background:linear-gradient(135deg,#e25583,#bf3262);box-shadow:0 8px 20px rgba(184,50,96,.36)}
.bq-main{display:grid;grid-template-columns:440px 1fr;gap:20px;align-items:start}
@media (max-width:920px){.bq-main{grid-template-columns:1fr}.bq-stage-col{position:static!important}}
.bq-stage-col{position:sticky;top:12px;display:flex;flex-direction:column;gap:10px}
.bq-stage{background:radial-gradient(circle at 50% 35%,#fff 0%,#faf0f5 65%,#f1e2ec 100%);border:1px solid rgba(214,150,178,.45);border-radius:22px;box-shadow:inset 0 2px 12px rgba(255,255,255,.8),0 12px 30px rgba(60,20,45,.08);padding:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;min-height:410px}
.bq-svg-box{width:100%;max-width:440px;aspect-ratio:1000/860;display:flex;align-items:center;justify-content:center}
.bq-svg-box svg{width:100%;height:100%;display:block;overflow:visible}
.bq-chips{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;padding:4px 8px;min-height:28px}
.bq-chip{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid #e7b9cd;color:#692647;border-radius:999px;padding:3px 10px;font-size:.78rem;font-weight:600;box-shadow:0 2px 5px rgba(0,0,0,.04)}
.bq-chip button{border:0;background:#f8dce8;color:#9e2a5b;border-radius:50%;width:16px;height:16px;font-size:.72rem;line-height:1;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0}
.bq-chip button:hover{background:#e89ab8;color:#fff}
.bq-ctrl-col{display:flex;flex-direction:column;gap:16px}
.bq-sec{background:rgba(255,255,255,.82);backdrop-filter:blur(8px);border:1px solid rgba(214,150,178,.35);border-radius:18px;padding:14px 16px;box-shadow:0 6px 18px rgba(70,30,50,.05)}
.bq-sec-hdr{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.bq-sec-hdr h3{margin:0;font-size:1rem;color:#441c33}
.bq-sec-hdr span{font-size:.8rem;color:#84546d}
.bq-grid-fl,.bq-grid-pa,.bq-grid-de{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.bq-card{background:#fff;border:1.5px solid #eee0e7;border-radius:14px;padding:10px;display:flex;flex-direction:column;align-items:center;gap:6px;transition:border-color .15s ease,box-shadow .15s ease,transform .15s ease}
.bq-card:hover{border-color:#dfb7c9}
.bq-card.on{border-color:#d64575;background:#fff9fb;box-shadow:0 4px 14px rgba(214,69,117,.13)}
.bq-thumb{width:56px;height:56px;display:flex;align-items:center;justify-content:center}
.bq-thumb svg{width:100%;height:100%;overflow:visible}
.bq-name{font-size:.84rem;font-weight:600;color:#3d1b2e;text-align:center}
.bq-stepper{display:flex;align-items:center;gap:8px;margin-top:2px}
.bq-step-btn{width:28px;height:28px;border-radius:50%;border:0;background:#f3dce6;color:#8f244e;font-weight:700;font-size:1rem;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s ease,transform .1s ease}
.bq-step-btn:hover:not(:disabled){background:#d94676;color:#fff;transform:scale(1.06)}
.bq-step-btn:disabled{opacity:.32;cursor:not-allowed}
.bq-cnt{min-width:22px;text-align:center;font-weight:700;font-size:.92rem;color:#3b1c2e}
.bq-pick-btn{width:100%;border:1px solid #e4c5d3;border-radius:999px;background:#fdf6f9;color:#6e2849;padding:5px 10px;font-size:.8rem;font-weight:600;cursor:pointer;transition:all .15s ease}
.bq-card.on .bq-pick-btn{background:#d94676;color:#fff;border-color:#d94676}
.bq-pick-btn:disabled{opacity:.35;cursor:not-allowed}
.bq-swatches{display:flex;gap:4px;margin:2px 0}
.bq-sw-dot{width:18px;height:18px;border-radius:50%;border:1px solid rgba(0,0,0,.15)}
.bq-note{min-height:22px;font-size:.9rem;font-weight:600;color:#b82b59;text-align:center;margin:0}
.bq-note.ok{color:#267847}
.bq-ftr{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding-top:4px}
.toast{position:fixed;top:16px;right:16px;z-index:40;background:#fff;color:#2b1d28;border:2px solid #d94676;border-radius:16px;padding:14px 16px;max-width:320px;box-shadow:0 14px 32px rgba(45,12,28,.18);animation:bqPop .35s cubic-bezier(.2,.9,.3,1.15) both}
.toast-acts{display:flex;gap:8px;margin-top:10px;justify-content:center}
.bq-show-ov{justify-content:center;align-items:center;padding:18px}
.bq-show-card{width:min(860px,96vw);background:rgba(255,255,255,.52);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.75);border-radius:26px;padding:16px 20px 22px;display:flex;flex-direction:column;align-items:center;gap:10px;box-shadow:0 18px 46px rgba(35,15,28,.16);z-index:2}
.bq-show-svg{width:min(760px,90vw);aspect-ratio:1000/860}
.bq-show-svg svg{width:100%;height:100%;display:block;overflow:visible}
.bq-show-cap{margin:0;font-size:1.05rem;font-weight:600;color:#3b1c2e}
.sw{animation:swLR 7.5s ease-in-out infinite alternate;transform-origin:500px 610px}
@keyframes swLR{from{transform:rotate(-2.1deg)}to{transform:rotate(2.1deg)}}
.fl{animation:flx 5.6s ease-in-out infinite alternate}
@keyframes flx{from{transform:translate(-3.5px,-1.5px) rotate(-1.5deg)}to{transform:translate(3.5px,1.5px) rotate(1.5deg)}}
.bf-wing{animation:bfFlap 2.2s ease-in-out infinite alternate;transform-origin:0 0}
@keyframes bfFlap{from{transform:scaleX(1) rotate(-3deg)}to{transform:scaleX(.58) rotate(4deg)}}
.tw{animation:twk 2.1s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:center}
@keyframes twk{from{opacity:.35;transform:scale(.88)}to{opacity:1;transform:scale(1.14)}}
.d0{animation-delay:0s}.d1{animation-delay:-1.1s}.d2{animation-delay:-2.2s}.d3{animation-delay:-3.3s}.d4{animation-delay:-4.4s}.d5{animation-delay:-5.5s}
.bq-pop{animation:bqPop .42s cubic-bezier(.22,1.28,.36,1) both}
.bq-pulse{animation:bqPulse .65s cubic-bezier(.22,1.3,.36,1) both;transform-box:fill-box;transform-origin:center}
@keyframes bqPop{0%{transform:scale(.92);opacity:.65}65%{transform:scale(1.03);opacity:1}100%{transform:scale(1);opacity:1}}
@keyframes bqPulse{0%{filter:drop-shadow(0 0 0 rgba(255,210,90,0));transform:scale(.94)}45%{filter:drop-shadow(0 0 18px rgba(255,200,60,.95));transform:scale(1.05)}100%{filter:drop-shadow(0 0 0 rgba(255,210,90,0));transform:scale(1)}}
.pt{position:fixed;top:-24px;width:11px;height:15px;border-radius:75% 0 75% 0;background:linear-gradient(135deg,#ffd1e1,#e889ab);opacity:.85;animation:ptFall linear infinite;pointer-events:none;z-index:1}
@keyframes ptFall{to{transform:translateY(110vh) rotate(520deg)}}
@media (prefers-reduced-motion:reduce){.sw,.fl,.bf-wing,.tw,.pt,.bq-pop,.bq-pulse{animation:none!important}}
'''

JS = r'''"use strict";
window.Features = window.Features || {};
window.Features["Bouquet Builder"] = (() => {
  const FL = [["red_rose", "Red Rose"], ["sunflower", "Sunflower"], ["pink_peony", "Pink Peony"], ["white_lily", "White Lily"], ["lavender", "Lavender"], ["blue_hydrangea", "Hydrangea"], ["tulip", "Tulip"], ["babys_breath", "Baby's Breath"]];
  const PA = [
    ["kraft_vintage", "Kraft Vintage", ["#c89d6c", "#a67846", "#e5c396"]],
    ["pastel_pink_silk", "Pastel Pink Silk", ["#f29bb8", "#d4658b", "#ffd4e3"]],
    ["midnight_gold", "Midnight Gold", ["#1d2449", "#101530", "#dfb453"]],
    ["botanical_newspaper", "Botanical News", ["#f2ece0", "#d8cfbe", "#5d8755"]]
  ];
  const DE = [["satin_bow", "Satin Bow"], ["fairy_lights", "Fairy Lights"], ["pearl_pins", "Pearl Pins"], ["gold_butterflies", "Gold Butterflies"], ["dried_eucalyptus", "Eucalyptus"], ["lace_ribbon", "Lace Ribbon"]];
  const BGB = {
    "Golden Hour Meadow": "linear-gradient(135deg, #fceabb 0%, #f8b500 100%)",
    "Starlight Balcony": "linear-gradient(135deg, #1b1938 0%, #3d356c 55%, #6e5b96 100%)",
    "Sakura Garden": "linear-gradient(135deg, #ffe4ed 0%, #f7bfd2 55%, #eca1bc 100%)",
    "Cozy Rain Window": "linear-gradient(135deg, #d7e4ec 0%, #a8c0cf 55%, #849fb2 100%)"
  };

  let inited = false, ov = null;
  let st = { f: { red_rose: 3, pink_peony: 2, babys_breath: 2 }, p: "kraft_vintage", d: ["satin_bow"] };
  let note = "", noteOk = false, lastAction = "", uidCounter = 0;

  const el = (t, c, txt) => { const e = document.createElement(t); if (c) e.className = c; if (txt != null) e.textContent = txt; return e; };
  const total = () => Object.values(st.f).reduce((a, b) => a + b, 0);
  function btn(label, fn, dis, cls = "bq-btn") { const b = el("button", cls, label); b.disabled = !!dis; b.onclick = fn; return b; }

  function makeRng(seedStr) {
    let s = 2166136261 >>> 0;
    for (let i = 0; i < seedStr.length; i++) { s ^= seedStr.charCodeAt(i); s = Math.imul(s, 16777619) >>> 0; }
    return () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  // Gradient helpers keep the (long) defs list compact
  const lg = (id, x1, y1, x2, y2, stops) => `<linearGradient id="${id}" x1="${x1}%" y1="${y1}%" x2="${x2}%" y2="${y2}%">${stops.map(([o, c, a]) => `<stop offset="${o}%" stop-color="${c}"${a ? ` stop-opacity="${a}"` : ""}/>`).join("")}</linearGradient>`;
  const rg = (id, cx, cy, r, stops) => `<radialGradient id="${id}" cx="${cx}%" cy="${cy}%" r="${r}%">${stops.map(([o, c, a]) => `<stop offset="${o}%" stop-color="${c}"${a ? ` stop-opacity="${a}"` : ""}/>`).join("")}</radialGradient>`;

  function sharedDefs(p) {
    return `<defs>
      <filter id="${p}_sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#1d0c16" flood-opacity="0.24"/></filter>
      <filter id="${p}_sh_sm" x="-25%" y="-25%" width="150%" height="150%"><feDropShadow dx="0" dy="2.5" stdDeviation="2.5" flood-color="#1d0c16" flood-opacity="0.22"/></filter>
      <filter id="${p}_kraft" x="0%" y="0%" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="3" seed="11" result="n"/><feColorMatrix type="matrix" values="0 0 0 0 0.55  0 0 0 0 0.38  0 0 0 0 0.22  0 0 0 0.14 0" in="n" result="t"/><feComposite in="t" in2="SourceGraphic" operator="in" result="tn"/><feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="tn"/></feMerge></filter>
      ${rg(p + "_rose_cup", 42, 38, 58, [[0, "#5e0816"], [45, "#9e1328"], [82, "#d62843"], [100, "#f0566e"]])}
      ${rg(p + "_rose_out", 35, 30, 68, [[0, "#ff7a8e"], [55, "#d41d39"], [100, "#870b1e"]])}
      ${rg(p + "_sun_disc", 38, 36, 60, [[0, "#6b4423"], [55, "#3d220e"], [85, "#261305"], [100, "#593818"]])}
      ${lg(p + "_sun_pet", 0, 0, 0, 100, [[0, "#ffe84d"], [65, "#f5a600"], [100, "#cc7000"]])}
      ${rg(p + "_peony_g", 50, 45, 56, [[0, "#b83768"], [38, "#e36d9b"], [76, "#f7adc9"], [100, "#ffe3ee"]])}
      ${lg(p + "_lily_pet", 0, 100, 0, 0, [[0, "#f4c7d8"], [35, "#fff9fb"], [100, "#ffffff"]])}
      ${lg(p + "_tulip_g", 20, 0, 80, 100, [[0, "#ff9ebb"], [45, "#ee4c7c"], [100, "#a31542"]])}
      ${rg(p + "_pearl_g", 34, 30, 65, [[0, "#ffffff"], [48, "#fdf4eb"], [82, "#dec9ba"], [100, "#b59d8e"]])}
      ${lg(p + "_gold_g", 0, 0, 100, 100, [[0, "#fff2b2"], [35, "#e8b948"], [70, "#b88418"], [100, "#f7d674"]])}
      ${lg(p + "_bow_g", 0, 0, 100, 100, [[0, "#ff8da8"], [35, "#dc3868"], [70, "#9e1943"], [100, "#f05a85"]])}
      ${rg(p + "_bulb_g", 50, 50, 50, [[0, "#ffffff"], [38, "#ffef99"], [72, "#ffbb24", 0.75], [100, "#ff8800", 0]])}
      ${lg(p + "_kraft_back", 0, 0, 100, 100, [[0, "#b58958"], [100, "#7c562e"]])}
      ${lg(p + "_kraft_L", 0, 0, 100, 85, [[0, "#e5c397"], [55, "#c99c69"], [100, "#996d3e"]])}
      ${lg(p + "_kraft_R", 100, 0, 0, 85, [[0, "#d8b282"], [55, "#b88956"], [100, "#855b30"]])}
      ${lg(p + "_silk_back", 0, 0, 100, 100, [[0, "#cf5d85"], [100, "#912d52"]])}
      ${lg(p + "_silk_L", 0, 0, 100, 85, [[0, "#ffd9e6"], [35, "#f294b4"], [70, "#d9628b"], [100, "#ad3b64"]])}
      ${lg(p + "_silk_R", 100, 0, 0, 85, [[0, "#ffc7da"], [45, "#e37aa0"], [100, "#9c3057"]])}
      ${lg(p + "_mid_back", 0, 0, 100, 100, [[0, "#192147"], [100, "#090c1f"]])}
      ${lg(p + "_mid_L", 0, 0, 100, 85, [[0, "#35427d"], [50, "#1e2752"], [100, "#0d122b"]])}
      ${lg(p + "_mid_R", 100, 0, 0, 85, [[0, "#2b376b"], [55, "#171f44"], [100, "#0a0e24"]])}
      ${lg(p + "_news_back", 0, 0, 100, 100, [[0, "#d4cab8"], [100, "#aba08c"]])}
      ${lg(p + "_news_L", 0, 0, 100, 85, [[0, "#fbf7ef"], [55, "#e7dfd0"], [100, "#c4baa6"]])}
      ${lg(p + "_news_R", 100, 0, 0, 85, [[0, "#f4eee2"], [55, "#dcd3c2"], [100, "#b5aa96"]])}
    </defs>`;
  }

  function drawFlowerHead(id, pfx) {
    if (id === "red_rose") {
      let s = `<g>`;
      for (let i = 0; i < 5; i++) s += `<path d="M0 0 L-7 -44 L0 -52 L7 -44 Z" fill="#2e6930" transform="rotate(${i * 72 + 18})"/>`;
      for (let i = 0; i < 6; i++) s += `<path d="M0 -8 C-26 -46 -42 -20 -26 12 C-14 28 14 28 26 12 C42 -20 26 -46 0 -8 Z" fill="url(#${pfx}_rose_out)" stroke="#6e0718" stroke-width="0.8" transform="rotate(${i * 60})"/>`;
      for (let i = 0; i < 5; i++) s += `<path d="M0 -5 C-20 -34 -32 -14 -18 10 C-8 20 8 20 18 10 C32 -14 20 -34 0 -5 Z" fill="url(#${pfx}_rose_cup)" stroke="#ffd0d8" stroke-width="0.6" stroke-opacity="0.45" transform="rotate(${i * 72 + 36})"/>`;
      s += `<circle r="15" fill="url(#${pfx}_rose_cup)"/><path d="M-11 -3 C-7 -14 8 -14 11 -2 C9 8 -6 11 -10 2 C-12 -5 -4 -10 3 -8 C8 -6 7 2 1 4 C-3 5 -5 1 -2 -2" fill="none" stroke="#ff99aa" stroke-width="1.6" stroke-linecap="round"/></g>`;
      return s;
    }
    if (id === "sunflower") {
      let s = `<g>`;
      for (let i = 0; i < 18; i++) s += `<path d="M0 -14 C-9 -30 -8 -44 0 -52 C8 -44 9 -30 0 -14 Z" fill="#e08e00" stroke="#b56c00" stroke-width="0.6" transform="rotate(${i * 20})"/>`;
      for (let i = 0; i < 18; i++) {
        const a = i * 20 + 10;
        s += `<path d="M0 -12 C-8 -28 -7 -41 0 -48 C7 -41 8 -28 0 -12 Z" fill="url(#${pfx}_sun_pet)" transform="rotate(${a})"/><path d="M0 -16 L0 -42" stroke="#cc7000" stroke-width="0.7" stroke-opacity="0.5" transform="rotate(${a})"/>`;
      }
      s += `<circle r="19" fill="url(#${pfx}_sun_disc)" stroke="#8a561e" stroke-width="1.2"/>`;
      for (let i = 0; i < 34; i++) {
        const a = i * 2.39996, r = Math.sqrt(i / 34) * 16.5;
        s += `<circle cx="${(Math.cos(a) * r).toFixed(1)}" cy="${(Math.sin(a) * r).toFixed(1)}" r="${i > 22 ? 1.5 : 1.1}" fill="${i % 2 ? "#d49b35" : "#241104"}"/>`;
      }
      return s + `</g>`;
    }
    if (id === "pink_peony") {
      let s = `<g>`;
      for (let i = 0; i < 9; i++) s += `<path d="M0 0 C-22 -38 -12 -46 -4 -41 C0 -47 4 -47 8 -41 C16 -46 22 -38 0 0 Z" fill="#f9c6da" stroke="#df8eb0" stroke-width="0.8" transform="rotate(${i * 40})"/>`;
      for (let i = 0; i < 8; i++) s += `<path d="M0 0 C-18 -30 -9 -37 -3 -32 C0 -37 3 -37 6 -32 C12 -37 18 -30 0 0 Z" fill="url(#${pfx}_peony_g)" stroke="#c95b88" stroke-width="0.7" transform="rotate(${i * 45 + 22})"/>`;
      for (let i = 0; i < 7; i++) s += `<path d="M0 0 C-13 -21 -6 -26 0 -22 C6 -26 13 -21 0 0 Z" fill="#df6897" stroke="#fcdb8e" stroke-width="0.4" transform="rotate(${i * 51.4 + 11})"/>`;
      s += `<circle r="7" fill="#b33062"/>`;
      for (let i = 0; i < 10; i++) { const a = (i * 36) * Math.PI / 180; s += `<circle cx="${(Math.cos(a) * 5).toFixed(1)}" cy="${(Math.sin(a) * 5).toFixed(1)}" r="1.3" fill="#ffe17d"/>`; }
      return s + `</g>`;
    }
    if (id === "white_lily") {
      let s = `<g>`;
      for (let i = 0; i < 3; i++) s += `<path d="M0 0 C-14 -16 -13 -38 0 -50 C13 -38 14 -16 0 0 Z" fill="url(#${pfx}_lily_pet)" stroke="#d9c6d0" stroke-width="0.8" transform="rotate(${i * 120 + 60})"/>`;
      for (let i = 0; i < 3; i++) {
        s += `<g transform="rotate(${i * 120})"><path d="M0 0 C-15 -16 -14 -40 0 -52 C14 -40 15 -16 0 0 Z" fill="url(#${pfx}_lily_pet)" stroke="#d9c6d0" stroke-width="0.9"/><path d="M0 -4 L0 -36" stroke="#e39bb6" stroke-width="1.3" stroke-linecap="round"/><circle cx="-4" cy="-16" r="1.1" fill="#c75b85"/><circle cx="4" cy="-20" r="1" fill="#c75b85"/><circle cx="-3" cy="-25" r="1.2" fill="#c75b85"/><circle cx="3" cy="-13" r="1.1" fill="#c75b85"/></g>`;
      }
      s += `<circle r="4" fill="#a8d173"/>`;
      for (let i = 0; i < 6; i++) {
        const a = (i * 60 + 25) * Math.PI / 180, x = Math.cos(a) * 19, y = Math.sin(a) * 19;
        s += `<path d="M0 0 Q${(x * 0.5).toFixed(1)} ${(y * 0.3).toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}" stroke="#b8d88b" stroke-width="1.4" fill="none"/><ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="3.2" ry="1.6" fill="#d96b1f" transform="rotate(${i * 60 + 25} ${x.toFixed(1)} ${y.toFixed(1)})"/>`;
      }
      return s + `</g>`;
    }
    if (id === "lavender") {
      let s = `<g><path d="M0 28 L0 -46" stroke="#537d46" stroke-width="3.2" stroke-linecap="round"/>`;
      for (let k = 0; k < 9; k++) {
        const y = 18 - k * 7, sc = 1 - k * 0.065;
        s += `<g transform="translate(0 ${y}) scale(${sc.toFixed(2)})"><ellipse cx="-6" cy="0" rx="5.5" ry="3.4" fill="#6b42b8" transform="rotate(-28 -6 0)"/><ellipse cx="6" cy="-2" rx="5.5" ry="3.4" fill="#8860d8" transform="rotate(28 6 -2)"/><ellipse cx="0" cy="-3" rx="4.2" ry="3" fill="#b191f2"/></g>`;
      }
      return s + `<ellipse cx="0" cy="-47" rx="3.5" ry="5" fill="#9c7ae8"/></g>`;
    }
    if (id === "blue_hydrangea") {
      let s = `<g>`;
      const cols = ["#5c82d6", "#789ce8", "#92b3f7", "#a594eb", "#7986df"];
      for (let i = 0; i < 16; i++) {
        const a = i * 2.39996, r = Math.sqrt(i / 16) * 29, c = cols[i % cols.length];
        s += `<g transform="translate(${(Math.cos(a) * r).toFixed(1)} ${(Math.sin(a) * r).toFixed(1)}) rotate(${(i * 37) % 90})"><ellipse cx="0" cy="-6" rx="5.2" ry="6.2" fill="${c}" stroke="#4464b0" stroke-width="0.5"/><ellipse cx="0" cy="6" rx="5.2" ry="6.2" fill="${c}" stroke="#4464b0" stroke-width="0.5"/><ellipse cx="-6" cy="0" rx="6.2" ry="5.2" fill="${c}" stroke="#4464b0" stroke-width="0.5"/><ellipse cx="6" cy="0" rx="6.2" ry="5.2" fill="${c}" stroke="#4464b0" stroke-width="0.5"/><circle r="2.2" fill="#eef4ff"/><circle r="1" fill="#526eb8"/></g>`;
      }
      return s + `</g>`;
    }
    if (id === "tulip") {
      return `<g><path d="M-16 6 C-25 -18 -14 -38 -6 -42 C-2 -28 -2 0 -16 6 Z" fill="#c92358"/><path d="M16 6 C25 -18 14 -38 6 -42 C2 -28 2 0 16 6 Z" fill="#c92358"/><path d="M-18 4 C-22 -22 -10 -38 0 -44 C10 -38 22 -22 18 4 C14 20 -14 20 -18 4 Z" fill="url(#${pfx}_tulip_g)"/><path d="M0 -44 C-9 -24 -8 6 0 16 C8 6 9 -24 0 -44 Z" fill="#ff85aa" opacity="0.65"/><path d="M-11 -34 C-5 -20 -5 2 -1 14" stroke="#ffdbe6" stroke-width="1.1" stroke-opacity="0.55" fill="none"/></g>`;
    }
    if (id === "babys_breath") {
      let s = `<g>`;
      const br = [[-18, -22], [18, -20], [-26, -4], [25, -2], [0, -30], [-10, -34], [12, -32], [-14, 8], [15, 9], [0, -10]];
      for (const [bx, by] of br) {
        s += `<path d="M0 18 Q${(bx * 0.4).toFixed(0)} ${(by * 0.3).toFixed(0)} ${bx} ${by}" stroke="#6c9460" stroke-width="1.2" fill="none"/><circle cx="${bx}" cy="${by}" r="5.2" fill="#ffffff" stroke="#dcd6e8" stroke-width="0.8"/><circle cx="${bx - 2}" cy="${by - 2}" r="2" fill="#fff"/><circle cx="${bx}" cy="${by}" r="1.4" fill="#f5e290"/>`;
      }
      return s + `</g>`;
    }
    return "";
  }

  function drawStemLeaf(id, x, y, side, rot) {
    const dir = side > 0 ? 1 : -1, pos = `translate(${x.toFixed(1)} ${y.toFixed(1)})`;
    if (id === "red_rose") return `<g transform="${pos} rotate(${rot + dir * 42}) scale(${dir} 1)"><path d="M0 0 C10 -8 24 -10 34 0 C24 10 10 8 0 0 Z" fill="#2e6b34" stroke="#1d4721" stroke-width="0.8"/><path d="M0 0 L29 0" stroke="#5fa366" stroke-width="1"/></g>`;
    if (id === "tulip" || id === "white_lily") return `<g transform="${pos} rotate(${rot + dir * 24}) scale(${dir} 1)"><path d="M0 0 C8 -26 18 -52 14 -72 C4 -48 -2 -24 0 0 Z" fill="#3b8042" stroke="#27592c" stroke-width="0.8"/></g>`;
    if (id === "sunflower") return `<g transform="${pos} rotate(${rot + dir * 46}) scale(${dir} 1)"><path d="M0 0 C12 -18 32 -14 40 0 C32 14 12 18 0 0 Z" fill="#387532" stroke="#234f1e" stroke-width="0.8"/><path d="M0 0 L34 0" stroke="#6eb365" stroke-width="1"/></g>`;
    return `<g transform="${pos} rotate(${rot + dir * 38}) scale(${dir} 1)"><path d="M0 0 C8 -10 22 -8 28 0 C22 8 8 10 0 0 Z" fill="#37753e"/></g>`;
  }

  const PAPER = {
    kraft_vintage: { stroke: "#8c6236", edge: "#a87948" },
    pastel_pink_silk: { stroke: "#f7b5cc", edge: "#ffdbe8" },
    midnight_gold: { stroke: "#dfb453", edge: "#e5bc5a" },
    botanical_newspaper: { stroke: "#678c5e", edge: "#739669" }
  };
  const PKEY = { kraft_vintage: "kraft", pastel_pink_silk: "silk", midnight_gold: "mid", botanical_newspaper: "news" };

  function drawPaperBack(pid, pfx) {
    const k = PKEY[pid] || "kraft", pp = PAPER[pid] || PAPER.kraft_vintage;
    const sw = pid === "midnight_gold" ? "3" : "1.5", flt = pid === "kraft_vintage" ? ` filter="url(#${pfx}_kraft)"` : "";
    return `<g filter="url(#${pfx}_sh)"><path d="M500 620 L130 330 L215 175 L370 190 L500 120 L630 190 L785 175 L870 330 Z" fill="url(#${pfx}_${k}_back)" stroke="${pp.stroke}" stroke-width="${sw}"${flt}/><path d="M500 620 L175 260 L310 155 L500 210 L690 155 L825 260 Z" fill="#ffffff" fill-opacity="0.16" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1.2"/><ellipse cx="500" cy="405" rx="260" ry="125" fill="#170912" fill-opacity="0.32"/></g>`;
  }

  function drawPaperFront(pid, pfx) {
    const k = PKEY[pid] || "kraft", edge = (PAPER[pid] || PAPER.kraft_vintage).edge, ew = pid === "midnight_gold" ? "3.2" : "1.6";
    const gL = `url(#${pfx}_${k}_L)`, gR = `url(#${pfx}_${k}_R)`;
    let s = `<g filter="url(#${pfx}_sh)">`;
    s += `<path d="M145 360 L495 515 L545 625 L355 775 L250 610 Z" fill="${gL}" stroke="${edge}" stroke-width="${ew}"/><path d="M145 360 L270 335 L495 515 Z" fill="#ffffff" fill-opacity="0.22" stroke="${edge}" stroke-width="1"/>`;
    s += `<path d="M855 360 L465 525 L445 625 L645 775 L750 610 Z" fill="${gR}" stroke="${edge}" stroke-width="${ew}"/><path d="M855 360 L730 335 L465 525 Z" fill="#ffffff" fill-opacity="0.18" stroke="${edge}" stroke-width="1"/>`;
    s += `<path d="M445 615 L555 615 L635 780 L500 795 L365 780 Z" fill="${gL}" stroke="${edge}" stroke-width="${ew}"/>`;
    s += `<path d="M260 440 L488 615 M740 440 L512 615 M485 615 L430 778 M515 615 L570 778" stroke="#000000" stroke-opacity="0.15" stroke-width="2" fill="none"/><path d="M263 438 L490 613 M737 438 L510 613" stroke="#ffffff" stroke-opacity="0.25" stroke-width="1.2" fill="none"/>`;
    if (pid === "kraft_vintage") {
      s += `<path d="M210 430 L340 520 M690 460 L560 560 M420 680 L540 730" stroke="#7a5228" stroke-width="1.2" stroke-opacity="0.35"/>`;
    } else if (pid === "pastel_pink_silk") {
      s += `<path d="M210 395 Q360 490 485 610" stroke="#ffffff" stroke-width="6" stroke-opacity="0.28" fill="none" stroke-linecap="round"/><path d="M780 395 Q630 490 515 610" stroke="#ffffff" stroke-width="5" stroke-opacity="0.22" fill="none" stroke-linecap="round"/>`;
    } else if (pid === "midnight_gold") {
      for (const [sx, sy, sr] of [[260, 460, 4], [340, 540, 3], [670, 470, 4.5], [610, 560, 3], [440, 690, 3.5], [560, 710, 4], [510, 650, 2.5], [380, 620, 3]]) {
        s += `<path d="M${sx} ${sy - sr * 2} L${sx + sr * 0.6} ${sy - sr * 0.6} L${sx + sr * 2} ${sy} L${sx + sr * 0.6} ${sy + sr * 0.6} L${sx} ${sy + sr * 2} L${sx - sr * 0.6} ${sy + sr * 0.6} L${sx - sr * 2} ${sy} L${sx - sr * 0.6} ${sy - sr * 0.6} Z" fill="#f7d674" opacity="0.88"/>`;
      }
    } else if (pid === "botanical_newspaper") {
      s += `<g stroke="#8c8270" stroke-width="1.3" stroke-opacity="0.42">`;
      for (let y = 450; y <= 590; y += 10) s += `<line x1="250" y1="${y}" x2="390" y2="${y + 45}"/><line x1="610" y1="${y + 45}" x2="750" y2="${y}"/>`;
      for (let y = 650; y <= 750; y += 10) s += `<line x1="420" y1="${y}" x2="580" y2="${y}"/>`;
      s += `</g><g stroke="#4f7849" stroke-width="2" fill="#6b9964" fill-opacity="0.55"><path d="M310 520 Q340 480 370 460"/><ellipse cx="330" cy="495" rx="9" ry="4" transform="rotate(-35 330 495)"/><ellipse cx="350" cy="478" rx="9" ry="4" transform="rotate(-35 350 478)"/><path d="M670 530 Q640 490 610 465"/><ellipse cx="650" cy="505" rx="9" ry="4" transform="rotate(35 650 505)"/><ellipse cx="630" cy="485" rx="9" ry="4" transform="rotate(35 630 485)"/></g>`;
    }
    return s + `</g>`;
  }

  function bouquetSVG(p) {
    const pfx = "bq" + (++uidCounter);
    const rnd = makeRng(JSON.stringify({ f: p.flowers || {}, p: p.paper_id || "", d: p.decorations || [] }));
    const pid = p.paper_id || "kraft_vintage", dec = p.decorations || [];
    const has = (d) => dec.includes(d);
    const pulseCls = (d) => (lastAction === "dec:" + d ? " bq-pulse" : "");

    const list = [];
    for (const [id, c] of Object.entries(p.flowers || {})) for (let i = 0; i < c; i++) list.push(id);
    for (let i = list.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [list[i], list[j]] = [list[j], list[i]]; }

    const count = list.length, gather = [500, 610];
    // rounded dome: centre highest and largest, outer flowers fan out and lower
    const placed = list.map((id, i) => {
      const golden = i * 2.399963, rad = count === 1 ? 0 : Math.sqrt((i + 0.45) / count);
      const spreadX = count <= 4 ? 130 : count <= 12 ? 210 : 265, spreadY = count <= 4 ? 75 : count <= 12 ? 120 : 155;
      const x = 500 + Math.cos(golden) * rad * spreadX + (rnd() - 0.5) * 22;
      const y = 285 + Math.sin(golden) * rad * spreadY + Math.pow(rad, 1.35) * 58 + (rnd() - 0.5) * 18;
      const sc = Math.max(0.72, Math.min(1.26, 1.15 - rad * 0.24 + (rnd() - 0.5) * 0.12));
      return { id, x, y, sc, rot: ((x - 500) / 270) * 28 + (rnd() - 0.5) * 14, depth: (y - 140) / 340, k: i % 6 };
    }).sort((a, b) => a.y - b.y);

    let o = `<svg viewBox="0 0 1000 860" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Custom floral bouquet">` + sharedDefs(pfx);
    o += `<ellipse cx="500" cy="815" rx="220" ry="24" fill="#210d18" opacity="0.18" filter="url(#${pfx}_sh)"/>`;
    o += drawPaperBack(pid, pfx);

    if (count > 0) {   // cut stem ends below the paper skirt
      o += `<g>`;
      const n = Math.min(11, Math.max(4, count));
      for (let i = 0; i < n; i++) {
        const t = i / (n - 1) - 0.5, ex = 500 + t * 88 + (rnd() - 0.5) * 8, ey = 805 + Math.abs(t) * 16 + (rnd() - 0.5) * 10;
        o += `<path d="M${(500 + t * 26).toFixed(1)} 750 L${ex.toFixed(1)} ${ey.toFixed(1)}" stroke="${i % 2 ? "#356936" : "#488246"}" stroke-width="6.5" stroke-linecap="round"/><ellipse cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" rx="3.3" ry="2.2" fill="#9ec492"/>`;
      }
      o += `</g>`;
    }

    o += `<g class="sw">`;
    if (count > 0) {   // foliage ring behind the dome
      o += `<g>`;
      for (let i = 0; i < 14; i++) {
        const a = (-168 + i * (156 / 13)) * Math.PI / 180;
        o += `<g transform="translate(${(500 + Math.cos(a) * 275).toFixed(1)} ${(335 + Math.sin(a) * 185).toFixed(1)}) rotate(${(a * 180 / Math.PI + 90).toFixed(1)})"><path d="M0 20 C-18 -10 -16 -46 0 -68 C16 -46 18 -10 0 20 Z" fill="${i % 2 ? "#28592e" : "#346e3b"}" stroke="#1c4221" stroke-width="1"/><path d="M0 14 L0 -58" stroke="#5da165" stroke-width="1.2" stroke-opacity="0.6"/></g>`;
      }
      o += `</g>`;
    }

    if (has("dried_eucalyptus")) {   // sprigs reach past the dome so they are easy to see
      o += `<g class="dec-euc${pulseCls("dried_eucalyptus")}" filter="url(#${pfx}_sh_sm)">`;
      const angles = [-158, -132, -108, -72, -48, -22, -172, -8];
      for (let i = 0; i < angles.length; i++) {
        const a = angles[i] * Math.PI / 180, R = i >= 6 ? 335 : 355;
        o += `<g transform="translate(${(500 + Math.cos(a) * R).toFixed(1)} ${(355 + Math.sin(a) * R * 0.74).toFixed(1)}) rotate(${(angles[i] + 90).toFixed(1)})"><path d="M0 95 Q4 10 0 -75" stroke="#5d7d6e" stroke-width="3" fill="none" stroke-linecap="round"/>`;
        for (let k = 0; k < 6; k++) {
          const ly = 50 - k * 21, lr = 16 - k * 1.1;
          o += `<ellipse cx="-14" cy="${ly}" rx="${lr}" ry="${(lr * 0.78).toFixed(1)}" fill="#8db3a2" stroke="#dcebe4" stroke-width="1" transform="rotate(-24 -14 ${ly})"/><ellipse cx="14" cy="${ly - 9}" rx="${lr}" ry="${(lr * 0.78).toFixed(1)}" fill="#7ca392" stroke="#dcebe4" stroke-width="1" transform="rotate(24 14 ${ly - 9})"/>`;
        }
        o += `<ellipse cx="0" cy="-76" rx="11" ry="14" fill="#9bc2b0" stroke="#dcebe4" stroke-width="1"/></g>`;
      }
      o += `</g>`;
    }

    o += `<g>`;   // a curved stem from every flower down to the shared gathering point, with matching leaves
    for (let i = 0; i < placed.length; i++) {
      const q = placed[i], dx = q.x - gather[0];
      const c1x = q.x - dx * 0.24, c1y = q.y + (gather[1] - q.y) * 0.38;
      const c2x = gather[0] + dx * 0.16 + (i % 2 ? 9 : -9), c2y = q.y + (gather[1] - q.y) * 0.76;
      const ex = (gather[0] + dx * 0.05).toFixed(1);   // FIX: was gather[0] + (..).toFixed(1) = string concatenation
      o += `<path d="M${q.x.toFixed(1)} ${q.y.toFixed(1)} C${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${ex} ${gather[1]}" stroke="#2d5e31" stroke-width="6" fill="none" stroke-linecap="round"/>`;
      o += `<path d="M${(q.x - 1).toFixed(1)} ${q.y.toFixed(1)} C${(c1x - 1).toFixed(1)} ${c1y.toFixed(1)} ${(c2x - 1).toFixed(1)} ${c2y.toFixed(1)} ${ex} ${gather[1]}" stroke="#68ab6c" stroke-width="1.8" fill="none" stroke-linecap="round"/>`;
      const lx = 0.55 * q.x + 0.45 * c1x, ly = 0.55 * q.y + 0.45 * c1y;
      o += `<circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="3.4" fill="#244d28"/>` + drawStemLeaf(q.id, lx, ly, i % 2 ? 1 : -1, q.rot * 0.4);
      if (q.id === "tulip" || q.id === "red_rose" || q.id === "sunflower") o += drawStemLeaf(q.id, 0.3 * q.x + 0.7 * c1x, 0.3 * q.y + 0.7 * c1y, i % 2 ? -1 : 1, q.rot * 0.3);
    }
    o += `</g>`;

    if (count === 0) {
      o += `<g transform="translate(500 320)"><circle r="88" fill="#ffffff" fill-opacity="0.7" stroke="#d99ab5" stroke-width="2" stroke-dasharray="6 6"/><text x="0" y="-6" text-anchor="middle" font-size="22" font-weight="700" fill="#7a3253">Your wrapper is ready</text><text x="0" y="24" text-anchor="middle" font-size="16" fill="#9c5676">Pick flowers on the right to build your bouquet</text></g>`;
    }

    for (const q of placed) {   // heads back-to-front; a cheap soft shadow instead of a filter on every flower
      o += `<g transform="translate(${q.x.toFixed(1)} ${q.y.toFixed(1)}) rotate(${q.rot.toFixed(1)}) scale(${q.sc.toFixed(2)})"><ellipse cx="2" cy="6" rx="36" ry="32" fill="#1c0a14" fill-opacity="0.16"/><g class="fl d${q.k}">${drawFlowerHead(q.id, pfx)}`;
      if (q.depth < 0.38) o += `<circle r="38" fill="#1c0a14" fill-opacity="0.16" pointer-events="none"/>`;
      o += `</g></g>`;
    }

    if (has("pearl_pins")) {
      o += `<g class="dec-pearls${pulseCls("pearl_pins")}" filter="url(#${pfx}_sh_sm)">`;
      for (const [px, py, pr] of [[330, 270, -25], [420, 210, -10], [510, 195, 5], [605, 215, 18], [675, 275, 30], [275, 360, -35], [385, 325, -12], [500, 295, 4], [615, 330, 16], [720, 365, 35], [345, 435, -18], [655, 435, 20]]) {
        o += `<g transform="translate(${px} ${py}) rotate(${pr})"><line x1="0" y1="0" x2="0" y2="28" stroke="#d8d0c5" stroke-width="2.4" stroke-linecap="round"/><circle cx="0" cy="0" r="10.5" fill="url(#${pfx}_pearl_g)" stroke="#9e8576" stroke-width="1"/><circle cx="-3.5" cy="-3.5" r="3.2" fill="#ffffff"/></g>`;
      }
      o += `</g>`;
    }

    if (has("gold_butterflies")) {
      o += `<g class="dec-bf${pulseCls("gold_butterflies")}" filter="url(#${pfx}_sh)">`;
      [[325, 205, -22, 1.05], [515, 165, 8, 1.12], [685, 220, 24, 1.0]].forEach(([bx, by, br, bs], i) => {
        o += `<g transform="translate(${bx} ${by}) rotate(${br}) scale(${bs})"><g class="bf-wing d${i}"><path d="M0 0 C-28 -36 -54 -14 -34 8 C-46 22 -24 38 -6 18 L0 6 Z" fill="url(#${pfx}_gold_g)" stroke="#7a5208" stroke-width="1.2"/><path d="M0 0 C28 -36 54 -14 34 8 C46 22 24 38 6 18 L0 6 Z" fill="url(#${pfx}_gold_g)" stroke="#7a5208" stroke-width="1.2"/><path d="M-8 -8 C-22 -20 -34 -8 -20 4 M8 -8 C22 -20 34 -8 20 4" stroke="#fff6cc" stroke-width="1.2" fill="none"/></g><ellipse cx="0" cy="4" rx="2.8" ry="12" fill="#593a04"/><path d="M-1 -6 Q-8 -18 -14 -16 M1 -6 Q8 -18 14 -16" stroke="#593a04" stroke-width="1.3" fill="none"/></g>`;
      });
      o += `</g>`;
    }
    o += `</g>`;   // end swaying dome

    o += drawPaperFront(pid, pfx);

    if (has("lace_ribbon")) {
      o += `<g class="dec-lace${pulseCls("lace_ribbon")}" filter="url(#${pfx}_sh_sm)"><path d="M262 560 Q500 625 738 560 L715 628 Q500 692 285 628 Z" fill="#fffdf9" stroke="#8c7662" stroke-width="1.8"/><path d="M270 576 Q500 640 730 576 M278 612 Q500 676 722 612" stroke="#cbbba8" stroke-width="1.2" stroke-dasharray="5 5" fill="none"/>`;
      for (let i = 0; i <= 14; i++) {
        const t = i / 14, lx = (1 - t) * (1 - t) * 265 + 2 * (1 - t) * t * 500 + t * t * 735;
        const lyTop = (1 - t) * (1 - t) * 560 + 2 * (1 - t) * t * 625 + t * t * 560, lyBot = (1 - t) * (1 - t) * 626 + 2 * (1 - t) * t * 690 + t * t * 626;
        o += `<circle cx="${lx.toFixed(1)}" cy="${lyTop.toFixed(1)}" r="9" fill="#fffdf9" stroke="#8c7662" stroke-width="1.4"/><circle cx="${lx.toFixed(1)}" cy="${lyTop.toFixed(1)}" r="3.2" fill="#8c7662" fill-opacity="0.45"/><circle cx="${lx.toFixed(1)}" cy="${lyBot.toFixed(1)}" r="9" fill="#fffdf9" stroke="#8c7662" stroke-width="1.4"/><circle cx="${lx.toFixed(1)}" cy="${lyBot.toFixed(1)}" r="3.2" fill="#8c7662" fill-opacity="0.45"/><circle cx="${lx.toFixed(1)}" cy="${((lyTop + lyBot) * 0.5).toFixed(1)}" r="4.2" fill="none" stroke="#9e8874" stroke-width="1.3"/>`;
      }
      o += `</g>`;
    }

    if (has("satin_bow")) {   // FIX: the pulse animation sets transform, so the translate lives on an outer wrapper
      o += `<g transform="translate(500 618)" filter="url(#${pfx}_sh)"><g class="dec-bow${pulseCls("satin_bow")}"><path d="M-16 8 C-42 68 -68 125 -88 165 L-42 152 L-24 176 C-14 120 -6 62 -4 12 Z" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.5"/><path d="M16 8 C42 68 68 125 88 165 L42 152 L24 176 C14 120 6 62 4 12 Z" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.5"/><path d="M-92 -12 Q0 18 92 -12 L86 14 Q0 42 -86 14 Z" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.5"/><path d="M-10 -4 C-68 -58 -132 -28 -116 18 C-102 56 -42 36 -8 8 Z" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.6"/><path d="M10 -4 C68 -58 132 -28 116 18 C102 56 42 36 8 8 Z" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.6"/><path d="M-18 -2 C-58 -24 -88 -8 -74 12" stroke="#ffb8ce" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M18 -2 C58 -24 88 -8 74 12" stroke="#ffb8ce" stroke-width="3" fill="none" stroke-linecap="round"/><rect x="-20" y="-16" width="40" height="32" rx="12" fill="url(#${pfx}_bow_g)" stroke="#7a0f32" stroke-width="1.6"/></g></g>`;
    } else {
      o += `<g transform="translate(500 616)" filter="url(#${pfx}_sh_sm)"><path d="M-78 -6 Q0 14 78 -6" stroke="#8c6239" stroke-width="6" fill="none" stroke-linecap="round"/><path d="M-76 2 Q0 22 76 2" stroke="#b08354" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M-74 10 Q0 30 74 10" stroke="#734d26" stroke-width="5" fill="none" stroke-linecap="round"/><circle cx="0" cy="10" r="10" fill="#9c7044" stroke="#5e3d1b" stroke-width="1.5"/><path d="M-4 14 Q-22 52 -32 78 M4 14 Q20 54 28 80" stroke="#8c6239" stroke-width="4" fill="none" stroke-linecap="round"/></g>`;
    }

    if (has("fairy_lights")) {   // FIX: each bulb sits in a translate wrapper so the twinkle animation can't move it to 0,0
      o += `<g class="dec-lights${pulseCls("fairy_lights")}"><path d="M210 380 Q350 475 500 410 Q650 345 785 400 Q660 545 500 570 Q340 595 255 685" stroke="#b89958" stroke-width="2.2" fill="none" stroke-dasharray="4 2"/>`;
      [[225, 390], [290, 428], [365, 442], [440, 428], [500, 410], [570, 384], [645, 375], [720, 384], [775, 402], [715, 475], [635, 530], [550, 560], [465, 575], [380, 602], [305, 645], [260, 682]].forEach(([bx, by], i) => {
        o += `<g transform="translate(${bx} ${by})"><g class="tw d${i % 6}"><circle r="19" fill="url(#${pfx}_bulb_g)"/><circle r="6.5" fill="#fffbe0" stroke="#f5a623" stroke-width="1.2"/></g></g>`;
      });
      o += `</g>`;
    }

    o += `<g transform="translate(618 525) rotate(11)" filter="url(#${pfx}_sh_sm)"><path d="M-118 90 Q-60 40 -42 0" stroke="#b08354" stroke-width="2" fill="none"/><path d="M-48 -28 L46 -28 L58 -14 L58 28 L-48 28 Z" fill="#fffaf2" stroke="#d4c2a8" stroke-width="1.5"/><circle cx="-36" cy="0" r="3.5" fill="#d4c2a8"/><text x="6" y="-2" text-anchor="middle" font-size="22" font-style="italic" font-family="Georgia, serif" fill="#8f294f">for you</text><path d="M6 19 C-2 12 -5 7 0 5 C3 4 6 8 6 8 C6 8 9 4 12 5 C17 7 14 12 6 19 Z" fill="#df3b68"/></g>`;
    return o + `</svg>`;
  }

  function flowerThumbSVG(id) {
    const pfx = "th_" + id + "_" + (++uidCounter);
    return `<svg viewBox="-55 -58 110 116" xmlns="http://www.w3.org/2000/svg">${sharedDefs(pfx)}${drawFlowerHead(id, pfx)}</svg>`;
  }

  function decorThumbSVG(id) {
    const pfx = "th_" + id + "_" + (++uidCounter);
    const lace = [-26, -9, 9, 26].map((x) => `<circle cx="${x}" cy="-8" r="6" fill="#fffdf9" stroke="#8c7662" stroke-width="1.4"/><circle cx="${x}" cy="16" r="6" fill="#fffdf9" stroke="#8c7662" stroke-width="1.4"/>`).join("");
    const art = {
      satin_bow: `<g transform="scale(0.38)"><path d="M-10 -4 C-68 -58 -132 -28 -116 18 C-102 56 -42 36 -8 8 Z" fill="#e04372" stroke="#7a0f32" stroke-width="3"/><path d="M10 -4 C68 -58 132 -28 116 18 C102 56 42 36 8 8 Z" fill="#e04372" stroke="#7a0f32" stroke-width="3"/><path d="M-14 8 L-55 95 L-20 85 L-8 105 Z M14 8 L55 95 L20 85 L8 105 Z" fill="#c82958"/><rect x="-18" y="-14" width="36" height="28" rx="10" fill="#ff7aa2" stroke="#7a0f32" stroke-width="3"/></g>`,
      fairy_lights: `<path d="M-38 10 Q0 -25 38 10" stroke="#9e824c" stroke-width="2.5" fill="none"/><circle cx="-24" cy="-1" r="14" fill="#ffcf40" opacity="0.45"/><circle cx="-24" cy="-1" r="6" fill="#fff9d2" stroke="#e09000" stroke-width="1.5"/><circle cx="0" cy="-8" r="16" fill="#ffcf40" opacity="0.5"/><circle cx="0" cy="-8" r="6.5" fill="#fff9d2" stroke="#e09000" stroke-width="1.5"/><circle cx="24" cy="-1" r="14" fill="#ffcf40" opacity="0.45"/><circle cx="24" cy="-1" r="6" fill="#fff9d2" stroke="#e09000" stroke-width="1.5"/>`,
      pearl_pins: `<line x1="-12" y1="-8" x2="18" y2="28" stroke="#b8aea2" stroke-width="3" stroke-linecap="round"/><circle cx="-12" cy="-8" r="14" fill="#fdf6ee" stroke="#a89282" stroke-width="1.5"/><circle cx="-16" cy="-12" r="4.5" fill="#fff"/><circle cx="14" cy="-12" r="10" fill="#fdf6ee" stroke="#a89282" stroke-width="1.5"/><circle cx="11" cy="-15" r="3" fill="#fff"/>`,
      gold_butterflies: `<g transform="rotate(-15)"><path d="M0 0 C-26 -34 -48 -12 -30 8 C-40 20 -20 34 -4 16 Z" fill="#e8b948" stroke="#7a5208" stroke-width="1.5"/><path d="M0 0 C26 -34 48 -12 30 8 C40 20 20 34 4 16 Z" fill="#e8b948" stroke="#7a5208" stroke-width="1.5"/><ellipse cx="0" cy="4" rx="2.5" ry="11" fill="#593a04"/></g>`,
      dried_eucalyptus: `<path d="M-18 32 Q0 0 18 -32" stroke="#5d7d6e" stroke-width="3" fill="none"/><ellipse cx="-14" cy="10" rx="13" ry="9" fill="#8db3a2" stroke="#dcebe4" stroke-width="1.2" transform="rotate(-20 -14 10)"/><ellipse cx="8" cy="4" rx="13" ry="9" fill="#7ca392" stroke="#dcebe4" stroke-width="1.2" transform="rotate(30 8 4)"/><ellipse cx="-4" cy="-14" rx="12" ry="8" fill="#8db3a2" stroke="#dcebe4" stroke-width="1.2" transform="rotate(-20 -4 -14)"/><ellipse cx="16" cy="-22" rx="11" ry="8" fill="#9bc2b0" stroke="#dcebe4" stroke-width="1.2"/>`,
      lace_ribbon: `<path d="M-38 -10 Q0 4 38 -10 L38 14 Q0 28 -38 14 Z" fill="#fffdf9" stroke="#8c7662" stroke-width="1.8"/>${lace}`
    }[id] || "";
    return `<svg viewBox="-48 -45 96 90" xmlns="http://www.w3.org/2000/svg">${art}</svg>`;
  }

  function surpriseMe() {
    const rng = Math.random, f = {};
    const picks = [...FL].sort(() => rng() - 0.5).slice(0, 3 + Math.floor(rng() * 3));
    let rem = 10 + Math.floor(rng() * 14);
    picks.forEach(([id], idx) => { const cnt = idx === picks.length - 1 ? rem : Math.max(1, Math.floor(rem / (picks.length - idx))); f[id] = cnt; rem -= cnt; });
    st = { f, p: PA[Math.floor(rng() * PA.length)][0], d: [...DE].sort(() => rng() - 0.5).slice(0, 2 + Math.floor(rng() * 2)).map((x) => x[0]) };
    lastAction = "pop"; note = ""; draw();
  }
  function clearAll() { st = { f: {}, p: st.p || "kraft_vintage", d: [] }; lastAction = ""; note = ""; draw(); }

  function draw() {
    if (!ov) return;
    ov.replaceChildren();
    const wrap = el("div", "bq-wrap");
    const hdr = el("div", "bq-hdr"), tGrp = el("div", "bq-title-grp");
    tGrp.append(el("h2", "", "Bouquet Builder"), el("span", "bq-badge", `${total()} / 40 flowers`));
    const hActs = el("div", "bq-hdr-acts");
    hActs.append(btn("Surprise Me", surpriseMe, false), btn("Clear", clearAll, total() === 0 && st.d.length === 0), btn("Back", close, false));
    hdr.append(tGrp, hActs); wrap.append(hdr);

    const main = el("div", "bq-main"), stageCol = el("div", "bq-stage-col"), stage = el("div", "bq-stage");
    const svgBox = el("div", "bq-svg-box" + (lastAction === "pop" ? " bq-pop" : ""));
    svgBox.innerHTML = bouquetSVG({ flowers: st.f, paper_id: st.p || "kraft_vintage", decorations: st.d });
    stage.append(svgBox);
    const chips = el("div", "bq-chips"), activePa = PA.find((x) => x[0] === st.p);
    if (activePa) chips.append(el("span", "bq-chip", `Paper: ${activePa[1]}`));
    for (const did of st.d) {
      const dObj = DE.find((x) => x[0] === did); if (!dObj) continue;
      const ch = el("span", "bq-chip", dObj[1]), xb = el("button", "", "×");
      xb.title = `Remove ${dObj[1]}`;
      xb.onclick = () => { st.d = st.d.filter((x) => x !== did); lastAction = ""; draw(); };
      ch.append(xb); chips.append(ch);
    }
    stage.append(chips); stageCol.append(stage); main.append(stageCol);

    const ctrlCol = el("div", "bq-ctrl-col");
    const secFl = el("div", "bq-sec"), hdrFl = el("div", "bq-sec-hdr");
    hdrFl.append(el("h3", "", "1. Pick Flowers"), el("span", "", "1 to 40 stems"));
    const gridFl = el("div", "bq-grid-fl");
    for (const [id, name] of FL) {
      const c = st.f[id] || 0, card = el("div", "bq-card" + (c ? " on" : "")), th = el("div", "bq-thumb");
      th.innerHTML = flowerThumbSVG(id);
      const step = el("div", "bq-stepper"), m = el("button", "bq-step-btn", "−"), p = el("button", "bq-step-btn", "+");
      m.disabled = !c; p.disabled = total() >= 40;
      m.onclick = () => { st.f[id] = c - 1; if (!st.f[id]) delete st.f[id]; lastAction = ""; draw(); };
      p.onclick = () => { st.f[id] = c + 1; lastAction = "pop"; draw(); };
      step.append(m, el("span", "bq-cnt", String(c)), p);
      card.append(th, el("div", "bq-name", name), step); gridFl.append(card);
    }
    secFl.append(hdrFl, gridFl); ctrlCol.append(secFl);

    const secPa = el("div", "bq-sec"), hdrPa = el("div", "bq-sec-hdr");
    hdrPa.append(el("h3", "", "2. Wrapping Paper"), el("span", "", "Choose 1 style"));
    const gridPa = el("div", "bq-grid-pa");
    for (const [id, name, cols] of PA) {
      const on = st.p === id, card = el("div", "bq-card" + (on ? " on" : "")), sw = el("div", "bq-swatches");
      for (const hex of cols) { const dot = el("span", "bq-sw-dot"); dot.style.backgroundColor = hex; sw.append(dot); }
      const b = el("button", "bq-pick-btn", on ? "Selected ✓" : "Select Paper");
      b.onclick = () => { st.p = id; lastAction = "pop"; draw(); };
      card.append(sw, el("div", "bq-name", name), b); gridPa.append(card);
    }
    secPa.append(hdrPa, gridPa); ctrlCol.append(secPa);

    const secDe = el("div", "bq-sec"), hdrDe = el("div", "bq-sec-hdr");
    hdrDe.append(el("h3", "", "3. Finishing Touches"), el("span", "", `${st.d.length} / 3 selected`));
    const gridDe = el("div", "bq-grid-de");
    for (const [id, name] of DE) {
      const on = st.d.includes(id), card = el("div", "bq-card" + (on ? " on" : "")), th = el("div", "bq-thumb");
      th.innerHTML = decorThumbSVG(id);
      const b = el("button", "bq-pick-btn", on ? "Added ✓" : "Add Touch");
      b.disabled = !on && st.d.length >= 3;
      b.onclick = () => { st.d = on ? st.d.filter((x) => x !== id) : [...st.d, id]; lastAction = on ? "" : "dec:" + id; draw(); };
      card.append(th, el("div", "bq-name", name), b); gridDe.append(card);
    }
    secDe.append(hdrDe, gridDe); ctrlCol.append(secDe);

    const noteEl = el("p", "bq-note" + (noteOk ? " ok" : ""), note), ftr = el("div", "bq-ftr");
    ftr.append(btn("Back", close, false), btn("Send Bouquet to Partner 💌", send, total() < 1 || !st.p, "bq-btn bq-btn-pri"));
    ctrlCol.append(noteEl, ftr); main.append(ctrlCol); wrap.append(main); ov.append(wrap);
  }

  function send() {
    note = ""; noteOk = false;
    SocketClient.emit("gift:send", { gift_type: "BOUQUET", payload: { flowers: st.f, paper_id: st.p, decorations: st.d } });
  }
  function open() { if (ov) return; ov = el("div", "bq-ov"); document.body.append(ov); draw(); }
  function close() { if (ov) { ov.remove(); ov = null; } }

  function toast(g) {
    const t = el("div", "toast");
    t.append(el("p", "", `${g.sender_name} sent you a ${g.gift_type}! Would you like to open it?`));
    const row = el("div", "toast-acts");
    const reply = (ok) => { SocketClient.emit("gift:respond", { gift_id: g.gift_id, accepted: ok }); t.remove(); };
    row.append(btn("Yes", () => reply(true), false, "bq-btn bq-btn-pri"), btn("No", () => reply(false), false, "bq-btn"));
    t.append(row); document.body.append(t);
  }

  function showcase({ payload, bg }) {
    lastAction = "";   // FIX: don't replay the sender's "just added" pulse on the received bouquet
    const s = el("div", "bq-ov bq-show-ov");
    s.style.background = BGB[bg] || BGB["Golden Hour Meadow"];
    for (let i = 0; i < 16; i++) {
      const p = el("span", "pt");
      p.style.left = `${(i * 37) % 95}%`; p.style.animationDuration = `${6 + (i % 5)}s`; p.style.animationDelay = `${-i * 0.7}s`;
      s.append(p);
    }
    const card = el("div", "bq-show-card"), w = el("div", "bq-show-svg");
    w.innerHTML = bouquetSVG(payload);
    const paName = (PA.find((x) => x[0] === payload.paper_id) || [0, ""])[1];
    card.append(w, el("p", "bq-show-cap", `“${bg}” · ${paName}`), btn("Close", () => s.remove(), false, "bq-btn bq-btn-pri"));
    s.append(card); document.body.append(s);
  }

  function init() {
    if (inited) return; inited = true;
    SocketClient.on("gift:incoming", toast);
    SocketClient.on("gift:open", showcase);
    SocketClient.on("gift:error", (e) => { note = e.message; noteOk = false; draw(); });
    SocketClient.on("gift:sent", () => { note = "Sent! 💌"; noteOk = true; draw(); });
  }
  return { init, open };
})();
'''
