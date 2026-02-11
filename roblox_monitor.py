import streamlit as st
import requests
import time

# ================= 配置區 =================
# 為了避免被 Roblox API 封鎖 (HTTP 429 Too Many Requests)，設定每次請求的延遲秒數
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定
st.set_page_config(page_title="Roblox 社群預警比對系統", page_icon="🚨", layout="centered")

# ================= 暫存狀態初始化 =================
if 'group_roles_cache' not in st.session_state:
    st.session_state.group_roles_cache = {}
# 新增：快取預警社群的「相關同盟群組」，避免重複消耗 API 請求
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
# ========================================================

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
    """取得指定玩家加入的所有社群 (包含名稱與 Rank 職階)"""
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            # 修改：回傳字典中包含 name (社群名) 與 role (該玩家職階)
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
    """抓取特定社群的同盟(Allies)，作為關聯群組掃描依據"""
    # 若已快取過，直接返回，避免浪費 API 與時間
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
            
    # 將抓完的名單存入快取中
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

def check_and_alert(user_id, user_name, relation_type, warning_group_ids):
    """核心比對邏輯：包含本群組掃描，以及「關聯群組」交叉掃描與 Rank 回傳"""
    user_groups = get_user_groups(user_id) # 回傳 {gid: {"name": 社群名, "role": 職階}}
    time.sleep(REQUEST_DELAY)
    
    # 尋找是否加入了任何「核心預警名單」
    matched_ids = set(user_groups.keys()).intersection(warning_group_ids)
    
    if matched_ids:
        alert_msg = f"🚨 **[預警]** {relation_type} **{user_name}** (ID: {user_id}) 位於監控社群中！\n"
        
        for gid in matched_ids:
            g_info = user_groups[gid]
            # 印出核心預警社群與該玩家在裡面的 Rank
            alert_msg += f"- 🏴 **核心預警社群**: {g_info['name']} (ID: {gid}) | 職階: **{g_info['role']}**\n"
            
            # === 同步搜尋該預警社群的「相關群組 (同盟)」 ===
            allies = get_group_allies(gid)
            if allies:
                # 交叉比對：看該玩家除了預警核心社群外，有沒有「同時」加入該社群的任何相關組織
                matched_allies = set(user_groups.keys()).intersection(set(allies.keys()))
                
                if matched_allies:
                    alert_msg += f"  ↳ ⚠️ **延伸警告**：該人員亦加入了此社群的「相關附屬群組」：\n"
                    for ally_id in matched_allies:
                        ally_info = user_groups[ally_id]
                        # 回傳他所加入的附屬群組名稱與他在裡面的 Rank (可能有多個)
                        alert_msg += f"      ▪️ {ally_info['name']} (ID: {ally_id}) | 職階: **{ally_info['role']}**\n"
            # =======================================================
            
        return alert_msg
    return None

# ================= Streamlit 網頁介面 =================
st.title("🚨 Roblox 社群交叉比對與預警系統")
st.write("透過輸入玩家或社群的資料，自動比對是否與指定的「黑名單社群」有重疊。")

if not WARNING_GROUP_IDS:
    st.error("👈 系統尚未準備就緒：請先在左側邊欄設定至少一個有效的「黑名單社群 ID」！")
else:
    tab1, tab2 = st.tabs(["👤 玩家與關聯掃描", "🛡️ 特定社群進階掃描"])

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
                        st.error(f"❌ 找不到名為或 ID 為「{user_input}」的玩家，請確認輸入是否正確。")
                    else:
                        st.success(f"✅ 成功找到玩家！名稱：**{target_user_name}** (ID: {target_user_id})")
                        st.divider()

                        st.markdown("#### 👤 [1] 玩家本人檢查")
                        with st.spinner("正在檢查玩家本人的社群..."):
                            alert = check_and_alert(target_user_id, target_user_name, "目標玩家", WARNING_GROUP_IDS)
                            if alert:
                                st.error(alert)
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
                                
                                alert = check_and_alert(friend["id"], friend["name"], "好友", WARNING_GROUP_IDS)
                                if alert:
                                    st.error(alert)
                                    alerted_friends.append(friend['name'])
                                    
                            friend_status.text("✔️ 好友名單檢查完畢！")
                            if alerted_friends:
                                st.warning(f"⚠️ **統計**：共 **{len(alerted_friends)}** 位好友在預警名單內！\n\n**名單**：{', '.join(alerted_friends)}")

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
                                
                                alert = check_and_alert(follower["id"], follower["name"], "追蹤者", WARNING_GROUP_IDS)
                                if alert:
                                    st.error(alert)
                                    alerted_followers.append(follower['name'])
                                    
                            follower_status.text("✔️ 追蹤者名單檢查完畢！")
                            if alerted_followers:
                                st.warning(f"⚠️ **統計**：共 **{len(alerted_followers)}** 位追蹤者在預警名單內！\n\n**名單**：{', '.join(alerted_followers)}")

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
                            
                            relation_str = f"特定職階成員 [Rank: {member['rank_name']}]"
                            
                            # 注意：所有複雜的神奇檢查邏輯，都在這個自訂的 check_and_alert 函數裡自動執行了！
                            alert = check_and_alert(member["id"], member["name"], relation_str, WARNING_GROUP_IDS)
                            
                            if alert:
                                st.error(alert)
                                alerted_members.append(f"{member['name']} (職階: {member['rank_name']})")
                                
                        member_status.text("✔️ 特定職階成員掃描完畢！")
                        
                        if not alerted_members:
                            st.info("✅ 掃描的區間成員中，皆未加入任何預警社群。")
                        else:
                            st.warning(f"⚠️ **統計結果**：在這次掃描中，共有 **{len(alerted_members)}** 位成員在預警名單內！\n\n**抓到的名單**：\n" + "\n".join([f"- {m}" for m in alerted_members]))
                    
                    st.balloons()