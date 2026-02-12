import streamlit as st
import requests
import time
import pandas as pd
import re

# ================= 配置區 =================
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定 (寬螢幕模式)
st.set_page_config(page_title="Roblox 情報與預警系統", page_icon="👁️‍🗨️", layout="wide")

# 自訂 CSS 美化
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# ================= 暫存狀態初始化 =================
if 'group_roles_cache' not in st.session_state:
    st.session_state.group_roles_cache = {}
if 'group_allies_cache' not in st.session_state:
    st.session_state.group_allies_cache = {}

# ================= 側邊欄：預警名單設定 =================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Roblox_player_icon_black.svg/512px-Roblox_player_icon_black.svg.png", width=50)
    st.header("⚙️ 戰情室監控設定")
    st.write("請輸入要監控的黑名單社群 ID（多個請用 `,` 分隔）：")
    warning_input = st.text_area("高風險社群 IDs", value="11826423, 36093699", height=100)

    WARNING_GROUP_IDS = set()
    if warning_input:
        for gid in warning_input.split(','):
            gid = gid.strip()
            if gid.isdigit():
                WARNING_GROUP_IDS.add(int(gid))

    st.divider()
    st.metric("已載入預警社群數", f"{len(WARNING_GROUP_IDS)} 個")

# === API 抓取功能區 === (維持原邏輯)

def get_short_name(full_name):
    match = re.search(r'\[(.*?)\]', full_name)
    if match: return match.group(1)
    return full_name

def resolve_user_input(user_input):
    user_input = str(user_input).strip()
    url_username_to_id = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [user_input], "excludeBannedUsers": False}
    try:
        response = requests.post(url_username_to_id, json=payload)
        if response.status_code == 200:
            data = response.json().get("data", [])
            if len(data) > 0: return str(data[0]["id"]), data[0]["name"]
    except: pass 
    if user_input.isdigit():
        url_verify_id = f"https://users.roblox.com/v1/users/{user_input}"
        try:
            res = requests.get(url_verify_id)
            if res.status_code == 200: return str(res.json()["id"]), res.json()["name"]
        except: pass
    return None, None

def get_user_thumbnail(user_id):
    default_img = "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png"
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=true"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("data") and len(res["data"]) > 0:
            img_url = res["data"][0].get("imageUrl")
            if img_url: return img_url
    except Exception: pass
    return default_img

def get_user_groups(user_id):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {item["group"]["id"]: {"name": item["group"]["name"], "role": item["role"]["name"], "rank": item["role"]["rank"]} for item in data}
        elif response.status_code == 429:
            time.sleep(5) 
            return get_user_groups(user_id)
    except Exception: pass
    return {}

def get_group_allies(group_id):
    if group_id in st.session_state.group_allies_cache:
        return st.session_state.group_allies_cache[group_id]
    allies = {}
    start_row = 0
    while True:
        url = f"https://groups.roblox.com/v1/groups/{group_id}/relationships/allies?maxRows=100&startRowIndex={start_row}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for grp in data.get("relatedGroups", []): allies[grp["id"]] = grp["name"]
                next_row = data.get("nextRowIndex")
                if not next_row: break
                start_row = next_row
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429: time.sleep(5)
            else: break
        except Exception: break
    st.session_state.group_allies_cache[group_id] = allies
    return allies

def get_user_friends(user_id):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [{"id": user["id"], "name": user["name"]} for user in data]
    except Exception: pass
    return []

def get_user_followers(user_id, limit=None):
    followers, cursor = [], ""
    while cursor is not None:
        if limit and len(followers) >= limit: break
        url = f"https://friends.roblox.com/v1/users/{user_id}/followers?limit=100" + (f"&cursor={cursor}" if cursor else "")
        try:
            res = requests.get(url)
            if res.status_code == 200:
                json_data = res.json()
                followers.extend([{"id": u["id"], "name": u["name"]} for u in json_data.get("data", [])])
                cursor = json_data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif res.status_code == 429: time.sleep(5)
            else: break
        except Exception: break
    return followers[:limit] if limit else followers

def get_user_followings(user_id, limit=None):
    followings, cursor = [], ""
    while cursor is not None:
        if limit and len(followings) >= limit: break
        url = f"https://friends.roblox.com/v1/users/{user_id}/followings?limit=100" + (f"&cursor={cursor}" if cursor else "")
        try:
            res = requests.get(url)
            if res.status_code == 200:
                json_data = res.json()
                followings.extend([{"id": u["id"], "name": u["name"]} for u in json_data.get("data", [])])
                cursor = json_data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif res.status_code == 429: time.sleep(5)
            else: break
        except Exception: break
    return followings[:limit] if limit else followings

def get_group_roles(group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}/roles"
    try:
        res = requests.get(url)
        if res.status_code == 200: return res.json().get("roles", [])
        elif res.status_code == 429: time.sleep(5); return get_group_roles(group_id)
    except Exception: pass
    return []

def get_members_of_roles(group_id, selected_roles):
    members = []
    for role in selected_roles:
        role_id, role_name, role_rank, cursor = role["id"], role["name"], role.get("rank", 0), ""
        while cursor is not None:
            url = f"https://groups.roblox.com/v1/groups/{group_id}/roles/{role_id}/users?sortOrder=Desc&limit=100" + (f"&cursor={cursor}" if cursor else "")
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("data", []):
                        uid = item.get("userId") or item.get("user", {}).get("userId")
                        uname = item.get("username") or item.get("user", {}).get("username")
                        if uid and uname: members.append({"id": uid, "name": uname, "rank_name": role_name, "rank_num": role_rank})
                    cursor = data.get("nextPageCursor")
                    time.sleep(REQUEST_DELAY)
                elif res.status_code == 429: time.sleep(5)
                else: break
            except Exception: break
    return members

# === UI 排版與視覺化資料處理函數 ===

def get_rank_style(rank_num, role_name=""):
    role_lower = str(role_name).lower()
    rank_num = int(rank_num)
    if any(kw in role_lower for kw in ["將", "司令", "總長", "元首", "部長", "general", "admiral", "commander"]): return "#8B0000", "👑"
    elif any(kw in role_lower for kw in ["校", "colonel", "major"]): return "#FF4B4B", "🔴"
    elif any(kw in role_lower for kw in ["尉", "captain", "lieutenant"]): return "#FF8C00", "🟠"
    elif any(kw in role_lower for kw in ["士", "sergeant", "corporal"]): return "#DAA520", "🟡"
    elif any(kw in role_lower for kw in ["兵", "卒", "private", "seaman", "airman"]): return "#4682B4", "🔵"
    elif any(kw in role_lower for kw in ["生", "學", "新", "cadet", "recruit", "trainee"]): return "#2E8B57", "🟢"
    else:
        if rank_num == 255: return "#8B0000", "👑"
        elif rank_num >= 200: return "#FF4B4B", "🔴"
        elif rank_num >= 150: return "#FF8C00", "🟠"
        elif rank_num >= 100: return "#DAA520", "🟡"
        elif rank_num >= 50: return "#8A2BE2", "🟣"
        elif rank_num >= 10: return "#4682B4", "🔵"
        else: return "#2E8B57", "🟢"

def format_badge_html(g_data, group_type):
    bg_color, icon = get_rank_style(g_data['rank_num'], g_data['role_name']) 
    type_icon = "🏴" if group_type == "core" else ("⚠️" if group_type == "ally" else "🎯")
    return f"<span style='background-color: {bg_color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 600; margin-right: 6px; display: inline-block; margin-bottom: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>{type_icon} {g_data['group_name']} (ID: {g_data['group_id']}) | {icon} {g_data['role_name']} (Lv.{g_data['rank_num']})</span>"

def format_df_string(g_data, group_type):
    _, icon = get_rank_style(g_data['rank_num'], g_data['role_name'])
    type_icon = "🏴" if group_type == "core" else ("⚠️" if group_type == "ally" else "🎯")
    return f"{type_icon} {g_data['group_name']} (ID: {g_data['group_id']}) - {icon} {g_data['role_name']} (Lv.{g_data['rank_num']})"

def fetch_alert_data(user_id, user_name, relation_type, warning_group_ids, scanned_group_id=None):
    user_groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    matched_ids = set(user_groups.keys()).intersection(warning_group_ids)
    if not matched_ids: return None
    report = {"user_name": user_name, "user_id": user_id, "relation": relation_type, "avatar_url": get_user_thumbnail(user_id), "core_groups": [], "ally_groups": [], "scanned_ally_groups": [], "grouped_matches": []}
    for gid in matched_ids:
        g_info = user_groups[gid]
        core_data = {"group_id": gid, "group_name": get_short_name(g_info['name']), "role_name": g_info['role'], "rank_num": g_info['rank']}
        report["core_groups"].append(core_data)
        current_cluster = {"core": core_data, "allies": []}
        allies = get_group_allies(gid)
        if allies:
            matched_allies = set(user_groups.keys()).intersection(set(allies.keys()))
            for ally_id in matched_allies:
                ally_info = user_groups[ally_id]
                ally_data = {"group_id": ally_id, "group_name": get_short_name(ally_info['name']), "role_name": ally_info['role'], "rank_num": ally_info['rank']}
                report["ally_groups"].append(ally_data); current_cluster["allies"].append(ally_data)
        report["grouped_matches"].append(current_cluster)
    if scanned_group_id:
        target_allies = get_group_allies(scanned_group_id)
        if target_allies:
            matched_target_allies = set(user_groups.keys()).intersection(set(target_allies.keys()))
            for ally_id in matched_target_allies:
                ally_info = user_groups[ally_id]
                report["scanned_ally_groups"].append({"group_id": ally_id, "group_name": get_short_name(ally_info['name']), "role_name": ally_info['role'], "rank_num": ally_info['rank']})
    return report

# ================= 核心顯示函式 (唯一且修正 HTML 格式) =================
def draw_alert_card(alert_data):
    with st.container(border=True):
        col1, col2 = st.columns([1, 6])
        with col1:
            safe_avatar = alert_data.get("avatar_url") or "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png"
            st.image(safe_avatar, use_container_width=True)
        with col2:
            st.markdown(f"#### 🚨 {alert_data['user_name']} `(ID: {alert_data['user_id']})`")
            st.caption(f"身分關聯: **{alert_data['relation']}**")
            if alert_data.get("scanned_ally_groups"):
                scanned_ally_html = "".join([format_badge_html(a, "scanned_ally") for a in alert_data["scanned_ally_groups"]])
                st.markdown(f"<div style='margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px dashed #ccc;'><span style='color: #666; font-size: 13px; font-weight: bold;'>🎯 來自目標社群 (A) 之相關同盟：</span><br>{scanned_ally_html}</div>", unsafe_allow_html=True)
            st.markdown("<span style='color: #d9534f; font-size: 13px; font-weight: bold;'>⚠️ 命中預警黑名單 (B) 及其同盟：</span>", unsafe_allow_html=True)
            if "grouped_matches" in alert_data:
                for cluster in alert_data["grouped_matches"]:
                    core_html, ally_html_content = format_badge_html(cluster["core"], "core"), ""
                    if cluster["allies"]:
                        ally_badges = "".join([format_badge_html(a, "ally") for a in cluster["allies"]])
                        ally_h = f"<div style='margin-top:4px;margin-left:20px;display:flex;align-items:center;'><span style='color:#ccc;margin-right:5px;'>└─ </span>{ally_badges}</div>"
                    st.markdown(f"<div style='margin-bottom:8px;padding-left:8px;border-left:3px solid #d9534f;background-color:rgba(255,0,0,0.03);padding:5px 0 5px 8px;border-radius:0 5px 5px 0;'><div>{core_h}</div>{ally_h}</div>", unsafe_allow_html=True)

# ================= 統整表格優化 (強化階層辨識) =================
def draw_summary_dashboard(alerted_list, total_scanned, title="掃描總結"):
    st.divider()
    st.markdown(f"### 📊 {title} 報告")
    col1, col2, col3 = st.columns(3)
    col1.metric("🔍 總掃描人數", f"{total_scanned} 人")
    flagged_count = len(alerted_list)
    safe_ratio = ((total_scanned - flagged_count) / total_scanned * 100) if total_scanned > 0 else 0
    col2.metric("🚨 觸發預警人數", f"{flagged_count} 人", delta=f"-{flagged_count} 威脅" if flagged_count > 0 else "0 威脅", delta_color="inverse")
    col3.metric("🛡️ 安全比例", f"{safe_ratio:.1f} %")
    if flagged_count > 0:
        df_data = [{"頭像": m["avatar_url"], "名稱": m["user_name"], "關聯": m["relation"], "預警核心": "\n".join([format_df_string(g, "core") for g in m["core_groups"]]), "預警附屬": "\n".join([format_df_string(a, "ally") for a in m["ally_groups"]]) if m.get("ally_groups") else "無", "玩家 ID": str(m["user_id"])} for m in alerted_list]
        st.dataframe(pd.DataFrame(df_data), column_config={"頭像": st.column_config.ImageColumn("大頭貼"), "玩家 ID": st.column_config.TextColumn("ID")}, hide_index=True, use_container_width=True)

# ================= Streamlit 網頁介面 =================
st.title("👁️‍🗨️ Roblox 深度情報交叉比對系統")

if not WARNING_GROUP_IDS:
    st.error("👈 請先在左側邊欄輸入有效的「高風險社群 ID」！")
else:
    tab1, tab2 = st.tabs(["👤 單一目標深度掃描", "🛡️ 群組大範圍降維掃描"])

    with tab1:
        st.subheader("針對單一目標及其社交圈進行掃描")
        c1, c2 = st.columns([2, 1])
        with c1: 
            user_input = st.text_input("輸入目標玩家名稱或 ID：", key="input_player")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            scan_all = st.checkbox("⚠️ 解除人數限制 (全數掃描追蹤名單)")
            limit = None if scan_all else 100
            
        if st.button("啟動掃描程序", type="primary", key="btn_p"):
            if not user_input:
                st.error("❌ 請輸入玩家名稱或 ID")
            else:
                uid, uname = resolve_user_input(user_input)
                if not uid: 
                    st.error("❌ 無法解析目標玩家。")
                else:
                    st.success(f"✅ 鎖定目標：{uname} (ID: {uid})")
                    
                    alerted_list = []
                    scan_queue = []
                    
                    # 1. 加入玩家本體
                    scan_queue.append({"id": uid, "name": uname, "rel": "目標玩家本體"})
                    
                    # 2. 抓取好友
                    with st.status("正在獲取社交圈資料...", expanded=True) as status:
                        st.write("正在讀取好友列表...")
                        friends = get_user_friends(uid)
                        for f in friends:
                            scan_queue.append({"id": f["id"], "name": f["name"], "rel": "目標的好友"})
                        
                        st.write("正在讀取關注中名單...")
                        followings = get_user_followings(uid, limit=limit)
                        for f in followings:
                            scan_queue.append({"id": f["id"], "name": f["name"], "rel": "目標關注的人"})
                            
                        st.write("正在讀取粉絲名單...")
                        followers = get_user_followers(uid, limit=limit)
                        for f in followers:
                            scan_queue.append({"id": f["id"], "name": f["name"], "rel": "目標的粉絲"})
                        
                        st.write(f"準備掃描總計 {len(scan_queue)} 位關聯人員...")
                        
                        # 開始掃描
                        progress_bar = st.progress(0)
                        for i, person in enumerate(scan_queue):
                            # 更新進度
                            progress_bar.progress((i + 1) / len(scan_queue))
                            
                            # 執行預警檢查
                            alert = fetch_alert_data(person["id"], person["name"], person["rel"], WARNING_GROUP_IDS)
                            
                            if alert:
                                alerted_list.append(alert)
                                # 即時在介面上繪製發現的威脅卡片
                                draw_alert_card(alert)
                        
                        status.update(label="✅ 掃描完成！", state="complete", expanded=False)

                    # 顯示總結報告
                    draw_summary_dashboard(alerted_list, len(scan_queue), f"{uname} 的社交圈掃描")
                    st.balloons()
    with tab2:
        st.subheader("針對大型群組進行地毯式排查")
        target_group_id = st.text_input("請輸入目標群組 ID (Group ID)：", placeholder="例如: 1234567", key="input_group")
        if st.button("1. 獲取群組結構 (Ranks)", type="secondary"):
            if target_group_id.isdigit():
                with st.spinner("正在解析群組階層結構..."):
                    roles = get_group_roles(target_group_id)
                    if roles:
                        st.session_state.group_roles_cache[target_group_id] = sorted(roles, key=lambda x: x.get("rank", 0))
                        st.success("✅ 結構解析成功！")
            else: st.warning("⚠️ ID 格式錯誤")

        if target_group_id in st.session_state.group_roles_cache:
            st.divider()
            st.markdown("#### ⚙️ 第二步：劃定打擊範圍 (Rank 區間)")
            roles = st.session_state.group_roles_cache[target_group_id]
            role_options = [f"[Rank: {r['rank']}] {r['name']} (約 {r['memberCount']} 人)" for r in roles]
            
            # ========== 這裡已還原為原本的雙欄與格式化顯示 ==========
            col1, col2 = st.columns(2)
            with col1:
                start_idx = st.selectbox("起始階層：", range(len(role_options)), format_func=lambda x: role_options[x], index=0)
            with col2:
                end_idx = st.selectbox("結束階層：", range(len(role_options)), format_func=lambda x: role_options[x], index=len(role_options)-1)

            selected_roles = roles[min(start_idx, end_idx) : max(start_idx, end_idx) + 1]
            total_est = sum(r.get("memberCount", 0) for r in selected_roles)
            st.info(f"💡 預計排查區間包含 {len(selected_roles)} 個階層，約 {total_est} 名人員。")

            if st.button("2. 執行大範圍掃描", type="primary"):
                with st.spinner("正在執行深度比對..."):
                    mems = get_members_of_roles(target_group_id, selected_roles)
                    if mems:
                        alerted_m, bar, status = [], st.progress(0), st.empty()
                        for i, m in enumerate(mems):
                            bar.progress((i+1)/len(mems))
                            status.text(f"檢查中 {i+1}/{len(mems)}: {m['name']}")
                            a = fetch_alert_data(m["id"], m["name"], f"成員 [{m['rank_name']}]", WARNING_GROUP_IDS, int(target_group_id))
                            if a: draw_alert_card(a); alerted_m.append(a)
                        draw_summary_dashboard(alerted_m, len(mems), "群組深度排查")
                        st.balloons()
