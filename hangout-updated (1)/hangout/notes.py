"""notes.py - Custom Styled Notes: sanitized on the server, partner must accept (Yes/No) before opening."""
import html, uuid
from typing import Literal
import nh3
from pydantic import BaseModel, Field, ValidationError
from core import partner_of

NAME = "Custom Notes"
SLUG = "notes"


class NotePayload(BaseModel):
    title: str = Field("", max_length=60)
    body: str = Field(..., min_length=1, max_length=1500)
    paper_style: Literal["parchment", "lined", "pastel", "midnight"]
    font_style: Literal["cursive", "typewriter", "serif", "handwritten"]
    ink_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


pending = {}


def setup(sio, auth, rooms):
    @sio.on("note:send")
    @auth
    async def send(sid, sess, data):
        peer = partner_of(rooms, sess["pid"])
        try:
            n = NotePayload(**(data or {}))
        except (ValidationError, TypeError):
            return await sio.emit("note:error", {"message": "Invalid note."}, to=sid)
        if not peer or sum(1 for g in pending.values() if g["from"] == sess["pid"]) >= 3:
            return await sio.emit("note:error", {"message": "Can't send right now."}, to=sid)
        clean = n.model_dump()
        clean["title"] = html.unescape(nh3.clean(clean["title"], tags=set()))   # strips all HTML (XSS-proof)
        clean["body"] = html.unescape(nh3.clean(clean["body"], tags=set()))
        gid = uuid.uuid4().hex
        pending[gid] = {"to": peer["sid"], "from": sess["pid"], "note": clean, "name": sess["name"]}
        await sio.emit("note:incoming", {"gift_id": gid, "sender_name": sess["name"]}, to=peer["sid"])
        await sio.emit("note:sent", {}, to=sid)

    @sio.on("note:respond")
    @auth
    async def respond(sid, sess, data):
        gid = data.get("gift_id") if isinstance(data, dict) else None
        g = pending.get(gid) if isinstance(gid, str) else None
        if not g or g["to"] != sid:
            return
        pending.pop(gid)
        if data.get("accepted") is True:
            await sio.emit("note:open", {"note": g["note"], "from": g["name"]}, to=sid)


CSS = r'''.hn-paper{width:400px;max-width:100%;aspect-ratio:1/1.414;box-sizing:border-box;overflow:auto;padding:22px;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.2);white-space:pre-wrap;word-break:break-word;font-size:1.15rem;line-height:1.6}
.hn-parchment{background:#f3e3bf}.hn-lined{line-height:28px;background:repeating-linear-gradient(#fff,#fff 27px,#9cc7ee 28px)}.hn-pastel{background:#ffe3ee;border:3px dotted #f29ac0}.hn-midnight{background:#14102e;box-shadow:0 0 24px #7a5cff}
.hn-cursive{font-family:"Brush Script MT","Segoe Script",cursive}.hn-typewriter{font-family:"Courier New",monospace}.hn-serif{font-family:"Cormorant Garamond",Georgia,serif}.hn-handwritten{font-family:"Comic Sans MS","Segoe Print",cursive}
.hn-count{font-size:.85rem;margin:4px 0;min-height:1.2em}.hn-form{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}.hn-form input,.hn-form select,.hn-form textarea{padding:8px;border-radius:10px;border:1px solid #d9488f;background:#fff;color:#140810;font:inherit}'''

JS = r'''"use strict";
window.Features = window.Features || {};
window.Features["Custom Notes"] = (() => {
  const H = Hang; let inited = false, st = { title: "", body: "", paper: "parchment", font: "serif", ink: "#3b1c32" }, msg = "";
  const INK = { midnight: "#e9e2ff" };
  function paper(n, box) {
    const p = H.el("div", "hn-paper hn-" + n.paper_style + " hn-" + n.font_style);
    p.style.color = n.paper_style === "midnight" ? INK.midnight : n.ink_color;
    if (n.title) { const t = H.el("b", "", n.title); t.style.cssText = "display:block;font-size:1.4rem;margin-bottom:8px"; p.append(t); }
    p.append(document.createTextNode(n.body)); box.append(p); return p;
  }
  function download(n, from) {
    const fam = { cursive: "cursive", typewriter: "monospace", serif: "Georgia, serif", handwritten: "'Comic Sans MS', cursive" }[n.font_style];
    const m = document.createElement("canvas").getContext("2d"); m.font = "28px " + fam;
    const lines = [];
    for (const para of n.body.split("\n")) { let line = ""; for (const w of para.split(" ")) { const t = line + w + " "; if (m.measureText(t).width > 800 && line) { lines.push(line); line = w + " "; } else line = t; } lines.push(line); }
    const c = document.createElement("canvas"); c.width = 900; c.height = Math.max(1273, 70 + (n.title ? 55 : 0) + lines.length * 40 + 60);   // 900x1273 = one A-series sheet
    const x = c.getContext("2d");
    x.fillStyle = { parchment: "#f3e3bf", lined: "#ffffff", pastel: "#ffe3ee", midnight: "#14102e" }[n.paper_style]; x.fillRect(0, 0, c.width, c.height);
    if (n.paper_style === "lined") { x.strokeStyle = "#9cc7ee"; for (let y = 90; y < c.height; y += 40) { x.beginPath(); x.moveTo(30, y); x.lineTo(870, y); x.stroke(); } }
    x.fillStyle = n.paper_style === "midnight" ? INK.midnight : n.ink_color;
    let y = 70; if (n.title) { x.font = "bold 38px " + fam; x.fillText(n.title, 40, y); y += 55; }
    x.font = "28px " + fam;
    for (const l of lines) { x.fillText(l, 40, y); y += 40; }
    const a = document.createElement("a"); a.download = "note-from-" + String(from).replace(/[^A-Za-z0-9]/g, "") + ".png"; a.href = c.toDataURL("image/png"); a.click();
  }
  function view(n, from) { const o = H.overlay("A note from " + from); paper(n, o.box); o.box.append(H.btn("Download", () => download(n, from))); }
  function draw(o) {
    o.box.replaceChildren(); const f = H.el("div", "hn-form");
    const t = H.el("input"); t.placeholder = "Title"; t.maxLength = 60; t.value = st.title; t.oninput = () => { st.title = t.value; live(); };
    const sel = (opts, key) => { const s = H.el("select"); for (const [v, l] of opts) { const op = H.el("option", "", l); op.value = v; s.append(op); } s.value = st[key]; s.onchange = () => { st[key] = s.value; live(); }; return s; };
    const ink = H.el("input"); ink.type = "color"; ink.value = st.ink; ink.oninput = () => { st.ink = ink.value; live(); };
    f.append(t, sel([["parchment", "Vintage Parchment"], ["lined", "Lined School Note"], ["pastel", "Pastel Hearts"], ["midnight", "Midnight Neon"]], "paper"), sel([["cursive", "Cursive Script"], ["typewriter", "Typewriter Mono"], ["serif", "Elegant Serif"], ["handwritten", "Clean Handwritten"]], "font"), ink);
    const ta = H.el("textarea"); ta.rows = 5; ta.maxLength = 1500; ta.placeholder = "Write something sweet..."; ta.style.cssText = "width:min(400px,100%)"; ta.value = st.body; ta.oninput = () => { st.body = ta.value; live(); };
    const prev = H.el("div"), cnt = H.el("p", "hn-count", "");
    let sheet = null;
    const fits = () => sheet.scrollHeight <= sheet.clientHeight + 1;
    const live = () => {   // fixed-size sheet: when the text no longer fits, cut it back to what fits
      prev.replaceChildren(); sheet = paper(payload(), prev); cnt.textContent = "";
      if (fits()) return;
      const txt = st.body, tn = sheet.lastChild; let lo = 0, hi = txt.length;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; tn.nodeValue = txt.slice(0, mid) || " "; if (fits()) lo = mid; else hi = mid - 1; }
      st.body = txt.slice(0, lo); ta.value = st.body; tn.nodeValue = st.body || " "; cnt.textContent = "The sheet is full ✋";
    };
    live();
    const row = H.el("div"); row.append(H.btn("Send Note to Partner", () => { msg = ""; SocketClient.emit("note:send", payload()); }), document.createTextNode(" "), H.btn("Download Note", () => download(payload(), "me")));
    const m = H.el("p", "err", msg); m.id = "hnMsg"; o.box.append(f, ta, cnt, prev, row, m);
  }
  const payload = () => ({ title: st.title, body: st.body || " ", paper_style: st.paper, font_style: st.font, ink_color: st.ink });
  const open = () => { const o = H.overlay("Custom Notes"); draw(o); };
  const init = () => {
    if (inited) return; inited = true;
    SocketClient.on("note:incoming", (g) => H.toast(g.sender_name + " sent you a NOTE! Would you like to open it?", () => SocketClient.emit("note:respond", { gift_id: g.gift_id, accepted: true }), () => SocketClient.emit("note:respond", { gift_id: g.gift_id, accepted: false })));
    SocketClient.on("note:open", (d) => view(d.note, d.from));
    SocketClient.on("note:sent", () => { const m = document.getElementById("hnMsg"); if (m) m.textContent = "Sent! 💌"; });
    SocketClient.on("note:error", (e) => { const m = document.getElementById("hnMsg"); if (m) m.textContent = e.message; });
  };
  return { init, open };
})();'''
