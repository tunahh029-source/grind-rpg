import calendar
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config("The Grind RPG", layout="wide")

# Endpoint giữ app "thức" (dịch vụ ping gọi ?ping=1)
if st.query_params.get("ping") == "1":
    st.write("alive")
    st.stop()

import game  # noqa: E402
from db import backup_player, fetch_player, insert_player, save_player  # noqa: E402

BG_IMAGE = "https://i.pinimg.com/originals/73/19/75/731975324c0d55280298b4b5824417d1.gif"

# Màu biểu đồ lấy theo ảnh mẫu (vàng / xanh lá / đỏ)
COLOR_DONE = "#8fc35b"
COLOR_PENDING = "#c9962b"
COLOR_OVERDUE = "#c0392b"

MONTH_NAMES = [f"Tháng {m}" for m in range(1, 13)]


# ================= THÔNG BÁO (không bị mất khi st.rerun) =================
if "flash" not in st.session_state:
    st.session_state.flash = []
if "chest_msg" not in st.session_state:
    st.session_state.chest_msg = None
if "reset_confirm" not in st.session_state:
    st.session_state.reset_confirm = False
if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0


def flash(kind, text=""):
    st.session_state.flash.append((kind, text))


def show_flash():
    msgs, st.session_state.flash = st.session_state.flash, []
    for kind, text in msgs:
        if kind == "success":
            st.success(text)
        elif kind == "error":
            st.error(text)
        elif kind == "warning":
            st.warning(text)
        elif kind == "info":
            st.info(text)
        elif kind == "toast":
            st.toast(text)
        elif kind == "balloons":
            st.balloons()


# ================= LƯU / TẢI =================
def commit(d):
    """Lưu tiến trình. Nếu lưu lỗi thì báo rõ và dừng, không im lặng làm mất dữ liệu."""
    try:
        save_player(d)
    except Exception as e:
        st.error("❌ Không thể lưu dữ liệu — thay đổi vừa rồi CHƯA được lưu.")
        st.exception(e)
        st.stop()


def load_data():
    try:
        exists, data = fetch_player()
    except Exception as e:
        st.error("❌ Không thể tải dữ liệu từ Supabase")
        st.exception(e)
        st.stop()

    if not exists:
        data = game.new_player_data()
        try:
            insert_player(data)
        except Exception as e:
            st.error("❌ Không thể tạo nhân vật mới")
            st.exception(e)
            st.stop()
    elif not isinstance(data, dict) or not data:
        st.error(
            "⚠️ Dòng dữ liệu của bạn trên Supabase đang rỗng hoặc hỏng. "
            "App dừng lại để không ghi đè lên dữ liệu cũ — hãy kiểm tra bảng `players` "
            "hoặc khôi phục từ dòng sao lưu (xem README.md)."
        )
        st.stop()

    before = json.dumps(data, sort_keys=True, default=str)
    game.migrate(data)
    changed = json.dumps(data, sort_keys=True, default=str) != before
    if game.apply_regen(data):
        changed = True
    if changed:
        commit(data)
    return data


# ================= CALLBACK =================
def _ask_reset():
    st.session_state.reset_confirm = True


def _cancel_reset():
    st.session_state.reset_confirm = False


def _do_reset():
    st.session_state.reset_confirm = False
    st.session_state.reset_do = True


def _shift_month(delta):
    idx = st.session_state.dash_year * 12 + (st.session_state.dash_month - 1) + delta
    st.session_state.dash_year, month0 = divmod(idx, 12)
    st.session_state.dash_month = month0 + 1


def _go_today():
    t = game.today()
    st.session_state.dash_year, st.session_state.dash_month = t.year, t.month


# ================= GIAO DIỆN CHUNG =================
st.markdown(
    f"""
    <style>
    html, body {{ height: 100%; }}
    body {{
        background-image:
            linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.8)),
            url("{BG_IMAGE}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background: transparent;
    }}
    section.main > div {{ background: transparent; }}
    section[data-testid="stSidebar"] {{
        background-color: rgba(2, 6, 23, 0.92);
        border-right: 1px solid #1f2937;
    }}
    .card {{
        background: rgba(17, 24, 39, 0.85);
        border: 1px solid #374151;
        padding: 16px;
        border-radius: 14px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        text-align: center;
    }}
    .big {{ font-size: 32px; }}
    .status-head {{ display:flex; align-items:center; gap:12px; margin-bottom:4px; }}
    .status-icon {{
        width:44px; height:44px; border-radius:50%; background:{COLOR_OVERDUE};
        display:flex; align-items:center; justify-content:center; font-size:22px;
    }}
    .status-title {{ font-weight:700; font-size:20px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

show_flash()

data = load_data()

# Reset được xử lý sau khi nhấn xác nhận (có sao lưu trước)
if st.session_state.pop("reset_do", False):
    backup_player(data, "reset")
    data = game.migrate(game.new_player_data())
    commit(data)
    flash("success", "Đã reset nhân vật! (bản trước đó được sao lưu trong Supabase)")
    st.rerun()

env = game.get_environment()
max_energy = game.get_max_energy(data)
now_dt = game.now_local()

# ================= SIDEBAR =================
st.sidebar.title("⚔️ From the ordinary to flee")

st.sidebar.metric("💰 Points", data["points"])
st.sidebar.write(f"⚡ Energy {int(data['energy'])}/{max_energy}")
st.sidebar.progress(min(data["energy"] / max_energy, 1))

st.sidebar.metric("🏆 Boss đã hạ", data.get("boss_kills", 0))
st.sidebar.metric("📜 Task đã hoàn thành", data.get("tasks_done", 0))
st.sidebar.metric("🔥 Chuỗi ngày liên tục", data.get("streak", 0))

hp_pct = min(1.0, max(0.0, data["boss_hp"] / game.BOSS_MAX_HP))
st.sidebar.progress(hp_pct, text=f"🐉 Boss HP {data['boss_hp']}/{game.BOSS_MAX_HP}")

days_in_year = 366 if calendar.isleap(now_dt.year) else 365
year_prog = (now_dt.timetuple().tm_yday - 1) / days_in_year
st.sidebar.progress(year_prog, text=f"📅 Year {year_prog:.1%}")

st.sidebar.divider()
st.sidebar.subheader("🌍 Environment Buff")
if env["buffs"]:
    for buff in env["buffs"]:
        st.sidebar.success(buff)
else:
    st.sidebar.info("Không có buff đặc biệt")

st.sidebar.divider()
st.sidebar.subheader("☠️ Debuff đang dính")
debuffs_now = game.active_debuffs(data)
if debuffs_now:
    for line in debuffs_now:
        st.sidebar.error(line)
else:
    st.sidebar.write("✨ Không có debuff")

st.sidebar.button("🗑️ Reset", on_click=_ask_reset)
if st.session_state.reset_confirm:
    st.sidebar.warning(
        "Reset toàn bộ tiến trình, kể cả danh sách task? "
        "Bản hiện tại sẽ được sao lưu trước khi xóa."
    )
    c1, c2 = st.sidebar.columns(2)
    c1.button("❌ Hủy", on_click=_cancel_reset)
    c2.button("✅ Xác nhận", on_click=_do_reset)

# ================= TABS =================
tab_task, tab_chest, tab_bag, tab_armory, tab_tavern, tab_ach = st.tabs(
    ["⚔️ Task", "📦 Rương", "🎒 Túi đồ", "🛠️ Rèn", "🍻 Tavern", "🏆 ACHIEVEMENTS"]
)


# ================= TASK TAB =================
def build_donut(stats):
    if stats["total"] == 0:
        labels, values, colors = ["Chưa có task"], [1], ["#4b5563"]
    else:
        labels = [
            f"Hoàn thành · {stats['done']}",
            f"Chờ làm · {stats['pending']}",
            f"Quá hạn · {stats['overdue']}",
        ]
        values = [stats["done"], stats["pending"], stats["overdue"]]
        colors = [COLOR_DONE, COLOR_PENDING, COLOR_OVERDUE]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            direction="clockwise",
            textinfo="none",
            hoverinfo="label+percent",
            marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
            domain=dict(x=[0, 0.58], y=[0, 1]),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="middle", y=0.5, xanchor="left", x=0.64,
            font=dict(size=15),
        ),
        annotations=[
            dict(
                text=f"<b>{stats['done']}/{stats['total']}</b><br>"
                     f"<span style='font-size:12px'>hoàn thành</span>",
                x=0.29, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(size=26),
            )
        ],
    )
    return fig


with tab_task:
    today = game.today()

    if "dash_year" not in st.session_state:
        st.session_state.dash_year = today.year
        st.session_state.dash_month = today.month

    years = list(range(min(2024, today.year), today.year + 6))
    if st.session_state.dash_year not in years:
        years = sorted(set(years + [st.session_state.dash_year]))

    n1, n2, n3, n4, n5 = st.columns([1, 2, 2, 1, 2])
    n1.button("◀", key="prev_month", on_click=_shift_month, args=(-1,))
    n2.selectbox(
        "Tháng", list(range(1, 13)), key="dash_month",
        format_func=lambda m: MONTH_NAMES[m - 1], label_visibility="collapsed",
    )
    n3.selectbox("Năm", years, key="dash_year", label_visibility="collapsed")
    n4.button("▶", key="next_month", on_click=_shift_month, args=(1,))
    n5.button("📍 Hôm nay", key="go_today", on_click=_go_today)

    year, month = st.session_state.dash_year, st.session_state.dash_month
    all_tasks = data["tasks"]
    month_tasks = game.tasks_in_month(all_tasks, year, month)
    year_tasks = game.tasks_in_year(all_tasks, year)
    stats = game.task_stats(month_tasks, today.isoformat())
    year_stats = game.task_stats(year_tasks, today.isoformat())
    all_stats = game.task_stats(all_tasks, today.isoformat())

    # ----- Biểu đồ trạng thái task (theo ảnh mẫu) -----
    with st.container(border=True):
        st.markdown(
            "<div class='status-head'><div class='status-icon'>📋</div>"
            f"<span class='status-title'>Task status — {MONTH_NAMES[month - 1]} {year}</span></div>",
            unsafe_allow_html=True,
        )
        chart_col, num_col = st.columns([3, 2])
        with chart_col:
            st.plotly_chart(build_donut(stats), key=f"donut_{year}_{month}")
        with num_col:
            m1, m2 = st.columns(2)
            m1.metric("Task đặt ra", stats["total"])
            m2.metric("Đã hoàn thành", stats["done"])
            m3, m4 = st.columns(2)
            m3.metric("Chưa xong", stats["pending"] + stats["overdue"])
            m4.metric("Tỉ lệ", f"{stats['rate']:.0%}")
            st.caption(
                f"📆 Cả năm {year}: {year_stats['done']}/{year_stats['total']} task hoàn thành "
                f"({year_stats['rate']:.0%})"
            )
            st.caption(
                f"🗂️ Tất cả các tháng: {all_stats['done']}/{all_stats['total']} task hoàn thành "
                f"({all_stats['rate']:.0%})"
            )

    # ----- To-do checklist dạng bảng -----
    st.subheader("📝 To-do checklist")

    weeks = game.month_weeks(year, month)
    first_day, last_day = weeks[0][0], weeks[-1][1]
    week_labels = ["Cả tháng"] + [
        f"Tuần {i + 1} ({a:%d/%m} – {b:%d/%m})" for i, (a, b) in enumerate(weeks)
    ]
    default_week = 0
    for i, (a, b) in enumerate(weeks):
        if a <= today <= b:
            default_week = i + 1
    sel_label = st.selectbox(
        "Hiển thị", week_labels, index=default_week, key=f"week_sel_{year}_{month}"
    )
    sel_idx = week_labels.index(sel_label)
    lo, hi = (first_day, last_day) if sel_idx == 0 else weeks[sel_idx - 1]

    shown = sorted(
        (t for t in month_tasks if lo.isoformat() <= t["date"] <= hi.isoformat()),
        key=lambda t: t["date"],
    )
    default_day = today if lo <= today <= hi else lo

    cols = ["id", "Xong", "Thứ", "Ngày", "Task", "Điểm", "⚔️ Dmg"]
    rows = []
    for t in shown:
        d = game.parse_date(t["date"])
        rows.append(
            {
                "id": t["id"],
                "Xong": t["done"],
                "Thứ": game.WEEKDAYS[d.weekday()],
                "Ngày": d,
                "Task": t["name"],
                "Điểm": t["points"],
                "⚔️ Dmg": game.calc_damage(t["points"], data, env),
            }
        )
    df = pd.DataFrame(rows, columns=cols)

    editor_key = f"editor_{year}_{month}_{sel_idx}_{st.session_state.editor_nonce}"
    with st.form(f"task_form_{year}_{month}_{sel_idx}", border=False):
        edited = st.data_editor(
            df,
            key=editor_key,
            num_rows="dynamic",
            hide_index=True,
            column_order=["Xong", "Thứ", "Ngày", "Task", "Điểm", "⚔️ Dmg"],
            column_config={
                "id": None,
                "Xong": st.column_config.CheckboxColumn("✅", default=False),
                "Thứ": st.column_config.TextColumn("Thứ", disabled=True),
                "Ngày": st.column_config.DateColumn(
                    "Ngày", format="DD/MM/YYYY", min_value=first_day, max_value=last_day,
                    default=default_day, required=True,
                ),
                "Task": st.column_config.TextColumn("Task", max_chars=120, required=True),
                "Điểm": st.column_config.NumberColumn(
                    "Điểm", min_value=game.TASK_MIN_POINTS, max_value=game.TASK_MAX_POINTS,
                    step=5, default=20, format="%d",
                ),
                "⚔️ Dmg": st.column_config.NumberColumn("⚔️ Dmg", disabled=True, format="%d"),
            },
        )
        submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary")

    st.caption(
        f"Bấm ➕ dưới bảng để thêm task, chọn dòng rồi nhấn Delete để xóa, bấm vào ô để sửa. "
        f"Tick ✅ rồi **Lưu thay đổi** để hoàn thành task (tốn {game.task_energy_cost(data)}⚡). "
        "Nhớ lưu trước khi đổi tháng/tuần."
    )

    if submitted:
        records = edited.to_dict("records")
        if "id" not in edited.columns:  # dự phòng: ánh xạ theo chỉ số dòng gốc
            id_by_index = dict(zip(df.index, df["id"]))
            for idx, rec in zip(edited.index, records):
                rec["id"] = id_by_index.get(idx)
        # Đổi tên cột hiển thị -> khoá logic
        records = [
            {
                "id": r.get("id"),
                "done": r.get("Xong"),
                "date": r.get("Ngày"),
                "task": r.get("Task"),
                "points": r.get("Điểm"),
            }
            for r in records
        ]

        res = game.apply_table_edits(data, records, [t["id"] for t in shown], env, now_dt)
        commit(data)

        changes = res["added"] + res["edited"] + res["deleted"] + res["completed"]
        if changes:
            flash(
                "success",
                f"💾 Đã lưu: +{res['added']} mới · {res['edited']} sửa · "
                f"{res['deleted']} xóa · {res['completed']} hoàn thành",
            )
        else:
            flash("info", "Không có thay đổi nào để lưu.")
        for w in res["warnings"]:
            flash("warning", w)
        for tmsg in res["toasts"]:
            flash("toast", tmsg)
        if res["boss_kills"]:
            flash("success", f"🐉 Bạn đã hạ Boss {res['boss_kills']} lần!")
            flash("balloons")
        for ach in res["unlocked"]:
            flash("toast", f"{ach['emoji']} Achievement unlocked: {ach['name']}!")

        st.session_state.editor_nonce += 1
        st.rerun()

# ================= CHEST TAB =================
with tab_chest:
    st.subheader("📦 RƯƠNG MAY MẮN")

    if st.session_state.chest_msg:
        st.info(st.session_state.chest_msg)
        if st.button("OK"):
            st.session_state.chest_msg = None
            st.rerun()

    if st.button(f"🔓 MỞ RƯƠNG ({game.CHEST_COST} pts)"):
        out = game.open_chest(data)
        if not out["ok"]:
            st.error(out["msg"])
        else:
            commit(data)
            st.session_state.chest_msg = out["msg"]
            st.rerun()

# ================= INVENTORY TAB =================
with tab_bag:
    st.subheader("🎒 Túi đồ")

    col_a, col_b = st.columns([3, 1])
    col_a.write(f"Số ô: {data['max_slots']}")
    if col_b.button(f"➕ Mua ô ({game.slot_price(data)} pts)"):
        out = game.buy_slot(data)
        if out["ok"]:
            commit(data)
            flash("success", out["msg"])
            st.rerun()
        else:
            st.error(out["msg"])

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
                    unsafe_allow_html=True,
                )
                with st.expander("📖 Công dụng", expanded=False):
                    st.write(it["desc"])

                col_use, col_sell = st.columns(2)

                if col_use.button("Dùng", key=f"use_{i}"):
                    out = game.use_item(data, i)
                    commit(data)
                    flash("success", out["msg"])
                    if out["boss_killed"]:
                        flash("success", "🐉 Bạn đã hạ Boss!")
                        flash("balloons")
                    for ach in out["unlocked"]:
                        flash("toast", f"{ach['emoji']} Achievement unlocked: {ach['name']}!")
                    st.rerun()

                sell_price = it.get("sell", game.DEFAULT_SELL_PRICE)
                if col_sell.button(f"Bán (+{sell_price})", key=f"sell_{i}"):
                    out = game.sell_item(data, i)
                    commit(data)
                    flash("success", out["msg"])
                    st.rerun()
            else:
                st.markdown(
                    "<div class='card' style='border:dashed 1px #444'>Ô trống</div>",
                    unsafe_allow_html=True,
                )

# ================= ARMORY TAB =================
with tab_armory:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='card'><div class='big'>⚔️</div>"
            f"Sword Lv.{data['equips']['sword']}</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Rèn kiếm ({game.upgrade_cost(data, 'sword')} pts)"):
            out = game.upgrade_equipment(data, "sword")
            if out["ok"]:
                commit(data)
                flash("success", out["msg"])
                st.rerun()
            else:
                st.error(out["msg"])

    with c2:
        st.markdown(
            "<div class='card'><div class='big'>👞</div>"
            f"Boots Lv.{data['equips']['boots']}</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Rèn giày ({game.upgrade_cost(data, 'boots')} pts)"):
            out = game.upgrade_equipment(data, "boots")
            if out["ok"]:
                commit(data)
                flash("success", out["msg"])
                st.rerun()
            else:
                st.error(out["msg"])

# ================= TAVERN TAB =================
with tab_tavern:
    st.subheader("🍻 TAVERN – Hồi phục & Xa xỉ")

    if env["tavern_price_multiplier"] < 1:
        st.success("🍻 Ngày hội Tavern! Giá giảm 50%")

    cols = st.columns(len(game.TAVERN_ITEMS))
    for idx, item in enumerate(game.TAVERN_ITEMS):
        with cols[idx]:
            st.markdown(
                f"""
                <div class='card'>
                    <h2>{item['emoji']}</h2>
                    <b>{item['name']}</b><br>
                    <small>+{item['energy']} ⚡</small><br>
                    <small>{game.tavern_price(item, env)} pts</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Mua", key=f"tavern_{idx}"):
                out = game.buy_tavern(data, idx, env)
                if out["ok"]:
                    commit(data)
                    flash("success", out["msg"])
                    st.rerun()
                else:
                    st.error(out["msg"])

# ================= ACHIEVEMENTS TAB =================
with tab_ach:
    st.subheader("🏆 ACHIEVEMENTS")

    unlocked_keys = [k for k in data.get("achievements", []) if k in game.ACHIEVEMENTS]
    if not unlocked_keys:
        st.info("Chưa có thành tựu nào. Hãy tiếp tục grind 💀")
    else:
        for key in unlocked_keys:
            ach = game.ACHIEVEMENTS[key]
            st.markdown(
                f"""
                <div class='card'>
                    <h2>{ach['emoji']}</h2>
                    <b>{ach['name']}</b><br>
                    <small>{ach['desc']}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
