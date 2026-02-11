import streamlit as st
import requests
import time
import pandas as pd # 新增：用來製作精美的排版表格

# ================= 配置區 =================
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定 (改為 wide 寬螢幕模式，讓表格更好看)
st.set_page_config(page_title="Roblox 社群預警比對系統", page_icon="🚨", layout="wide")

# ================= 暫存狀態初始化 =================
if 'group_roles_cache' not in st.session_state:
    st.session_state.group_roles_cache = {}
if 'group_allies_cache' not in st.session_state:
    st.session_state.group_allies_cache = {}

# ================= 側邊欄：預警名單設定 =================
st.sidebar.header("⚙️ 預警名單設定")
st.sidebar.write("請輸入要監控的黑名單社群 ID（若有多個請用半形逗號 `,` 分隔）：")
warning_input = st.sidebar.text_area("黑名單社群 IDs", value="11826423, 36093699", height=100)

WARNING_GROUP_IDS = set()
if warning_input:
    for gid in warning_input.split(','):
        gid = gid.strip()
        if gid.isdigit():
            WARNING_GROUP_IDS.add(int(gid))

st.sidebar.divider()
st.sidebar.write(f"目前已載入 **{len(WARNING_GROUP_IDS)}** 個預警社群。")

# === API 抓取功能區 ===

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

def get_user_groups(user_id):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {
                item["group"]["id"]: {
                    "name": item["group"]["name"], 
                    "role": item["role"]["name"]
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

def get_user_followers(user_id, limit=100):
    followers = []
    cursor = ""
    while cursor is not None and len(followers) < limit:
        url = f"https://friends.roblox.com/v1/users/{user_id}/followers?limit=100&cursor={cursor}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                data = json_data.get("data", [])
                followers.extend([{"id": user["id"], "name": user["name"]} for user in data])
                cursor = json_data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            else:
                break
        except Exception:
            break
    return followers[:limit]

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
                                "rank_name": role_name
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

# === UI 排版與資料處理函數 ===

def fetch_alert_data(user_id, user_name, relation_type, warning_group_ids):
    """資料層：檢查並回傳結構化的預警資料字典，不再回傳字串"""
    user_groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    
    matched_ids = set(user_groups.keys()).intersection(warning_group_ids)
    if not matched_ids:
        return None
        
    report = {
        "user_name": user_name,
        "user_id": user_id,
        "relation": relation_type,
        "core_groups": [],
        "ally_groups": []
    }
    
    for gid in matched_ids:
        g_info = user_groups[gid]
        report["core_groups"].append(f"[{gid}] {g_info['name']} (職階: {g_info['role']})")
        
        allies = get_group_allies(gid)
        if allies:
            matched_allies = set(user_groups.keys()).intersection(set(allies.keys()))
            for ally_id in matched_allies:
                ally_info = user_groups[ally_id]
                report["ally_groups"].append(f"[{ally_id}] {ally_info['name']} (職階: {ally_info['role']})")
                
    return report

def draw_alert_card(alert_data):
    """介面層：畫出單筆預警的摺疊面板"""
    with st.expander(f"🚨 [發現目標] {alert_data['relation']} : {alert_data['user_name']} (ID: {alert_data['user_id']})", expanded=False):
        st.markdown("**🏴 核心預警社群：**")
        for g in alert_data["core_groups"]:
            st.markdown(f"- {g}")
            
        if alert_data["ally_groups"]:
            st.markdown("**⚠️ 延伸附屬群組：**")
            for a in alert_data["ally_groups"]:
                st.markdown(f"- {a}")

def draw_summary_table(alerted_list, title="掃描統計結果"):
    """介面層：將收集到的所有預警名單畫成一張精美的 DataFrame 表格"""
    st.error(f"⚠️ **{title}**：本次掃描中，共抓出 **{len(alerted_list)}** 名人員！")
    
    # 將資料轉換為 Pandas 格式以便排版
    df_data = []
    for m in alerted_list:
        df_data.append({
            "身分 / 關聯": m["relation"],
            "Roblox 名稱": m["user_name"],
            "玩家 ID": str(m["user_id"]),
            "加入的預警社群 (核心)": "\n".join(m["core_groups"]),
            "加入的附屬群組 (同盟)": "\n".join(m["ally_groups"]) if m["ally_groups"] else "無"
        })
        
    df = pd.DataFrame(df_data)
    # 使用 streamlit dataframe，設定寬度自動展開
    st.dataframe(df, use_container_width=True)


# ================= Streamlit 網頁介面 =================
st.title("🚨 Roblox 社群深度交叉比對系統")
st.write("透過輸入玩家或社群的資料，自動比對是否與指定的「黑名單社群」及其附屬群組有重疊。")

if not WARNING_GROUP_IDS:
    st.error("👈 系統尚未準備就緒：請先在左側邊欄設定至少一個有效的「黑名單社群 ID」！")
else:
    tab1, tab2 = st.tabs(["👤 單一玩家關聯掃描", "🛡️ 特定社群進階深度掃描"])

    # ================= TAB 1: 玩家掃描 =================
    with tab1:
        st.subheader("針對單一玩家進行關聯性掃描")
        user_input = st.text_input("請輸入目標玩家名稱或 User ID：", placeholder="例如: builderman 或 156", key="input_player")

        if st.button("開始掃描玩家", type="primary", key="btn_player"):
            if not user_input:
                st.warning("⚠️ 請先輸入玩家名稱或 ID！")
            else:
                status_container = st.container()
                with status_container:
                    with st.spinner("正在尋找並驗證玩家資料..."):
                        target_user_id, target_user_name = resolve_user_input(user_input)
                    
                    if not target_user_id:
                        st.error(f"❌ 找不到名為或 ID 為「{user_input}」的玩家。")
                    else:
                        st.success(f"✅ 成功找到玩家！名稱：**{target_user_name}** (ID: {target_user_id})")
                        st.divider()

                        st.markdown("#### 👤 [1] 玩家本人檢查")
                        with st.spinner("正在檢查玩家本人的社群..."):
                            alert_data = fetch_alert_data(target_user_id, target_user_name, "目標玩家", WARNING_GROUP_IDS)
                            if alert_data:
                                draw_alert_card(alert_data)
                                draw_summary_table([alert_data], "本人掃描結果")
                            else:
                                st.info("✅ 玩家本人未加入任何預警社群。")

                        st.markdown("#### 👥 [2] 好友名單檢查")
                        friends = get_user_friends(target_user_id)
                        if not friends:
                            st.info("該玩家沒有好友，或隱私設定為不公開。")
                        else:
                            st.write(f"共找到 {len(friends)} 位好友，開始逐一比對...")
                            friend_bar = st.progress(0)
                            friend_status = st.empty()
                            alerted_friends = [] 
                            
                            start_time = time.time() 
                            for index, friend in enumerate(friends):
                                friend_bar.progress((index + 1) / len(friends))
                                
                                elapsed_time = time.time() - start_time
                                avg_time_per_user = elapsed_time / (index + 1)
                                remaining_users = len(friends) - (index + 1)
                                m, s = divmod(int(avg_time_per_user * remaining_users), 60)
                                
                                friend_status.text(f"正在檢查好友 {index + 1}/{len(friends)}: {friend['name']} ⏳ 預估剩餘: {m}分{s}秒")
                                
                                alert_data = fetch_alert_data(friend["id"], friend["name"], "好友", WARNING_GROUP_IDS)
                                if alert_data:
                                    draw_alert_card(alert_data)
                                    alerted_friends.append(alert_data)
                                    
                            friend_status.text("✔️ 好友名單檢查完畢！")
                            if alerted_friends:
                                draw_summary_table(alerted_friends, "好友名單掃描結果")
                            else:
                                st.info("✅ 所有好友皆未加入預警社群。")

                        st.markdown("#### 👀 [3] 追蹤者名單檢查 (前 100 名)")
                        followers = get_user_followers(target_user_id, limit=100)
                        if not followers:
                            st.info("該玩家沒有追蹤者，或隱私設定為不公開。")
                        else:
                            st.write(f"共擷取 {len(followers)} 位追蹤者，開始逐一比對...")
                            follower_bar = st.progress(0)
                            follower_status = st.empty()
                            alerted_followers = []
                            
                            start_time = time.time()
                            for index, follower in enumerate(followers):
                                follower_bar.progress((index + 1) / len(followers))
                                
                                elapsed_time = time.time() - start_time
                                avg_time_per_user = elapsed_time / (index + 1)
                                remaining_users = len(followers) - (index + 1)
                                m, s = divmod(int(avg_time_per_user * remaining_users), 60)
                                
                                follower_status.text(f"正在檢查追蹤者 {index + 1}/{len(followers)}: {follower['name']} ⏳ 預估剩餘: {m}分{s}秒")
                                
                                alert_data = fetch_alert_data(follower["id"], follower["name"], "追蹤者", WARNING_GROUP_IDS)
                                if alert_data:
                                    draw_alert_card(alert_data)
                                    alerted_followers.append(alert_data)
                                    
                            follower_status.text("✔️ 追蹤者名單檢查完畢！")
                            if alerted_followers:
                                draw_summary_table(alerted_followers, "追蹤者名單掃描結果")
                            else:
                                st.info("✅ 掃描的追蹤者皆未加入預警社群。")

                        st.balloons() 
                        st.success("🎉 玩家掃描作業已全部完成！")

    # ================= TAB 2: 特定社群掃描 (進階版) =================
    with tab2:
        st.subheader("搜尋特定社群內是否有「預警名單」成員")
        target_group_id = st.text_input("請輸入要掃描的目標社群 ID (Group ID)：", placeholder="例如: 1234567", key="input_group")
        
        if st.button("1. 讀取此社群的職階 (Ranks) 名單", type="secondary"):
            if not target_group_id.isdigit():
                st.warning("⚠️ 請輸入有效的純數字社群 ID！")
            else:
                with st.spinner("正在向伺服器請求社群職階資訊..."):
                    roles = get_group_roles(target_group_id)
                    if not roles:
                        st.error("❌ 找不到該社群的職階資訊，請確認 ID 是否正確或該群組是否被關閉。")
                    else:
                        sorted_roles = sorted(roles, key=lambda x: x.get("rank", 0))
                        st.session_state.group_roles_cache[target_group_id] = sorted_roles
                        st.success("✅ 職階讀取成功！請在下方設定你要掃描的範圍。")

        if target_group_id in st.session_state.group_roles_cache:
            st.divider()
            st.markdown("#### ⚙️ 第二步：設定要掃描的 Rank 範圍")
            
            roles = st.session_state.group_roles_cache[target_group_id]
            role_options = [f"[Rank: {r['rank']}] {r['name']} (約 {r['memberCount']} 人)" for r in roles]
            
            col1, col2 = st.columns(2)
            with col1:
                start_idx = st.selectbox("起始職階：", range(len(role_options)), format_func=lambda x: role_options[x], index=0)
            with col2:
                end_idx = st.selectbox("結束職階：", range(len(role_options)), format_func=lambda x: role_options[x], index=len(role_options)-1)

            real_start, real_end = min(start_idx, end_idx), max(start_idx, end_idx)
            selected_roles = roles[real_start : real_end + 1]
            
            total_estimated = sum(r.get("memberCount", 0) for r in selected_roles)
            st.info(f"💡 範圍設定完畢！預計將掃描區間內的 **{len(selected_roles)}** 個職階，總計約 **{total_estimated}** 人。")

            if st.button("2. 開始掃描選定範圍", type="primary"):
                if total_estimated == 0:
                    st.warning("⚠️ 你選擇的職階範圍內目前沒有任何成員！")
                else:
                    st.markdown("---")
                    with st.spinner("📦 正在從 Roblox 伺服器獲取此範圍的完整成員名單 (若人數達千人以上需稍候片刻)..."):
                        members = get_members_of_roles(target_group_id, selected_roles)
                    
                    if not members:
                        st.info("無法獲取到任何成員，可能權限不足。")
                    else:
                        st.write(f"成功擷取到 **{len(members)}** 位成員名單！開始逐一比對交叉資訊...")
                        member_bar = st.progress(0)
                        member_status = st.empty()
                        
                        alerted_members = []
                        start_time = time.time() 
                        
                        for index, member in enumerate(members):
                            member_bar.progress((index + 1) / len(members))
                            
                            elapsed_time = time.time() - start_time
                            avg_time_per_user = elapsed_time / (index + 1)
                            remaining_users = len(members) - (index + 1)
                            m, s = divmod(int(avg_time_per_user * remaining_users), 60)
                            
                            member_status.text(f"正在檢查 {index + 1}/{len(members)}: {member['name']} (職階:{member['rank_name']}) ⏳ 預估剩餘: {m}分{s}秒")
                            
                            relation_str = f"社群成員 [Rank: {member['rank_name']}]"
                            
                            # 獲取結構化的資料
                            alert_data = fetch_alert_data(member["id"], member["name"], relation_str, WARNING_GROUP_IDS)
                            
                            if alert_data:
                                draw_alert_card(alert_data)
                                alerted_members.append(alert_data)
                                
                        member_status.text("✔️ 特定職階成員掃描完畢！")
                        
                        if alerted_members:
                            draw_summary_table(alerted_members, "特定社群深潛掃描結果")
                        else:
                            st.info("✅ 掃描的區間成員中，皆未加入任何預警社群。")
                    
                    st.balloons()