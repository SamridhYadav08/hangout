"""chess_game.py - Two-player chess. python-chess is the referee: only legal moves are ever played."""
import chess
from core import partner_of

NAME = "Chess"
SLUG = "chess"
games = {}   # room code -> chess.Board


def setup(sio, auth, rooms):
    def info(pid):
        code = rooms.by_player.get(pid)
        room = rooms.rooms.get(code)
        return (code, room, room.players[pid]) if room and room.locked else (None, None, None)

    def state(b):
        legal = {}
        for m in b.legal_moves:
            legal.setdefault(chess.square_name(m.from_square), []).append(chess.square_name(m.to_square))
        status = "checkmate" if b.is_checkmate() else "stalemate" if b.is_stalemate() else "draw" if (b.is_insufficient_material() or b.can_claim_fifty_moves() or b.is_repetition(3)) else "check" if b.is_check() else "play"
        return {"fen": b.fen(), "turn": "white" if b.turn else "black", "status": status, "legal": legal}

    async def push(code, room):
        s = state(games[code])
        for p in room.players.values():
            await sio.emit("chess:state", s, to=p["sid"])

    @sio.on("chess:sync")
    @auth
    async def sync(sid, sess, data):
        code, room, me = info(sess["pid"])
        if room:
            games.setdefault(code, chess.Board())
            await sio.emit("chess:state", {**state(games[code]), "role": me["role"]}, to=sid)

    @sio.on("chess:move")
    @auth
    async def move(sid, sess, data):
        code, room, me = info(sess["pid"])
        b = games.get(code)
        if not room or b is None or not isinstance(data, dict):
            return
        if me["role"] != ("white" if b.turn else "black"):
            return   # not your turn
        try:
            uci = str(data.get("from", "")) + str(data.get("to", "")) + (str(data.get("promotion", "")) if data.get("promotion") in ("q", "r", "b", "n") else "")
            mv = chess.Move.from_uci(uci)
        except ValueError:
            return
        if mv not in b.legal_moves:
            return await sio.emit("chess:state", {**state(b), "role": me["role"], "rejected": True}, to=sid)
        b.push(mv)
        await push(code, room)

    @sio.on("chess:reset")
    @auth
    async def reset(sid, sess, data):
        code, room, me = info(sess["pid"])
        if room and games.get(code) and games[code].is_game_over(claim_draw=True):
            games[code] = chess.Board()
            await push(code, room)


CSS = r'''
.hc-board {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  grid-template-rows: repeat(8, 1fr);
  width: min(480px, 94vw);
  aspect-ratio: 1 / 1;
  border: 10px solid #4a2c11;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55), inset 0 0 0 2px #d4af37;
  overflow: hidden;
  box-sizing: border-box;
}
.hc-sq {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  cursor: pointer;
  user-select: none;
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
}
.hc-l {
  background-color: #f0d9b5;
  background-image: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(181,136,99,0.08) 100%);
  box-shadow: inset 0 0 2px rgba(139, 90, 43, 0.15);
}
.hc-d {
  background-color: #b58863;
  background-image: linear-gradient(135deg, rgba(0,0,0,0.06) 0%, rgba(74,44,17,0.18) 100%);
  box-shadow: inset 0 0 3px rgba(45, 23, 6, 0.25);
}
.hc-sel {
  background-color: #e6c65a !important;
  box-shadow: inset 0 0 0 3px #6b440a;
}
.hc-dot::after {
  content: "";
  width: 28%;
  height: 28%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(45, 25, 10, 0.55) 0%, rgba(45, 25, 10, 0.35) 100%);
  box-shadow: 0 1px 3px rgba(255, 255, 255, 0.3);
  position: absolute;
  pointer-events: none;
  z-index: 2;
}
.hc-piece {
  width: 82%;
  height: 82%;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  transition: transform 0.12s ease;
  filter: drop-shadow(0 3px 3px rgba(0, 0, 0, 0.45));
}
.hc-sq:hover .hc-piece {
  transform: translateY(-2px) scale(1.04);
}
.hc-piece svg {
  width: 100%;
  height: 100%;
  display: block;
}
.hc-p-w .hc-detail { stroke: #5c3a1e; stroke-width: 1.3; fill: none; }
.hc-p-b .hc-detail { stroke: #d4af37; stroke-width: 1.3; fill: none; }
.hc-p-w .hc-eye { fill: #2c1808; stroke: none; }
.hc-p-b .hc-eye { fill: #d4af37; stroke: none; }
.hc-status { font-weight: 700; color: #140810; margin: 0; }
.hc-coord { position: absolute; font: 700 .62rem/1 system-ui, sans-serif; opacity: .55; pointer-events: none; }
.hc-coord-r { top: 4px; left: 4px; }
.hc-coord-f { bottom: 3px; right: 4px; }
.hc-l .hc-coord { color: #8b5a2b; }
.hc-d .hc-coord { color: #f0d9b5; }
'''

JS = r'''"use strict";
window.Features = window.Features || {};
window.Features["Chess"] = (() => {
  const H = Hang;

  // Custom crafted Staunton-style SVG chess pieces
  const SHAPES = {
    p: `<path d="M 22.5,9 C 19.5,9 17,11.5 17,14.5 C 17,16.8 18.4,18.7 20.4,19.5 C 18,21 16.5,23.5 16.5,27 C 16.5,29 19,31 19,31 L 14,34.5 L 14,37 L 31,37 L 31,34.5 L 26,31 C 26,31 28.5,29 28.5,27 C 28.5,23.5 27,21 24.6,19.5 C 26.6,18.7 28,16.8 28,14.5 C 28,11.5 25.5,9 22.5,9 z"/>`,
    r: `<g><path d="M 9,39 L 36,39 L 36,36 L 9,36 L 9,39 z M 12,36 L 12,32 L 33,32 L 33,36 L 12,36 z M 14,29.5 L 14,16.5 L 31,16.5 L 31,29.5 L 14,29.5 z M 14,16.5 L 11,14 L 34,14 L 31,16.5 L 14,16.5 z M 11,14 L 11,9 L 15,9 L 15,11 L 20,11 L 20,9 L 25,9 L 25,11 L 30,11 L 30,9 L 34,9 L 34,14" stroke-linejoin="round"/><path d="M 12,35.5 L 33,35.5 M 13,31.5 L 32,31.5 M 14,29.5 L 31,29.5" fill="none" class="hc-detail"/></g>`,
    n: `<g><path d="M 22,10 C 32.5,11 38.5,18 38,39 L 15,39 C 15,30 25,32.5 23,18"/><path d="M 24,18 C 24.38,20.91 18.45,25.37 16,27 C 13,29 13.18,31.34 11,31 C 9.958,30.06 12.41,27.96 11,28 C 10,28 11.19,29.23 10,30 C 9,30 5.997,31 6,26 C 6,24 12,14 12,14 C 12,14 13.89,12.1 14,10.5 C 13.27,9.506 13.5,8.5 13.5,7.5 C 14.5,6.5 16.5,10 16.5,10 L 18.5,10 C 18.5,10 19.28,8.008 21,7 C 22,7 22,10 22,10"/><circle cx="15.5" cy="14.5" r="1.2" class="hc-eye"/></g>`,
    b: `<g><path d="M 9,36 C 12.39,35.03 19.11,36.43 22.5,34 C 25.89,36.43 32.61,35.03 36,36 C 36,36 37.65,36.54 39,38 C 38.32,38.97 37.35,38.99 36,38.5 C 32.61,37.53 25.89,38.96 22.5,37.5 C 19.11,38.96 12.39,37.53 9,38.5 C 7.646,38.99 6.677,38.97 6,38 C 7.354,36.06 9,36 9,36 z M 15,32 C 17.5,34.5 27.5,34.5 30,32 C 30.5,30.5 30,30 30,30 C 30,27.5 27.5,26 27.5,26 C 33,24.5 33.5,14.5 22.5,10.5 C 11.5,14.5 12,24.5 17.5,26 C 17.5,26 15,27.5 15,30 C 15,30 14.5,30.5 15,32 z M 25,8 A 2.5,2.5 0 1,1 20,8 A 2.5,2.5 0 1,1 25,8 z"/><path d="M 17.5,26 L 27.5,26 M 15,30 L 30,30 M 22.5,15.5 L 22.5,20.5 M 20,18 L 25,18" fill="none" class="hc-detail"/></g>`,
    q: `<g><path d="M 9,26 C 17.5,24.5 30,24.5 36,26 L 38.5,13.5 L 31,25 L 30.7,10.9 L 25.5,24.5 L 22.5,10 L 19.5,24.5 L 14.3,10.9 L 14,25 L 6.5,13.5 L 9,26 z M 9,26 C 9,28 10.5,28 11.5,30 C 12.5,31.5 12.5,31 12,33.5 C 10.5,34.5 11,36 11,36 C 9.5,37.5 11,38.5 11,38.5 C 17.5,39.5 27.5,39.5 34,38.5 C 34,38.5 35.5,37.5 34,36 C 34,36 34.5,34.5 33,33.5 C 32.5,31 32.5,31.5 33.5,30 C 34.5,28 36,28 36,26 C 27.5,24.5 17.5,24.5 9,26 z"/><circle cx="6" cy="12" r="1.8"/><circle cx="14" cy="9" r="1.8"/><circle cx="22.5" cy="8" r="1.8"/><circle cx="31" cy="9" r="1.8"/><circle cx="39" cy="12" r="1.8"/><path d="M 11.5,30 C 15,29 30,29 33.5,30 M 12,33.5 C 18,32.5 27,32.5 33,33.5" fill="none" class="hc-detail"/></g>`,
    k: `<g><path d="M 22.5,11.63 L 22.5,6 M 20,8 L 25,8" fill="none" stroke-width="2.2"/><path d="M 22.5,25 C 22.5,25 27,17.5 25.5,14.5 C 25.5,14.5 24.5,12 22.5,12 C 20.5,12 19.5,14.5 19.5,14.5 C 18,17.5 22.5,25 22.5,25"/><path d="M 11.5,37 C 17,40.5 27,40.5 32.5,37 L 32.5,30 C 32.5,30 41.5,25.5 38.5,19.5 C 34.5,13 25,16 22.5,23.5 L 22.5,27 L 22.5,23.5 C 19,16 9.5,13 6.5,19.5 C 3.5,25.5 11.5,29.5 11.5,29.5 L 11.5,37 z"/><path d="M 11.5,30 C 17,27 27,27 32.5,30 M 11.5,33.5 C 17,30.5 27,30.5 32.5,33.5 M 11.5,37 C 17,34 27,34 32.5,37" fill="none" class="hc-detail"/></g>`
  };

  function pieceSVG(ch) {
    const w = ch === ch.toUpperCase(), type = ch.toLowerCase(), side = w ? "w" : "b";
    // NOTE: no inline <style> here - the site's CSP forbids it. Colours are presentation attributes + classes in chess.css.
    return `<svg viewBox="0 0 45 45" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hc-wg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#fffdf9"/><stop offset="55%" stop-color="#f3ead8"/><stop offset="100%" stop-color="#d5c09e"/>
        </linearGradient>
        <linearGradient id="hc-bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#4a3525"/><stop offset="50%" stop-color="#261910"/><stop offset="100%" stop-color="#120b07"/>
        </linearGradient>
      </defs>
      <g class="hc-p hc-p-${side}" fill="url(#hc-${w ? "wg" : "bg"})" stroke="${w ? "#2c1808" : "#110904"}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${SHAPES[type] || ""}</g>
    </svg>`;
  }

  let inited = false, s = null, sel = null, role = "white", box = null;
  function cells(fen) { const out = []; for (const row of fen.split(" ")[0].split("/")) for (const ch of row) { if (/\d/.test(ch)) for (let i = 0; i < +ch; i++) out.push(null); else out.push(ch); } return out; }
  function draw() {
    if (!box || !s) return; box.replaceChildren();
    const msg = { checkmate: "Checkmate! " + (s.turn === "white" ? "Black" : "White") + " wins.", stalemate: "Stalemate - draw.", draw: "Draw.", check: "Check! " + s.turn + " to move.", play: s.turn + " to move" }[s.status];
    box.append(H.el("p", "hc-status", "You are " + role + " · " + msg));
    const board = H.el("div", "hc-board"), c = cells(s.fen), flip = role === "black";
    const ids = [...Array(64).keys()]; if (flip) ids.reverse();
    for (const i of ids) {
      const f = i % 8, r = Math.floor(i / 8), name = "abcdefgh"[f] + (8 - r), ch = c[i];
      const q = H.el("div", "hc-sq " + ((f + r) % 2 ? "hc-d" : "hc-l") + (sel === name ? " hc-sel" : "") + (sel && s.legal[sel] && s.legal[sel].includes(name) ? " hc-dot" : ""));
      if ((flip ? f === 7 : f === 0)) q.append(H.el("span", "hc-coord hc-coord-r", String(8 - r)));
      if ((flip ? r === 0 : r === 7)) q.append(H.el("span", "hc-coord hc-coord-f", "abcdefgh"[f]));
      if (ch) {
        const pWrap = H.el("div", "hc-piece");
        pWrap.innerHTML = pieceSVG(ch);
        q.append(pWrap);
      }
      q.onclick = () => click(name, ch); board.append(q);
    }
    box.append(board);
    if (s.status === "checkmate" || s.status === "stalemate" || s.status === "draw") box.append(H.btn("New game", () => SocketClient.emit("chess:reset")));
  }
  function click(name, ch) {
    if (!s || s.turn !== role || s.status === "checkmate") return;
    if (sel && s.legal[sel] && s.legal[sel].includes(name)) {
      const piece = cells(s.fen)["abcdefgh".indexOf(sel[0]) + (8 - +sel[1]) * 8], last = name[1] === "8" || name[1] === "1";
      SocketClient.emit("chess:move", { from: sel, to: name, promotion: piece && piece.toLowerCase() === "p" && last ? "q" : undefined }); sel = null; return;
    }
    sel = s.legal[name] ? name : null; draw();
  }
  const open = () => { const o = H.overlay("Chess", () => { box = null; }); box = o.box; SocketClient.emit("chess:sync"); };
  const init = () => { if (inited) return; inited = true; SocketClient.on("chess:state", (d) => { s = d; if (d.role) role = d.role; sel = null; draw(); }); };
  return { init, open };
})();'''