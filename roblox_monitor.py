import streamlit as st
import requests
import time

# ================= 配置區 =================
# 為了避免被 Roblox API 封鎖 (HTTP 429 Too Many Requests)，設定每次請求的延遲秒數
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定
st.set_page_config(page_title="Roblox 社群預警比對系統", page_icon="🚨", layout="centered")

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
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {item["group"]["id"]: item["group"]["name"] for item in data}
        elif response.status_code == 429:
            time.sleep(5) 
            return get_user_groups(user_id)
    except Exception:
        pass
    return {}

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

def get_group_info(group_id):
    url = f"https://groups.roblox.com/v1/groups/{group_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            time.sleep(5)
            return get_group_info(group_id)
    except Exception:
        pass
    return None

# --- 修改：支援抓取 Rank 以及解除人數上限 ---
def get_group_members(group_id, limit=None):
    """
    取得社群成員名單。
    若 limit 為 None，則會不斷翻頁直到抓完社群「所有人」。
    """
    members = []
    cursor = ""
    while cursor is not None:
        # 如果有設定上限，且已經抓夠了，就提早結束
        if limit is not None and len(members) >= limit:
            break
            
        url = f"https://groups.roblox.com/v1/groups/{group_id}/users?sortOrder=Desc&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
            
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    user = item.get("user", {})
                    role = item.get("role", {}) # 取得該玩家在此社群的職階資訊
                    
                    members.append({
                        "id": user.get("userId"), 
                        "name": user.get("username"),
                        "rank_name": role.get("name", "未知職階") # 儲存 Rank Name
                    })
                cursor = data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429:
                time.sleep(5) # 遇到限制強制休息
            else:
                break
        except Exception:
            break
            
    if limit is not None:
        return members[:limit]
    return members
# -----------------------------------------------

def check_and_alert(user_id, user_name, relation_type, warning_group_ids):
    groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    matched_ids = set(groups.keys()).intersection(warning_group_ids)
    
    if matched_ids:
        alert_msg = f"🚨 **[預警]** {relation_type} **{user_name}** (ID: {user_id}) 位於監控社群中！\n"
        for gid in matched_ids:
            alert_msg += f"- 發現社群: {groups[gid]} (ID: {gid})\n"
        return alert_msg
    return None

# ================= Streamlit 網頁介面 =================
st.title("🚨 Roblox 社群交叉比對與預警系統")
st.write("透過輸入玩家或社群的資料，自動比對是否與指定的「黑名單社群」有重疊。")

if not WARNING_GROUP_IDS:
    st.error("👈 系統尚未準備就緒：請先在左側邊欄設定至少一個有效的「黑名單社群 ID」！")
else:
    tab1, tab2 = st.tabs(["👤 玩家與關聯掃描", "🛡️ 特定社群內部掃描"])

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

                        # --- 1. 檢查本人 ---
                        st.markdown("#### 👤 [1] 玩家本人檢查")
                        with st.spinner("正在檢查玩家本人的社群..."):
                            alert = check_and_alert(target_user_id, target_user_name, "目標玩家", WARNING_GROUP_IDS)
                            if alert:
                                st.error(alert)
                            else:
                                st.info("✅ 玩家本人未加入任何預警社群。")

                        # --- 2. 檢查好友 ---
                        st.markdown("#### 👥 [2] 好友名單檢查")
                        friends = get_user_friends(target_user_id)
                        if not friends:
                            st.info("該玩家沒有好友，或隱私設定為不公開。")
                        else:
                            st.write(f"共找到 {len(friends)} 位好友，開始逐一比對...")
                            friend_bar = st.progress(0)
                            friend_status = st.empty()
                            alerted_friends = [] 
                            
                            for index, friend in enumerate(friends):
                                friend_bar.progress((index + 1) / len(friends))
                                friend_status.text(f"正在檢查好友 {index + 1}/{len(friends)}: {friend['name']}")
                                
                                alert = check_and_alert(friend["id"], friend["name"], "好友", WARNING_GROUP_IDS)
                                if alert:
                                    st.error(alert)
                                    alerted_friends.append(friend['name'])
                                    
                            friend_status.text("✔️ 好友名單檢查完畢！")
                            if not alerted_friends:
                                st.info("✅ 所有好友皆未加入預警社群。")
                            else:
                                st.warning(f"⚠️ **統計**：共 **{len(alerted_friends)}** 位好友在預警名單內！\n\n**名單**：{', '.join(alerted_friends)}")

                        # --- 3. 檢查追蹤者 ---
                        st.markdown("#### 👀 [3] 追蹤者名單檢查 (前 100 名)")
                        followers = get_user_followers(target_user_id, limit=100)
                        if not followers:
                            st.info("該玩家沒有追蹤者，或隱私設定為不公開。")
                        else:
                            st.write(f"共擷取 {len(followers)} 位追蹤者，開始逐一比對...")
                            follower_bar = st.progress(0)
                            follower_status = st.empty()
                            alerted_followers = []
                            
                            for index, follower in enumerate(followers):
                                follower_bar.progress((index + 1) / len(followers))
                                follower_status.text(f"正在檢查追蹤者 {index + 1}/{len(followers)}: {follower['name']}")
                                
                                alert = check_and_alert(follower["id"], follower["name"], "追蹤者", WARNING_GROUP_IDS)
                                if alert:
                                    st.error(alert)
                                    alerted_followers.append(follower['name'])
                                    
                            follower_status.text("✔️ 追蹤者名單檢查完畢！")
                            if not alerted_followers:
                                st.info("✅ 前 100 名追蹤者皆未加入預警社群。")
                            else:
                                st.warning(f"⚠️ **統計**：共 **{len(alerted_followers)}** 位追蹤者在預警名單內！\n\n**名單**：{', '.join(alerted_followers)}")

                        st.balloons() 
                        st.success("🎉 玩家掃描作業已全部完成！")

    # ================= TAB 2: 特定社群掃描 =================
    with tab2:
        st.subheader("搜尋特定社群內是否有「預警名單」成員")
        target_group_id = st.text_input("請輸入要掃描的目標社群 ID (Group ID)：", placeholder="例如: 1234567", key="input_group")
        
        # --- 新增：無限掃描模式開關 ---
        st.markdown("#### ⚙️ 掃描範圍設定")
        scan_all = st.checkbox("⚠️ 掃描該社群【所有】成員 (忽略人數上限，破萬人社群將耗時極長)")
        
        if not scan_all:
            scan_limit = st.slider("選擇要掃描的成員數量 (從最新加入的成員開始排查)", min_value=10, max_value=1000, value=50, step=10, key="slider_limit")
        else:
            scan_limit = None # 代表不設限
            st.info("💡 已開啟無限掃描模式：將依序抓取整個社群的名單。請確保網頁保持開啟。")
        # -------------------------------
        
        if st.button("開始掃描社群", type="primary", key="btn_group"):
            if not target_group_id.isdigit():
                st.warning("⚠️ 請輸入有效的純數字社群 ID！")
            else:
                with st.spinner("正在獲取社群資訊..."):
                    group_info = get_group_info(target_group_id)
                    
                if not group_info:
                    st.error("❌ 找不到該社群，請確認 ID 是否正確或該社群是否被封鎖。")
                else:
                    total_members_in_group = group_info.get('memberCount')
                    st.success(f"✅ 成功找到社群：**{group_info.get('name')}** (總人數: {total_members_in_group} 人)")
                    st.divider()
                    
                    with st.spinner("正在擷取社群成員名單，請稍候..."):
                        # 呼叫更新後的函數
                        members = get_group_members(target_group_id, limit=scan_limit)
                    
                    if not members:
                        st.info("該社群目前沒有成員，或權限不足無法讀取。")
                    else:
                        st.write(f"成功擷取到 **{len(members)}** 位成員，開始逐一比對社群交集...")
                        member_bar = st.progress(0)
                        member_status = st.empty()
                        
                        alerted_members = []
                        
                        for index, member in enumerate(members):
                            member_bar.progress((index + 1) / len(members))
                            member_status.text(f"正在檢查成員 {index + 1}/{len(members)}: {member['name']} (職階: {member['rank_name']})")
                            
                            # --- 修改：將 Rank 名稱傳遞給警報訊息 ---
                            relation_str = f"社群成員 [職階: {member['rank_name']}]"
                            alert = check_and_alert(member["id"], member["name"], relation_str, WARNING_GROUP_IDS)
                            
                            if alert:
                                st.error(alert)
                                # 儲存時一併記錄職階
                                alerted_members.append(f"{member['name']} (職階: {member['rank_name']})")
                                
                        member_status.text("✔️ 特定社群成員掃描完畢！")
                        
                        if not alerted_members:
                            st.info("✅ 掃描的成員中，皆未加入任何預警社群。")
                        else:
                            st.warning(f"⚠️ **統計結果**：在這次掃描中，共有 **{len(alerted_members)}** 位成員在預警名單內！\n\n**抓到的名單**：\n" + "\n".join([f"- {m}" for m in alerted_members]))
                    
                    st.balloons()