"""Logic thuần của The Grind RPG v1.1 (không phụ thuộc Streamlit để dễ kiểm thử)."""
import calendar
import copy
import random
import time
import uuid
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:  # máy không có cơ sở dữ liệu múi giờ
    TZ = timezone(timedelta(hours=7))

SCHEMA_VERSION = 2

BASE_ENERGY = 100
ENERGY_PER_BOOT_LEVEL = 20
REGEN_SECONDS = 120  # 1 energy mỗi 2 phút
TASK_ENERGY_COST = 10
BOSS_MAX_HP = 1000
CHEST_COST = 50
TASK_MIN_POINTS = 10
TASK_MAX_POINTS = 50
DEFAULT_SELL_PRICE = 15

WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]

# Các khoá của bản cũ không còn dùng (Treat, debuff dạng danh sách...)
OBSOLETE_KEYS = ("treats", "treat_history", "debuffs")


# ============ THỜI GIAN ============
def now_local():
    return datetime.now(TZ)


def today():
    return now_local().date()


# ============ DỮ LIỆU MẶC ĐỊNH & MIGRATION ============
def new_player_data():
    t = time.time()
    return {
        "schema_version": SCHEMA_VERSION,
        "points": 0,
        "total_points": 0,
        "energy": BASE_ENERGY,
        "boss_hp": BOSS_MAX_HP,
        "boss_kills": 0,
        "tasks": [],
        "tasks_done": 0,
        "inventory": [],
        "max_slots": 3,
        "equips": {"sword": 1, "boots": 1},
        "achievements": [],
        "streak": 0,
        "last_done_date": None,
        "bonus_damage": 0,
        "bonus_max_energy": 0,
        "last_regen": t,
        "created_at": t,
        "last_updated": t,
    }


def to_text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v != v:  # NaN
        return ""
    return str(v).strip()


def to_bool(v):
    if v is None:
        return False
    if isinstance(v, float) and v != v:  # NaN
        return False
    return bool(v)


def parse_date(v):
    """Nhận date / datetime / Timestamp / chuỗi ISO. Trả về date hoặc None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def clamp_points(v, default=20):
    """Điểm task: làm tròn về bội số của 5, trong khoảng 10–50."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x != x:  # NaN
        return default
    x = 5 * round(x / 5)
    return int(min(TASK_MAX_POINTS, max(TASK_MIN_POINTS, x)))


def make_task(name, points, day, done=False, rewarded=False):
    return {
        "id": uuid.uuid4().hex,
        "name": to_text(name) or "Task",
        "points": clamp_points(points),
        "date": day if isinstance(day, str) else day.isoformat(),
        "done": done,
        "rewarded": rewarded,
        "done_at": None,
    }


def _normalize_task(t):
    t.setdefault("id", uuid.uuid4().hex)
    t["name"] = to_text(t.get("name")) or "Task"
    t["points"] = clamp_points(t.get("points"))
    t["date"] = (parse_date(t.get("date")) or today()).isoformat()
    t["done"] = to_bool(t.get("done", False))
    t["rewarded"] = to_bool(t.get("rewarded", t["done"]))
    t.setdefault("done_at", None)


def migrate(data):
    """Đưa dữ liệu (kể cả bản cũ) về schema v2. An toàn khi chạy nhiều lần."""
    base = new_player_data()
    for k, v in base.items():
        data.setdefault(k, copy.deepcopy(v))

    if not isinstance(data.get("equips"), dict):
        data["equips"] = {}
    for k, v in base["equips"].items():
        data["equips"].setdefault(k, v)

    # tasks kiểu cũ: {tên: điểm} -> danh sách task có ngày
    old_tasks = data.get("tasks")
    if isinstance(old_tasks, dict):
        d = today().isoformat()
        data["tasks"] = [make_task(n, p, d) for n, p in old_tasks.items()]
    elif not isinstance(old_tasks, list):
        data["tasks"] = []

    # lịch sử kiểu cũ -> task đã hoàn thành (đã nhận thưởng)
    hist = data.pop("task_history", None)
    if isinstance(hist, list):
        for h in hist:
            if not isinstance(h, dict):
                continue
            day = parse_date(to_text(h.get("date"))[:10]) or today()
            data["tasks"].append(
                make_task(h.get("name"), h.get("points"), day, done=True, rewarded=True)
            )

    for t in data["tasks"]:
        _normalize_task(t)

    for k in OBSOLETE_KEYS:
        data.pop(k, None)

    data["schema_version"] = SCHEMA_VERSION
    return data


# ============ MÔI TRƯỜNG ============
def get_environment(now=None):
    now = now or now_local()
    hour, weekday = now.hour, now.weekday()
    env = {
        "damage_multiplier": 1,
        "tavern_price_multiplier": 1,
        "debuff_chance": 0.20,
        "buffs": [],
    }
    if 9 <= hour < 11:
        env["damage_multiplier"] = 2
        env["buffs"].append("⚡ Sóng năng lượng (x2 Damage)")
    if weekday >= 5:
        env["tavern_price_multiplier"] = 0.5
        env["buffs"].append("🍻 Ngày hội Tavern (-50% giá)")
    if hour >= 23:
        env["debuff_chance"] = 0.40
        env["buffs"].append("🌫️ Sương mù (↑ tỉ lệ Debuff)")
    return env


# ============ NĂNG LƯỢNG ============
def get_max_energy(data):
    boots = data["equips"].get("boots", 1)
    return (
        BASE_ENERGY
        + (boots - 1) * ENERGY_PER_BOOT_LEVEL
        + data.get("bonus_max_energy", 0)
    )


def apply_regen(data, now=None):
    """Hồi energy theo thời gian. Trả về True nếu dữ liệu thay đổi và cần lưu."""
    now = time.time() if now is None else now
    changed = False
    max_e = get_max_energy(data)

    if data["energy"] > max_e:
        data["energy"] = max_e
        changed = True

    block = data.get("energy_block_until", 0)
    if now < block:  # đang bị Choáng
        return changed

    last = max(data.get("last_regen", now), block)
    if data["energy"] >= max_e:
        data["last_regen"] = now  # đầy rồi thì không tích lũy thời gian
        return changed

    ticks = int((now - last) // REGEN_SECONDS)
    if ticks > 0:
        data["energy"] = min(max_e, data["energy"] + ticks)
        data["last_regen"] = now if data["energy"] >= max_e else last + ticks * REGEN_SECONDS
        changed = True
    else:
        data["last_regen"] = last
    return changed


# ============ DEBUFF ============
DEBUFFS = [
    {"key": "tired", "name": "Mệt Mỏi", "emoji": "😵", "desc": "Task tiếp theo tốn +5 energy"},
    {"key": "injury", "name": "Chấn Thương", "emoji": "🩸", "desc": "Giảm 20 energy ngay lập tức"},
    {"key": "sluggish", "name": "Uể Oải", "emoji": "🐌", "desc": "Giảm 50% sát thương task kế tiếp"},
    {"key": "stun", "name": "Choáng", "emoji": "💫", "desc": "Không hồi energy trong 10 phút"},
    {"key": "temptation", "name": "Cám Dỗ", "emoji": "🍩", "desc": "Mất 10 pts vì xao nhãng"},
]


def apply_debuff(data, key, now=None):
    now = time.time() if now is None else now
    if key == "tired":
        data["next_task_penalty"] = 5
    elif key == "injury":
        data["energy"] = max(0, data["energy"] - 20)
    elif key == "sluggish":
        data["next_half_damage"] = True
    elif key == "stun":
        data["energy_block_until"] = now + 600
    elif key == "temptation":
        data["points"] = max(0, data["points"] - 10)


def active_debuffs(data, now=None):
    """Các debuff đang có hiệu lực (suy ra từ trạng thái, hiển thị ở sidebar)."""
    now = time.time() if now is None else now
    out = []
    if data.get("next_task_penalty", 0) > 0:
        out.append("😵 Mệt Mỏi (task kế tiếp tốn +%d⚡)" % data["next_task_penalty"])
    if data.get("next_half_damage"):
        out.append("🐌 Uể Oải (task kế tiếp -50% dmg)")
    block = data.get("energy_block_until", 0)
    if now < block:
        mins = int((block - now) // 60) + 1
        out.append(f"💫 Choáng (không hồi energy, còn ~{mins} phút)")
    return out


# ============ THÀNH TỰU ============
def _reward_dragon_slayer(d):
    d["bonus_damage"] = d.get("bonus_damage", 0) + 10


def _reward_millionaire(d):
    d["max_slots"] = d.get("max_slots", 3) + 2


def _reward_iron_discipline(d):
    d["bonus_max_energy"] = d.get("bonus_max_energy", 0) + 20


ACHIEVEMENTS = {
    "dragon_slayer": {
        "name": "Kẻ Diệt Rồng",
        "emoji": "🐉",
        "desc": "Hạ gục 7 Boss (thưởng +10 sát thương mỗi task)",
        "condition": lambda d: d.get("boss_kills", 0) >= 7,
        "reward": _reward_dragon_slayer,
    },
    "millionaire": {
        "name": "Triệu Phú",
        "emoji": "💰",
        "desc": "Tích lũy tổng cộng 5000 pts (thưởng +2 ô túi đồ)",
        "condition": lambda d: d.get("total_points", 0) >= 5000,
        "reward": _reward_millionaire,
    },
    "iron_discipline": {
        "name": "Kỷ Luật Thép",
        "emoji": "🛡️",
        "desc": "Hoàn thành task liên tục 7 ngày (thưởng +20 energy tối đa)",
        "condition": lambda d: d.get("streak", 0) >= 7,
        "reward": _reward_iron_discipline,
    },
}


def check_achievements(data):
    """Mở thành tựu đủ điều kiện. Trả về danh sách thành tựu vừa mở."""
    unlocked = data.setdefault("achievements", [])
    new = []
    for key, ach in ACHIEVEMENTS.items():
        if key in unlocked:
            continue
        if ach["condition"](data):
            unlocked.append(key)
            ach["reward"](data)
            new.append(ach)
    return new


# ============ BOSS / SÁT THƯƠNG / STREAK ============
def calc_damage(points, data, env):
    base = (points // 2) * data["equips"].get("sword", 1) + data.get("bonus_damage", 0)
    return base * env["damage_multiplier"]


def resolve_boss(data):
    """Nếu Boss hết HP: +1 kill và hồi đầy HP. Trả về True nếu vừa hạ Boss."""
    if data["boss_hp"] <= 0:
        data["boss_kills"] += 1
        data["boss_hp"] = BOSS_MAX_HP
        return True
    return False


def update_streak(data, day):
    last = data.get("last_done_date")
    today_s = day.isoformat()
    if last == today_s:
        return
    yesterday = (day - timedelta(days=1)).isoformat()
    data["streak"] = data.get("streak", 0) + 1 if last == yesterday else 1
    data["last_done_date"] = today_s


# ============ TASK ============
def task_energy_cost(data):
    return TASK_ENERGY_COST + data.get("next_task_penalty", 0)


def complete_task(data, task, env, now_dt=None, rng=random):
    """Hoàn thành 1 task: trừ energy, cộng điểm, đánh Boss, có thể dính debuff."""
    now_dt = now_dt or now_local()
    cost = task_energy_cost(data)
    if data["energy"] < cost:
        return {"ok": False, "cost": cost, "toasts": [], "boss_killed": False}

    toasts = []
    data["energy"] -= cost
    data.pop("next_task_penalty", None)

    pts = task["points"]
    data["points"] += pts
    data["total_points"] = data.get("total_points", 0) + pts

    dmg = calc_damage(pts, data, env)
    if data.pop("next_half_damage", False):
        dmg //= 2
        toasts.append("🐌 Uể Oải: sát thương task này bị giảm 50%")

    if rng.random() < env["debuff_chance"]:
        deb = rng.choice(DEBUFFS)
        apply_debuff(data, deb["key"], now_dt.timestamp())
        toasts.append(f"{deb['emoji']} {deb['name']}: {deb['desc']}")

    data["boss_hp"] -= dmg
    data["tasks_done"] = data.get("tasks_done", 0) + 1
    update_streak(data, now_dt.date())

    task["done"] = True
    task["rewarded"] = True
    task["done_at"] = now_dt.strftime("%Y-%m-%d %H:%M")

    return {"ok": True, "cost": cost, "toasts": toasts, "boss_killed": resolve_boss(data), "damage": dmg}


def apply_table_edits(data, records, shown_ids, env, now_dt=None, rng=random):
    """Áp dụng những gì người dùng sửa trong bảng to-do.

    records: danh sách dict {id, done, date, task, points} sau khi sửa
    shown_ids: id các task đang hiển thị trong bảng (chỉ những task này mới bị xóa)
    """
    now_dt = now_dt or now_local()
    day_today = now_dt.date()
    by_id = {t["id"]: t for t in data["tasks"]}
    shown_ids = set(shown_ids)
    kept = set()
    res = {
        "added": 0, "edited": 0, "deleted": 0, "completed": 0, "skipped": 0,
        "warnings": [], "toasts": [], "boss_kills": 0, "unlocked": [],
    }

    for r in records:
        rid = r.get("id")
        name = to_text(r.get("task"))
        day = parse_date(r.get("date"))
        pts = clamp_points(r.get("points"))
        want_done = to_bool(r.get("done"))

        if isinstance(rid, str) and rid in by_id and rid in shown_ids:
            kept.add(rid)
            t = by_id[rid]
            before = (t["name"], t["date"], t["points"])
            if name:
                t["name"] = name
            else:
                res["warnings"].append("Có task bị xóa trống tên nên mình giữ lại tên cũ.")
            if day:
                t["date"] = day.isoformat()
            if not t["rewarded"]:
                t["points"] = pts
            elif pts != t["points"]:
                res["warnings"].append(f"“{t['name']}” đã nhận thưởng nên giữ nguyên điểm.")
            if (t["name"], t["date"], t["points"]) != before:
                res["edited"] += 1
            target = t
        else:
            if not name:
                res["skipped"] += 1
                continue
            target = make_task(name, pts, (day or day_today))
            data["tasks"].append(target)
            by_id[target["id"]] = target
            res["added"] += 1

        if want_done and not target["done"]:
            if target["rewarded"]:
                target["done"] = True  # đã nhận thưởng trước đó, không thưởng lần nữa
            else:
                out = complete_task(data, target, env, now_dt, rng)
                if out["ok"]:
                    res["completed"] += 1
                    res["toasts"].extend(out["toasts"])
                    if out["boss_killed"]:
                        res["boss_kills"] += 1
                else:
                    res["warnings"].append(
                        f"⚡ Không đủ energy cho “{target['name']}” (cần {out['cost']}⚡) — task vẫn chưa xong."
                    )
        elif not want_done and target["done"]:
            target["done"] = False

    gone = shown_ids - kept
    if gone:
        data["tasks"] = [t for t in data["tasks"] if t["id"] not in gone]
        res["deleted"] = len(gone)

    res["unlocked"] = check_achievements(data)
    return res


# ============ THỐNG KÊ CHO DASHBOARD ============
def tasks_in_month(tasks, year, month):
    prefix = f"{year:04d}-{month:02d}"
    return [t for t in tasks if t["date"].startswith(prefix)]


def tasks_in_year(tasks, year):
    prefix = f"{year:04d}-"
    return [t for t in tasks if t["date"].startswith(prefix)]


def task_stats(tasks, today_iso):
    total = len(tasks)
    done = sum(1 for t in tasks if t["done"])
    overdue = sum(1 for t in tasks if not t["done"] and t["date"] < today_iso)
    pending = total - done - overdue
    return {
        "total": total,
        "done": done,
        "pending": pending,
        "overdue": overdue,
        "rate": done / total if total else 0.0,
    }


def month_weeks(year, month):
    """Các tuần (Thứ 2 → CN) của tháng, cắt theo ranh giới tháng: [(ngày đầu, ngày cuối), ...]."""
    weeks = []
    for w in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        days = [d for d in w if d.month == month]
        weeks.append((days[0], days[-1]))
    return weeks


# ============ RƯƠNG / TÚI ĐỒ ============
CHEST_ITEMS = [
    {"name": "Mana Potion", "desc": "Hồi 50⚡ energy", "type": "energy", "value": 50, "sell": 20},
    {"name": "Greater Mana Potion", "desc": "Hồi 100⚡ energy", "type": "energy", "value": 100, "sell": 35},
    {"name": "Boss Bomb", "desc": "Gây 200 dmg lên Boss", "type": "damage", "value": 200, "sell": 30},
    {"name": "Mega Bomb", "desc": "Gây 400 dmg lên Boss", "type": "damage", "value": 400, "sell": 45},
    {"name": "Energy Scroll", "desc": "Tăng energy tối đa +10", "type": "max_energy", "value": 10, "sell": 30},
    {"name": "Lucky Coin", "desc": "Nhận thêm 100 pts", "type": "points", "value": 100, "sell": 40},
    {"name": "Cursed Coin", "desc": "Mất 50 pts (đen)", "type": "points", "value": -50, "sell": 5},
    {"name": "Boss Poison", "desc": "Boss mất 10% HP hiện tại", "type": "percent_damage", "value": 0.1, "sell": 20},
    {"name": "Stimulant", "desc": "Hồi 30⚡ energy ngay", "type": "energy", "value": 30, "sell": 12},
    {"name": "Empty Chest", "desc": "Không có gì… xui 😭", "type": "none", "value": 0, "sell": 0},
]


def open_chest(data, rng=random):
    if data["points"] < CHEST_COST:
        return {"ok": False, "msg": "Không đủ points"}
    if len(data["inventory"]) >= data["max_slots"]:
        return {"ok": False, "msg": "Túi đồ đã đầy"}

    data["points"] -= CHEST_COST
    item = rng.choice(CHEST_ITEMS)
    msg = ""

    if rng.random() < 0.2:  # rương bị nguyền
        lost = rng.randint(10, 30)
        data["points"] = max(0, data["points"] - lost)
        msg += f"💀 Rương bị nguyền! Mất {lost} pts\n"

    if item["type"] == "none":
        msg += "😢 Rương trống..."
    else:
        data["inventory"].append(dict(item))
        msg += f"🎉 Nhận được: {item['name']}\n👉 {item['desc']}"
    return {"ok": True, "msg": msg}


def use_item(data, idx):
    inv = data["inventory"]
    if not 0 <= idx < len(inv):
        return {"ok": False, "msg": "Vật phẩm không tồn tại", "boss_killed": False, "unlocked": []}

    it = inv[idx]
    kind, value = it["type"], it["value"]
    if kind == "energy":
        data["energy"] = min(get_max_energy(data), data["energy"] + value)
    elif kind == "damage":
        data["boss_hp"] -= value
    elif kind == "percent_damage":
        data["boss_hp"] -= int(data["boss_hp"] * value)
    elif kind == "points":
        data["points"] = max(0, data["points"] + value)
    elif kind == "max_energy":
        data["bonus_max_energy"] = data.get("bonus_max_energy", 0) + value

    inv.pop(idx)
    killed = resolve_boss(data)
    unlocked = check_achievements(data)
    return {"ok": True, "msg": f"Đã dùng {it['name']}", "boss_killed": killed, "unlocked": unlocked}


def sell_item(data, idx):
    inv = data["inventory"]
    if not 0 <= idx < len(inv):
        return {"ok": False, "msg": "Vật phẩm không tồn tại"}
    it = inv.pop(idx)
    price = it.get("sell", DEFAULT_SELL_PRICE)
    data["points"] += price
    return {"ok": True, "msg": f"Đã bán {it['name']} (+{price} pts)"}


def slot_price(data):
    return 100 + (data["max_slots"] - 3) * 50


def buy_slot(data):
    price = slot_price(data)
    if data["points"] < price:
        return {"ok": False, "msg": f"Không đủ points (cần {price})"}
    data["points"] -= price
    data["max_slots"] += 1
    return {"ok": True, "msg": "Đã mở rộng kho đồ!"}


# ============ RÈN / TAVERN ============
def upgrade_cost(data, kind):
    return data["equips"][kind] * (100 if kind == "sword" else 150)


def upgrade_equipment(data, kind):
    cost = upgrade_cost(data, kind)
    name = "kiếm" if kind == "sword" else "giày"
    if data["points"] < cost:
        return {"ok": False, "msg": f"Không đủ points để rèn {name} (cần {cost})"}
    data["points"] -= cost
    data["equips"][kind] += 1
    return {"ok": True, "msg": f"Đã rèn {name} lên Lv.{data['equips'][kind]}"}


TAVERN_ITEMS = [
    {"name": "Nước Lã", "emoji": "🥛", "cost": 10, "energy": 10},
    {"name": "Trà Đậm", "emoji": "🍵", "cost": 25, "energy": 25},
    {"name": "Cà Phê Đen", "emoji": "☕", "cost": 50, "energy": 40},
    {"name": "Bữa Thịnh Soạn", "emoji": "🍖", "cost": 80, "energy": 70},
    {"name": "Yến Tiệc Vương Giả", "emoji": "🍗", "cost": 120, "energy": 100},
]


def tavern_price(item, env):
    return int(item["cost"] * env["tavern_price_multiplier"])


def buy_tavern(data, idx, env):
    item = TAVERN_ITEMS[idx]
    price = tavern_price(item, env)
    if data["energy"] >= get_max_energy(data):
        return {"ok": False, "msg": "Energy đã đầy, không cần mua lúc này"}
    if data["points"] < price:
        return {"ok": False, "msg": "Không đủ points"}
    data["points"] -= price
    data["energy"] = min(get_max_energy(data), data["energy"] + item["energy"])
    return {"ok": True, "msg": f"Đã dùng {item['name']}"}
