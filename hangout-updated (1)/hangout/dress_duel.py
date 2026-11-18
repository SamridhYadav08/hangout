"""Dress Duel - Complete 3D Glass Tube Dress to Impress (60s) + 3D Weapon Duel.
Exports NAME, SLUG, CSS, JS, and setup(sio, auth, rooms) for your website,
plus a built-in CLI test/browser runner at the bottom.
"""
import asyncio
import math
import random
import sys
import time
import uuid

# Uses partner_of if already defined in your main file, otherwise defines it
if "partner_of" not in globals():
    try:
        from core import partner_of
    except ImportError:
        def partner_of(rooms, pid):
            code = rooms.by_player.get(pid)
            room = rooms.rooms.get(code)
            if not room:
                return None
            for other_pid, pl in room.players.items():
                if other_pid != pid:
                    return pl
            return None

NAME = "Dress Duel"
SLUG = "duel"

DRESS_SECONDS = 60
REVEAL_SECONDS = 3.5
ARENA_SECONDS = 90
ARENA_MIN_X = -14.0
ARENA_MAX_X = 14.0
MAX_MOVE_SPEED = 9.5

THEMES = [
    "Royal Gala",
    "Cyberpunk Heist",
    "Beach Samurai",
    "Enchanted Forest",
    "Neon Disco",
]

SWATCHES = ["#ff5ca8", "#8c52ff", "#00e5ff", "#ffd166", "#191324", "#f4f1fa"]

# Weapon stats: (base_damage, range_3d_units, cooldown_sec, windup_sec, knockback)
WEAPONS = {
    "lightsaber": (10, 2.75, 0.48, 0.10, 1.2),
    "broadsword": (20, 3.25, 1.15, 0.22, 2.4),
    "daggers":    (6,  1.95, 0.24, 0.06, 0.6),
    "staff":      (13, 4.70, 1.35, 0.20, 1.9),
}

RARITY_POINTS = {"common": 6, "rare": 11, "epic": 17, "legendary": 24}

# 64-item catalogue: (id, name, category, shape, rarity, tags_tuple, weapon_type)
CATALOGUE_LIST = [
    # HAIR (8)
    ("hair_bob", "Silk Bob", "hair", "bob", "common", ("Royal Gala", "Neon Disco"), None),
    ("hair_cyber_pigtails", "Holo Twin-Tails", "hair", "pigtails", "epic", ("Cyberpunk Heist", "Neon Disco"), None),
    ("hair_samurai_bun", "Ronin Topknot", "hair", "bun", "rare", ("Beach Samurai",), None),
    ("hair_royal_updo", "Imperial Updo", "hair", "updo", "legendary", ("Royal Gala",), None),
    ("hair_elf_braids", "Sylvan Braids", "hair", "long_waves", "epic", ("Enchanted Forest", "Royal Gala"), None),
    ("hair_disco_afro", "Starlight Afro", "hair", "afro", "legendary", ("Neon Disco",), None),
    ("hair_beach_waves", "Saltwater Waves", "hair", "long_waves", "common", ("Beach Samurai", "Enchanted Forest"), None),
    ("hair_neon_mohawk", "Laser Spikes", "hair", "spiky", "rare", ("Cyberpunk Heist", "Neon Disco"), None),
    # HATS (8)
    ("hat_none", "No Hat", "hat", "none", "common", (), None),
    ("hat_crown", "Sovereign Crown", "hat", "crown", "legendary", ("Royal Gala",), None),
    ("hat_cyber_visor", "Netrunner Visor", "hat", "visor", "epic", ("Cyberpunk Heist", "Neon Disco"), None),
    ("hat_kasa", "Bamboo Kasa", "hat", "kasa", "rare", ("Beach Samurai",), None),
    ("hat_antlers", "Moonlit Antlers", "hat", "antlers", "legendary", ("Enchanted Forest",), None),
    ("hat_disco_fedora", "Mirrorball Fedora", "hat", "fedora", "rare", ("Neon Disco", "Royal Gala"), None),
    ("hat_tiara", "Starlight Tiara", "hat", "tiara", "epic", ("Royal Gala", "Enchanted Forest"), None),
    ("hat_oni_helm", "Neon Oni Crest", "hat", "oni", "epic", ("Cyberpunk Heist", "Beach Samurai"), None),
    # TOPS (8)
    ("top_corset", "Velvet Corset", "top", "corset", "rare", ("Royal Gala", "Enchanted Forest"), None),
    ("top_cyber_jacket", "Synthwave Bolero", "top", "jacket", "epic", ("Cyberpunk Heist", "Neon Disco"), None),
    ("top_haori", "Wave Haori Coat", "top", "haori", "rare", ("Beach Samurai",), None),
    ("top_leaf_tunic", "Moss & Vine Tunic", "top", "tunic", "common", ("Enchanted Forest",), None),
    ("top_sequin_halter", "Prism Sequin Top", "top", "crop", "epic", ("Neon Disco",), None),
    ("top_royal_blazer", "Gold-Epaulet Coat", "top", "blazer", "legendary", ("Royal Gala",), None),
    ("top_rashguard", "Tidal Armor Top", "top", "crop", "common", ("Beach Samurai", "Cyberpunk Heist"), None),
    ("top_holo_armor", "Aegis Chestplate", "top", "armor", "legendary", ("Cyberpunk Heist", "Beach Samurai"), None),
    # BOTTOMS (8)
    ("bot_pleated_skirt", "Velvet Pleat Skirt", "bottom", "skirt", "common", ("Royal Gala", "Neon Disco"), None),
    ("bot_tech_cargo", "Strapped Tech Pants", "bottom", "cargo", "epic", ("Cyberpunk Heist",), None),
    ("bot_hakama", "Tide Hakama Trousers", "bottom", "hakama", "rare", ("Beach Samurai",), None),
    ("bot_petal_skirt", "Fern Petal Skirt", "bottom", "petal_skirt", "rare", ("Enchanted Forest",), None),
    ("bot_bell_bottoms", "Glitter Flare Pants", "bottom", "flares", "legendary", ("Neon Disco",), None),
    ("bot_board_shorts", "Shogun Surf Shorts", "bottom", "shorts", "common", ("Beach Samurai",), None),
    ("bot_silk_trousers", "Tailored Tux Pants", "bottom", "trousers", "rare", ("Royal Gala",), None),
    ("bot_cyber_greaves", "Neon Exo-Leggings", "bottom", "cargo", "epic", ("Cyberpunk Heist", "Neon Disco"), None),
    # DRESSES (8)
    ("dress_none", "Two-Piece Mode", "dress", "none", "common", (), None),
    ("dress_ballgown", "Empress Crinoline Gown", "dress", "ballgown", "legendary", ("Royal Gala",), None),
    ("dress_cyber_trench", "Matrix Holo-Trench", "dress", "trench", "legendary", ("Cyberpunk Heist",), None),
    ("dress_kimono", "Coral Silk Furisode", "dress", "kimono", "epic", ("Beach Samurai", "Royal Gala"), None),
    ("dress_fairy_gown", "Dryad Blossom Gown", "dress", "fairy", "legendary", ("Enchanted Forest",), None),
    ("dress_disco_jumpsuit", "Studio 77 Jumpsuit", "dress", "jumpsuit", "epic", ("Neon Disco",), None),
    ("dress_mermaid", "Pearl Mermaid Dress", "dress", "mermaid", "rare", ("Royal Gala", "Beach Samurai"), None),
    ("dress_neon_mini", "Laser Grid Dress", "dress", "mini", "rare", ("Neon Disco", "Cyberpunk Heist"), None),
    # SHOES (8)
    ("shoe_heels", "Crystal Stilettos", "shoes", "heels", "epic", ("Royal Gala", "Neon Disco"), None),
    ("shoe_cyber_boots", "Mag-Lev Combat Boots", "shoes", "boots", "epic", ("Cyberpunk Heist",), None),
    ("shoe_geta", "Lacquered Surf Geta", "shoes", "geta", "rare", ("Beach Samurai",), None),
    ("shoe_vine_wraps", "Sylvan Dew Wraps", "shoes", "wraps", "common", ("Enchanted Forest",), None),
    ("shoe_platforms", "Starlight Platforms", "shoes", "platforms", "legendary", ("Neon Disco",), None),
    ("shoe_greaves", "Gilded Sabatons", "shoes", "boots", "rare", ("Royal Gala", "Beach Samurai"), None),
    ("shoe_sandals", "Shell Strap Sandals", "shoes", "geta", "common", ("Beach Samurai", "Enchanted Forest"), None),
    ("shoe_hover_skates", "Pulse Roller Blades", "shoes", "platforms", "legendary", ("Cyberpunk Heist", "Neon Disco"), None),
    # ACCESSORIES (8)
    ("acc_none", "No Accessory", "accessory", "none", "common", (), None),
    ("acc_royal_cape", "Ermine Velvet Cape", "accessory", "cape", "legendary", ("Royal Gala",), None),
    ("acc_fairy_wings", "Iridescent Monarch Wings", "accessory", "wings", "legendary", ("Enchanted Forest",), None),
    ("acc_cyber_halo", "Floating Data Halo", "accessory", "halo", "epic", ("Cyberpunk Heist", "Neon Disco"), None),
    ("acc_surf_shield", "Tsunami Back-Board", "accessory", "board", "rare", ("Beach Samurai",), None),
    ("acc_feather_boa", "Neon Flamingo Boa", "accessory", "boa", "epic", ("Neon Disco", "Royal Gala"), None),
    ("acc_fox_tail", "Kitsune Spirit Tail", "accessory", "tail", "rare", ("Beach Samurai", "Enchanted Forest"), None),
    ("acc_shoulder_drone", "Sentinel Drone", "accessory", "drone", "epic", ("Cyberpunk Heist",), None),
    # WEAPONS (8)
    ("wep_saber_cyan", "Plasma Katana (Saber)", "weapon", "saber_katana", "epic", ("Cyberpunk Heist", "Beach Samurai"), "lightsaber"),
    ("wep_saber_pink", "Disco Saber (Saber)", "weapon", "saber_disco", "rare", ("Neon Disco", "Cyberpunk Heist"), "lightsaber"),
    ("wep_broad_royal", "Sovereign Claymore (Heavy)", "weapon", "broad_royal", "legendary", ("Royal Gala",), "broadsword"),
    ("wep_broad_coral", "Reef Breaker Blade (Heavy)", "weapon", "broad_coral", "epic", ("Beach Samurai", "Enchanted Forest"), "broadsword"),
    ("wep_dagger_fang", "Thorn Twin-Fangs (Daggers)", "weapon", "dagger_thorn", "rare", ("Enchanted Forest", "Cyberpunk Heist"), "daggers"),
    ("wep_dagger_fan", "Gilded War Fans (Daggers)", "weapon", "dagger_fan", "epic", ("Royal Gala", "Neon Disco"), "daggers"),
    ("wep_staff_sylvan", "Elderwood Greatstaff (Staff)", "weapon", "staff_wood", "legendary", ("Enchanted Forest", "Royal Gala"), "staff"),
    ("wep_staff_mic", "Bass Drop Scepter (Staff)", "weapon", "staff_mic", "epic", ("Neon Disco", "Beach Samurai"), "staff"),
]

CATALOGUE = {
    i_id: {"id": i_id, "name": nm, "category": cat, "shape": shp, "rarity": rar, "tags": list(tgs), "weapon_type": wt}
    for (i_id, nm, cat, shp, rar, tgs, wt) in CATALOGUE_LIST
}

CATEGORY_DEFAULTS = {
    "hair": "hair_bob", "hat": "hat_none", "top": "top_corset", "bottom": "bot_pleated_skirt",
    "dress": "dress_none", "shoes": "shoe_heels", "accessory": "acc_none", "weapon": "wep_saber_cyan",
}

games = {}


def default_outfit():
    return {
        "hair": "hair_bob", "hat": "hat_none", "top": "top_corset", "bottom": "bot_pleated_skirt",
        "dress": "dress_none", "shoes": "shoe_heels", "accessory": "acc_none", "weapon": "wep_saber_cyan",
        "colors": {"hair": 4, "hat": 3, "top": 0, "bottom": 4, "dress": 0, "shoes": 0, "accessory": 2, "weapon": 2},
    }


def sanitize_outfit(raw):
    clean = default_outfit()
    if not isinstance(raw, dict):
        return clean
    for cat in CATEGORY_DEFAULTS:
        val = raw.get(cat)
        if isinstance(val, str) and val in CATALOGUE and CATALOGUE[val]["category"] == cat:
            clean[cat] = val
    raw_colors = raw.get("colors")
    if isinstance(raw_colors, dict):
        for cat in CATEGORY_DEFAULTS:
            c = raw_colors.get(cat)
            if isinstance(c, int) and 0 <= c < len(SWATCHES):
                clean["colors"][cat] = c
    return clean


def score_outfit(outfit, theme):
    outfit = sanitize_outfit(outfit)
    using_dress = outfit["dress"] != "dress_none"
    active_cats = ["hair", "hat", "shoes", "accessory", "weapon"] + (["dress"] if using_dress else ["top", "bottom"])
    total, matched_slots, breakdown = 0, 0, {}
    for cat in active_cats:
        item = CATALOGUE[outfit[cat]]
        w = 2 if cat == "dress" else 1
        base = RARITY_POINTS.get(item["rarity"], 6) * w
        hit = theme in item["tags"]
        pts = base + ((26 * w) if hit else 0)
        if hit:
            matched_slots += w
        breakdown[cat] = pts
        total += pts
    synergy = 20 if matched_slots >= 4 else (10 if matched_slots >= 2 else 0)
    used_colors = {outfit["colors"][c] for c in active_cats}
    palette_bonus = 12 if 2 <= len(used_colors) <= 3 else 5
    return {
        "total": min(250, total + synergy + palette_bonus),
        "matched_slots": matched_slots,
        "synergy": synergy,
        "palette_bonus": palette_bonus,
        "breakdown": breakdown,
    }


def setup(sio, auth, rooms):
    if not hasattr(auth, "fast"):
        auth.fast = auth   # core.py has a separate movement limiter; fall back to the normal one if absent

    async def cleanup_game(code, notify_sid=None, reason="Partner left the duel."):
        g = games.pop(code, None)
        if g and notify_sid:
            await sio.emit("duel:aborted", {"gid": g["gid"], "reason": reason}, to=notify_sid)

    async def resolve_game_over(code, gid, winner_pid=None, reason="ko"):
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["gid"] != gid or g["phase"] == "over":
            return
        g["phase"] = "over"
        pids = list(room.players.keys())
        if winner_pid is None and len(pids) == 2:
            p0, p1 = g["p"].get(pids[0], {}), g["p"].get(pids[1], {})
            pct0 = p0.get("hp", 0) / max(1, p0.get("max_hp", 100))
            pct1 = p1.get("hp", 0) / max(1, p1.get("max_hp", 100))
            if pct0 != pct1:
                winner_pid = pids[0] if pct0 > pct1 else pids[1]
            else:
                winner_pid = pids[0] if p0.get("style_score", 0) >= p1.get("style_score", 0) else pids[1]

        w_pl = room.players.get(winner_pid) if winner_pid else None
        stats = {}
        for pid, pl in room.players.items():
            ps = g["p"].get(pid, {})
            stats[pl["role"]] = {
                "name": pl["name"],
                "style_score": ps.get("style_score", 0),
                "damage_dealt": round(ps.get("damage_dealt", 0), 1),
                "hp_left": max(0, round(ps.get("hp", 0), 1)),
                "max_hp": ps.get("max_hp", 100),
                "buff": ps.get("buff_label", "None"),
            }
        payload = {
            "gid": gid,
            "winner": w_pl["name"] if w_pl else "Draw",
            "winner_role": w_pl["role"] if w_pl else "white",
            "reason": reason,
            "stats": stats,
        }
        for pl in room.players.values():
            await sio.emit("duel:over", payload, to=pl["sid"])

    async def enter_arena_phase(code, gid):
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["gid"] != gid or g["phase"] != "reveal":
            return
        g["phase"] = "arena"
        view = {}
        for pid, pl in room.players.items():
            s = g["p"].setdefault(pid, {})
            s.setdefault("outfit", default_outfit())
            w_type = CATALOGUE.get(s["outfit"]["weapon"], CATALOGUE["wep_saber_cyan"])["weapon_type"] or "lightsaber"
            s["weapon_type"] = w_type
            max_hp = s.get("max_hp", 100)
            s.update(
                x=-6.0 if pl["role"] == "white" else 6.0,
                y=0.0,
                facing=1 if pl["role"] == "white" else -1,
                anim="idle",
                blocking=False,
                hp=float(max_hp),
                last_atk=0.0,
                last_dodge=0.0,
                dodge_until=0.0,
                t=time.time(),
            )
            view[pl["role"]] = {
                "name": pl["name"], "role": pl["role"], "outfit": s["outfit"], "weapon_type": w_type,
                "x": s["x"], "y": s["y"], "facing": s["facing"], "hp": s["hp"], "max_hp": max_hp,
                "style_score": s.get("style_score", 0), "buff": s.get("buff", "none"),
                "buff_label": s.get("buff_label", "Standard Kit"), "dmg_mult": s.get("dmg_mult", 1.0),
            }
        for pl in room.players.values():
            await sio.emit("duel:arena", {"gid": gid, "theme": g["theme"], "you": pl["role"], "seconds": ARENA_SECONDS, "players": view}, to=pl["sid"])

        async def _arena_timeout():
            await asyncio.sleep(ARENA_SECONDS)
            await resolve_game_over(code, gid, reason="timeout")
        asyncio.create_task(_arena_timeout())

    async def start_reveal_and_arena(code, gid):
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["gid"] != gid or g["phase"] != "dress":
            return
        g["phase"] = "reveal"
        role_scores, pids = {}, list(room.players.keys())
        for pid in pids:
            pl = room.players[pid]
            s = g["p"].setdefault(pid, {})
            s["outfit"] = sanitize_outfit(s.get("outfit"))
            sc = score_outfit(s["outfit"], g["theme"])
            s["style_score"], s["score_detail"], s["damage_dealt"] = sc["total"], sc, 0.0
            role_scores[pl["role"]] = {"name": pl["name"], "role": pl["role"], "outfit": s["outfit"], "score": sc["total"], "detail": sc}

        if len(pids) == 2:
            p0, p1 = g["p"][pids[0]], g["p"][pids[1]]
            w_pid = pids[0] if p0["style_score"] > p1["style_score"] else (pids[1] if p1["style_score"] > p0["style_score"] else None)
        else:
            w_pid = pids[0] if pids else None

        w_role = room.players[w_pid]["role"] if w_pid else "tie"
        for pid in pids:
            s, role = g["p"][pid], room.players[pid]["role"]
            if w_pid is None:
                s.update(max_hp=105, dmg_mult=1.03, buff="tie_glam", buff_label="Twin Icon (+5% HP, +3% DMG)")
            elif pid == w_pid:
                s.update(max_hp=110, dmg_mult=1.05, buff="style_winner", buff_label="Runway Crown (+10% HP, +5% DMG)")
            else:
                s.update(max_hp=100, dmg_mult=1.0, buff="none", buff_label="Standard Kit")
            role_scores[role].update(buff=s["buff"], buff_label=s["buff_label"], max_hp=s["max_hp"])

        for pl in room.players.values():
            await sio.emit("duel:reveal", {"gid": gid, "theme": g["theme"], "style_winner": w_role, "players": role_scores, "reveal_seconds": REVEAL_SECONDS}, to=pl["sid"])

        async def _wait_rev():
            await asyncio.sleep(REVEAL_SECONDS)
            await enter_arena_phase(code, gid)
        asyncio.create_task(_wait_rev())

    def create_new_game(code, room):
        gid = uuid.uuid4().hex[:12]
        theme = random.choice(THEMES)
        g = {"gid": gid, "phase": "dress", "theme": theme, "end": time.time() + DRESS_SECONDS, "p": {}}
        for pid in room.players:
            g["p"][pid] = {"outfit": default_outfit(), "ready": False, "style_score": score_outfit(default_outfit(), theme)["total"]}
        games[code] = g
        async def _dress_clock():
            await asyncio.sleep(DRESS_SECONDS)
            await start_reveal_and_arena(code, gid)
        asyncio.create_task(_dress_clock())
        return g

    @sio.on("duel:join")
    @auth
    async def join(sid, sess, data=None):
        code = rooms.by_player.get(sess["pid"])
        room = rooms.rooms.get(code)
        if not room or not room.locked:
            return
        g = games.get(code)
        if not g or g["phase"] == "over":
            g = create_new_game(code, room)
        me = g["p"].setdefault(sess["pid"], {"outfit": default_outfit(), "ready": False})
        sc = score_outfit(me["outfit"], g["theme"])
        me["style_score"] = sc["total"]
        if g["phase"] == "dress":
            await sio.emit("duel:theme", {
                "gid": g["gid"], "theme": g["theme"], "you": room.players[sess["pid"]]["role"],
                "seconds": max(1, int(round(g["end"] - time.time()))), "outfit": me["outfit"], "score": sc,
            }, to=sid)

    @sio.on("duel:preview")
    @auth.fast
    async def preview(sid, sess, data):
        code = rooms.by_player.get(sess["pid"])
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["phase"] != "dress" or not isinstance(data, dict):
            return
        if data.get("gid") and data.get("gid") != g["gid"]:
            return
        clean = sanitize_outfit(data.get("outfit"))
        sc = score_outfit(clean, g["theme"])
        p_entry = g["p"].setdefault(sess["pid"], {})
        p_entry["outfit"], p_entry["style_score"] = clean, sc["total"]
        await sio.emit("duel:score", {"gid": g["gid"], "score": sc, "outfit": clean}, to=sid)
        peer = partner_of(rooms, sess["pid"])
        if peer:
            await sio.emit("duel:opp_pulse", {"gid": g["gid"], "role": room.players[sess["pid"]]["role"], "ready": bool(p_entry.get("ready"))}, to=peer["sid"])

    @sio.on("duel:outfit")
    @auth
    async def outfit(sid, sess, data):
        code = rooms.by_player.get(sess["pid"])
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["phase"] != "dress" or not isinstance(data, dict):
            return
        if data.get("gid") and data.get("gid") != g["gid"]:
            return
        raw_outfit = data.get("outfit") if isinstance(data.get("outfit"), dict) else data
        clean = sanitize_outfit(raw_outfit)
        sc = score_outfit(clean, g["theme"])
        g["p"][sess["pid"]] = {"outfit": clean, "ready": True, "style_score": sc["total"], "score_detail": sc}
        role = room.players[sess["pid"]]["role"]
        for pl in room.players.values():
            await sio.emit("duel:ready_state", {"gid": g["gid"], "role": role, "ready": True, "score": sc["total"]}, to=pl["sid"])
        if len(room.players) == 2 and all(g["p"].get(pid, {}).get("ready") for pid in room.players):
            await start_reveal_and_arena(code, g["gid"])

    @sio.on("duel:pos")
    @auth.fast
    async def pos(sid, sess, data):
        code = rooms.by_player.get(sess["pid"])
        g, room = games.get(code), rooms.rooms.get(code)
        if not g or not room or g["phase"] != "arena" or not isinstance(data, dict):
            return
        if data.get("gid") and data.get("gid") != g["gid"]:
            return
        s = g["p"].get(sess["pid"])
        if not s:
            return
        try:
            x = float(data.get("x", s["x"]))
            y = float(data.get("y", 0.0))
            facing = 1 if int(data.get("facing", s["facing"])) >= 0 else -1
        except (TypeError, ValueError):
            return
        if not (math.isfinite(x) and math.isfinite(y)):
            return
        now = time.time()
        dt = max(0.005, min(now - s["t"], 0.5))
        speed_cap = MAX_MOVE_SPEED * (1.55 if now < s.get("dodge_until", 0.0) else 1.0)
        max_dx = speed_cap * dt + 0.45
        x = max(ARENA_MIN_X, min(ARENA_MAX_X, max(s["x"] - max_dx, min(s["x"] + max_dx, x))))
        y = max(0.0, min(3.8, y))
        anim = str(data.get("anim", "idle"))
        if anim not in ("idle", "walk", "run", "jump", "dodge", "block", "attack", "hit"):
            anim = "idle"
        blocking = bool(data.get("blocking", False)) and anim == "block"
        if anim == "dodge" and now - s.get("last_dodge", 0.0) >= 1.1:
            s["last_dodge"], s["dodge_until"] = now, now + 0.28
        s.update(x=x, y=y, facing=facing, anim=anim, blocking=blocking, t=now)
        peer = partner_of(rooms, sess["pid"])
        if peer:
            await sio.emit("duel:opp", {"gid": g["gid"], "x": round(x, 3), "y": round(y, 3), "facing": facing, "anim": anim, "blocking": blocking}, to=peer["sid"])

    @sio.on("duel:attack")
    @auth.fast
    async def attack(sid, sess, data=None):
        code = rooms.by_player.get(sess["pid"])
        g, room = games.get(code), rooms.rooms.get(code)
        peer = partner_of(rooms, sess["pid"])
        if not g or not room or not peer or g["phase"] != "arena":
            return
        if isinstance(data, dict) and data.get("gid") and data.get("gid") != g["gid"]:
            return
        me = g["p"].get(sess["pid"])
        foe_id = next((pid for pid in room.players if pid != sess["pid"]), None)
        foe = g["p"].get(foe_id) if foe_id else None
        if not me or not foe or me.get("hp", 0) <= 0 or foe.get("hp", 0) <= 0:
            return
        w_type = me.get("weapon_type", "lightsaber")
        base_dmg, rng, cd, windup, knockback = WEAPONS.get(w_type, WEAPONS["lightsaber"])
        now = time.time()
        if now - me.get("last_atk", 0.0) < cd:
            return
        me["last_atk"], me["blocking"] = now, False
        attacker_role, foe_role = room.players[sess["pid"]]["role"], room.players[foe_id]["role"]
        for pl in room.players.values():
            await sio.emit("duel:swing", {"gid": g["gid"], "role": attacker_role, "weapon_type": w_type, "cooldown": cd}, to=pl["sid"])

        dx = foe["x"] - me["x"]
        if abs(dx) <= rng and abs(foe.get("y", 0.0) - me.get("y", 0.0)) <= 2.2:
            if now < foe.get("dodge_until", 0.0):
                for pl in room.players.values():
                    await sio.emit("duel:evade", {"gid": g["gid"], "role": foe_role, "x": foe["x"]}, to=pl["sid"])
                return
            raw_dmg = base_dmg * me.get("dmg_mult", 1.0)
            blocked = bool(foe.get("blocking", False))
            dmg = round(raw_dmg * (0.30 if blocked else 1.0), 1)
            kb = knockback * (0.35 if blocked else 1.0)
            foe["x"] = max(ARENA_MIN_X, min(ARENA_MAX_X, foe["x"] + (1.0 if dx >= 0 else -1.0) * kb))
            foe["hp"] = max(0.0, round(foe["hp"] - dmg, 1))
            me["damage_dealt"] = round(me.get("damage_dealt", 0.0) + dmg, 1)
            is_final = foe["hp"] <= 0.0
            for pl in room.players.values():
                await sio.emit("duel:hit", {
                    "gid": g["gid"], "target": foe_role, "attacker": attacker_role,
                    "hp": foe["hp"], "max_hp": foe.get("max_hp", 100), "dmg": dmg,
                    "blocked": blocked, "x": round(foe["x"], 3), "final_blow": is_final,
                }, to=pl["sid"])
            if is_final:
                await resolve_game_over(code, g["gid"], winner_pid=sess["pid"], reason="ko")

    @sio.on("duel:rematch")
    @auth
    async def rematch(sid, sess, data=None):
        code = rooms.by_player.get(sess["pid"])
        room = rooms.rooms.get(code)
        if not room or not room.locked:
            return
        g = create_new_game(code, room)
        for pid, pl in room.players.items():
            p_state = g["p"][pid]
            sc = score_outfit(p_state["outfit"], g["theme"])
            await sio.emit("duel:theme", {
                "gid": g["gid"], "theme": g["theme"], "you": pl["role"],
                "seconds": DRESS_SECONDS, "outfit": p_state["outfit"], "score": sc,
            }, to=pl["sid"])

    @sio.on("duel:leave")
    @auth
    async def leave(sid, sess, data=None):
        code = rooms.by_player.get(sess["pid"])
        if not code:
            return
        peer = partner_of(rooms, sess["pid"])
        await cleanup_game(code, notify_sid=peer["sid"] if peer else None, reason=f"{sess.get('name', 'Partner')} closed Dress Duel.")


CSS = r"""
.dd-root{position:relative;width:min(1120px,96vw);height:min(740px,86vh);min-height:480px;background:radial-gradient(circle at 50% 18%,#351429 0%,#140810 72%);color:#ffe3ee;border:2px solid #d9488f;border-radius:18px;overflow:hidden;display:flex;flex-direction:column;font-family:system-ui,-apple-system,sans-serif;user-select:none;box-shadow:0 18px 50px rgba(20,8,16,.75),inset 0 0 32px rgba(217,72,143,.22)}
.dd-topbar{position:relative;z-index:5;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 14px;background:rgba(20,8,16,.82);border-bottom:1px solid rgba(217,72,143,.45);backdrop-filter:blur(8px)}
.dd-theme-pill{display:flex;align-items:center;gap:8px;background:linear-gradient(90deg,rgba(217,72,143,.32),rgba(140,82,255,.28));border:1px solid #ff7fb0;padding:5px 12px;border-radius:999px;font-weight:700;font-size:.92rem;color:#ffe3ee}
.dd-meter-wrap{display:flex;align-items:center;gap:8px;flex:1;max-width:280px}
.dd-meter-label{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:#ff9ec7;white-space:nowrap}
.dd-meter-track{flex:1;height:10px;background:rgba(255,227,238,.12);border-radius:999px;overflow:hidden;border:1px solid rgba(217,72,143,.5)}
.dd-meter-fill{height:100%;width:20%;background:linear-gradient(90deg,#ff5ca8,#ffd166,#00e5ff);border-radius:999px;transition:width .28s ease}
.dd-timer-ring{display:flex;align-items:center;gap:8px;font-weight:800;font-size:.95rem;color:#ffe3ee}
.dd-ring-svg{width:36px;height:36px;transform:rotate(-90deg)}
.dd-ring-bg{fill:none;stroke:rgba(255,227,238,.16);stroke-width:3.6}
.dd-ring-fg{fill:none;stroke:#ff5ca8;stroke-width:3.6;stroke-linecap:round;transition:stroke-dashoffset .3s linear}
.dd-main{position:relative;flex:1;display:flex;min-height:0;overflow:hidden}
.dd-stage-wrap{position:relative;flex:1.15;min-width:0;height:100%;overflow:hidden}
.dd-canvas{width:100%;height:100%;display:block;touch-action:none}
.dd-cam-bar{position:absolute;left:12px;bottom:12px;z-index:4;display:flex;gap:6px;flex-wrap:wrap}
.dd-chip-btn{background:rgba(20,8,16,.78);color:#ffe3ee;border:1px solid rgba(217,72,143,.65);border-radius:999px;padding:5px 11px;font-size:.76rem;font-weight:600;cursor:pointer}
.dd-chip-btn:hover,.dd-chip-btn:focus-visible,.dd-chip-btn.is-active{background:#ff5ca8;color:#140810;border-color:#fff;outline:none}
.dd-wardrobe{width:min(430px,46%);height:100%;background:rgba(20,8,16,.9);border-left:1px solid rgba(217,72,143,.45);display:flex;flex-direction:column;z-index:4}
.dd-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;padding:8px;background:rgba(255,227,238,.04);border-bottom:1px solid rgba(217,72,143,.3)}
.dd-tab{background:rgba(255,227,238,.07);color:#ffe3ee;border:1px solid transparent;border-radius:8px;padding:6px 4px;font-size:.74rem;font-weight:700;cursor:pointer;text-align:center}
.dd-tab.is-active{background:linear-gradient(135deg,#d9488f,#8c52ff);color:#fff;border-color:#ffe3ee}
.dd-swatches{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:7px 10px;border-bottom:1px solid rgba(217,72,143,.25);background:rgba(20,8,16,.65)}
.dd-swatch-row{display:flex;gap:7px}
.dd-swatch{width:22px;height:22px;border-radius:50%;border:2px solid rgba(255,227,238,.45);cursor:pointer}
.dd-swatch.c0{background:#ff5ca8}.dd-swatch.c1{background:#8c52ff}.dd-swatch.c2{background:#00e5ff}.dd-swatch.c3{background:#ffd166}.dd-swatch.c4{background:#191324}.dd-swatch.c5{background:#f4f1fa}
.dd-swatch.is-active,.dd-swatch:focus-visible{transform:scale(1.2);border-color:#fff;box-shadow:0 0 8px #ff7fb0;outline:none}
.dd-grid{flex:1;overflow-y:auto;padding:8px;display:grid;grid-template-columns:repeat(2,1fr);gap:8px;align-content:start}
.dd-card{position:relative;display:flex;flex-direction:column;align-items:center;background:rgba(255,227,238,.05);border:2px solid rgba(255,227,238,.18);border-radius:12px;padding:6px;cursor:pointer;text-align:center;color:#ffe3ee}
.dd-card:hover,.dd-card:focus-visible{transform:translateY(-2px);outline:none;box-shadow:0 4px 14px rgba(217,72,143,.38)}
.dd-card.r-common{border-color:#9aa0b5}.dd-card.r-rare{border-color:#36c5f0}.dd-card.r-epic{border-color:#b565ff}.dd-card.r-legendary{border-color:#ffd166}
.dd-card.is-equipped{background:rgba(217,72,143,.25);box-shadow:0 0 0 2px #ff5ca8,0 0 16px rgba(255,92,168,.55)}
.dd-thumb{width:68px;height:68px;object-fit:contain;border-radius:8px;background:radial-gradient(circle,rgba(255,227,238,.14),rgba(20,8,16,.6));margin-bottom:4px}
.dd-card-title{font-size:.75rem;font-weight:700;line-height:1.15}
.dd-card-tag{font-size:.64rem;color:#ffadd2;opacity:.88;margin-top:2px}
.dd-ready-footer{padding:9px 12px;border-top:1px solid rgba(217,72,143,.35);display:flex;gap:8px;background:rgba(20,8,16,.95)}
.dd-ready-btn{flex:1;background:linear-gradient(90deg,#ff5ca8,#d9488f);color:#140810;font-weight:800;font-size:.92rem;border:none;border-radius:10px;padding:9px 14px;cursor:pointer}
.dd-ready-btn.is-locked{background:#2bb3a3;color:#fff;cursor:default}
.dd-arena-hud{position:absolute;top:48px;left:0;right:0;z-index:4;display:flex;justify-content:space-between;padding:10px 16px;pointer-events:none;gap:12px}
.dd-fighter-card{width:min(340px,42vw);background:rgba(20,8,16,.78);border:1px solid rgba(217,72,143,.6);border-radius:12px;padding:8px 10px;backdrop-filter:blur(6px)}
.dd-fighter-top{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.dd-portrait{width:36px;height:36px;border-radius:50%;border:2px solid #ff7fb0;background:#2a1021;object-fit:cover}
.dd-fighter-meta{flex:1;min-width:0}
.dd-fighter-name{font-weight:800;font-size:.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dd-buff-badge{display:inline-block;font-size:.66rem;padding:1px 6px;border-radius:999px;background:rgba(255,209,102,.2);border:1px solid #ffd166;color:#ffd166}
.dd-hp-track{height:11px;background:rgba(255,255,255,.12);border-radius:999px;overflow:hidden;border:1px solid rgba(255,227,238,.3)}
.dd-hp-fill{height:100%;width:100%;background:linear-gradient(90deg,#ff477e,#ff85a1);transition:width .15s ease-out}
.dd-cd-track{margin-top:4px;height:4px;background:rgba(255,255,255,.1);border-radius:999px;overflow:hidden}
.dd-cd-fill{height:100%;width:100%;background:#00e5ff}
.dd-float-layer{position:absolute;inset:0;pointer-events:none;z-index:4;overflow:hidden}
.dd-dmg-num{position:absolute;font-weight:900;font-size:1.35rem;color:#ffd166;text-shadow:0 2px 6px #140810;transform:translate(-50%,-50%);animation:ddFloatUp .75s ease-out forwards}
.dd-dmg-num.is-blocked{color:#00e5ff;font-size:1.05rem}
@keyframes ddFloatUp{0%{opacity:1;transform:translate(-50%,-20%) scale(.85)}100%{opacity:0;transform:translate(-50%,-140%) scale(1.15)}}
.dd-touch-bar{position:absolute;left:12px;right:12px;bottom:12px;z-index:5;display:flex;justify-content:space-between;pointer-events:none}
.dd-touch-cluster{display:flex;gap:8px;pointer-events:auto}
.dd-touch-btn{width:52px;height:52px;border-radius:50%;border:2px solid rgba(255,227,238,.65);background:rgba(20,8,16,.72);color:#ffe3ee;font-weight:800;font-size:.78rem;cursor:pointer;touch-action:manipulation}
.dd-banner-modal{position:absolute;inset:0;z-index:7;background:rgba(20,8,16,.78);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;padding:16px}
.dd-modal-card{width:min(460px,92%);background:#1f0d1a;border:2px solid #ff5ca8;border-radius:18px;padding:20px;text-align:center;box-shadow:0 18px 45px rgba(0,0,0,.75)}
.dd-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0;text-align:left}
.dd-stat-box{background:rgba(255,227,238,.06);border:1px solid rgba(217,72,143,.4);border-radius:10px;padding:8px 10px;font-size:.8rem}
.dd-hidden{display:none!important}
@media(max-width:780px){.dd-main{flex-direction:column}.dd-wardrobe{width:100%;height:48%;border-left:none;border-top:1px solid rgba(217,72,143,.45)}.dd-grid{grid-template-columns:repeat(4,1fr)}}
"""

JS = r"""
"use strict";
window.Features = window.Features || {};
window.Features["Dress Duel"] = (() => {
  const H = window.Hang;
  const THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js";
  const SWATCHES = ["#ff5ca8", "#8c52ff", "#00e5ff", "#ffd166", "#191324", "#f4f1fa"];
  const CATEGORIES = [
    { key: "hair", label: "Hair" }, { key: "hat", label: "Hats" },
    { key: "top", label: "Tops" }, { key: "bottom", label: "Bottoms" },
    { key: "dress", label: "Dresses" }, { key: "shoes", label: "Shoes" },
    { key: "accessory", label: "Access." }, { key: "weapon", label: "Weapon" },
  ];
  const CATALOGUE_RAW = [
    ["hair_bob","Silk Bob","hair","bob","common",["Royal Gala","Neon Disco"],null],
    ["hair_cyber_pigtails","Holo Twin-Tails","hair","pigtails","epic",["Cyberpunk Heist","Neon Disco"],null],
    ["hair_samurai_bun","Ronin Topknot","hair","bun","rare",["Beach Samurai"],null],
    ["hair_royal_updo","Imperial Updo","hair","updo","legendary",["Royal Gala"],null],
    ["hair_elf_braids","Sylvan Braids","hair","long_waves","epic",["Enchanted Forest","Royal Gala"],null],
    ["hair_disco_afro","Starlight Afro","hair","afro","legendary",["Neon Disco"],null],
    ["hair_beach_waves","Saltwater Waves","hair","long_waves","common",["Beach Samurai","Enchanted Forest"],null],
    ["hair_neon_mohawk","Laser Spikes","hair","spiky","rare",["Cyberpunk Heist","Neon Disco"],null],
    ["hat_none","No Hat","hat","none","common",[],null],
    ["hat_crown","Sovereign Crown","hat","crown","legendary",["Royal Gala"],null],
    ["hat_cyber_visor","Netrunner Visor","hat","visor","epic",["Cyberpunk Heist","Neon Disco"],null],
    ["hat_kasa","Bamboo Kasa","hat","kasa","rare",["Beach Samurai"],null],
    ["hat_antlers","Moonlit Antlers","hat","antlers","legendary",["Enchanted Forest"],null],
    ["hat_disco_fedora","Mirrorball Fedora","hat","fedora","rare",["Neon Disco","Royal Gala"],null],
    ["hat_tiara","Starlight Tiara","hat","tiara","epic",["Royal Gala","Enchanted Forest"],null],
    ["hat_oni_helm","Neon Oni Crest","hat","oni","epic",["Cyberpunk Heist","Beach Samurai"],null],
    ["top_corset","Velvet Corset","top","corset","rare",["Royal Gala","Enchanted Forest"],null],
    ["top_cyber_jacket","Synthwave Bolero","top","jacket","epic",["Cyberpunk Heist","Neon Disco"],null],
    ["top_haori","Wave Haori Coat","top","haori","rare",["Beach Samurai"],null],
    ["top_leaf_tunic","Moss & Vine Tunic","top","tunic","common",["Enchanted Forest"],null],
    ["top_sequin_halter","Prism Sequin Top","top","crop","epic",["Neon Disco"],null],
    ["top_royal_blazer","Gold-Epaulet Coat","top","blazer","legendary",["Royal Gala"],null],
    ["top_rashguard","Tidal Armor Top","top","crop","common",["Beach Samurai","Cyberpunk Heist"],null],
    ["top_holo_armor","Aegis Chestplate","top","armor","legendary",["Cyberpunk Heist","Beach Samurai"],null],
    ["bot_pleated_skirt","Velvet Pleat Skirt","bottom","skirt","common",["Royal Gala","Neon Disco"],null],
    ["bot_tech_cargo","Strapped Tech Pants","bottom","cargo","epic",["Cyberpunk Heist"],null],
    ["bot_hakama","Tide Hakama Trousers","bottom","hakama","rare",["Beach Samurai"],null],
    ["bot_petal_skirt","Fern Petal Skirt","bottom","petal_skirt","rare",["Enchanted Forest"],null],
    ["bot_bell_bottoms","Glitter Flare Pants","bottom","flares","legendary",["Neon Disco"],null],
    ["bot_board_shorts","Shogun Surf Shorts","bottom","shorts","common",["Beach Samurai"],null],
    ["bot_silk_trousers","Tailored Tux Pants","bottom","trousers","rare",["Royal Gala"],null],
    ["bot_cyber_greaves","Neon Exo-Leggings","bottom","cargo","epic",["Cyberpunk Heist","Neon Disco"],null],
    ["dress_none","Two-Piece Mode","dress","none","common",[],null],
    ["dress_ballgown","Empress Crinoline Gown","dress","ballgown","legendary",["Royal Gala"],null],
    ["dress_cyber_trench","Matrix Holo-Trench","dress","trench","legendary",["Cyberpunk Heist"],null],
    ["dress_kimono","Coral Silk Furisode","dress","kimono","epic",["Beach Samurai","Royal Gala"],null],
    ["dress_fairy_gown","Dryad Blossom Gown","dress","fairy","legendary",["Enchanted Forest"],null],
    ["dress_disco_jumpsuit","Studio 77 Jumpsuit","dress","jumpsuit","epic",["Neon Disco"],null],
    ["dress_mermaid","Pearl Mermaid Dress","dress","mermaid","rare",["Royal Gala","Beach Samurai"],null],
    ["dress_neon_mini","Laser Grid Dress","dress","mini","rare",["Neon Disco","Cyberpunk Heist"],null],
    ["shoe_heels","Crystal Stilettos","shoes","heels","epic",["Royal Gala","Neon Disco"],null],
    ["shoe_cyber_boots","Mag-Lev Combat Boots","shoes","boots","epic",["Cyberpunk Heist"],null],
    ["shoe_geta","Lacquered Surf Geta","shoes","geta","rare",["Beach Samurai"],null],
    ["shoe_vine_wraps","Sylvan Dew Wraps","shoes","wraps","common",["Enchanted Forest"],null],
    ["shoe_platforms","Starlight Platforms","shoes","platforms","legendary",["Neon Disco"],null],
    ["shoe_greaves","Gilded Sabatons","shoes","boots","rare",["Royal Gala","Beach Samurai"],null],
    ["shoe_sandals","Shell Strap Sandals","shoes","geta","common",["Beach Samurai","Enchanted Forest"],null],
    ["shoe_hover_skates","Pulse Roller Blades","shoes","platforms","legendary",["Cyberpunk Heist","Neon Disco"],null],
    ["acc_none","No Accessory","accessory","none","common",[],null],
    ["acc_royal_cape","Ermine Velvet Cape","accessory","cape","legendary",["Royal Gala"],null],
    ["acc_fairy_wings","Iridescent Monarch Wings","accessory","wings","legendary",["Enchanted Forest"],null],
    ["acc_cyber_halo","Floating Data Halo","accessory","halo","epic",["Cyberpunk Heist","Neon Disco"],null],
    ["acc_surf_shield","Tsunami Back-Board","accessory","board","rare",["Beach Samurai"],null],
    ["acc_feather_boa","Neon Flamingo Boa","accessory","boa","epic",["Neon Disco","Royal Gala"],null],
    ["acc_fox_tail","Kitsune Spirit Tail","accessory","tail","rare",["Beach Samurai","Enchanted Forest"],null],
    ["acc_shoulder_drone","Sentinel Drone","accessory","drone","epic",["Cyberpunk Heist"],null],
    ["wep_saber_cyan","Plasma Katana","weapon","saber_katana","epic",["Cyberpunk Heist","Beach Samurai"],"lightsaber"],
    ["wep_saber_pink","Disco Saber","weapon","saber_disco","rare",["Neon Disco","Cyberpunk Heist"],"lightsaber"],
    ["wep_broad_royal","Sovereign Claymore","weapon","broad_royal","legendary",["Royal Gala"],"broadsword"],
    ["wep_broad_coral","Reef Breaker Blade","weapon","broad_coral","epic",["Beach Samurai","Enchanted Forest"],"broadsword"],
    ["wep_dagger_fang","Thorn Twin-Fangs","weapon","dagger_thorn","rare",["Enchanted Forest","Cyberpunk Heist"],"daggers"],
    ["wep_dagger_fan","Gilded War Fans","weapon","dagger_fan","epic",["Royal Gala","Neon Disco"],"daggers"],
    ["wep_staff_sylvan","Elderwood Greatstaff","weapon","staff_wood","legendary",["Enchanted Forest","Royal Gala"],"staff"],
    ["wep_staff_mic","Bass Drop Scepter","weapon","staff_mic","epic",["Neon Disco","Beach Samurai"],"staff"]
  ];

  const CATALOGUE = {}, BY_CAT = {};
  for (const r of CATALOGUE_RAW) {
    const it = { id: r[0], name: r[1], category: r[2], shape: r[3], rarity: r[4], tags: r[5], weapon_type: r[6] };
    CATALOGUE[it.id] = it;
    (BY_CAT[it.category] = BY_CAT[it.category] || []).push(it);
  }

  const makeDefaultOutfit = () => ({
    hair: "hair_bob", hat: "hat_none", top: "top_corset", bottom: "bot_pleated_skirt",
    dress: "dress_none", shoes: "shoe_heels", accessory: "acc_none", weapon: "wep_saber_cyan",
    colors: { hair: 4, hat: 3, top: 0, bottom: 4, dress: 0, shoes: 0, accessory: 2, weapon: 2 },
  });

  const thumbCache = {};
  let threePromise = null, inited = false, box = null, rootEl = null, gid = null, phase = "idle";
  let myRole = "white", currentTheme = "Royal Gala", activeCategory = "hair", myOutfit = makeDefaultOutfit();
  let isReady = false, reducedMotion = false, renderer = null, scene = null, camera = null, rafId = 0, countdownInterval = 0;
  let secondsLeft = 60, maxPhaseSeconds = 60, cleanupListeners = [], tubes = {}, rigs = {};
  let sparkles = [], shockwaves = [], hitSparks = [], dustPuffs = [];
  let turntableAngle = 0, targetZoom = 5.2, targetCamY = 1.45, spinImpulse = 0, camShake = 0, slowMoFactor = 1.0, slowMoUntil = 0;
  let arenaState = null, keys = {}, touchInput = { left: false, right: false, jump: false, block: false }, lastPosSend = 0, prevFrameTime = 0, ui = {};

  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    if (threePromise) return threePromise;
    threePromise = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = THREE_CDN;
      s.async = true;
      s.onload = () => (window.THREE ? res(window.THREE) : rej(new Error("THREE missing")));
      s.onerror = () => rej(new Error("Failed to load Three.js"));
      document.head.appendChild(s);
    });
    return threePromise;
  }

  function hasWebGL() {
    try {
      const c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (c.getContext("webgl") || c.getContext("experimental-webgl")));
    } catch (_) { return false; }
  }

  function addManagedListener(target, type, fn, opts) {
    target.addEventListener(type, fn, opts);
    cleanupListeners.push(() => target.removeEventListener(type, fn, opts));
  }

  function disposeObject3D(obj) {
    if (!obj) return;
    obj.traverse((ch) => {
      if (ch.geometry) ch.geometry.dispose();
      if (ch.material) {
        (Array.isArray(ch.material) ? ch.material : [ch.material]).forEach((m) => {
          if (m.map) m.map.dispose();
          m.dispose();
        });
      }
    });
  }

  function buildItemMesh(THREE, item, colorHex) {
    const group = new THREE.Group();
    if (!item || item.shape === "none") return group;
    const col = new THREE.Color(colorHex || "#ff5ca8");
    const matPrimary = new THREE.MeshStandardMaterial({ color: col, roughness: 0.35, metalness: item.rarity === "legendary" ? 0.55 : 0.2 });
    const matAccent = new THREE.MeshStandardMaterial({ color: 0xffd166, roughness: 0.25, metalness: 0.75 });
    const matGlow = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.85, roughness: 0.2 });
    const s = item.shape;

    if (item.category === "hair") {
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.24, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.65), matPrimary);
      cap.position.y = 0.03;
      group.add(cap);
      if (s === "bob") {
        for (const d of [-1, 1]) {
          const side = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.28, 0.26), matPrimary);
          side.position.set(d * 0.2, -0.06, 0);
          group.add(side);
        }
      } else if (s === "pigtails") {
        for (const d of [-1, 1]) {
          const tail = new THREE.Mesh(new THREE.ConeGeometry(0.11, 0.55, 10), matPrimary);
          tail.position.set(d * 0.28, -0.1, -0.05);
          tail.rotation.z = d * 0.35;
          group.add(tail);
        }
      } else if (s === "bun" || s === "updo") {
        const bun = new THREE.Mesh(new THREE.SphereGeometry(s === "updo" ? 0.16 : 0.11, 12, 12), matPrimary);
        bun.position.set(0, 0.28, -0.06);
        const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.42, 8), matAccent);
        pin.position.set(0, 0.28, -0.06);
        pin.rotation.z = Math.PI * 0.4;
        group.add(bun, pin);
      } else if (s === "long_waves") {
        const back = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.62, 0.16), matPrimary);
        back.position.set(0, -0.22, -0.14);
        group.add(back);
      } else if (s === "afro") {
        const afro = new THREE.Mesh(new THREE.SphereGeometry(0.36, 16, 14), matPrimary);
        afro.position.set(0, 0.08, -0.02);
        group.add(afro);
      } else if (s === "spiky") {
        for (let i = -2; i <= 2; i++) {
          const sp = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.26, 6), matGlow);
          sp.position.set(0, 0.26, i * 0.07);
          sp.rotation.x = i * 0.22;
          group.add(sp);
        }
      }
    } else if (item.category === "hat") {
      if (s === "crown" || s === "tiara") {
        const band = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.17, 0.1, 14, 1, true), matAccent);
        band.position.y = 0.25;
        group.add(band);
        const n = s === "crown" ? 6 : 3;
        for (let i = 0; i < n; i++) {
          const a = (i / n) * Math.PI * 2;
          const g = new THREE.Mesh(new THREE.ConeGeometry(0.04, 0.12, 5), matGlow);
          g.position.set(Math.cos(a) * 0.17, 0.34, Math.sin(a) * 0.17);
          group.add(g);
        }
      } else if (s === "visor") {
        const v = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.11, 16, 1, true, -Math.PI * 0.45, Math.PI * 0.9), matGlow);
        v.rotation.y = Math.PI;
        v.position.set(0, 0.04, 0.02);
        group.add(v);
      } else if (s === "kasa") {
        const c = new THREE.Mesh(new THREE.ConeGeometry(0.48, 0.2, 20), matPrimary);
        c.position.y = 0.28;
        group.add(c);
      } else if (s === "antlers") {
        for (const d of [-1, 1]) {
          const b = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.035, 0.38, 7), matAccent);
          b.position.set(d * 0.2, 0.36, 0);
          b.rotation.z = -d * 0.45;
          group.add(b);
        }
      } else if (s === "fedora") {
        const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.03, 18), matPrimary);
        const top = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.22, 0.16, 16), matPrimary);
        brim.position.y = 0.22;
        top.position.y = 0.3;
        group.add(brim, top);
      } else if (s === "oni") {
        for (const d of [-1, 1]) {
          const h = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.25, 8), matGlow);
          h.position.set(d * 0.15, 0.3, 0.12);
          h.rotation.x = -0.35;
          group.add(h);
        }
      }
    } else if (item.category === "top") {
      group.add(new THREE.Mesh(new THREE.CylinderGeometry(0.23, 0.19, s === "crop" ? 0.34 : 0.48, 12), matPrimary));
      if (s === "jacket" || s === "haori" || s === "blazer") {
        for (const d of [-1, 1]) {
          const p = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.12, 0.26), s === "blazer" ? matAccent : matPrimary);
          p.position.set(d * 0.25, 0.16, 0);
          group.add(p);
        }
      } else if (s === "armor") {
        const pl = new THREE.Mesh(new THREE.OctahedronGeometry(0.24, 1), matGlow);
        pl.scale.set(1.1, 0.85, 0.6);
        pl.position.set(0, 0.05, 0.08);
        group.add(pl);
      }
    } else if (item.category === "bottom") {
      if (s === "skirt" || s === "petal_skirt") {
        const sk = new THREE.Mesh(new THREE.ConeGeometry(0.36, 0.42, s === "petal_skirt" ? 7 : 18, 1, true), matPrimary);
        sk.position.y = -0.14;
        group.add(sk);
      } else {
        const h = s === "shorts" ? 0.28 : 0.54;
        const rBot = s === "hakama" || s === "flares" ? 0.19 : 0.1;
        for (const d of [-1, 1]) {
          const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.11, rBot, h, 10), matPrimary);
          leg.position.set(d * 0.11, -h * 0.5, 0);
          group.add(leg);
        }
      }
    } else if (item.category === "dress") {
      const bod = new THREE.Mesh(new THREE.CylinderGeometry(0.23, 0.18, 0.46, 14), matPrimary);
      bod.position.y = 0.22;
      group.add(bod);
      if (s === "ballgown" || s === "fairy") {
        const dm = new THREE.Mesh(new THREE.SphereGeometry(0.52, 18, 12, 0, Math.PI * 2, 0, Math.PI * 0.55), matPrimary);
        dm.position.y = -0.02;
        group.add(dm);
      } else {
        const sk = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.35, s === "mini" ? 0.42 : 0.82, 14), matPrimary);
        sk.position.y = s === "mini" ? -0.06 : -0.22;
        group.add(sk);
      }
    } else if (item.category === "shoes") {
      for (const d of [-1, 1]) {
        const bh = s === "boots" ? 0.24 : 0.11;
        const sh = new THREE.Mesh(new THREE.BoxGeometry(0.13, bh, 0.25), matPrimary);
        sh.position.set(d * 0.11, bh * 0.5, 0.03);
        if (s === "platforms" || s === "geta") {
          const sl = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.06, 0.26), matAccent);
          sl.position.set(0, -bh * 0.45, 0);
          sh.add(sl);
        }
        group.add(sh);
      }
    } else if (item.category === "accessory") {
      if (s === "cape") {
        const cp = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.88, 0.04), matPrimary);
        cp.position.set(0, -0.22, -0.2);
        cp.rotation.x = 0.14;
        group.add(cp);
      } else if (s === "wings") {
        for (const d of [-1, 1]) {
          const w = new THREE.Mesh(new THREE.ConeGeometry(0.32, 0.65, 4), matGlow);
          w.position.set(d * 0.28, 0.12, -0.18);
          w.rotation.z = -d * 0.8;
          w.scale.z = 0.18;
          group.add(w);
        }
      } else if (s === "halo") {
        const rg = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.025, 10, 24), matGlow);
        rg.rotation.x = Math.PI / 2;
        rg.position.set(0, 0.65, 0);
        group.add(rg);
      } else {
        const orb = new THREE.Mesh(new THREE.OctahedronGeometry(0.16, 1), matGlow);
        orb.position.set(0.36, 0.35, -0.12);
        group.add(orb);
      }
    } else if (item.category === "weapon") {
      group.add(new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.035, 0.26, 8), matAccent));
      if (item.weapon_type === "lightsaber") {
        const bl = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.95, 10), matGlow);
        bl.position.y = 0.58;
        group.add(bl);
      } else if (item.weapon_type === "broadsword") {
        const gd = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.05, 0.08), matAccent);
        gd.position.y = 0.12;
        const bl = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.05, 0.03), matPrimary);
        bl.position.y = 0.65;
        group.add(gd, bl);
      } else if (item.weapon_type === "daggers") {
        const bl = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.48, 6), matPrimary);
        bl.position.y = 0.34;
        group.add(bl);
      } else {
        const sh = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, 1.35, 8), matAccent);
        sh.position.y = 0.45;
        const hd = new THREE.Mesh(new THREE.OctahedronGeometry(0.16, 1), matGlow);
        hd.position.y = 1.16;
        group.add(sh, hd);
      }
    }
    return group;
  }

  function ensureThumbnails(THREE) {
    if (Object.keys(thumbCache).length === CATALOGUE_RAW.length) return;
    const offCv = document.createElement("canvas");
    offCv.width = 96;
    offCv.height = 96;
    let offR;
    try {
      offR = new THREE.WebGLRenderer({ canvas: offCv, alpha: true, antialias: true, preserveDrawingBuffer: true });
    } catch (_) { return; }
    offR.setSize(96, 96, false);
    const sc = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(38, 1, 0.1, 20);
    const dir = new THREE.DirectionalLight(0xffffff, 1.15);
    dir.position.set(2, 3, 3);
    sc.add(new THREE.AmbientLight(0xffe3ee, 0.95), dir);

    const dMat = new THREE.MeshStandardMaterial({ color: 0x5c4353, roughness: 0.7 });
    const dHead = new THREE.Mesh(new THREE.SphereGeometry(0.21, 14, 12), dMat);
    dHead.position.y = 0.55;
    const dBody = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.16, 0.55, 12), dMat);
    dBody.position.y = 0.05;
    const man = new THREE.Group();
    man.add(dHead, dBody);
    const mount = new THREE.Group();
    sc.add(man, mount);

    for (const item of Object.values(CATALOGUE)) {
      if (thumbCache[item.id]) continue;
      while (mount.children.length) disposeObject3D(mount.children.pop());
      const mesh = buildItemMesh(THREE, item, SWATCHES[item.category === "hat" ? 3 : item.category === "weapon" ? 2 : 0]);
      mount.add(mesh);
      man.visible = item.category !== "weapon" && item.shape !== "none";
      if (item.category === "hair" || item.category === "hat") {
        mesh.position.set(0, 0.55, 0); cam.position.set(0.3, 0.68, 1.45); cam.lookAt(0, 0.62, 0);
      } else if (item.category === "shoes") {
        man.visible = false; mesh.position.set(0, -0.1, 0); cam.position.set(0.35, 0.08, 1.15); cam.lookAt(0, 0, 0);
      } else if (item.category === "weapon") {
        mesh.position.set(0, -0.35, 0); mesh.rotation.z = -0.45; cam.position.set(0, 0.15, 1.95); cam.lookAt(0, 0.1, 0);
      } else {
        mesh.position.set(0, 0.02, 0); cam.position.set(0.4, 0.1, 1.85); cam.lookAt(0, 0.05, 0);
      }
      offR.render(sc, cam);
      thumbCache[item.id] = offCv.toDataURL("image/png");
    }
    disposeObject3D(man);
    disposeObject3D(mount);
    offR.dispose();
    offR.forceContextLoss();
  }

  function createCharacterRig(THREE) {
    const root = new THREE.Group(), hips = new THREE.Group(), torso = new THREE.Group(), headGroup = new THREE.Group();
    hips.position.y = 0.75;
    headGroup.position.y = 0.62;
    root.add(hips);
    hips.add(torso);
    torso.add(headGroup);

    const skinMat = new THREE.MeshStandardMaterial({ color: 0xffd6c4, roughness: 0.55 });
    const eyeMat = new THREE.MeshBasicMaterial({ color: 0x140810 });
    const chest = new THREE.Mesh(new THREE.CylinderGeometry(0.21, 0.17, 0.46, 12), skinMat);
    chest.position.y = 0.24;
    torso.add(chest);
    headGroup.add(new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 14), skinMat));
    for (const d of [-1, 1]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(0.028, 8, 8), eyeMat);
      eye.position.set(d * 0.075, 0.02, 0.195);
      headGroup.add(eye);
    }

    const armL = new THREE.Group(), armR = new THREE.Group();
    armL.position.set(-0.27, 0.42, 0);
    armR.position.set(0.27, 0.42, 0);
    const armMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.048, 0.44, 8), skinMat);
    armMesh.position.y = -0.2;
    armL.add(armMesh);
    armR.add(armMesh.clone());

    const weaponHand = new THREE.Group();
    weaponHand.position.set(0, -0.4, 0.04);
    weaponHand.rotation.x = Math.PI * 0.38;
    armR.add(weaponHand);
    torso.add(armL, armR);

    const legL = new THREE.Group(), legR = new THREE.Group();
    legL.position.set(-0.11, 0, 0);
    legR.position.set(0.11, 0, 0);
    const legMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.055, 0.56, 8), skinMat);
    legMesh.position.y = -0.28;
    legL.add(legMesh);
    legR.add(legMesh.clone());
    hips.add(legL, legR);

    const slots = {
      hair: new THREE.Group(), hat: new THREE.Group(), top: new THREE.Group(),
      bottom: new THREE.Group(), dress: new THREE.Group(), shoesL: new THREE.Group(),
      shoesR: new THREE.Group(), accessory: new THREE.Group(), weapon: new THREE.Group(),
    };
    headGroup.add(slots.hair, slots.hat);
    slots.top.position.y = 0.24;
    slots.dress.position.y = 0.02;
    slots.accessory.position.y = 0.26;
    torso.add(slots.top, slots.dress, slots.accessory);
    hips.add(slots.bottom);
    slots.shoesL.position.set(0, -0.58, 0);
    slots.shoesR.position.set(0, -0.58, 0);
    legL.add(slots.shoesL);
    legR.add(slots.shoesR);
    weaponHand.add(slots.weapon);

    const trailGeo = new THREE.BufferGeometry();
    trailGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(36), 3));
    const trailMesh = new THREE.Mesh(trailGeo, new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0, side: THREE.DoubleSide }));

    return { root, hips, torso, headGroup, armL, armR, legL, legR, weaponHand, slots, trailMesh, trailHistory: [], animState: "idle", swingUntil: 0, hitUntil: 0, ko: false, prevX: 0, clothTilt: 0 };
  }

  function applyOutfitToRig(THREE, rig, outfit) {
    if (!rig || !outfit) return;
    for (const g of Object.values(rig.slots)) {
      while (g.children.length) disposeObject3D(g.children.pop());
    }
    const cols = outfit.colors || {};
    const c = (k) => SWATCHES[cols[k] ?? 0] || SWATCHES[0];
    rig.slots.hair.add(buildItemMesh(THREE, CATALOGUE[outfit.hair], c("hair")));
    rig.slots.hat.add(buildItemMesh(THREE, CATALOGUE[outfit.hat], c("hat")));
    rig.slots.accessory.add(buildItemMesh(THREE, CATALOGUE[outfit.accessory], c("accessory")));
    if (outfit.dress && outfit.dress !== "dress_none") {
      rig.slots.dress.add(buildItemMesh(THREE, CATALOGUE[outfit.dress], c("dress")));
    } else {
      rig.slots.top.add(buildItemMesh(THREE, CATALOGUE[outfit.top], c("top")));
      rig.slots.bottom.add(buildItemMesh(THREE, CATALOGUE[outfit.bottom], c("bottom")));
    }
    const sh = CATALOGUE[outfit.shoes];
    if (sh) {
      const pair = buildItemMesh(THREE, sh, c("shoes"));
      if (pair.children.length >= 2) {
        const l = pair.children[0].clone(), r = pair.children[1].clone();
        l.position.x = 0; r.position.x = 0;
        rig.slots.shoesL.add(l); rig.slots.shoesR.add(r);
      }
      disposeObject3D(pair);
    }
    rig.slots.weapon.add(buildItemMesh(THREE, CATALOGUE[outfit.weapon] || CATALOGUE.wep_saber_cyan, c("weapon")));
    if (rig.trailMesh) rig.trailMesh.material.color.set(c("weapon"));
  }

  function createGlassTubePod(THREE, xPos, frosted) {
    const pod = new THREE.Group();
    pod.position.set(xPos, 0, 0);
    const capMat = new THREE.MeshStandardMaterial({ color: 0x2c1625, metalness: 0.85, roughness: 0.22 });
    const baseCap = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.25, 0.22, 32), capMat);
    baseCap.position.y = 0.11;
    const turntable = new THREE.Mesh(new THREE.CylinderGeometry(0.92, 0.96, 0.08, 28), new THREE.MeshStandardMaterial({ color: 0xffe3ee, metalness: 0.4, roughness: 0.3 }));
    turntable.position.y = 0.24;
    const topCap = new THREE.Mesh(new THREE.CylinderGeometry(1.22, 1.15, 0.24, 32), capMat);
    topCap.position.y = 3.15;

    const ringMat = new THREE.MeshStandardMaterial({ color: 0xff5ca8, emissive: 0xff5ca8, emissiveIntensity: 1.4, roughness: 0.1 });
    const bottomRing = new THREE.Mesh(new THREE.TorusGeometry(1.06, 0.035, 12, 36), ringMat);
    bottomRing.rotation.x = Math.PI / 2; bottomRing.position.y = 0.24;
    const topRing = new THREE.Mesh(new THREE.TorusGeometry(1.06, 0.035, 12, 36), ringMat.clone());
    topRing.rotation.x = Math.PI / 2; topRing.position.y = 3.02;

    const glassMat = new THREE.MeshPhysicalMaterial({
      color: frosted ? 0xffcce5 : 0xffffff, transparent: true, opacity: frosted ? 0.86 : 0.26,
      roughness: frosted ? 0.65 : 0.08, metalness: 0.08, reflectivity: 0.9, side: THREE.DoubleSide,
    });
    const glassCyl = new THREE.Mesh(new THREE.CylinderGeometry(1.05, 1.05, 2.8, 32, 1, true), glassMat);
    glassCyl.position.y = 1.62;
    const rimCyl = new THREE.Mesh(new THREE.CylinderGeometry(1.075, 1.075, 2.8, 32, 1, true), new THREE.MeshBasicMaterial({ color: 0xff85c0, transparent: true, opacity: 0.14, side: THREE.BackSide }));
    rimCyl.position.y = 1.62;

    const mistGroup = new THREE.Group();
    const mistMat = new THREE.MeshBasicMaterial({ color: 0xffe3ee, transparent: true, opacity: 0.22 });
    for (let i = 0; i < 8; i++) {
      const pf = new THREE.Mesh(new THREE.SphereGeometry(0.24, 10, 8), mistMat);
      const a = (i / 8) * Math.PI * 2;
      pf.position.set(Math.cos(a) * 0.62, 0.32, Math.sin(a) * 0.62);
      pf.scale.y = 0.45;
      mistGroup.add(pf);
    }
    pod.add(baseCap, turntable, topCap, bottomRing, topRing, glassCyl, rimCyl, mistGroup);
    return { pod, turntable, glassMat, bottomRing, topRing, mistGroup, pulseEnergy: 0 };
  }

  function triggerTubePulse(role, withSparkles) {
    const t = tubes[role];
    if (!t) return;
    t.pulseEnergy = 1.0;
    if (role === myRole) spinImpulse = 7.5;
    if (withSparkles && !reducedMotion && window.THREE && scene) {
      const THREE = window.THREE;
      const bp = t.pod.position;
      for (let i = 0; i < 14; i++) {
        const sp = new THREE.Mesh(new THREE.OctahedronGeometry(0.055, 0), new THREE.MeshBasicMaterial({ color: i % 2 ? 0xffd166 : 0x00e5ff, transparent: true, opacity: 1 }));
        sp.position.set(bp.x + (Math.random() - 0.5) * 0.9, 0.8 + Math.random() * 1.4, (Math.random() - 0.5) * 0.9);
        scene.add(sp);
        sparkles.push({ mesh: sp, vx: (Math.random() - 0.5) * 1.6, vy: 1.0 + Math.random(), vz: (Math.random() - 0.5) * 1.6, life: 0.55 });
      }
    }
  }

  function setupShowroomScene(THREE) {
    if (!scene) return;
    while (scene.children.length) disposeObject3D(scene.children.pop());
    sparkles = []; shockwaves = []; hitSparks = []; dustPuffs = [];
    scene.background = new THREE.Color(0x140810);
    scene.fog = new THREE.FogExp2(0x1f0b18, 0.065);
    const keyL = new THREE.DirectionalLight(0xfff0f6, 1.15); keyL.position.set(3, 6, 5);
    const pL = new THREE.PointLight(0xd9488f, 1.8, 14); pL.position.set(-2, 3, 2);
    scene.add(new THREE.AmbientLight(0xffe3ee, 0.78), keyL, pL);

    const fl = new THREE.Mesh(new THREE.CircleGeometry(12, 40), new THREE.MeshStandardMaterial({ color: 0x240d1c, roughness: 0.25, metalness: 0.5 }));
    fl.rotation.x = -Math.PI / 2;
    scene.add(fl);

    const oppRole = myRole === "white" ? "black" : "white";
    tubes[myRole] = createGlassTubePod(THREE, -1.35, false);
    tubes[oppRole] = createGlassTubePod(THREE, 1.45, true);
    scene.add(tubes[myRole].pod, tubes[oppRole].pod);

    rigs[myRole] = createCharacterRig(THREE);
    rigs[myRole].root.position.set(-1.35, 0.28, 0);
    applyOutfitToRig(THREE, rigs[myRole], myOutfit);

    rigs[oppRole] = createCharacterRig(THREE);
    rigs[oppRole].root.position.set(1.45, 0.28, 0);
    applyOutfitToRig(THREE, rigs[oppRole], makeDefaultOutfit());
    scene.add(rigs[myRole].root, rigs[oppRole].root);

    targetZoom = 5.2; targetCamY = 1.45;
    camera.position.set(-0.2, targetCamY, targetZoom);
    camera.lookAt(-0.35, 1.35, 0);
  }

  function setupArenaScene(THREE, theme, playersData) {
    if (!scene) return;
    while (scene.children.length) disposeObject3D(scene.children.pop());
    sparkles = []; shockwaves = []; hitSparks = []; dustPuffs = [];
    const palettes = {
      "Royal Gala": { sky: 0x1b0e26, fog: 0x261233, floor: 0x42213d, accent: 0xffd166 },
      "Cyberpunk Heist": { sky: 0x090b1a, fog: 0x0d122b, floor: 0x141b38, accent: 0x00e5ff },
      "Beach Samurai": { sky: 0x1f2d42, fog: 0x2b3e57, floor: 0xd9b282, accent: 0xff7fb0 },
      "Enchanted Forest": { sky: 0x0d211d, fog: 0x13302a, floor: 0x1f4738, accent: 0x72efdd },
      "Neon Disco": { sky: 0x180724, fog: 0x260b38, floor: 0x2d0f42, accent: 0xff5ca8 },
    };
    const pal = palettes[theme] || palettes["Royal Gala"];
    scene.background = new THREE.Color(pal.sky);
    scene.fog = new THREE.FogExp2(pal.fog, 0.035);
    const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(4, 10, 7);
    const rim = new THREE.PointLight(pal.accent, 2.2, 24); rim.position.set(0, 4, -3);
    scene.add(new THREE.AmbientLight(0xffe3ee, 0.8), sun, rim);

    const floor = new THREE.Mesh(new THREE.BoxGeometry(32, 0.6, 8), new THREE.MeshStandardMaterial({ color: pal.floor, roughness: 0.4, metalness: 0.3 }));
    floor.position.y = -0.3;
    scene.add(floor);

    for (let i = -3; i <= 3; i++) {
      if (i === 0) continue;
      const prop = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.38, 3.8, 12), new THREE.MeshStandardMaterial({ color: pal.accent, roughness: 0.3, metalness: 0.5 }));
      prop.position.set(i * 4.2, 1.6, -3.2);
      scene.add(prop);
    }

    for (const rk of ["white", "black"]) {
      const pInfo = playersData[rk];
      const rig = createCharacterRig(THREE);
      applyOutfitToRig(THREE, rig, pInfo.outfit);
      rig.root.position.set(pInfo.x, pInfo.y || 0, 0);
      rig.root.rotation.y = pInfo.facing >= 0 ? Math.PI * 0.5 : -Math.PI * 0.5;
      rig.prevX = pInfo.x;
      rigs[rk] = rig;
      scene.add(rig.root, rig.trailMesh);
    }
    camera.position.set(0, 2.6, 11.5);
    camera.lookAt(0, 1.3, 0);
  }

  function spawnHitEffects(THREE, x, y, blocked) {
    if (reducedMotion) return;
    camShake = blocked ? 0.12 : 0.32;
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.15, 0.28, 24), new THREE.MeshBasicMaterial({ color: blocked ? 0x00e5ff : 0xff5ca8, side: THREE.DoubleSide, transparent: true, opacity: 0.95 }));
    ring.position.set(x, y + 1.0, 0.3);
    scene.add(ring);
    shockwaves.push({ mesh: ring, life: 0.35 });
    for (let i = 0; i < 10; i++) {
      const sp = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.07, 0.07), new THREE.MeshBasicMaterial({ color: blocked ? 0x00e5ff : 0xffd166, transparent: true, opacity: 1 }));
      sp.position.set(x, y + 1.0, 0.2);
      scene.add(sp);
      hitSparks.push({ mesh: sp, vx: (Math.random() - 0.5) * 6, vy: 1.5 + Math.random() * 4, vz: (Math.random() - 0.5) * 4, life: 0.38 });
    }
  }

  function spawnFloatingDamage(worldX, worldY, dmg, blocked) {
    if (!ui.floatLayer || !camera || !renderer) return;
    const v = new window.THREE.Vector3(worldX, worldY + 1.75, 0).project(camera);
    const rect = renderer.domElement.getBoundingClientRect();
    const tag = H.el("div", "dd-dmg-num" + (blocked ? " is-blocked" : ""), (blocked ? "BLOCK -" : "-") + dmg);
    tag.style.left = (v.x * 0.5 + 0.5) * rect.width + "px";
    tag.style.top = (-v.y * 0.5 + 0.5) * rect.height + "px";
    ui.floatLayer.append(tag);
    setTimeout(() => tag.remove(), 760);
  }

  function animateRig(THREE, rig, t, dt, isArena) {
    if (!rig) return;
    const now = performance.now();
    if (rig.ko) {
      rig.root.rotation.z = THREE.MathUtils.lerp(rig.root.rotation.z, Math.PI * 0.48, dt * 6);
      rig.hips.position.y = THREE.MathUtils.lerp(rig.hips.position.y, 0.25, dt * 6);
      return;
    }
    rig.root.rotation.z = 0;
    const vx = (rig.root.position.x - rig.prevX) / Math.max(dt, 0.001);
    rig.prevX = rig.root.position.x;
    rig.clothTilt = THREE.MathUtils.lerp(rig.clothTilt, THREE.MathUtils.clamp(-vx * 0.045, -0.35, 0.35), dt * 10);
    rig.slots.accessory.rotation.x = 0.12 + Math.abs(rig.clothTilt);
    rig.slots.hair.rotation.z = rig.clothTilt * 0.5;
    rig.hips.position.y = 0.75 + Math.sin(t * 3.2) * 0.025;
    rig.torso.rotation.x = now < rig.hitUntil ? -0.38 : 0;

    if (isArena && Math.abs(vx) > 0.35) {
      const w = Math.sin(t * 13);
      rig.legL.rotation.x = w * 0.65; rig.legR.rotation.x = -w * 0.65; rig.armL.rotation.x = -w * 0.45;
    } else {
      rig.legL.rotation.x = THREE.MathUtils.lerp(rig.legL.rotation.x, 0, dt * 10);
      rig.legR.rotation.x = THREE.MathUtils.lerp(rig.legR.rotation.x, 0, dt * 10);
      rig.armL.rotation.x = THREE.MathUtils.lerp(rig.armL.rotation.x, 0, dt * 10);
    }

    if (now < rig.swingUntil) {
      const rem = (rig.swingUntil - now) / 260;
      const sw = rem > 0.75 ? -0.7 : Math.sin((1 - rem) * Math.PI) * 2.1;
      rig.armR.rotation.x = -sw;
      rig.torso.rotation.y = sw * 0.3;
    } else {
      rig.armR.rotation.x = rig.animState === "block" ? -1.1 : -0.25;
      rig.armR.rotation.z = rig.animState === "block" ? -0.5 : 0;
      rig.torso.rotation.y = phase === "reveal" ? Math.sin(t * 2.5) * 0.35 : 0;
    }
  }

  function renderFrame(rawTime) {
    const nowSec = rawTime * 0.001;
    let dt = Math.min(nowSec - (prevFrameTime || nowSec), 0.05);
    prevFrameTime = nowSec;
    if (performance.now() < slowMoUntil) dt *= slowMoFactor;
    const THREE = window.THREE;

    if (THREE && renderer && scene && camera) {
      if (phase === "dress" || phase === "reveal") {
        if (spinImpulse > 0.01) {
          turntableAngle += spinImpulse * dt;
          spinImpulse *= Math.pow(0.08, dt);
        }
        if (rigs[myRole]) rigs[myRole].root.rotation.y = turntableAngle;
        for (const rk of ["white", "black"]) {
          const tb = tubes[rk];
          if (tb) {
            tb.pulseEnergy = Math.max(0, tb.pulseEnergy - dt * 1.8);
            const em = 1.1 + tb.pulseEnergy * 2.6 + Math.sin(nowSec * 3) * 0.2;
            tb.bottomRing.material.emissiveIntensity = em;
            tb.topRing.material.emissiveIntensity = em;
            tb.mistGroup.rotation.y += dt * 0.45;
          }
          animateRig(THREE, rigs[rk], nowSec, dt, false);
        }
        if (phase === "reveal") {
          const opp = myRole === "white" ? "black" : "white";
          if (tubes[opp]) {
            tubes[opp].glassMat.opacity = THREE.MathUtils.lerp(tubes[opp].glassMat.opacity, 0.24, dt * 4);
            tubes[opp].glassMat.roughness = THREE.MathUtils.lerp(tubes[opp].glassMat.roughness, 0.08, dt * 4);
          }
          camera.position.set(THREE.MathUtils.lerp(camera.position.x, 0.05, dt * 3), 1.45, THREE.MathUtils.lerp(camera.position.z, 5.8, dt * 3));
          camera.lookAt(0.05, 1.35, 0);
        } else {
          camera.position.y = THREE.MathUtils.lerp(camera.position.y, targetCamY, dt * 7);
          camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZoom, dt * 7);
          camera.lookAt(-1.1, targetCamY - 0.05, 0);
        }
      } else if (phase === "arena" && arenaState) {
        const me = arenaState.players[myRole];
        const oppRole = myRole === "white" ? "black" : "white";
        const opp = arenaState.players[oppRole];
        const dir = ((keys.d || keys.arrowright || touchInput.right) ? 1 : 0) - ((keys.a || keys.arrowleft || touchInput.left) ? 1 : 0);
        const blockKey = keys.k || touchInput.block;
        if (dir !== 0 && !blockKey) me.x = Math.max(-14, Math.min(14, me.x + dir * 7.8 * dt));
        if ((keys.w || keys.arrowup || touchInput.jump) && (me.y || 0) <= 0.02) { me.vy = 6.6; me.anim = "dodge"; }
        me.vy = (me.vy || 0) - 18.0 * dt;
        me.y = Math.max(0, (me.y || 0) + me.vy * dt);
        if (me.y === 0) me.vy = 0;
        me.facing = opp.x >= me.x ? 1 : -1;
        me.blocking = !!blockKey;
        me.anim = me.blocking ? "block" : me.y > 0.1 ? "jump" : dir !== 0 ? "run" : "idle";

        if (rawTime - lastPosSend >= 50) {
          lastPosSend = rawTime;
          window.SocketClient.emit("duel:pos", { gid, x: me.x, y: me.y, facing: me.facing, anim: me.anim, blocking: me.blocking });
        }
        if (opp.targetX !== undefined) {
          opp.x = THREE.MathUtils.lerp(opp.x, opp.targetX, Math.min(1, dt * 14));
          opp.y = THREE.MathUtils.lerp(opp.y || 0, opp.targetY || 0, Math.min(1, dt * 14));
        }
        for (const rk of ["white", "black"]) {
          const pData = arenaState.players[rk], rig = rigs[rk];
          if (rig && pData) {
            rig.root.position.set(pData.x, pData.y || 0, 0);
            rig.root.rotation.y = THREE.MathUtils.lerp(rig.root.rotation.y, pData.facing >= 0 ? Math.PI * 0.5 : -Math.PI * 0.5, dt * 12);
            rig.animState = pData.anim || "idle";
            animateRig(THREE, rig, nowSec, dt, true);
          }
        }
        const midX = (me.x + opp.x) * 0.5;
        const desiredZ = Math.max(7.2, Math.min(13.5, 6.2 + Math.abs(me.x - opp.x) * 0.52)) - camShake * 1.8;
        camera.position.x = THREE.MathUtils.lerp(camera.position.x, midX, dt * 5);
        camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredZ, dt * 5);
        if (camShake > 0.005 && !reducedMotion) {
          camera.position.x += (Math.random() - 0.5) * camShake;
          camShake *= Math.pow(0.02, dt);
        }
        camera.lookAt(midX, 1.25, 0);
      }

      for (const arr of [sparkles, shockwaves, hitSparks]) {
        for (let i = arr.length - 1; i >= 0; i--) {
          const p = arr[i]; p.life -= dt;
          if (p.vx !== undefined) { p.mesh.position.x += p.vx * dt; p.mesh.position.y += p.vy * dt; p.mesh.position.z += p.vz * dt; }
          else { const s = 1 + (0.35 - p.life) * 8; p.mesh.scale.set(s, s, 1); }
          if (p.life <= 0) { scene.remove(p.mesh); disposeObject3D(p.mesh); arr.splice(i, 1); }
        }
      }
      renderer.render(scene, camera);
    }
    rafId = requestAnimationFrame(renderFrame);
  }

  function renderWardrobeGrid() {
    if (!ui.grid) return;
    for (const b of ui.tabs.children) b.classList.toggle("is-active", b.dataset.cat === activeCategory);
    const curSw = myOutfit.colors[activeCategory] ?? 0;
    Array.from(ui.swatchRow.children).forEach((b, i) => b.classList.toggle("is-active", i === curSw));
    ui.grid.replaceChildren();
    const items = BY_CAT[activeCategory] || [];
    items.forEach((item, idx) => {
      const card = H.el("button", `dd-card r-${item.rarity}`);
      card.type = "button";
      if (myOutfit[activeCategory] === item.id) card.classList.add("is-equipped");
      const img = document.createElement("img");
      img.className = "dd-thumb"; img.alt = item.name;
      img.src = thumbCache[item.id] || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
      card.append(img, H.el("div", "dd-card-title", item.name), H.el("div", "dd-card-tag", item.tags.includes(currentTheme) ? "★ Theme Match" : item.rarity.toUpperCase()));
      card.onclick = () => {
        if (isReady || phase !== "dress") return;
        myOutfit[item.category] = item.id;
        if (window.THREE && rigs[myRole]) { applyOutfitToRig(window.THREE, rigs[myRole], myOutfit); triggerTubePulse(myRole, true); }
        renderWardrobeGrid();
        window.SocketClient.emit("duel:preview", { gid, outfit: myOutfit });
      };
      card.onkeydown = (e) => {
        const cards = Array.from(ui.grid.querySelectorAll(".dd-card"));
        const map = { ArrowRight: (idx + 1) % items.length, ArrowLeft: (idx - 1 + items.length) % items.length, ArrowDown: Math.min(items.length - 1, idx + 2), ArrowUp: Math.max(0, idx - 2) };
        if (map[e.key] !== undefined && cards[map[e.key]]) { e.preventDefault(); cards[map[e.key]].focus(); }
      };
      ui.grid.append(card);
    });
  }

  function updateMeterUI(scoreObj) {
    if (!scoreObj || !ui.meterFill) return;
    const total = scoreObj.total || 0;
    ui.meterFill.style.width = Math.min(100, Math.max(8, Math.round((total / 180) * 100))) + "%";
    ui.meterValue.textContent = total + " pts";
  }

  function startCountdown(seconds) {
    clearInterval(countdownInterval);
    secondsLeft = seconds; maxPhaseSeconds = Math.max(1, seconds);
    const tick = () => {
      if (ui.timerText) ui.timerText.textContent = Math.max(0, secondsLeft) + "s";
      if (ui.ringFg) {
        ui.ringFg.style.strokeDasharray = "100 100";
        ui.ringFg.style.strokeDashoffset = String(100 - (Math.max(0, secondsLeft) / maxPhaseSeconds) * 100);
      }
    };
    tick();
    countdownInterval = setInterval(() => { secondsLeft = Math.max(0, secondsLeft - 1); tick(); }, 1000);
  }

  function buildShellDOM() {
    box.replaceChildren();
    rootEl = H.el("div", "dd-root");
    const topbar = H.el("div", "dd-topbar");
    const themePill = H.el("div", "dd-theme-pill", "Theme: Loading...");
    const meterWrap = H.el("div", "dd-meter-wrap");
    const meterTrack = H.el("div", "dd-meter-track"), meterFill = H.el("div", "dd-meter-fill"), meterValue = H.el("span", "dd-meter-label", "0 pts");
    meterTrack.append(meterFill);
    meterWrap.append(H.el("span", "dd-meter-label", "Style"), meterTrack, meterValue);

    const timerWrap = H.el("div", "dd-timer-ring");
    const svgNS = "http://www.w3.org/2000/svg", svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 36 36"); svg.setAttribute("class", "dd-ring-svg");
    const cBg = document.createElementNS(svgNS, "circle"), cFg = document.createElementNS(svgNS, "circle");
    cBg.setAttribute("class", "dd-ring-bg"); cBg.setAttribute("cx", "18"); cBg.setAttribute("cy", "18"); cBg.setAttribute("r", "15.9");
    cFg.setAttribute("class", "dd-ring-fg"); cFg.setAttribute("cx", "18"); cFg.setAttribute("cy", "18"); cFg.setAttribute("r", "15.9");
    svg.append(cBg, cFg);
    const timerText = H.el("span", "", "60s");
    timerWrap.append(svg, timerText);
    topbar.append(themePill, meterWrap, timerWrap);

    const main = H.el("div", "dd-main"), stageWrap = H.el("div", "dd-stage-wrap"), canvas = H.el("canvas", "dd-canvas"), floatLayer = H.el("div", "dd-float-layer"), camBar = H.el("div", "dd-cam-bar");
    [{ label: "Full Body", y: 1.45, z: 5.2 }, { label: "Face / Hair", y: 1.92, z: 2.65 }, { label: "Shoes", y: 0.55, z: 2.85 }].forEach((p, idx) => {
      const b = H.el("button", "dd-chip-btn" + (idx === 0 ? " is-active" : ""), p.label);
      b.onclick = () => { targetCamY = p.y; targetZoom = p.z; Array.from(camBar.children).forEach((c) => c.classList.remove("is-active")); b.classList.add("is-active"); };
      camBar.append(b);
    });
    stageWrap.append(canvas, floatLayer, camBar);

    const wardrobe = H.el("div", "dd-wardrobe"), tabs = H.el("div", "dd-tabs");
    CATEGORIES.forEach((cat) => {
      const tb = H.el("button", "dd-tab", cat.label); tb.dataset.cat = cat.key;
      tb.onclick = () => { activeCategory = cat.key; renderWardrobeGrid(); };
      tabs.append(tb);
    });
    const swatchesWrap = H.el("div", "dd-swatches"), swatchRow = H.el("div", "dd-swatch-row");
    for (let i = 0; i < SWATCHES.length; i++) {
      const sb = H.el("button", `dd-swatch c${i}`);
      sb.onclick = () => {
        if (isReady || phase !== "dress") return;
        myOutfit.colors[activeCategory] = i;
        if (window.THREE && rigs[myRole]) { applyOutfitToRig(window.THREE, rigs[myRole], myOutfit); triggerTubePulse(myRole, true); }
        renderWardrobeGrid();
        window.SocketClient.emit("duel:preview", { gid, outfit: myOutfit });
      };
      swatchRow.append(sb);
    }
    swatchesWrap.append(H.el("span", "dd-meter-label", "Color"), swatchRow);
    const grid = H.el("div", "dd-grid"), readyFooter = H.el("div", "dd-ready-footer"), readyBtn = H.el("button", "dd-ready-btn", "Lock Outfit & Ready!");
    readyBtn.onclick = () => {
      if (isReady || phase !== "dress") return;
      isReady = true; readyBtn.classList.add("is-locked"); readyBtn.textContent = "Outfit Locked ✓";
      window.SocketClient.emit("duel:outfit", { gid, outfit: myOutfit });
    };
    readyFooter.append(readyBtn);
    wardrobe.append(tabs, swatchesWrap, grid, readyFooter);
    main.append(stageWrap, wardrobe);

    const makeCard = (rk) => {
      const card = H.el("div", "dd-fighter-card"), top = H.el("div", "dd-fighter-top"), portrait = document.createElement("img");
      portrait.className = "dd-portrait";
      const meta = H.el("div", "dd-fighter-meta"), name = H.el("div", "dd-fighter-name", rk.toUpperCase()), buff = H.el("span", "dd-buff-badge", "Standard");
      meta.append(name, buff); top.append(portrait, meta);
      const hpTrack = H.el("div", "dd-hp-track"), hpFill = H.el("div", "dd-hp-fill"), cdTrack = H.el("div", "dd-cd-track"), cdFill = H.el("div", "dd-cd-fill");
      hpTrack.append(hpFill); cdTrack.append(cdFill); card.append(top, hpTrack, cdTrack);
      return { card, portrait, name, buff, hpFill, cdFill };
    };
    const arenaHud = H.el("div", "dd-arena-hud dd-hidden"), cardWhite = makeCard("white"), cardBlack = makeCard("black");
    arenaHud.append(cardWhite.card, cardBlack.card);

    const touchBar = H.el("div", "dd-touch-bar dd-hidden"), lCl = H.el("div", "dd-touch-cluster"), rCl = H.el("div", "dd-touch-cluster");
    const mkT = (lbl, fn) => { const b = H.el("button", "dd-touch-btn", lbl); b.onpointerdown = (e) => { e.preventDefault(); fn(true); }; b.onpointerup = b.onpointerleave = () => fn(false); return b; };
    const atkB = H.el("button", "dd-touch-btn", "ATK"); atkB.onclick = () => window.SocketClient.emit("duel:attack", { gid });
    lCl.append(mkT("◀", (v) => (touchInput.left = v)), mkT("▶", (v) => (touchInput.right = v)));
    rCl.append(mkT("JUMP", (v) => (touchInput.jump = v)), mkT("BLK", (v) => (touchInput.block = v)), atkB);
    touchBar.append(lCl, rCl);

    const modal = H.el("div", "dd-banner-modal dd-hidden");
    rootEl.append(topbar, main, arenaHud, touchBar, modal);
    box.append(rootEl);

    ui = { themePill, meterWrap, meterFill, meterValue, ringFg: cFg, timerText, stageWrap, canvas, floatLayer, camBar, wardrobe, tabs, swatchRow, grid, readyBtn, arenaHud, cards: { white: cardWhite, black: cardBlack }, touchBar, modal };

    let drag = false, lx = 0;
    addManagedListener(canvas, "pointerdown", (e) => { drag = true; lx = e.clientX; });
    addManagedListener(window, "pointermove", (e) => { if (drag && phase === "dress") { turntableAngle += (e.clientX - lx) * 0.012; lx = e.clientX; } });
    addManagedListener(window, "pointerup", () => { drag = false; });
    addManagedListener(canvas, "wheel", (e) => { if (phase === "dress") { e.preventDefault(); targetZoom = Math.max(2.3, Math.min(6.4, targetZoom + e.deltaY * 0.003)); } }, { passive: false });
  }

  function onResize() {
    if (!renderer || !camera || !ui.stageWrap) return;
    const w = Math.max(1, ui.stageWrap.clientWidth), h = Math.max(1, ui.stageWrap.clientHeight);
    camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h, false);
  }

  function stopAndDispose(notifyServer = true) {
    if (notifyServer && gid) window.SocketClient.emit("duel:leave", { gid });
    cancelAnimationFrame(rafId); clearInterval(countdownInterval);
    while (cleanupListeners.length) { try { cleanupListeners.pop()(); } catch (_) {} }
    if (scene) { disposeObject3D(scene); scene = null; }
    if (renderer) { renderer.dispose(); renderer.forceContextLoss(); renderer = null; }
    camera = null; tubes = {}; rigs = {}; arenaState = null; keys = {}; gid = null; phase = "idle"; box = null; rootEl = null;
  }

  async function open() {
    reducedMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    box = H.overlay("Dress Duel", () => stopAndDispose(true)).box;
    if (!hasWebGL()) {
      box.append(H.el("div", "dd-modal-card", "WebGL 3D is unavailable in your browser."));
      return;
    }
    buildShellDOM();
    try {
      const THREE = await loadThree();
      ensureThumbnails(THREE);
      renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(45, 1.5, 0.1, 80);
      onResize();
      addManagedListener(window, "resize", onResize);
      addManagedListener(window, "keydown", (e) => {
        const k = e.key.toLowerCase(); keys[k] = true;
        if (phase === "arena" && (k === " " || k === "j")) { e.preventDefault(); window.SocketClient.emit("duel:attack", { gid }); }
      });
      addManagedListener(window, "keyup", (e) => { keys[e.key.toLowerCase()] = false; });
      addManagedListener(window, "blur", () => { keys = {}; });
      setupShowroomScene(THREE);
      renderWardrobeGrid();
      prevFrameTime = performance.now() * 0.001;
      rafId = requestAnimationFrame(renderFrame);
      window.SocketClient.emit("duel:join", {});
    } catch (err) {
      box.replaceChildren(H.el("p", "", "3D Load Error: " + err.message));
    }
  }

  function init() {
    if (inited) return;
    inited = true;
    window.SocketClient.on("duel:theme", (d) => {
      if (!box || !d) return;
      gid = d.gid; phase = "dress"; myRole = d.you || "white"; currentTheme = d.theme; myOutfit = d.outfit || makeDefaultOutfit(); isReady = false;
      ui.modal.classList.add("dd-hidden"); ui.wardrobe.classList.remove("dd-hidden"); ui.camBar.classList.remove("dd-hidden"); ui.meterWrap.classList.remove("dd-hidden");
      ui.arenaHud.classList.add("dd-hidden"); ui.touchBar.classList.add("dd-hidden"); ui.readyBtn.classList.remove("is-locked"); ui.readyBtn.textContent = "Lock Outfit & Ready!";
      ui.themePill.textContent = "Theme: " + currentTheme;
      if (window.THREE && scene) { setupShowroomScene(window.THREE); onResize(); }
      renderWardrobeGrid(); updateMeterUI(d.score); startCountdown(d.seconds || 60);
    });
    window.SocketClient.on("duel:score", (d) => { if (box && d && d.gid === gid) updateMeterUI(d.score); });
    window.SocketClient.on("duel:opp_pulse", (d) => { if (box && d && d.gid === gid) triggerTubePulse(d.role, false); });
    window.SocketClient.on("duel:ready_state", (d) => { if (box && d && d.gid === gid) triggerTubePulse(d.role, true); });
    window.SocketClient.on("duel:reveal", (d) => {
      if (!box || !d || d.gid !== gid) return;
      phase = "reveal"; ui.wardrobe.classList.add("dd-hidden"); ui.camBar.classList.add("dd-hidden"); onResize();
      const opp = myRole === "white" ? "black" : "white";
      if (window.THREE && d.players?.[opp] && rigs[opp]) applyOutfitToRig(window.THREE, rigs[opp], d.players[opp].outfit);
      triggerTubePulse("white", true); triggerTubePulse("black", true);
      ui.themePill.textContent = d.style_winner === "tie" ? "Runway Tie! Both Buffed!" : `Runway Winner: ${d.players[d.style_winner]?.name || d.style_winner}`;
      startCountdown(Math.ceil(d.reveal_seconds || 4));
    });
    window.SocketClient.on("duel:arena", (d) => {
      if (!box || !d || d.gid !== gid) return;
      phase = "arena"; myRole = d.you || myRole; arenaState = d;
      ui.wardrobe.classList.add("dd-hidden"); ui.camBar.classList.add("dd-hidden"); ui.meterWrap.classList.add("dd-hidden");
      ui.arenaHud.classList.remove("dd-hidden"); ui.touchBar.classList.remove("dd-hidden"); ui.themePill.textContent = `${d.theme} Arena`;
      for (const rk of ["white", "black"]) {
        const p = d.players[rk], c = ui.cards[rk];
        if (p && c) {
          c.name.textContent = `${p.name} (${p.style_score}★)`; c.buff.textContent = p.buff_label || "Standard";
          c.hpFill.style.width = "100%"; c.portrait.src = thumbCache[p.outfit.hair] || "";
        }
      }
      if (window.THREE && scene) { setupArenaScene(window.THREE, d.theme, d.players); onResize(); }
      startCountdown(d.seconds || 90);
    });
    window.SocketClient.on("duel:opp", (d) => {
      if (!box || !arenaState || !d || d.gid !== gid) return;
      const opp = arenaState.players[myRole === "white" ? "black" : "white"];
      if (opp) { opp.targetX = d.x; opp.targetY = d.y; opp.facing = d.facing; opp.anim = d.anim; opp.blocking = d.blocking; }
    });
    window.SocketClient.on("duel:swing", (d) => {
      if (box && arenaState && d && d.gid === gid && rigs[d.role]) rigs[d.role].swingUntil = performance.now() + 260;
    });
    window.SocketClient.on("duel:hit", (d) => {
      if (!box || !arenaState || !d || d.gid !== gid) return;
      const t = arenaState.players[d.target];
      if (t) {
        t.hp = d.hp; t.x = d.x; t.targetX = d.x;
        if (ui.cards[d.target]) ui.cards[d.target].hpFill.style.width = Math.max(0, (d.hp / (d.max_hp || 100)) * 100) + "%";
      }
      if (rigs[d.target]) {
        rigs[d.target].hitUntil = performance.now() + 220;
        if (d.final_blow) { rigs[d.target].ko = true; slowMoFactor = 0.22; slowMoUntil = performance.now() + 1400; }
      }
      if (window.THREE && scene) spawnHitEffects(window.THREE, d.x, t ? t.y || 0 : 0, d.blocked);
      spawnFloatingDamage(d.x, t ? t.y || 0 : 0, d.dmg, d.blocked);
    });
    window.SocketClient.on("duel:over", (d) => {
      if (!box || !d || d.gid !== gid) return;
      phase = "over"; clearInterval(countdownInterval); ui.modal.replaceChildren();
      const mc = H.el("div", "dd-modal-card"), grid = H.el("div", "dd-stat-grid");
      for (const rk of ["white", "black"]) {
        const st = d.stats?.[rk];
        if (st) {
          const sb = H.el("div", "dd-stat-box");
          sb.append(H.el("strong", "", st.name), H.el("div", "", `Style: ${st.style_score} pts`), H.el("div", "", `Damage: ${st.damage_dealt}`), H.el("div", "", `HP Left: ${st.hp_left}/${st.max_hp}`));
          grid.append(sb);
        }
      }
      const row = H.el("div", "dd-swatches");
      row.append(H.btn("Rematch", () => window.SocketClient.emit("duel:rematch", { gid })), H.btn("Close", () => stopAndDispose(true)));
      mc.append(H.el("h2", "", `🏆 ${d.winner} Wins!`), grid, row);
      ui.modal.append(mc); ui.modal.classList.remove("dd-hidden");
    });
    window.SocketClient.on("duel:aborted", (d) => {
      if (!box) return;
      phase = "over"; clearInterval(countdownInterval); ui.modal.replaceChildren();
      const mc = H.el("div", "dd-modal-card");
      mc.append(H.el("h3", "", "Match Ended"), H.el("p", "", d?.reason || "Partner left."));
      ui.modal.append(mc); ui.modal.classList.remove("dd-hidden");
    });
  }
  return { init, open };
})();
"""


# =====================================================================
# BUILT-IN SELF-TEST & HEADLESS BROWSER CHECK (Run: python your_file.py)
# =====================================================================
async def _run_builtin_unit_tests():
    global REVEAL_SECONDS
    REVEAL_SECONDS = 0.05

    class FakeSIO:
        def __init__(self):
            self.handlers, self.emitted = {}, []
        def on(self, evt):
            def dec(fn):
                self.handlers[evt] = fn
                return fn
            return dec
        async def emit(self, evt, data, to=None):
            self.emitted.append((evt, data, to))
        async def trigger(self, evt, sid, data=None):
            return await self.handlers[evt](sid, data)

    class FakeRoom:
        locked = True
        players = {
            "p1": {"pid": "p1", "sid": "s1", "name": "Alice", "role": "white"},
            "p2": {"pid": "p2", "sid": "s2", "name": "Bob", "role": "black"},
        }

    class FakeRooms:
        rooms = {"R1": FakeRoom()}
        by_player = {"p1": "R1", "p2": "R1"}

    sess_map = {"s1": {"pid": "p1", "name": "Alice"}, "s2": {"pid": "p2", "name": "Bob"}}
    def fake_auth(fn):
        async def w(sid, data=None):
            return await fn(sid, sess_map[sid], data)
        return w

    fake_auth.fast = fake_auth
    sio, rooms = FakeSIO(), FakeRooms()
    setup(sio, fake_auth, rooms)

    await sio.trigger("duel:join", "s1", {})
    await sio.trigger("duel:join", "s2", {})
    g = games["R1"]
    gid = g["gid"]
    g["theme"] = "Royal Gala"

    await sio.trigger("duel:outfit", "s1", {"gid": gid, "outfit": {"hair": "hair_royal_updo", "hat": "hat_crown", "dress": "dress_ballgown", "shoes": "shoe_heels", "accessory": "acc_royal_cape", "weapon": "wep_broad_royal"}})
    await sio.trigger("duel:outfit", "s2", {"gid": gid, "outfit": default_outfit()})
    await asyncio.sleep(0.08)
    assert g["phase"] == "arena" and g["p"]["p1"]["max_hp"] == 110, "Phase 2 & Style Winner buff failed"

    for i in range(80):
        await sio.trigger("duel:pos", "s1", {"gid": gid, "x": -3.0, "y": 0.0, "facing": 1, "anim": "run", "blocking": False})
    g["p"]["p2"]["x"] = -1.5
    await sio.trigger("duel:attack", "s1", {"gid": gid})
    assert g["p"]["p2"]["hp"] < 100, "Hit detection failed"
    print("[PASS] All built-in server unit tests succeeded!")


if __name__ == "__main__":
    asyncio.run(_run_builtin_unit_tests())