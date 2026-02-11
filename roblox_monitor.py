import streamlit as st
import requests
import time

# ================= 配置區 =================
# 在這裡填入你想要監控/預警的「黑名單社群 ID」
# 11826423: 延平營區
# 36093699: 羚山營區
WARNING_GROUP_IDS = {11826423, 36093699} 

# 為了避免被 Roblox API 封鎖 (HTTP 429 Too Many Requests)，設定每次請求的延遲秒數
REQUEST_DELAY = 0.5  
# ==========================================

# 網頁基礎設定
st.set_page_config(page_title="Roblox 社群預警比對系統", page_icon="🚨")

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
        pass # 發生錯誤則靜默往下執行

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
            time.sleep(5) # 遇到 429 強制等待 5 秒
            return get_user_groups(user_id)
        else:
            return {}
    except Exception:
        return {}

def get_user_friends(user_id):
    """取得指定玩家的好友名單"""
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [{"id": user["id"], "name": user["name"]} for user in data]
        return []
    except Exception:
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

def check_and_alert(user_id, user_name, relation_type):
    """檢查並回傳預警訊息 (如果有的話)"""
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
st.write("輸入玩家的 Roblox 名稱 (Username) 或數字 ID，系統將自動比對該玩家及其好友、追蹤者是否加入指定的「黑名單社群」。")

user_input = st.text_input("請輸入目標玩家名稱或 User ID：", placeholder="例如: builderman 或 156")

if st.button("開始掃描比對", type="primary"):
    if not user_input:
        st.warning("⚠️ 請先輸入玩家名稱或 ID！")
    else:
        # 用一個區塊來顯示處理狀態
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
                st.subheader("👤 [1] 玩家本人檢查")
                with st.spinner("正在檢查玩家本人的社群..."):
                    alert = check_and_alert(target_user_id, target_user_name, "目標玩家")
                    if alert:
                        st.error(alert)
                    else:
                        st.info("✅ 玩家本人未加入任何預警社群。")

                # --- 2. 檢查好友 ---
                st.subheader("👥 [2] 好友名單檢查")
                friends = get_user_friends(target_user_id)
                if not friends:
                    st.info("該玩家沒有好友，或隱私設定為不公開。")
                else:
                    st.write(f"共找到 {len(friends)} 位好友，開始逐一比對...")
                    friend_bar = st.progress(0)
                    friend_status = st.empty()
                    
                    found_friend_alerts = False
                    for index, friend in enumerate(friends):
                        # 更新進度條與文字
                        progress_pct = (index + 1) / len(friends)
                        friend_bar.progress(progress_pct)
                        friend_status.text(f"正在檢查好友 {index + 1}/{len(friends)}: {friend['name']}")
                        
                        alert = check_and_alert(friend["id"], friend["name"], "好友")
                        if alert:
                            st.error(alert)
                            found_friend_alerts = True
                            
                    friend_status.text("✔️ 好友名單檢查完畢！")
                    if not found_friend_alerts:
                        st.info("✅ 所有好友皆未加入預警社群。")

                # --- 3. 檢查追蹤者 ---
                st.subheader("👀 [3] 追蹤者名單檢查 (前 100 名)")
                followers = get_user_followers(target_user_id, limit=100)
                if not followers:
                    st.info("該玩家沒有追蹤者，或隱私設定為不公開。")
                else:
                    st.write(f"共擷取 {len(followers)} 位追蹤者，開始逐一比對...")
                    follower_bar = st.progress(0)
                    follower_status = st.empty()
                    
                    found_follower_alerts = False
                    for index, follower in enumerate(followers):
                        progress_pct = (index + 1) / len(followers)
                        follower_bar.progress(progress_pct)
                        follower_status.text(f"正在檢查追蹤者 {index + 1}/{len(followers)}: {follower['name']}")
                        
                        alert = check_and_alert(follower["id"], follower["name"], "追蹤者")
                        if alert:
                            st.error(alert)
                            found_follower_alerts = True
                            
                    follower_status.text("✔️ 追蹤者名單檢查完畢！")
                    if not found_follower_alerts:
                        st.info("✅ 前 100 名追蹤者皆未加入預警社群。")

                st.balloons() # 掃描完成撒氣球特效
                st.success("🎉 掃描與交叉比對作業已全部完成！")