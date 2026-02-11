import streamlit as st
import requests
import time

# ================= 配置區 =================
# 這裡填寫你想要監控/預警的「黑名單社群 ID」
# 11826423: 延平營區
# 36093699: 羚山營區
WARNING_GROUP_IDS = {11826423, 36093699} 

# 為了避免被 Roblox API 封鎖 (HTTP 429 Too Many Requests)，設定每次請求的延遲秒數
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定
st.set_page_config(page_title="Roblox 社群預警比對系統", page_icon="🚨", layout="centered")

# === API 抓取功能區 ===

def resolve_user_input(user_input):
    """智慧解析使用者的輸入 (支援 Username 或 User ID)"""
    user_input = str(user_input).strip()
    
    # 步驟 1：先嘗試將輸入當作「玩家名稱 (Username)」來查詢
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

    # 步驟 2：如果名稱查不到，檢查輸入是不是「純數字 (User ID)」
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
    """取得指定玩家加入的所有社群"""
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
    """取得指定玩家的好友名單"""
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
    """取得指定玩家的追蹤者名單"""
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

# --- 新增：社群專用 API 函數 ---
def get_group_info(group_id):
    """取得特定社群的基本資訊"""
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

def get_recent_group_members(group_id, limit=100):
    """取得社群最新加入的成員名單"""
    members = []
    cursor = ""
    while cursor is not None and len(members) < limit:
        url = f"https://groups.roblox.com/v1/groups/{group_id}/users?sortOrder=Desc&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
            
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    user = item.get("user", {})
                    members.append({"id": user.get("userId"), "name": user.get("username")})
                cursor = data.get("nextPageCursor")
                time.sleep(REQUEST_DELAY)
            elif response.status_code == 429:
                time.sleep(5)
            else:
                break
        except Exception:
            break
    return members[:limit]
# --------------------------------

def check_and_alert(user_id, user_name, relation_type):
    """核心比對邏輯：檢查該玩家的社群並回傳預警訊息"""
    groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY)
    matched_ids = set(groups.keys()).intersection(WARNING_GROUP_IDS)
    
    if matched_ids:
        alert_msg = f"🚨 **[預警]** {relation_type} **{user_name}** (ID: {user_id}) 位於監控社群中！\n"
        for gid in matched_ids:
            alert_msg += f"- 發現社群: {groups[gid]} (ID: {gid})\n"
        return alert_msg
    return None

# ================= Streamlit 網頁介面 =================
st.title("🚨 Roblox 社群交叉比對與預警系統")
st.write("透過輸入玩家或社群的資料，自動比對是否與指定的「黑名單社群」有重疊。")

# 建立兩個標籤頁 (Tabs)
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
                        alert = check_and_alert(target_user_id, target_user_name, "目標玩家")
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
                            
                            alert = check_and_alert(friend["id"], friend["name"], "好友")
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
                            
                            alert = check_and_alert(follower["id"], follower["name"], "追蹤者")
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
    st.write("輸入指定的社群 ID，系統將抓取該社群內的最新成員，並交叉比對他們是否同時加入了預警社群。")
    
    target_group_id = st.text_input("請輸入要掃描的目標社群 ID (Group ID)：", placeholder="例如: 1234567", key="input_group")
    
    # 加入一個滑桿，限制掃描人數，防止 API 呼叫過載
    scan_limit = st.slider("選擇要掃描的成員數量 (從最新加入的成員開始排查)", min_value=10, max_value=200, value=50, step=10, key="slider_limit")
    
    if st.button("開始掃描社群", type="primary", key="btn_group"):
        if not target_group_id.isdigit():
            st.warning("⚠️ 請輸入有效的純數字社群 ID！")
        else:
            with st.spinner("正在獲取社群資訊..."):
                group_info = get_group_info(target_group_id)
                
            if not group_info:
                st.error("❌ 找不到該社群，請確認 ID 是否正確或該社群是否被封鎖。")
            else:
                st.success(f"✅ 成功找到社群：**{group_info.get('name')}** (總人數: {group_info.get('memberCount')} 人)")
                st.divider()
                
                with st.spinner(f"正在獲取最新 {scan_limit} 位成員名單..."):
                    members = get_recent_group_members(target_group_id, limit=scan_limit)
                
                if not members:
                    st.info("該社群目前沒有成員，或權限不足無法讀取。")
                else:
                    st.write(f"共擷取到 {len(members)} 位成員，開始逐一比對社群交集...")
                    member_bar = st.progress(0)
                    member_status = st.empty()
                    
                    alerted_members = []
                    
                    for index, member in enumerate(members):
                        member_bar.progress((index + 1) / len(members))
                        member_status.text(f"正在檢查成員 {index + 1}/{len(members)}: {member['name']}")
                        
                        # 重複利用我們寫好的核心邏輯
                        alert = check_and_alert(member["id"], member["name"], "社群成員")
                        if alert:
                            st.error(alert)
                            alerted_members.append(member['name'])
                            
                    member_status.text("✔️ 特定社群成員掃描完畢！")
                    
                    if not alerted_members:
                        st.info("✅ 掃描的成員中，皆未加入任何預警社群。")
                    else:
                        st.warning(f"⚠️ **統計結果**：在這次掃描中，共有 **{len(alerted_members)}** 位成員在預警名單內！\n\n**抓到的名單**：{', '.join(alerted_members)}")
                
                st.balloons()