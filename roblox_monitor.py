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

# 自訂 CSS 美化：隱藏頂部多餘空白
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

# === API 抓取功能區 ===

def get_short_name(full_name):
    match = re.search(r'\[(.*?)\]', full_name)
    if match:
        return match.group(1)
    return full_name

def resolve_user_input(user_input):
    user_input = str(user_input).strip()
    url_username_to_id = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [user_input], "excludeBannedUsers": False}
    try:
        response = requests.post(url_username_to_id, json=payload)
        if response.status_code == 200:
            data = response.json().get("data", [])
            if len(data) > 0:
                return str(data[0]["id"]), data[0]["name"]
    except Exception:
        pass 

    if user_input.isdigit():
        url_verify_id = f"https://users.roblox.com/v1/users/{user_input}"
        try:
            res = requests.get(url_verify_id)
            if res.status_code == 200:
                user_data = res.json()
                return str(user_data["id"]), user_data["name"]
        except Exception:
            pass
    return None, None

def get_user_thumbnail(user_id):
    default_img = "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png"
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=true"
    
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("data") and len(res["data"]) > 0:
            img_url = res["data"][0].get("imageUrl")
            if img_url: 
                return img_url
    except Exception:
        pass
        
    return default_img

def get_user_groups(user_id):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {
                item["group"]["id"]: {
                    "name": item["group"]["name"], 
                    "role": item["role"]["name"],
                    "rank": item["role"]["rank"]
                } for item in data
            }
        elif response.status_code == 429:
            time.sleep(5) 
            return get_user_groups(user_id)
    except Exception:
        pass
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
                for grp in data.get("relatedGroups", []):
                    allies[grp["id"]] = grp["name"]
                
                next_row = data.get("nextRowIndex")
                if not next_row:
                    break
                start_row = next_row
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429:
                time.sleep(5)
            else:
                break
        except Exception:
            break
            
    st.session_state.group_allies_cache[group_id] = allies
    return allies

def get_user_friends(user_id):
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [{"id": user["id"], "name": user["name"]} for user in data]
    except Exception:
        pass
    return []

def get_user_followers(user_id, limit=None):
    followers = []
    cursor = ""
    while cursor is not None:
        if limit is not None and len(followers) >= limit:
            break
        url = f"https://friends.roblox.com/v1/users/{user_id}/followers?limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                data = json_data.get("data", [])
                followers.extend([{"id": user["id"], "name": user["name"]} for user in data])
                cursor = json_data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429:
                time.sleep(5)
            else:
                break
        except Exception:
            break
    if limit is not None:
        return followers[:limit]
    return followers

def get_user_followings(user_id, limit=None):
    followings = []
    cursor = ""
    while cursor is not None:
        if limit is not None and len(followings) >= limit:
            break
        url = f"https://friends.roblox.com/v1/users/{user_id}/followings?limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                data = json_data.get("data", [])
                followings.extend([{"id": user["id"], "name": user["name"]} for user in data])
                cursor = json_data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429:
                time.sleep(5)
            else:
                break
        except Exception:
            break
    if limit is not None:
        return followings[:limit]
    return followings

def get_group_roles(group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("roles", [])
        elif response.status_code == 429:
            time.sleep(5)
            return get_group_roles(group_id)
    except Exception:
        pass
    return []

def get_members_of_roles(group_id, selected_roles):
    members = []
    for role in selected_roles:
        role_id = role["id"]
        role_name = role["name"]
        role_rank = role.get("rank", 0)
        
        cursor = ""
        while cursor is not None:
            url = f"https://groups.roblox.com/v1/groups/{group_id}/roles/{role_id}/users?sortOrder=Desc&limit=100"
            if cursor:
                url += f"&cursor={cursor}"
                
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("data", []):
                        user_id = item.get("userId") or item.get("user", {}).get("userId")
                        username = item.get("username") or item.get("user", {}).get("username")
                        
                        if user_id and username:
                            members.append({
                                "id": user_id, 
                                "name": username,
                                "rank_name": role_name,
                                "rank_num": role_rank
                            })
                    cursor = data.get("nextPageCursor")
                    time.sleep(REQUEST_DELAY)
                elif response.status_code == 429:
                    time.sleep(5)
                else:
                    break
            except Exception:
                break
    return members

# === UI 排版與視覺化資料處理函數 ===

def get_rank_style(rank_num):
    if rank_num == 255:
        return "#8B0000", "👑" 
    elif rank_num >= 200:
        return "#FF4B4B", "🔴" 
    elif rank_num >= 100:
        return "#FF8C00", "🟠" 
    else:
        return "#4682B4", "🔵" 

def format_badge_html(g_data, group_type):
    """【修改】：支援三種標籤 (core/ally/scanned_ally) 的圖示與顏色渲染"""
    bg_color, icon = get_rank_style(g_data['rank_num'])
    
    if group_type == "core":
        type_icon = "🏴"
    elif group_type == "ally":
        type_icon = "⚠️"
    else:
        type_icon = "🎯" # A社群的附屬同盟
        
    return f"<span style='background-color: {bg_color}; color: white; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 600; margin-right: 6px; display: inline-block; margin-bottom: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>{type_icon} {g_data['group_name']} (ID: {g_data['group_id']}) | {icon} {g_data['role_name']} (Lv.{g_data['rank_num']})</span>"

def format_df_string(g_data, group_type):
    _, icon = get_rank_style(g_data['rank_num'])
    if group_type == "core":
        type_icon = "🏴"
    elif group_type == "ally":
        type_icon = "⚠️"
    else:
        type_icon = "🎯"
    return f"{type_icon} {g_data['group_name']} (ID: {g_data['group_id']}) - {icon} {g_data['role_name']} (Lv.{g_data['rank_num']})"

def fetch_alert_data(user_id, user_name, relation_type, warning_group_ids, scanned_group_id=None):
    """【修改】：新增 scanned_group_id 參數，用來查詢 A社群(目標社群) 的同盟"""
    user_groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    
    matched_ids = set(user_groups.keys()).intersection(warning_group_ids)
    if not matched_ids:
        return None
        
    report = {
        "user_name": user_name,
        "user_id": user_id,
        "relation": relation_type,
        "avatar_url": get_user_thumbnail(user_id), 
        "core_groups": [],
        "ally_groups": [],
        "scanned_ally_groups": [] # 儲存 A 社群同盟的資料
    }
    
    # 1. 處理預警社群 (B社群) 及其附屬群組
    for gid in matched_ids:
        g_info = user_groups[gid]
        report["core_groups"].append({
            "group_id": gid, 
            "group_name": get_short_name(g_info['name']),
            "role_name": g_info['role'],
            "rank_num": g_info['rank']
        })
        
        allies = get_group_allies(gid)
        if allies:
            matched_allies = set(user_groups.keys()).intersection(set(allies.keys()))
            for ally_id in matched_allies:
                ally_info = user_groups[ally_id]
                report["ally_groups"].append({
                    "group_id": ally_id,
                    "group_name": get_short_name(ally_info['name']),
                    "role_name": ally_info['role'],
                    "rank_num": ally_info['rank']
                })
                
    # 2. 處理正在被掃描的目標社群 (A社群) 的附屬群組
    if scanned_group_id:
        target_allies = get_group_allies(scanned_group_id)
        if target_allies:
            matched_target_allies = set(user_groups.keys()).intersection(set(target_allies.keys()))
            for ally_id in matched_target_allies:
                ally_info = user_groups[ally_id]
                report["scanned_ally_groups"].append({
                    "group_id": ally_id,
                    "group_name": get_short_name(ally_info['name']),
                    "role_name": ally_info['role'],
                    "rank_num": ally_info['rank']
                })

    return report

def draw_alert_card(alert_data):
    with st.container(border=True):
        col1, col2 = st.columns([1, 6])
        with col1:
            safe_avatar = alert_data.get("avatar_url")
            if not safe_avatar:
                safe_avatar = "https://tr.rbxcdn.com/38c6edcb50633730ff4cf39ac8859840/150/150/AvatarHeadshot/Png"
                
            st.image(safe_avatar, use_container_width=True)
            
        with col2:
            st.markdown(f"#### 🚨 {alert_data['user_name']} `(ID: {alert_data['user_id']})`")
            st.caption(f"身分關聯: **{alert_data['relation']}**")
            
            # 渲染核心與附屬預警群組
            core_html = "".join([format_badge_html(g, "core") for g in alert_data["core_groups"]])
            st.markdown(core_html, unsafe_allow_html=True)
            
            if alert_data.get("ally_groups"):
                ally_html = "".join([format_badge_html(a, "ally") for a in alert_data["ally_groups"]])
                st.markdown(f"<div style='margin-top: 4px;'>{ally_html}</div>", unsafe_allow_html=True)
                
            # 【修改】：若有掃描出「A社群(目標社群)」的附屬同盟，額外顯示出來
            if alert_data.get("scanned_ally_groups"):
                scanned_ally_html = "".join([format_badge_html(a, "scanned_ally") for a in alert_data["scanned_ally_groups"]])
                st.markdown(f"<div style='margin-top: 6px;'><span style='color: #888; font-size: 13px; font-weight: bold;'>🎯 該成員亦潛伏於「目標掃描社群」的同盟：</span><br>{scanned_ally_html}</div>", unsafe_allow_html=True)

def draw_summary_dashboard(alerted_list, total_scanned, title="掃描總結"):
    st.divider()
    st.markdown(f"### 📊 {title} 報告")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔍 總掃描人數", f"{total_scanned} 人")
    
    flagged_count = len(alerted_list)
    safe_count = total_scanned - flagged_count
    safe_ratio = (safe_count / total_scanned * 100) if total_scanned > 0 else 0
    
    col2.metric("🚨 觸發預警人數", f"{flagged_count} 人", delta=f"-{flagged_count} 潛在威脅" if flagged_count > 0 else "0 威脅", delta_color="inverse")
    col3.metric("🛡️ 人員安全比例", f"{safe_ratio:.1f} %", delta=f"{safe_ratio:.1f}%", delta_color="normal" if safe_ratio == 100 else "off")
    
    if flagged_count == 0:
        st.success("🎉 太棒了！本次掃描範圍內，未發現任何預警名單成員。")
        return
        
    st.markdown("##### 📌 詳細威脅名單")
    df_data = []
    for m in alerted_list:
        df_data.append({
            "頭像": m["avatar_url"],
            "Roblox 名稱": m["user_name"],
            "身分 / 關聯": m["relation"],
            "預警社群 (核心)": "\n".join([format_df_string(g, "core") for g in m["core_groups"]]),
            "預警附屬群組 (階級)": "\n".join([format_df_string(a, "ally") for a in m["ally_groups"]]) if m.get("ally_groups") else "無",
            # 【修改】：新增這一個欄位至表格中
            "目標社群附屬 (階級)": "\n".join([format_df_string(a, "scanned_ally") for a in m.get("scanned_ally_groups", [])]) if m.get("scanned_ally_groups") else "無",
            "玩家 ID": str(m["user_id"])
        })
        
    df = pd.DataFrame(df_data)
    
    st.dataframe(
        df,
        column_config={
            "頭像": st.column_config.ImageColumn("大頭貼", help="Roblox 真實頭像"),
            "玩家 ID": st.column_config.TextColumn("玩家 ID"),
        },
        hide_index=True,
        use_container_width=True
    )


# ================= Streamlit 網頁介面 =================
st.title("👁️‍🗨️ Roblox 深度情報交叉比對系統")
st.write("透過玩家關聯或特定群組職階，自動深潛比對「核心黑名單」與其「情報附屬組織」。")

if not WARNING_GROUP_IDS:
    st.error("👈 系統尚未啟動：請先在左側邊欄輸入至少一組有效的「高風險社群 ID」！")
else:
    tab1, tab2 = st.tabs(["👤 單一目標深度掃描", "🛡️ 群組大範圍降維掃描"])

    # ================= TAB 1: 玩家掃描 =================
    with tab1:
        st.subheader("針對單一目標及其社交圈進行掃描")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            user_input = st.text_input("請輸入目標玩家名稱或 User ID：", placeholder="例如: builderman 或 156", key="input_player")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            scan_all_social = st.checkbox("⚠️ 解除人數限制 (全數掃描追蹤名單)", help="打勾後將無視 100 人上限，將名單徹底翻找完畢。如果目標有數十萬粉絲，可能耗時極長。")
            social_limit = None if scan_all_social else 100

        if st.button("啟動掃描程序", type="primary", key="btn_player"):
            if not user_input:
                st.warning("⚠️ 請提供目標識別碼！")
            else:
                with st.spinner("正在建立與 Roblox 伺服器的連線並驗證身分..."):
                    target_user_id, target_user_name = resolve_user_input(user_input)
                
                if not target_user_id:
                    st.error(f"❌ 無法解析目標「{user_input}」，請確認名稱或 ID 正確。")
                else:
                    st.success(f"✅ 鎖定目標：**{target_user_name}** (ID: {target_user_id})")
                    st.divider()

                    st.markdown("#### 👤 [階段一] 目標本體檢查")
                    with st.spinner("正在剖析目標所屬社群..."):
                        alert_data = fetch_alert_data(target_user_id, target_user_name, "目標玩家", WARNING_GROUP_IDS)
                        if alert_data:
                            draw_alert_card(alert_data)
                            draw_summary_dashboard([alert_data], 1, "本體掃描")
                        else:
                            st.info("✅ 目標本體安全，未檢測到危險社群足跡。")

                    st.markdown("#### 👥 [階段二] 社交圈 (好友) 檢查")
                    friends = get_user_friends(target_user_id) 
                    if not friends:
                        st.info("目標無公開好友資料。")
                    else:
                        st.write(f"取得 {len(friends)} 名聯繫人，開始比對...")
                        friend_bar = st.progress(0)
                        friend_status = st.empty()
                        alerted_friends = [] 
                        
                        start_time = time.time() 
                        for index, friend in enumerate(friends):
                            friend_bar.progress((index + 1) / len(friends))
                            
                            elapsed_time = time.time() - start_time
                            avg_time_per_user = elapsed_time / (index + 1)
                            m, s = divmod(int(avg_time_per_user * (len(friends) - (index + 1))), 60)
                            
                            friend_status.text(f"檢查中 {index + 1}/{len(friends)}: {friend['name']} ⏳ 預估剩餘: {m}分{s}秒")
                            
                            alert_data = fetch_alert_data(friend["id"], friend["name"], "好友", WARNING_GROUP_IDS)
                            if alert_data:
                                draw_alert_card(alert_data)
                                alerted_friends.append(alert_data)
                                
                        friend_status.text("✔️ 好友圈檢查完畢！")
                        draw_summary_dashboard(alerted_friends, len(friends), "好友圈掃描")

                    st.markdown("#### 👁️‍🗨️ [階段三] 目標關注名單 (Followings) 檢查")
                    followings = get_user_followings(target_user_id, limit=social_limit)
                    if not followings:
                        st.info("目標並未追蹤任何人，或隱私設定為不公開。")
                    else:
                        limit_text = "全部" if scan_all_social else f"前 {social_limit} 名"
                        st.write(f"取得 {limit_text} 正在追蹤的對象，共 {len(followings)} 人，開始比對...")
                        following_bar = st.progress(0)
                        following_status = st.empty()
                        alerted_followings = []
                        
                        start_time = time.time()
                        for index, user_followed in enumerate(followings):
                            following_bar.progress((index + 1) / len(followings))
                            
                            elapsed_time = time.time() - start_time
                            avg_time_per_user = elapsed_time / (index + 1)
                            m, s = divmod(int(avg_time_per_user * (len(followings) - (index + 1))), 60)
                            
                            following_status.text(f"檢查中 {index + 1}/{len(followings)}: {user_followed['name']} ⏳ 預估剩餘: {m}分{s}秒")
                            
                            alert_data = fetch_alert_data(user_followed["id"], user_followed["name"], "目標追蹤的對象", WARNING_GROUP_IDS)
                            if alert_data:
                                draw_alert_card(alert_data)
                                alerted_followings.append(alert_data)
                                
                        following_status.text("✔️ 關注名單檢查完畢！")
                        draw_summary_dashboard(alerted_followings, len(followings), "關注對象(Followings)掃描")

                    st.markdown("#### 👀 [階段四] 追蹤者 (Followers) 檢查")
                    followers = get_user_followers(target_user_id, limit=social_limit)
                    if not followers:
                        st.info("目標無公開追蹤者資料。")
                    else:
                        limit_text = "所有" if scan_all_social else f"前 {social_limit} 名"
                        st.write(f"取得 {limit_text} 追蹤者，共 {len(followers)} 人，開始比對...")
                        follower_bar = st.progress(0)
                        follower_status = st.empty()
                        alerted_followers = []
                        
                        start_time = time.time()
                        for index, follower in enumerate(followers):
                            follower_bar.progress((index + 1) / len(followers))
                            
                            elapsed_time = time.time() - start_time
                            avg_time_per_user = elapsed_time / (index + 1)
                            m, s = divmod(int(avg_time_per_user * (len(followers) - (index + 1))), 60)
                            
                            follower_status.text(f"檢查中 {index + 1}/{len(followers)}: {follower['name']} ⏳ 預估剩餘: {m}分{s}秒")
                            
                            alert_data = fetch_alert_data(follower["id"], follower["name"], "粉絲/追蹤者", WARNING_GROUP_IDS)
                            if alert_data:
                                draw_alert_card(alert_data)
                                alerted_followers.append(alert_data)
                                
                        follower_status.text("✔️ 追蹤者檢查完畢！")
                        draw_summary_dashboard(alerted_followers, len(followers), "追蹤者(Followers)掃描")

                    st.balloons() 

    # ================= TAB 2: 特定社群掃描 (進階版) =================
    with tab2:
        st.subheader("針對大型群組進行地毯式排查")
        target_group_id = st.text_input("請輸入目標群組 ID (Group ID)：", placeholder="例如: 1234567", key="input_group")
        
        if st.button("1. 獲取群組結構 (Ranks)", type="secondary"):
            if not target_group_id.isdigit():
                st.warning("⚠️ 群組 ID 格式錯誤！")
            else:
                with st.spinner("正在解析群組階層結構..."):
                    roles = get_group_roles(target_group_id)
                    if not roles:
                        st.error("❌ 獲取失敗，請確認群組是否存在或公開。")
                    else:
                        sorted_roles = sorted(roles, key=lambda x: x.get("rank", 0))
                        st.session_state.group_roles_cache[target_group_id] = sorted_roles
                        st.success("✅ 結構解析成功！請設定排查範圍。")

        if target_group_id in st.session_state.group_roles_cache:
            st.divider()
            st.markdown("#### ⚙️ 第二步：劃定打擊範圍 (Rank 區間)")
            
            roles = st.session_state.group_roles_cache[target_group_id]
            role_options = [f"[Rank: {r['rank']}] {r['name']} (約 {r['memberCount']} 人)" for r in roles]
            
            col1, col2 = st.columns(2)
            with col1:
                start_idx = st.selectbox("起始階層：", range(len(role_options)), format_func=lambda x: role_options[x], index=0)
            with col2:
                end_idx = st.selectbox("結束階層：", range(len(role_options)), format_func=lambda x: role_options[x], index=len(role_options)-1)

            real_start, real_end = min(start_idx, end_idx), max(start_idx, end_idx)
            selected_roles = roles[real_start : real_end + 1]
            
            total_estimated = sum(r.get("memberCount", 0) for r in selected_roles)
            st.info(f"💡 預計排查區間包含 **{len(selected_roles)}** 個階層，約 **{total_estimated}** 名人員。")

            if st.button("2. 執行大範圍掃描", type="primary"):
                if total_estimated == 0:
                    st.warning("⚠️ 該區間內無任何人！")
                else:
                    st.markdown("---")
                    with st.spinner("📦 正在下載人員名單 (若破萬人請耐心等候)..."):
                        members = get_members_of_roles(target_group_id, selected_roles)
                    
                    if not members:
                        st.info("獲取名單失敗。")
                    else:
                        st.write(f"名單下載完成，共計 **{len(members)}** 人。開始執行深度比對...")
                        member_bar = st.progress(0)
                        member_status = st.empty()
                        
                        alerted_members = []
                        start_time = time.time() 
                        
                        for index, member in enumerate(members):
                            member_bar.progress((index + 1) / len(members))
                            
                            elapsed_time = time.time() - start_time
                            avg_time_per_user = elapsed_time / (index + 1)
                            m, s = divmod(int(avg_time_per_user * (len(members) - (index + 1))), 60)
                            
                            member_status.text(f"檢查中 {index + 1}/{len(members)}: {member['name']} (Lv.{member['rank_num']}) ⏳ 預估剩餘: {m}分{s}秒")
                            
                            relation_str = f"群組成員 [Rank: {member['rank_name']}]"
                            
                            # 【核心修改】：在這裡將正在掃描的 target_group_id 傳入函數，啟動 A社群 的同盟追蹤！
                            alert_data = fetch_alert_data(member["id"], member["name"], relation_str, WARNING_GROUP_IDS, int(target_group_id))
                            
                            if alert_data:
                                draw_alert_card(alert_data)
                                alerted_members.append(alert_data)
                                
                        member_status.text("✔️ 區域排查完畢！")
                        draw_summary_dashboard(alerted_members, len(members), "群組深度排查")
                    
                    st.balloons()