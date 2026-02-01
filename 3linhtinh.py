import streamlit as st
import random
import pandas as pd
import plotly.express as px
import time  # ⬅️ DÒNG NÀY
from datetime import datetime
from db import supabase, PLAYER_ID

DEFAULT_DATA = {
    "points": 0,
    "energy": 100,
    "boss_hp": 1000,
    "boss_kills": 0,

    "tasks": {},
    "task_history": [],
    "tasks_done": 0,

    "treats": {},

    "inventory": [],
    "max_slots": 3,

    "equips": {
        "sword": 1,
        "boots": 1
    },

    "debuffs": [],
    "achievements": [],

    "last_updated": time.time()
}

ACHIEVEMENTS = {
    "dragon_slayer": {
        "name": "Kẻ Diệt Rồng",
        "emoji": "🐉",
        "desc": "Hạ gục 7 Boss",
        "condition": lambda d: d.get("boss_kills", 0) >= 7,
        "reward": lambda d: d.update({
            "bonus_damage": d.get("bonus_damage", 0) + 10
        })
    },

    "millionaire": {
        "name": "Triệu Phú",
        "emoji": "💰",
        "desc": "Tích lũy tổng cộng 5000 pts",
        "condition": lambda d: d.get("total_points", 0) >= 5000,
        "reward": lambda d: d.update({
            "max_slots": d.get("max_slots", 3) + 2
        })
    },

    "iron_discipline": {
        "name": "Kỷ Luật Thép",
        "emoji": "🛡️",
        "desc": "Hoàn thành task liên tục 7 ngày",
        "condition": lambda d: d.get("streak", 0) >= 7,
        "reward": lambda d: d.update({
            "bonus_max_energy": d.get("bonus_max_energy", 0) + 20
        })
    }
}

DEBUFFS = [
    {
        "name": "Mệt Mỏi",
        "emoji": "😵",
        "desc": "Task tiếp theo tốn +5 energy",
        "apply": lambda d: d.__setitem__("next_task_penalty", 5)
    },
    {
        "name": "Chấn Thương",
        "emoji": "🩸",
        "desc": "Giảm 20 energy ngay lập tức",
        "apply": lambda d: d.__setitem__("energy", max(0, d["energy"] - 20))
    },
    {
        "name": "Uể Oải",
        "emoji": "🐌",
        "desc": "Giảm 50% sát thương task kế tiếp",
        "type": "half_damage"
    },
    {
        "name": "Choáng",
        "emoji": "💫",
        "desc": "Không hồi energy trong 10 phút",
        "apply": lambda d: d.__setitem__("energy_block_until", time.time() + 600)
    },
    {
        "name": "Cám Dỗ",
        "emoji": "🍩",
        "desc": "Mất 10 pts vì xao nhãng",
        "apply": lambda d: d.__setitem__("points", max(0, d["points"] - 10))
    }
]

CHEST_ITEMS = [
    {"name": "Mana Potion", "desc": "Hồi 50⚡ energy", "type": "energy", "value": 50},
    {"name": "Greater Mana Potion", "desc": "Hồi 100⚡ energy", "type": "energy", "value": 100},
    {"name": "Boss Bomb", "desc": "Gây 200 dmg lên Boss", "type": "damage", "value": 200},
    {"name": "Mega Bomb", "desc": "Gây 400 dmg lên Boss", "type": "damage", "value": 400},
    {"name": "Energy Scroll", "desc": "Tăng energy tối đa +10", "type": "max_energy", "value": 10},
    {"name": "Lucky Coin", "desc": "Nhận thêm 100 pts", "type": "points", "value": 100},
    {"name": "Cursed Coin", "desc": "Mất 50 pts (đen)", "type": "points", "value": -50},
    {"name": "Boss Poison", "desc": "Boss mất 10% HP hiện tại", "type": "percent_damage", "value": 0.1},
    {"name": "Stimulant", "desc": "Hồi 30⚡ energy ngay", "type": "energy", "value": 30},
    {"name": "Empty Chest", "desc": "Không có gì… xui 😭", "type": "none", "value": 0},
]
if "chest_msg" not in st.session_state:
    st.session_state.chest_msg = None


def get_environment():
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0 = Mon, 6 = Sun

    env = {
        "damage_multiplier": 1,
        "tavern_price_multiplier": 1,
        "debuff_bonus": 0
    }

    # ⚡ Giờ vàng 9–11h
    if 9 <= hour < 11:
        env["damage_multiplier"] = 2

    # 🍻 Cuối tuần
    if weekday >= 5:
        env["tavern_price_multiplier"] = 0.5

    # 🌫️ Ban đêm
    if hour >= 23:
        env["debuff_bonus"] = 0.15

    return env


def check_achievements(data):
    unlocked = data.setdefault("achievements", [])

    for key, ach in ACHIEVEMENTS.items():
        if key in unlocked:
            continue

        if ach["condition"](data):
            unlocked.append(key)
            ach["reward"](data)
            st.toast(f"{ach['emoji']} Achievement unlocked: {ach['name']}!", icon="🏆")


def get_max_energy(data):
    boots_lvl = data.get("equips", {}).get("boots", 1)
    return 100 + (boots_lvl - 1) * 10


def load_data():
    try:
        res = supabase.table("players") \
            .select("data") \
            .eq("id", PLAYER_ID) \
            .execute()
    except Exception as e:
        st.error("❌ Không thể tải dữ liệu từ Supabase")
        st.exception(e)
        st.stop()

    # ===== PLAYER TỒN TẠI =====
    if res.data and len(res.data) > 0:
        data = res.data[0]["data"]

    # ===== PLAYER CHƯA TỒN TẠI =====
    else:
        data = DEFAULT_DATA.copy()
        data["created_at"] = time.time()

        try:
            supabase.table("players").insert({
                "id": PLAYER_ID,
                "data": data
            }).execute()
        except Exception as e:
            st.error("❌ Không thể tạo player mới")
            st.exception(e)
            st.stop()

    # ===== DATA MIGRATION (LUÔN CHẠY) =====
    data.setdefault("tasks", {})
    data.setdefault("task_history", [])
    data.setdefault("tasks_done", 0)
    data.setdefault("total_points", 0)
    data.setdefault("points", 0)
    data.setdefault("energy", 100)
    data.setdefault("boss_hp", 1000)
    data.setdefault("boss_kills", 0)
    data.setdefault("inventory", [])
    data.setdefault("max_slots", 3)
    data.setdefault("equips", {"sword": 1, "boots": 1})
    data.setdefault("last_updated", time.time())

    # ===== ENERGY REGEN =====
    now = time.time()
    elapsed_minutes = int((now - data["last_updated"]) // 60)

    if time.time() < data.get("energy_block_until", 0):
        return data

    if elapsed_minutes >= 2:
        regen = elapsed_minutes // 2
        max_energy = 100 + (data["equips"]["boots"] - 1) * 20
        data["energy"] = min(max_energy, data["energy"] + regen)
        data["last_updated"] = now
        save_data(data)

    return data


def save_data(data):
    try:
        data["last_updated"] = time.time()

        supabase.table("players").update({
            "data": data
        }).eq("id", PLAYER_ID).execute()

    except Exception as e:
        st.error("❌ Không thể lưu dữ liệu")
        st.exception(e)
        st.stop()


# ================= UI =================
st.set_page_config("The Grind RPG", layout="wide")
data = load_data()
max_energy = get_max_energy(data)
data["energy"] = min(data["energy"], max_energy)
save_data(data)

env = get_environment()
bonus_energy = data.get("bonus_max_energy", 0)
max_energy = 100 + (data['equips']['boots'] - 1) * 20 + bonus_energy

st.markdown("""
<style>
.card {background:#111;border:1px solid #333;padding:16px;border-radius:14px;text-align:center}
.rare {border-color:#a335ee;box-shadow:0 0 10px #a335ee}
.big {font-size:32px}
</style>
""", unsafe_allow_html=True)

# ================= SIDEBAR =================
st.sidebar.title("⚔️ From the ordinary to flee")

# ===== CORE STATS =====
st.sidebar.metric("💰 Points", data["points"])
st.sidebar.write(f"⚡ Energy {int(data['energy'])}/{max_energy}")
st.sidebar.progress(min(data["energy"] / max_energy, 1))

st.sidebar.metric("🏆 Boss đã hạ", data.get("boss_kills", 0))
st.sidebar.metric("📜 Task đã hoàn thành", data.get("tasks_done", 0))

hp_pct = max(0, data["boss_hp"] / 1000)
st.sidebar.progress(hp_pct, text=f"🐉 Boss HP {data['boss_hp']}/1000")

year_prog = (datetime.now() - datetime(datetime.now().year, 1, 1)).days / 365
st.sidebar.progress(year_prog, text=f"📅 Year {year_prog:.1%}")

# ===== ENVIRONMENT BUFFS =====
st.sidebar.divider()
st.sidebar.subheader("🌍 Environment Buff")

now = datetime.now()
hour = now.hour
weekday = now.weekday()  # 5 = Sat, 6 = Sun

env_buffs = []

# 9h–11h sáng
if 9 <= hour < 11:
    env_buffs.append("⚡ Sóng năng lượng (x2 Damage)")

# Cuối tuần
if weekday in (5, 6):
    env_buffs.append("🍻 Ngày hội Tavern (-50% giá)")

# Ban đêm
if hour >= 23:
    env_buffs.append("🌫️ Sương mù (↑ tỉ lệ Debuff)")

if env_buffs:
    for buff in env_buffs:
        st.sidebar.success(buff)
else:
    st.sidebar.info("Không có buff đặc biệt")

# ===== ACTIVE DEBUFFS =====
st.sidebar.divider()
st.sidebar.subheader("☠️ Debuff đang dính")

active_debuffs = data.get("debuffs", [])

if active_debuffs:
    for d in active_debuffs:
        st.sidebar.error(f"{d['emoji']} {d['name']} ({d['remaining']} task)")
else:
    st.sidebar.write("✨ Không có debuff")

# ================= RESET =================
if "reset_confirm" not in st.session_state:
    st.session_state.reset_confirm = False

if st.sidebar.button("🗑️ Reset"):
    st.session_state.reset_confirm = True

if st.session_state.reset_confirm:
    st.sidebar.warning("Reset toàn bộ tiến trình?")

    col1, col2 = st.sidebar.columns(2)

    if col1.button("❌ Hủy"):
        st.session_state.reset_confirm = False

    if col2.button("✅ Xác nhận"):
        data = DEFAULT_DATA.copy()
        save_data(data)
        st.session_state.reset_confirm = False
        st.success("Đã reset nhân vật!")
        st.rerun()

# ================= TABS =================
tabs = st.tabs([
    "⚔️ Task",
    "🎁 Treat",
    "📦 Rương",
    "🎒 Túi đồ",
    "🛠️ Rèn",
    "🍻 Tavern",
    "📊 Thống kê",
    "⚙️ Forge", "🏆 ACHIEVEMENTS"
])

# ================= ACHIEVEMENTS TAB =================
with tabs[-1]:
    st.subheader("🏆 ACHIEVEMENTS")

    if not data.get("achievements"):
        st.info("Chưa có thành tựu nào. Hãy tiếp tục grind 💀")
    else:
        for key in data["achievements"]:
            ach = ACHIEVEMENTS[key]
            st.markdown(
                f"""
                <div class='card'>
                    <h2>{ach['emoji']}</h2>
                    <b>{ach['name']}</b><br>
                    <small>{ach['desc']}</small>
                </div>
                """,
                unsafe_allow_html=True
            )

# ================= TASK TAB =================
with tabs[0]:
    st.subheader("⚔️Fram þæm gemænan ætfleohan.")

    if not data.get("tasks"):
        st.info("Chưa có task nào. Hãy tạo trong Forge.")

    now = datetime.now()
    hour = now.hour

    # ===== ENVIRONMENT =====
    env_damage_mult = 2 if 9 <= hour < 11 else 1
    debuff_chance = 0.40 if hour >= 23 else 0.20

    for name, pts in list(data["tasks"].items()):
        base_dmg = (pts // 2) * data["equips"].get("sword", 1)
        preview_dmg = base_dmg * env_damage_mult

        col1, col2 = st.columns([4, 1])
        col1.write(
            f"**{name}** | +{pts} pts | ⚔️ {preview_dmg} dmg"
            + (" ⚡x2" if env_damage_mult == 2 else "")
        )

        if col2.button("Hoàn thành", key=f"done_{name}"):
            check_achievements(data)

            # ===== ENERGY COST =====
            energy_cost = 10 + data.get("next_task_penalty", 0)

            if data["energy"] < energy_cost:
                st.warning("⚡ Không đủ energy")
                st.stop()

            # ===== APPLY COST =====
            data["energy"] -= energy_cost
            data.pop("next_task_penalty", None)

            # ===== REWARD =====
            data["points"] += pts
            data["total_points"] = data.get("total_points", 0) + pts
            dmg = base_dmg * env_damage_mult

            # ===== RANDOM DEBUFF =====
            debuff_msg = None
            if random.random() < debuff_chance:
                debuff = random.choice(DEBUFFS)
                debuff_msg = f"{debuff['emoji']} {debuff['name']}: {debuff['desc']}"

                if debuff.get("type") == "half_damage":
                    dmg //= 2
                else:
                    debuff["apply"](data)

            # ===== DAMAGE =====
            data["boss_hp"] -= dmg

            # ===== HISTORY =====
            data.setdefault("task_history", []).append({
                "name": name,
                "points": pts,
                "date": now.strftime("%Y-%m-%d %H:%M")
            })
            data["tasks_done"] = data.get("tasks_done", 0) + 1

            # ===== REMOVE TASK =====
            del data["tasks"][name]

            # ===== BOSS DEAD =====
            if data["boss_hp"] <= 0:
                data["boss_kills"] += 1
                data["boss_hp"] = 1000
                st.balloons()

            save_data(data)

            if debuff_msg:
                st.toast(debuff_msg, icon="⚠️")  # tự biến sau ~3s

            st.rerun()

    # ===== TASK HISTORY VIEW =====
    st.divider()
    st.subheader("📜 Lịch sử Task đã hoàn thành")

    if not data.get("task_history"):
        st.info("Chưa hoàn thành task nào.")
    else:
        for t in data["task_history"][-5:][::-1]:
            st.markdown(
                f"✅ **{t['name']}** — +{t['points']} pts  \n"
                f"<small>{t['date']}</small>",
                unsafe_allow_html=True
            )

        st.caption(f"📊 Tổng task đã hoàn thành: {data.get('tasks_done', 0)}")

        with st.expander("📂 Xem toàn bộ lịch sử"):
            df = pd.DataFrame(data["task_history"][::-1])
            st.dataframe(df, use_container_width=True)

# ================= TREAT TAB =================
with tabs[1]:
    st.subheader("🎁 TREAT – Phần thưởng cho bản thân")

    if not data.get("treats"):
        st.info("Chưa có treat nào. Hãy tạo trong Forge.")
    else:
        for name, cost in list(data["treats"].items()):
            col1, col2, col3 = st.columns([4, 1, 1])

            col1.write(f"🎉 **{name}** — {cost} pts")

            # ---- CLAIM ----
            if col2.button("Nhận", key=f"treat_{name}"):
                if data["points"] >= cost:
                    data["points"] -= cost

                    data.setdefault("treat_history", []).append({
                        "name": name,
                        "cost": cost,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

                    save_data(data)
                    st.success(f"Đã nhận treat: {name}")
                    st.rerun()
                else:
                    st.error("Không đủ points")

            # ---- DELETE TREAT ----
            if col3.button("🗑️", key=f"del_treat_{name}"):
                del data["treats"][name]
                save_data(data)
                st.rerun()

# ================= CHEST TAB =================
with tabs[2]:
    st.subheader("📦 RƯƠNG MAY MẮN")

    # ---- HIỆN THÔNG BÁO CŨ ----
    if st.session_state.chest_msg:
        st.info(st.session_state.chest_msg)
        if st.button("OK"):
            st.session_state.chest_msg = None
            st.rerun()

    # ---- MỞ RƯƠNG ----
    if st.button("🔓 MỞ RƯƠNG"):
        if data["points"] < 50:
            st.error("Không đủ points")
        elif len(data["inventory"]) >= data["max_slots"]:
            st.error("Túi đồ đã đầy")
        else:
            data["points"] -= 50
            item = random.choice(CHEST_ITEMS)

            msg = ""

            # rủi ro mất thêm pts
            if random.random() < 0.2:
                lost = random.randint(10, 30)
                data["points"] = max(0, data["points"] - lost)
                msg += f"💀 Rương bị nguyền! Mất {lost} pts\n"

            if item["type"] == "none":
                msg += "😢 Rương trống..."
            else:
                data["inventory"].append(item)
                msg += f"🎉 Nhận được: {item['name']}\n👉 {item['desc']}"

            save_data(data)

            st.session_state.chest_msg = msg
            st.rerun()

# ================= INVENTORY TAB =================
with tabs[3]:
    st.subheader("🎒 Túi đồ")

    # ---- BUY INVENTORY SLOT (FIX) ----
    max_slots = data.get("max_slots", 3)
    slot_price = 100 + (max_slots - 3) * 50

    col_a, col_b = st.columns([3, 1])
    col_a.write(f"Số ô: {data['max_slots']}")

    if col_b.button(f"➕ Mua ô ({slot_price} pts)"):
        if data["points"] >= slot_price:
            data["points"] -= slot_price
            data["max_slots"] += 1
            save_data(data)
            st.success("Đã mở rộng kho đồ!")
            st.rerun()
        else:
            st.error("Không đủ points")
    st.subheader(f"🎒 Túi đồ ({len(data['inventory'])}/{data['max_slots']})")

    cols = st.columns(3)

    for i in range(data["max_slots"]):
        with cols[i % 3]:
            if i < len(data["inventory"]):
                it = data["inventory"][i]

                st.markdown(
                    f"""
                    <div class='card'>
                        <b>{it['name']}</b><br>
                        <small style='color:#aaa'>Bấm xem công dụng</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                with st.expander("📖 Công dụng", expanded=False):
                    st.write(it["desc"])

                col_use, col_sell = st.columns(2)

                # ---- USE ITEM ----
                if col_use.button("Dùng", key=f"use_{i}"):
                    if it["type"] == "energy":
                        data["energy"] = min(max_energy, data["energy"] + it["value"])

                    elif it["type"] == "damage":
                        data["boss_hp"] -= it["value"]

                    elif it["type"] == "percent_damage":
                        data["boss_hp"] -= int(data["boss_hp"] * it["value"])

                    elif it["type"] == "points":
                        data["points"] = max(0, data["points"] + it["value"])

                    elif it["type"] == "max_energy":
                        data.setdefault("bonus_max_energy", 0)
                        data["bonus_max_energy"] += it["value"]

                    data["inventory"].pop(i)

                    if data["boss_hp"] <= 0:
                        data["boss_kills"] += 1
                        data["boss_hp"] = 1000
                        st.balloons()

                    save_data(data)
                    st.rerun()

                # ---- SELL ITEM ----
                if col_sell.button("Bán", key=f"sell_{i}"):
                    sell_price = max(5, int(0.3 * 50))  # bán rẻ
                    data["points"] += sell_price
                    data["inventory"].pop(i)
                    save_data(data)
                    st.success(f"Đã bán {it['name']} (+{sell_price} pts)")
                    st.rerun()

            else:
                st.markdown(
                    "<div class='card' style='border:dashed 1px #444'>Ô trống</div>",
                    unsafe_allow_html=True
                )

# ================= 5. ARMORY =================
with tabs[4]:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'><div class='big'>⚔️</div>"
                    f"Sword Lv.{data['equips']['sword']}</div>", unsafe_allow_html=True)
        cost = data["equips"]["sword"] * 100
        if st.button(f"Rèn kiếm ({cost} pts)"):
            if data["points"] >= cost:
                data["points"] -= cost
                data["equips"]["sword"] += 1
                save_data(data)
                st.rerun()

    with c2:
        st.markdown("<div class='card'><div class='big'>👞</div>"
                    f"Boots Lv.{data['equips']['boots']}</div>", unsafe_allow_html=True)
        cost = data["equips"]["boots"] * 150
        if st.button(f"Rèn giày ({cost} pts)"):
            if data["points"] >= cost:
                data["points"] -= cost
                data["equips"]["boots"] += 1
                save_data(data)
                st.rerun()

# ================= TAVERN TAB =================
with tabs[5]:
    st.subheader("🍻 TAVERN – Hồi phục & Xa xỉ")

    tavern_items = [
        {"name": "Nước Lã", "emoji": "🥛", "cost": 10, "energy": 10},
        {"name": "Trà Đậm", "emoji": "🍵", "cost": 25, "energy": 25},
        {"name": "Cà Phê Đen", "emoji": "☕", "cost": 50, "energy": 40},
        {"name": "Bữa Thịnh Soạn", "emoji": "🍖", "cost": 80, "energy": 70},
        {"name": "Yến Tiệc Vương Giả", "emoji": "🍗", "cost": 120, "energy": 100},
    ]

    # 🌍 Environment buff (đã gọi sẵn ở đầu file)
    if env["tavern_price_multiplier"] < 1:
        st.success("🍻 Ngày hội Tavern! Giá giảm 50%")

    cols = st.columns(len(tavern_items))

    for idx, item in enumerate(tavern_items):
        with cols[idx]:
            # ✅ ÁP DỤNG GIẢM GIÁ
            final_cost = int(item["cost"] * env["tavern_price_multiplier"])

            st.markdown(
                f"""
                <div class='card'>
                    <h2>{item['emoji']}</h2>
                    <b>{item['name']}</b><br>
                    <small>+{item['energy']} ⚡</small><br>
                    <small>{final_cost} pts</small>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("Mua", key=f"tavern_{idx}"):
                if data["points"] >= final_cost:
                    data["points"] -= final_cost
                    data["energy"] = min(max_energy, data["energy"] + item["energy"])
                    save_data(data)
                    st.success(f"Đã dùng {item['name']}")
                    st.rerun()
                else:
                    st.error("Không đủ points")


# ================= 7. ANALYTICS =================
with tabs[6]:
    st.subheader("📊 Analytics")

    if not data.get("task_history"):
        st.info("Chưa có dữ liệu để thống kê.")
    else:
        df = pd.DataFrame(data["task_history"])

        # convert date
        df["date"] = pd.to_datetime(df["date"])

        # group theo ngày
        daily = (
            df.groupby(df["date"].dt.date)["points"]
            .sum()
            .reset_index()
        )

        daily["Day"] = pd.to_datetime(daily["date"]).dt.strftime("%d/%m")

        fig = px.bar(
            daily,
            x="Day",
            y="points",
            title="🔥 Points kiếm được mỗi ngày"
        )
        fig.update_layout(template="plotly_dark")

        st.plotly_chart(fig, use_container_width=True)


# ================= 8. FORGE =================
with tabs[7]:
    st.subheader("⚙️ FORGE")

    col_task, col_treat = st.columns(2)

    # -------- TASK FORGE --------
    with col_task:
        st.markdown("""
        <div class='card'>
        <h3>📜 Tạo TASK</h3>
        <p>Hành động grind – tiêu energy – đánh boss</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("task_forge"):
            task_name = st.text_input("Tên Task")
            task_pts = st.slider(
                "Points nhận được",
                min_value=10,
                max_value=50,
                value=20,
                step=5
            )

            if st.form_submit_button("⚔️ Tạo Task"):
                if task_name.strip() == "":
                    st.error("Task phải có tên")
                else:
                    data["tasks"][task_name] = task_pts
                    save_data(data)
                    st.success(f"Đã tạo task: {task_name}")
                    st.rerun()

    # -------- TREAT FORGE --------
    with col_treat:
        st.markdown("""
        <div class='card'>
        <h3>🎁 Tạo TREAT</h3>
        <p>Phần thưởng cho bản thân </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("treat_forge"):
            treat_name = st.text_input("Tên Treat")
            treat_cost = st.slider(
                "Giá (points)",
                min_value=50,
                max_value=1000,
                value=50,
                step=5
            )

            if st.form_submit_button("🍬 Tạo Treat"):
                if treat_name.strip() == "":
                    st.error("Treat phải có tên")
                else:
                    data["treats"][treat_name] = treat_cost
                    save_data(data)
                    st.success(f"Đã tạo treat: {treat_name}")
                    st.rerun()
