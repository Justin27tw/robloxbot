import streamlit as st
import requests
import time
import pandas as pd
import re

# ================= 配置區 =================
REQUEST_DELAY = 0.5  
# ==========================================

st.set_page_config(page_title="Roblox 情報與預警系統", page_icon="👁️‍🗨️", layout="wide")

# 自訂 CSS：強化區塊邊框與標題質感
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    .info-section { 
        background-color: rgba(255, 255, 255, 0.05); 
        border-left: 4px solid #ff4b4b; 
        padding: 10px; 
        margin-top: 10px; 
        border-radius: 4px;
    }
    .ally-section { 
        background-color: rgba(255, 255, 255, 0.02); 
        border-left: 4px solid #ffa500; 
        padding: 10px; 
        margin-top: 10px; 
        border-radius: 4px;
    }
    .section-title { font-size: 14px; font-weight: bold; margin-bottom: 8px; color: #ccc; }
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
    warning_input = st.text_area("高風險社群 IDs (逗號分隔)", value="11826423, 36093699", height=100)
    WARNING_GROUP_IDS = set()
    if warning_input:
        for gid in warning_input.split(','):
            gid = gid.strip()
            if gid.isdigit(): WARNING_GROUP_IDS.add(int(gid))
    st.divider()
    st.metric("監控社群數", f"{len(WARNING_GROUP_IDS)} 個")

# === API 抓取功能區 ===

def get_short_name(full_name):
    match = re.search(r'\[(.*?)\]', full_name)
    return match.group(1) if match else full_name

def resolve_user_input(user_input):
    user_input = str(user_input).strip()
    url = "https://users.roblox.com/v1/usernames/users"
    try:
        res = requests.post(url, json={"usernames": [user_input], "excludeBannedUsers": False})
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data: return str(data[0]["id"]), data[0]["name"]
    except: pass 
    if user_input.isdigit():
        try:
            res = requests.get(f"https://users.roblox.com/v1/users/{user_input}")
            if res.status_code == 200:
                d = res.json()
                return str(d["id"]), d["name"]
        except: pass
    return None, None

def get_user_thumbnail(user_id):
    default_img = "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png"
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=true"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("data"): return res["data"][0].get("imageUrl") or default_img
    except: pass
    return default_img

def get_user_groups(user_id):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            return {item["group"]["id"]: {"name": item["group"]["name"], "role": item["role"]["name"], "rank": item["role"]["rank"]} for item in res.json().get("data", [])}
        elif res.status_code == 429:
            time.sleep(5)
            return get_user_groups(user_id)
    except: pass
    return {}

def get_group_allies(group_id):
    if group_id in st.session_state.group_allies_cache: return st.session_state.group_allies_cache[group_id]
    allies = {}
    start_row = 0
    while True:
        url = f"https://groups.roblox.com/v1/groups/{group_id}/relationships/allies?maxRows=100&startRowIndex={start_row}"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                for grp in data.get("relatedGroups", []): allies[grp["id"]] = grp["name"]
                next_row = data.get("nextRowIndex")
                if not next_row: break
                start_row = next_row
                time.sleep(REQUEST_DELAY)
            elif res.status_code == 429: time.sleep(5)
            else: break
        except: break
    st.session_state.group_allies_cache[group_id] = allies
    return allies

# --- 社交圈 API ---
def get_user_social(user_id, mode="friends", limit=None):
    results = []
    cursor = ""
    while cursor is not None:
        if limit and len(results) >= limit: break
        url = f"https://friends.roblox.com/v1/users/{user_id}/{mode}?limit=100"
        if cursor: url += f"&cursor={cursor}"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                results.extend([{"id": u["id"], "name": u["name"]} for u in items])
                cursor = data.get("nextPageCursor")
                if mode == "friends": break # Friends API doesn't support cursor in public v1
                time.sleep(REQUEST_DELAY)
            elif res.status_code == 429: time.sleep(5)
            else: break
        except: break
    return results if not limit else results[:limit]

# --- 群組成員 API ---
def get_group_roles(group_id):
    try:
        res = requests.get(f"https://groups.roblox.com/v1/groups/{group_id}/roles")
        return res.json().get("roles", []) if res.status_code == 200 else []
    except: return []

def get_members_of_roles(group_id, selected_roles):
    members = []
    for role in selected_roles:
        cursor = ""
        while cursor is not None:
            url = f"https://groups.roblox.com/v1/groups/{group_id}/roles/{role['id']}/users?sortOrder=Desc&limit=100"
            if cursor: url += f"&cursor={cursor}"
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("data", []):
                        members.append({"id": item.get("userId") or item.get("user",{}).get("userId"), "name": item.get("username") or item.get("user",{}).get("username"), "rank_name": role["name"], "rank_num": role.get("rank", 0)})
                    cursor = data.get("nextPageCursor")
                    time.sleep(REQUEST_DELAY)
                elif res.status_code == 429: time.sleep(5)
                else: break
            except: break
    return members

# === UI 排版邏輯 ===

def get_rank_style(rank_num, role_name=""):
    role_l = str(role_name).lower()
    rank_num = int(rank_num)
    # 軍階優先判斷
    if any(kw in role_l for kw in ["將", "司令", "總長", "general", "admiral", "commander"]): return "#8B0000", "👑"
    elif any(kw in role_l for kw in ["校", "colonel", "major"]): return "#FF4B4B", "🔴"
    elif any(kw in role_l for kw in ["尉", "captain", "lieutenant"]): return "#FF8C00", "🟠"
    elif any(kw in role_l for kw in ["士", "sergeant", "corporal"]): return "#DAA520", "🟡"
    elif any(kw in role_l for kw in ["兵", "卒", "private"]): return "#4682B4", "🔵"
    elif any(kw in role_l for kw in ["生", "學", "新", "cadet", "recruit"]): return "#2E8B57", "🟢"
    # 純數值防護
    if rank_num == 255: return "#8B0000", "👑"
    elif rank_num >= 200: return "#FF4B4B", "🔴"
    elif rank_num >= 150: return "#FF8C00", "🟠"
    elif rank_num >= 100: return "#DAA520", "🟡"
    elif rank_num >= 50: return "#8A2BE2", "🟣"
    return "#4682B4", "🔵"

def format_badge_html(g_data, group_type):
    bg_color, icon = get_rank_style(g_data['rank_num'], g_data['role_name'])
    type_icon = {"core": "🏴", "ally": "⚠️", "target_ally": "🎯"}[group_type]
    return f"<span style='background-color: {bg_color}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-right: 5px; display: inline-block; margin-bottom: 4px;'>{type_icon} {g_data['group_name']} (ID: {g_data['group_id']}) | {icon} {g_data['role_name']} (Lv.{g_data['rank_num']})</span>"

def fetch_alert_data(user_id, user_name, relation, warning_ids, scanned_gid=None):
    ug = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    matched = set(ug.keys()).intersection(warning_ids)
    if not matched: return None
    
    res = {"user_name": user_name, "user_id": user_id, "relation": relation, "avatar": get_user_thumbnail(user_id), "core": [], "allies": []}
    
    # 預警核心與其同盟
    for gid in matched:
        res["core"].append({"group_id": gid, "group_name": get_short_name(ug[gid]['name']), "role_name": ug[gid]['role'], "rank_num": ug[gid]['rank']})
        ally_list = get_group_allies(gid)
        for aid in set(ug.keys()).intersection(set(ally_list.keys())):
            res["allies"].append({"type": "ally", "group_id": aid, "group_name": get_short_name(ug[aid]['name']), "role_name": ug[aid]['role'], "rank_num": ug[aid]['rank']})
            
    # 目標群組的同盟
    if scanned_gid:
        t_allies = get_group_allies(scanned_gid)
        for aid in set(ug.keys()).intersection(set(t_allies.keys())):
            res["allies"].append({"type": "target_ally", "group_id": aid, "group_name": get_short_name(ug[aid]['name']), "role_name": ug[aid]['role'], "rank_num": ug[aid]['rank']})
    return res

def draw_alert_card(data):
    with st.container(border=True):
        c1, c2 = st.columns([1, 8])
        c1.image(data["avatar"], use_container_width=True)
        with c2:
            st.markdown(f"#### 🚨 {data['user_name']} `(ID: {data['user_id']})` | 身分: {data['relation']}")
            
            # --- 核心預警區 ---
            st.markdown("<div class='info-section'><div class='section-title'>🏴 核心預警社群</div>", unsafe_allow_html=True)
            st.markdown("".join([format_badge_html(g, "core") for g in data["core"]]), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # --- 相關情報區 ---
            if data["allies"]:
                st.markdown("<div class='ally-section'><div class='section-title'>🔗 深度關聯情報 (同盟/附屬群組)</div>", unsafe_allow_html=True)
                st.markdown("".join([format_badge_html(a, a['type']) for a in data["allies"]]), unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

# ================= 網頁主體 =================
st.title("👁️‍🗨️ Roblox 深度情報監控儀表板")

if not WARNING_GROUP_IDS:
    st.error("👈 請於側邊欄輸入黑名單群組 ID。")
else:
    t1, t2 = st.tabs(["👤 單一目標掃描", "🛡️ 群組深度排查"])
    
    with t1:
        u_in = st.text_input("輸入名稱或 ID", key="p_in")
        scan_all = st.checkbox("⚠️ 掃描完整追蹤名單", key="all_check")
        if st.button("啟動監控", type="primary"):
            uid, uname = resolve_user_input(u_in)
            if not uid: st.error("查無此人")
            else:
                st.info(f"正在分析: {uname}")
                # 依序掃描 本體 -> 好友 -> Followings -> Followers
                for m, label in [("friends", "好友"), ("followings", "關注中"), ("followers", "粉絲")]:
                    st.write(f"正在排查 {label}...")
                    limit = None if scan_all else 100
                    social = get_user_social(uid, m, limit)
                    if not social and m == "friends": # 本體檢查
                        alert = fetch_alert_data(uid, uname, "監控目標", WARNING_GROUP_IDS)
                        if alert: draw_alert_card(alert)
                    for i, p in enumerate(social):
                        alert = fetch_alert_data(p["id"], p["name"], label, WARNING_GROUP_IDS)
                        if alert: draw_alert_card(alert)
                st.balloons()

    with t2:
        gid_in = st.text_input("輸入目標群組 ID", key="g_in")
        if st.button("讀取群組結構", type="secondary"):
            roles = get_group_roles(gid_in)
            if roles: st.session_state.group_roles_cache[gid_in] = sorted(roles, key=lambda x: x.get("rank", 0))
        
        if gid_in in st.session_state.group_roles_cache:
            roles = st.session_state.group_roles_cache[gid_in]
            opts = [f"Lv.{r['rank']} | {r['name']}" for r in roles]
            s_idx = st.selectbox("起始 Rank", range(len(opts)), format_func=lambda x: opts[x])
            e_idx = st.selectbox("結束 Rank", range(len(opts)), format_func=lambda x: opts[x], index=len(opts)-1)
            
            if st.button("啟動地毯式搜尋", type="primary"):
                sel = roles[min(s_idx, e_idx) : max(s_idx, e_idx)+1]
                mems = get_members_of_roles(gid_in, sel)
                st.write(f"共擷取 {len(mems)} 人，開始比對...")
                bar = st.progress(0)
                for i, m in enumerate(mems):
                    bar.progress((i+1)/len(mems))
                    alert = fetch_alert_data(m["id"], m["name"], f"成員({m['rank_name']})", WARNING_GROUP_IDS, int(gid_in))
                    if alert: draw_alert_card(alert)
                st.success("排查完畢")