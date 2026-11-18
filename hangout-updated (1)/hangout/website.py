"""website.py - the main page: HTML shell, theme CSS, animations, login/room screens and dashboard."""
PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#e68fb3">
  <meta name="description" content="A little corner of the internet for two: photo booth, chess, car races, bouquets and notes.">
  <title>Hangout for two</title>
  <link rel="icon" type="image/png" href="/heart.png">
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Nunito:wght@400;700;800&display=swap">
  <link rel="stylesheet" href="css/base_theme.css">
  <link rel="stylesheet" href="css/animations.css">
</head>
<body>
  <div id="bg"></div><div id="shade"></div><div id="glow"></div>
  <div id="net" role="status" aria-live="polite" hidden></div>
  <main id="app">
    <section id="VIEW_WELCOME" class="view active">
      <h1>Hi there. Glad you’re here.</h1>
      <p class="tagline">A little corner of the internet for two.</p>
      <button id="btnEnter" class="btn enter">Enter<span class="arr">→</span></button>
    </section>

    <section id="VIEW_NAME" class="view">
      <label for="nameInput" class="lead">Enter your name</label>
      <input id="nameInput" maxlength="20" autocomplete="off" placeholder="2–20 letters or numbers">
      <p id="nameErr" class="err" role="alert"></p>
      <button id="btnContinue" class="btn">Continue</button>
    </section>

    <section id="VIEW_ROOM_HUB" class="view">
      <h2 id="hubTitle"></h2>
      <div class="cards">
        <div class="card hub">
          <span class="ico t-create" aria-hidden="true"></span>
          <h3>Create a room</h3>
          <p class="blurb">Get a code and send it to your person.</p>
          <button id="btnCreate" class="btn">Create</button>
          <div id="codeRow" class="coderow" hidden>
            <p id="roomCode" class="code"></p>
            <button id="btnCopy" class="btn ghost" type="button">Copy</button>
          </div>
          <p id="waitMsg"></p>
        </div>
        <div class="card hub">
          <span class="ico t-join" aria-hidden="true"></span>
          <h3>Join a room</h3>
          <p class="blurb">Already have a code? Pop it in.</p>
          <input id="codeInput" maxlength="7" placeholder="K9P-4X2" autocomplete="off" autocapitalize="characters" spellcheck="false">
          <button id="btnJoin" class="btn">Join</button>
          <p id="joinErr" class="err" role="alert"></p>
        </div>
      </div>
    </section>

    <section id="VIEW_DASHBOARD" class="view">
      <h2 id="dashTitle"></h2>
      <p id="dashSub" class="tagline"></p>
      <div id="activityGrid" class="cards acts"></div>
    </section>
  </main>
  <noscript><p class="noscript">Hangout needs JavaScript to run.</p></noscript>
  <script src="https://cdn.jsdelivr.net/npm/socket.io-client@4.7.5/dist/socket.io.min.js"></script>
  <script src="js/socket_client.js"></script>
  <script src="js/fx.js"></script>
  <script src="js/ui.js"></script>
  <!--FEATURES-->
  <script src="js/main_router.js"></script>
</body>
</html>
'''
ASSETS = {
  "css/base_theme.css": r''':root {
  --ink: #140810; --muted: #5e2f48; --rose: #d9488f; --rose-2: #ff7eb6; --err: #c0264f;
  --glass: rgba(255,255,255,.74); --glass-hi: rgba(255,255,255,.9); --edge: rgba(217,72,143,.28); --r: 20px;
  --shadow: 0 14px 40px -12px rgba(120,20,70,.35);
  font-family: "Nunito", "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
html { background: #e68fb3; }
body { background: transparent; color: var(--ink); -webkit-font-smoothing: antialiased; }
h1, h2, h3, .lead, .btn { font-family: "Cormorant Garamond", "Playfair Display", Georgia, "Times New Roman", serif; }
h1, h2, h3 { color: var(--ink); margin: 0; }
h1 { font-size: clamp(2.3rem, 6vw, 3.8rem); font-weight: 600; letter-spacing: .02em; text-shadow: 0 2px 18px rgba(255,255,255,.6); }
h2 { font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 700; text-shadow: 0 2px 14px rgba(255,255,255,.6); }
h3 { font-size: 1.35rem; font-weight: 700; }
p { margin: 0; color: var(--muted); }
.tagline { font-size: 1.1rem; color: #4a1d37; text-shadow: 0 1px 10px rgba(255,255,255,.7); }
.lead { font-size: 1.7rem; font-weight: 600; }
.blurb { font-size: .95rem; line-height: 1.35; }
.noscript { position: fixed; inset: auto 0 20px; text-align: center; }

#app { min-height: 100%; display: grid; place-items: center; padding: 28px 20px 40px; }
.view { display: none; flex-direction: column; align-items: center; gap: 16px; text-align: center; width: min(820px, 100%); }
.view.active { display: flex; }
#VIEW_WELCOME { gap: 22px; min-height: 70vh; justify-content: center; }

/* ---------- background layers ---------- */
#bg { position: fixed; inset: -6%; z-index: -3; background: #e68fb3 url("/wallpaper.jpg") center / cover no-repeat; will-change: transform; }
#shade { position: fixed; inset: 0; z-index: -2; pointer-events: none; background: radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(12,0,8,.42) 100%); }
#glow { position: fixed; left: 0; top: 0; width: 400px; height: 400px; z-index: -1; pointer-events: none; background: radial-gradient(circle, rgba(255,255,255,.5), rgba(255,255,255,0) 65%); }
#sweep { position: fixed; inset: 0; z-index: -2; pointer-events: none; mix-blend-mode: soft-light; background: radial-gradient(circle at 30% 30%, rgba(255,255,255,.55), transparent 45%), radial-gradient(circle at 75% 70%, rgba(255,190,220,.5), transparent 50%); background-size: 170% 170%; animation: drift 16s ease-in-out infinite alternate; }
@keyframes drift { from { background-position: 0% 0%; } to { background-position: 100% 100%; } }

/* ---------- buttons + inputs ---------- */
.btn { padding: 12px 28px; border: 0; border-radius: 999px; background: linear-gradient(135deg, var(--rose-2), var(--rose)); color: #fff;
  font-size: 1.1rem; letter-spacing: .2em; text-transform: uppercase; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px -8px rgba(217,72,143,.8), inset 0 1px 0 rgba(255,255,255,.4); transition: transform .2s, box-shadow .2s, filter .2s; }
.btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 14px 26px -10px rgba(217,72,143,.9), inset 0 1px 0 rgba(255,255,255,.4); filter: saturate(1.1); }
.btn:active:not(:disabled) { transform: translateY(0) scale(.97); }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.btn.ghost { background: rgba(255,255,255,.85); color: var(--rose); border: 1px solid var(--edge); box-shadow: none; padding: 8px 18px; font-size: .85rem; }
input { width: 100%; max-width: 300px; padding: 13px 16px; border-radius: 14px; border: 1px solid var(--edge); background: rgba(255,255,255,.95); color: var(--ink); font: inherit; text-align: center; transition: box-shadow .2s, border-color .2s; }
input:focus { outline: none; border-color: var(--rose); box-shadow: 0 0 0 4px rgba(217,72,143,.22); }
input::placeholder { color: #a98597; }
:focus-visible { outline: 3px solid var(--rose); outline-offset: 3px; }
.err { color: var(--err); min-height: 1.2em; font-weight: 700; }

/* ---------- cards ---------- */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 18px; width: 100%; }
.card { position: relative; background: var(--glass); border: 1px solid var(--edge); border-radius: var(--r);
  backdrop-filter: blur(14px) saturate(1.2); -webkit-backdrop-filter: blur(14px) saturate(1.2);
  padding: 24px 20px; display: flex; flex-direction: column; align-items: center; gap: 12px; box-shadow: var(--shadow); }
.code { font-size: 2rem; font-weight: 800; letter-spacing: .12em; color: var(--ink); }
.coderow { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: center; }
.coderow[hidden], #net[hidden] { display: none; }

/* ---------- activity cards (dashboard) ---------- */
.acts { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.act { font: inherit; color: inherit; cursor: pointer; text-align: center; overflow: hidden; transition: transform .35s cubic-bezier(.3,1.4,.5,1), box-shadow .3s, border-color .3s, background .3s; }
.act::before { content: ""; position: absolute; inset: 0; background: radial-gradient(circle at 50% -20%, var(--b), transparent 65%); opacity: 0; transition: opacity .35s; pointer-events: none; }
.act:hover:not(:disabled), .act:focus-visible { transform: translateY(-7px) scale(1.02); border-color: var(--b); background: var(--glass-hi); box-shadow: 0 22px 44px -14px var(--b); }
.act:hover:not(:disabled)::before, .act:focus-visible::before { opacity: .16; }
.act:active:not(:disabled) { transform: translateY(-2px) scale(.99); }
.act:disabled { opacity: .55; cursor: not-allowed; }
.act h3, .act p, .act .go, .act .ico { position: relative; }
.go { font-size: .8rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: var(--b); transition: letter-spacing .3s; }
.act:hover:not(:disabled) .go { letter-spacing: .26em; }

/* ---------- icon badges ---------- */
.ico { position: relative; width: 62px; height: 62px; border-radius: 21px; display: grid; place-items: center;
  background: linear-gradient(145deg, var(--a, #ff9ac4), var(--b, #e0408a)); box-shadow: 0 12px 22px -8px var(--b, #e0408a), inset 0 1px 0 rgba(255,255,255,.6), inset 0 -3px 6px rgba(0,0,0,.12);
  transition: transform .45s cubic-bezier(.3,1.7,.5,1); }
.ico::after { content: ""; position: absolute; inset: 3px 3px 50% 3px; border-radius: 18px 18px 40px 40px; background: linear-gradient(rgba(255,255,255,.5), rgba(255,255,255,0)); pointer-events: none; }
.ico svg { position: relative; z-index: 1; width: 31px; height: 31px; fill: none; stroke: #fff; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 2px 3px rgba(0,0,0,.28)); }
.act:hover:not(:disabled) .ico, .hub:hover .ico { transform: translateY(-4px) rotate(-8deg) scale(1.1); }
.act:hover:not(:disabled) .ico svg { animation: wiggle .7s ease; }
@keyframes wiggle { 0%,100% { rotate: 0deg; } 25% { rotate: -10deg; } 60% { rotate: 8deg; } }
.act, .hub { --a: #ff9ac4; --b: #e0408a; }
.t-photo  { --a: #ff9ac4; --b: #e0408a; }
.t-car    { --a: #ffc27a; --b: #ee5a36; }
.t-duel   { --a: #c3a6ff; --b: #7447ee; }
.t-bouq   { --a: #9fe6b0; --b: #23a066; }
.t-chess  { --a: #8c88a8; --b: #2b2646; }
.t-notes  { --a: #ffe08f; --b: #e1951f; }
.t-create { --a: #ff9ac4; --b: #d9488f; }
.t-join   { --a: #9ad7ff; --b: #3b82e6; }

/* ---------- welcome button ---------- */
.btn.enter { position: relative; overflow: hidden; background: #140810; color: #fff; border: 1px solid rgba(255,255,255,.55); padding: 16px 46px; font-size: 1.05rem; letter-spacing: .32em; box-shadow: 0 12px 34px rgba(0,0,0,.4), 0 0 0 6px rgba(255,255,255,.25); transition: transform .3s, box-shadow .3s, letter-spacing .3s; animation: breathe 2.8s ease-in-out infinite; }
.btn.enter::after { content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%; background: linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent); transform: skewX(-20deg); animation: shine 3.2s ease-in-out infinite; }
.btn.enter .arr { display: inline-block; margin-left: 14px; color: #ff9ec7; transition: transform .3s; }
.btn.enter:hover:not(:disabled) { transform: translateY(-3px); letter-spacing: .38em; box-shadow: 0 18px 40px rgba(0,0,0,.5), 0 0 0 9px rgba(255,255,255,.35); }
.btn.enter:hover .arr { transform: translateX(8px); }
@keyframes shine { 0%,55% { left: -60%; } 100% { left: 130%; } }
@keyframes breathe { 0%,100% { box-shadow: 0 12px 34px rgba(0,0,0,.4), 0 0 0 6px rgba(255,255,255,.25); } 50% { box-shadow: 0 12px 34px rgba(0,0,0,.4), 0 0 0 12px rgba(255,255,255,.1); } }

/* ---------- falling cherry blossoms (spawned + animated by js/fx.js) ---------- */
.blossom, .burst { position: fixed; left: 0; top: 0; pointer-events: none; user-select: none; -webkit-user-drag: none; will-change: transform, opacity; opacity: 0; filter: drop-shadow(0 2px 3px rgba(150,40,90,.28)); }
.blossom { z-index: -1; }
.burst { z-index: 50; }

/* ---------- status banner ---------- */
#net { position: fixed; top: 14px; left: 50%; translate: -50% 0; z-index: 60; max-width: min(92vw, 460px); padding: 10px 20px; border-radius: 999px; background: #140810; color: #fff; font-weight: 700; font-size: .95rem; text-align: center; box-shadow: 0 12px 30px rgba(0,0,0,.35); animation: fadeIn .3s both; }
#net.bad { background: #b3173f; }

@media (max-width: 520px) { .card { padding: 20px 16px; } .ico { width: 56px; height: 56px; } .btn.enter { padding: 14px 34px; } }
''',
  "css/animations.css": r'''.fade-in { animation: fadeIn .7s ease both; }
.fade-out-slow { animation: fadeOutSlow .6s ease forwards; }
.slide-fade-out { animation: slideFadeOut .4s ease forwards; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes fadeOutSlow { from { opacity: 1; transform: scale(1); } to { opacity: 0; transform: scale(.96); } }
@keyframes slideFadeOut { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-20px); } }
@keyframes swayLeftRight { 0%, 100% { transform: translateX(-24px) rotate(-3deg); } 50% { transform: translateX(24px) rotate(3deg); } }
@keyframes petalFall { from { transform: translateY(-10vh) rotate(0); } to { transform: translateY(110vh) rotate(540deg); } }
@keyframes cardIn { from { opacity: 0; transform: translateY(22px) scale(.96); } to { opacity: 1; transform: none; } }
.view.active .acts > .act, .view.active .cards > .hub { animation: cardIn .6s cubic-bezier(.2,.9,.3,1.2) both; }
.acts > .act:nth-child(2) { animation-delay: .06s; } .acts > .act:nth-child(3) { animation-delay: .12s; }
.acts > .act:nth-child(4) { animation-delay: .18s; } .acts > .act:nth-child(5) { animation-delay: .24s; } .acts > .act:nth-child(6) { animation-delay: .3s; }
.cards > .hub:nth-child(2) { animation-delay: .1s; }
@media (prefers-reduced-motion: reduce) { * { animation-duration: .01ms !important; animation-delay: 0s !important; transition-duration: .01ms !important; } }
''',
  "js/socket_client.js": r'''"use strict";
window.SocketClient = (() => {
  let sock = null;
  const status = [];   // callbacks: (state) => void, state = "online" | "offline"
  const tell = (s) => status.forEach((fn) => { try { fn(s); } catch (_) {} });
  return {
    connect(token) {
      return new Promise((resolve, reject) => {
        sock = io({ auth: { token }, transports: ["websocket"] });
        sock.once("connect", resolve);
        sock.once("connect_error", (e) => { sock.close(); reject(e); });
        sock.on("connect", () => tell("online"));
        sock.on("disconnect", () => tell("offline"));
      });
    },
    emit: (ev, data) => sock && sock.emit(ev, data),
    on: (ev, fn) => sock && sock.on(ev, fn),
    onStatus: (fn) => status.push(fn),
  };
})();
''',
  "js/fx.js": r'''(() => {
  const bg = document.getElementById("bg"), glow = document.getElementById("glow");
  if (!bg || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const sweep = document.createElement("div"); sweep.id = "sweep"; document.body.prepend(sweep);

  // ---- wallpaper parallax + cursor glow ----
  let tx = 0, ty = 0, x = 0, y = 0;
  addEventListener("pointermove", (e) => {
    tx = e.clientX / innerWidth - .5; ty = e.clientY / innerHeight - .5;
    glow.style.transform = "translate(" + (e.clientX - 200) + "px," + (e.clientY - 200) + "px)";
  });
  (function loop() {
    x += (tx - x) * .06; y += (ty - y) * .06;
    bg.style.transform = "translate(" + (-x * 44) + "px," + (-y * 30) + "px) scale(1.1)";
    requestAnimationFrame(loop);
  })();

  // ---- cherry blossom art (inline SVG data URIs: nothing to download, CSP-safe) ----
  const NOTCHED = "M20 37 C10 31 5 20 10 10 C12 6 15 4 17 4 C18 6 19 7 20 8 C21 7 22 6 23 4 C25 4 28 6 30 10 C35 20 30 31 20 37 Z";
  const LOBE = "M20 20 C13 16 11 9 14.5 4.5 C16.5 2.5 19 3.5 20 6 C21 3.5 23.5 2.5 25.5 4.5 C29 9 27 16 20 20 Z";
  const uri = (body) => "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">' + body + "</svg>");
  const grad = (a, b) => '<defs><linearGradient id="g" x1="0.2" y1="0" x2="0.8" y2="1"><stop offset="0" stop-color="' + a + '"/><stop offset="1" stop-color="' + b + '"/></linearGradient></defs>';
  const TONES = [["#fff6f9", "#ffc6dc"], ["#ffe1ee", "#ff9ec4"], ["#ffeef5", "#f58db4"]];
  const petalArt = TONES.map(([a, b]) => uri(grad(a, b) + '<path d="' + NOTCHED + '" fill="url(#g)"/><path d="M20 35 L20 13" stroke="#d9588f" stroke-opacity=".28" stroke-width=".9" stroke-linecap="round"/>'));
  const flowerArt = TONES.map(([a, b]) => {
    let lobes = "";
    for (let i = 0; i < 5; i++) lobes += '<path d="' + LOBE + '" fill="url(#g)" stroke="#e0508a" stroke-opacity=".25" stroke-width=".6" transform="rotate(' + (i * 72) + ' 20 20)"/>';
    return uri(grad(a, b) + lobes + '<circle cx="20" cy="20" r="3" fill="#e0508a" fill-opacity=".85"/><circle cx="20" cy="20" r="1.3" fill="#ffd36b"/>');
  });
  const rnd = (lo, hi) => lo + Math.random() * (hi - lo);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  // ---- falling blossoms ----
  let alive = 0;
  const MAX = innerWidth < 600 ? 16 : 30;
  function fall(seed) {
    if (alive >= MAX) return;
    const isFlower = Math.random() < .3;
    const el = document.createElement("img");
    el.className = "blossom"; el.alt = ""; el.draggable = false;
    el.src = pick(isFlower ? flowerArt : petalArt);
    const size = isFlower ? rnd(30, 50) : rnd(20, 36);
    el.style.width = size + "px"; el.style.height = size + "px";
    const startX = rnd(-5, 105) * innerWidth / 100, drift = rnd(-60, 220), amp = rnd(18, 60);
    const freq = rnd(1, 2.4), phase = rnd(0, 6.28), spin = rnd(180, 720) * (Math.random() < .5 ? -1 : 1);
    const flutter = rnd(35, 75), dur = rnd(9, 17) * 1000, N = 16, frames = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N, sw = Math.sin(t * Math.PI * 2 * freq + phase);
      frames.push({
        transform: "translate3d(" + (startX + drift * t + sw * amp).toFixed(1) + "px," + (-8 + 116 * t).toFixed(2) + "vh,0) perspective(300px) rotateZ(" + (spin * t).toFixed(0) + "deg) rotateX(" + (Math.cos(t * Math.PI * 2 * freq + phase) * flutter).toFixed(0) + "deg)",
        opacity: t < .06 ? t / .06 * .95 : t > .92 ? (1 - t) / .08 * .95 : .95,
      });
    }
    document.body.append(el); alive++;
    const anim = el.animate(frames, { duration: dur, easing: "linear", fill: "forwards" });
    if (seed) anim.currentTime = rnd(.05, .85) * dur;   // pre-scatter blossoms on load
    anim.onfinish = () => { el.remove(); alive--; };
  }
  for (let i = 0; i < (innerWidth < 600 ? 7 : 14); i++) fall(true);
  setInterval(() => { if (!document.hidden) fall(false); }, 520);

  // ---- click: a little burst of petals ----
  addEventListener("pointerdown", (e) => {
    for (let i = 0; i < 7; i++) {
      const el = document.createElement("img");
      el.className = "burst"; el.alt = ""; el.draggable = false; el.src = pick(petalArt);
      const size = rnd(18, 30); el.style.width = size + "px"; el.style.height = size + "px";
      const ang = rnd(0, 6.28), dist = rnd(40, 110), rot = rnd(-200, 200);
      const x0 = e.clientX - size / 2, y0 = e.clientY - size / 2;
      el.animate([
        { transform: "translate3d(" + x0 + "px," + y0 + "px,0) scale(.4) rotate(0deg)", opacity: 0 },
        { transform: "translate3d(" + (x0 + Math.cos(ang) * dist * .6) + "px," + (y0 + Math.sin(ang) * dist * .6 - 10) + "px,0) scale(1) rotate(" + (rot * .5) + "deg)", opacity: 1, offset: .35 },
        { transform: "translate3d(" + (x0 + Math.cos(ang) * dist) + "px," + (y0 + Math.sin(ang) * dist + 46) + "px,0) scale(.8) rotate(" + rot + "deg)", opacity: 0 },
      ], { duration: rnd(800, 1200), easing: "ease-out", fill: "forwards" }).onfinish = () => el.remove();
      document.body.append(el);
    }
  });
})();
''',
  "js/ui.js": r'''"use strict";
window.Hang = (() => {
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const btn = (label, fn, dis) => { const b = el("button", "btn", label); b.disabled = !!dis; b.onclick = fn; return b; };
  function overlay(title, onClose) {
    const ov = el("div"); ov.style.cssText = "position:fixed;inset:0;z-index:20;background:radial-gradient(circle at 20% 15%,#ffd6e8,#fff 70%);overflow:auto;padding:20px;display:flex;flex-direction:column;align-items:center;gap:12px;color:#140810";
    const box = el("div"); box.style.cssText = "width:min(900px,100%);display:flex;flex-direction:column;align-items:center;gap:10px";
    const close = () => { onClose && onClose(); ov.remove(); };
    const back = btn("Back", close); back.style.cssText = "position:fixed;top:14px;right:14px;z-index:25;padding:8px 20px";
    ov.append(el("h2", "", title), box, back); document.body.append(ov); return { box, close };
  }
  function toast(text, yes, no) {
    const t = el("div"); t.style.cssText = "position:fixed;top:14px;right:14px;z-index:40;background:#fff;color:#140810;border:1px solid #d9488f;border-radius:14px;padding:12px;max-width:300px;text-align:center;box-shadow:0 14px 34px rgba(120,20,70,.3)";
    const row = el("div"); row.style.cssText = "display:flex;gap:8px;margin-top:8px;justify-content:center";
    row.append(btn("Yes", () => { t.remove(); yes(); }), btn("No", () => { t.remove(); no && no(); })); t.append(el("p", "", text), row); document.body.append(t);
  }
  return { el, btn, overlay, toast };
})();
''',
  "js/main_router.js": r'''(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const NAME_RE = /^[A-Za-z0-9 ]{2,20}$/;
  const NS = "http://www.w3.org/2000/svg";

  // Hand-drawn 24x24 line icons (inline SVG: nothing to download, CSP-safe).
  const ICONS = {
    camera: '<path d="M4 8.5h3.2L9 6h6l1.8 2.5H20V19H4z"/><circle cx="12" cy="13.4" r="3.6"/><path d="M17.2 11.2h.01"/>',
    car: '<path d="M3.5 16.5v-3.2l1.9-5.3h13.2l1.9 5.3v3.2z"/><path d="M3.5 16.5V19M20.5 16.5V19M6 11.8h12"/><circle cx="7.6" cy="14.2" r=".9"/><circle cx="16.4" cy="14.2" r=".9"/>',
    hanger: '<path d="M12 9.5V8.6a2.1 2.1 0 1 0-2.1-2.1"/><path d="M12 9.5 3.6 16.2a1.3 1.3 0 0 0 .8 2.3h15.2a1.3 1.3 0 0 0 .8-2.3z"/>',
    flower: '<circle cx="12" cy="9" r="1.7"/><circle cx="12" cy="4.9" r="2.1"/><circle cx="15.9" cy="7.8" r="2.1"/><circle cx="14.4" cy="12.2" r="2.1"/><circle cx="9.6" cy="12.2" r="2.1"/><circle cx="8.1" cy="7.8" r="2.1"/><path d="M12 14.2V21M12 18c-2.6 0-3.8-1.4-4-3M12 17c2.2 0 3.5-1.2 3.8-2.6"/>',
    pawn: '<circle cx="12" cy="6.4" r="2.7"/><path d="M9.8 10.4h4.4M10.4 10.4c0 2.4-.6 3.6-2 5.2h7.2c-1.4-1.6-2-2.8-2-5.2M7.4 19h9.2M8 15.6l-.6 3.4M16 15.6l.6 3.4"/>',
    note: '<rect x="3.5" y="5.5" width="17" height="13" rx="2.4"/><path d="m4.4 7.4 7.6 5.8 7.6-5.8"/><path d="M12 17.2s-2.1-1.4-2.1-2.7a1.2 1.2 0 0 1 2.1-.7 1.2 1.2 0 0 1 2.1.7c0 1.3-2.1 2.7-2.1 2.7z" fill="#fff" stroke-width="1"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    key: '<circle cx="8" cy="12" r="3.6"/><path d="M11.6 12H20M17 12v3M20 12v2.4"/>',
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" xmlns="${NS}">${ICONS[name]}</svg>`;

  // label must match each feature's NAME (= window.Features key)
  const ACTIVITIES = [
    { label: "Photo Booth",     tone: "t-photo", icon: "camera", blurb: "Strike a pose together, four frames and a countdown." },
    { label: "Car Race",        tone: "t-car",   icon: "car",    blurb: "3D buggy laps with boosts, rockets and TNT." },
    { label: "Dress Duel",      tone: "t-duel",  icon: "hanger", blurb: "Style battle on the runway, then a sword duel." },
    { label: "Bouquet Builder", tone: "t-bouq",  icon: "flower", blurb: "Pick the blooms and wrap a gift for them." },
    { label: "Chess",           tone: "t-chess", icon: "pawn",   blurb: "A classic game of kings, just the two of you." },
    { label: "Custom Notes",    tone: "t-notes", icon: "note",   blurb: "Write a note on pretty paper and send it over." },
  ];
  let current = "VIEW_WELCOME";
  let playerName = "";
  let bound = false, netTimer = 0;

  function say(msg, bad, ms) {   // small banner that works from any screen
    const n = $("net"); n.textContent = msg; n.classList.toggle("bad", !!bad); n.hidden = false;
    clearTimeout(netTimer); if (ms) netTimer = setTimeout(() => { n.hidden = true; }, ms);
  }

  function go(next, outClass, ms) {
    const cur = $(current);
    current = next;
    cur.classList.add(outClass);
    setTimeout(() => {
      cur.classList.remove("active", outClass, "fade-in");
      $(next).classList.add("active", "fade-in");
    }, ms);
  }

  function decorateHub() {
    document.querySelector(".t-create").innerHTML = icon("plus");
    document.querySelector(".t-join").innerHTML = icon("key");
  }

  function buildDashboard() {
    const grid = $("activityGrid");
    grid.replaceChildren();
    for (const a of ACTIVITIES) {
      const feat = (window.Features || {})[a.label];   // a feature file registers itself here
      const card = document.createElement("button");
      card.type = "button"; card.className = "card act " + a.tone; card.disabled = !feat;
      const ico = document.createElement("span"); ico.className = "ico"; ico.innerHTML = icon(a.icon);
      const title = document.createElement("h3"); title.textContent = a.label;
      const blurb = document.createElement("p"); blurb.className = "blurb"; blurb.textContent = a.blurb;
      const goEl = document.createElement("span"); goEl.className = "go"; goEl.textContent = feat ? "Open →" : "Coming soon";
      card.append(ico, title, blurb, goEl);
      if (feat) card.onclick = () => feat.open();
      grid.append(card);
    }
  }

  function bindSocket() {
    if (bound) return; bound = true;
    SocketClient.onStatus((s) => { if (s === "offline") say("Connection lost. Reconnecting…", true); else if (!$("net").hidden) say("Back online ✓", false, 1800); });
    SocketClient.on("room:created", ({ code }) => {
      $("roomCode").textContent = code; $("codeRow").hidden = false;
      $("waitMsg").textContent = "Share this code. Waiting for your partner…";
    });
    SocketClient.on("room:ready", ({ code, partner }) => {
      $("dashTitle").textContent = `${playerName} & ${partner}`;
      $("dashSub").textContent = `Room ${code} · pick something to do together`;
      buildDashboard();
      Object.values(window.Features || {}).forEach((f) => f.init());
      if (current !== "VIEW_DASHBOARD") go("VIEW_DASHBOARD", "slide-fade-out", 400);
    });
    SocketClient.on("room:error", ({ message }) => {
      if (current === "VIEW_ROOM_HUB") $("joinErr").textContent = message; else say(message, true, 2500);
    });
    SocketClient.on("room:closed", () => {
      say("Your partner left. The room was closed.", true);
      setTimeout(() => location.reload(), 2200);
    });
  }

  async function submitName() {
    const name = $("nameInput").value.trim().replace(/\s+/g, " ");
    if (!NAME_RE.test(name)) { $("nameErr").textContent = "Use 2–20 letters or numbers."; return; }
    $("nameErr").textContent = ""; $("btnContinue").disabled = true;
    try {
      const r = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      if (!r.ok) throw new Error("session");
      const { token } = await r.json();
      await SocketClient.connect(token);
    } catch (e) {
      $("nameErr").textContent = "Couldn’t connect. Try again in a moment.";
      $("btnContinue").disabled = false;
      return;
    }
    playerName = name;
    bindSocket(); decorateHub();
    $("hubTitle").textContent = `Welcome, ${name}`;
    go("VIEW_ROOM_HUB", "slide-fade-out", 400);
  }

  const join = () => { $("joinErr").textContent = ""; SocketClient.emit("room:join", { code: $("codeInput").value }); };

  $("btnEnter").onclick = () => { go("VIEW_NAME", "fade-out-slow", 600); setTimeout(() => $("nameInput").focus(), 700); };
  $("btnContinue").onclick = submitName;
  $("nameInput").addEventListener("keydown", (e) => { if (e.key === "Enter") submitName(); });
  $("btnCreate").onclick = () => { $("joinErr").textContent = ""; SocketClient.emit("room:create"); };
  $("btnJoin").onclick = join;
  $("codeInput").addEventListener("keydown", (e) => { if (e.key === "Enter") join(); });
  $("codeInput").addEventListener("input", (e) => { e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ""); });
  $("btnCopy").onclick = async () => {
    try { await navigator.clipboard.writeText($("roomCode").textContent); $("btnCopy").textContent = "Copied ✓"; }
    catch (_) { $("btnCopy").textContent = "Select & copy"; }
    setTimeout(() => { $("btnCopy").textContent = "Copy"; }, 1800);
  };
})();
''',
}


def page(features):
    """Builds index.html and adds each feature's CSS + JS automatically."""
    tags = "".join(f'<link rel="stylesheet" href="css/{f.SLUG}.css"><script src="js/{f.SLUG}.js"></script>\n  ' for f in features)
    return PAGE.replace("<!--FEATURES-->", tags)
