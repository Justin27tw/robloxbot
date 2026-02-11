import requests
import time

# ================= 配置區 =================
# 在這裡填入你想要監控/預警的「黑名單社群 ID」
#11826423延平營區
#36093699 羚山營區
WARNING_GROUP_IDS = {11826423, 36093699} 


# 為了避免被 Roblox API 封鎖 (HTTP 429 Too Many Requests)，設定每次請求的延遲秒數
REQUEST_DELAY = 0.5  
# ==========================================

def get_user_groups(user_id):
    """取得指定玩家加入的所有社群"""
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            # 回傳字典格式：{group_id: group_name}
            return {item["group"]["id"]: item["group"]["name"] for item in data}
        elif response.status_code == 429:
            print(f"  [系統] API 請求過於頻繁，等待 5 秒後重試...")
            time.sleep(5)
            return get_user_groups(user_id)
        else:
            return {}
    except Exception as e:
        print(f"  [錯誤] 無法取得玩家 {user_id} 的社群資料: {e}")
        return {}

def get_user_friends(user_id):
    """取得指定玩家的好友名單 (最多 200 人)"""
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
    """取得指定玩家的追蹤者名單 (支援分頁)"""
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
                time.sleep(REQUEST_DELAY) # 分頁請求延遲
            else:
                break
        except Exception:
            break
            
    return followers[:limit] # 只回傳指定數量上限的追蹤者

def check_and_alert(user_id, user_name, relation_type="玩家本人"):
    """檢查該玩家的社群是否觸發預警"""
    groups = get_user_groups(user_id)
    time.sleep(REQUEST_DELAY) # 每次查完社群後強制延遲
    
    # 取集交集，比對玩家社群 ID 是否在預警名單中
    matched_ids = set(groups.keys()).intersection(WARNING_GROUP_IDS)
    
    if matched_ids:
        print(f"🚨 [預警觸發] {relation_type} '{user_name}' (ID:{user_id}) 位於監控社群中！")
        for gid in matched_ids:
            print(f"   -> 發現社群: {groups[gid]} (ID: {gid})")
        return True
    return False

def main():
    print("=== Roblox 社群交叉比對與預警系統 ===")
    target_user_id = input("請輸入要查詢的目標玩家 User ID: ").strip()
    
    if not target_user_id.isdigit():
        print("請輸入有效的數字 ID！")
        return

    print(f"\n[1] 開始檢查玩家本人 (ID: {target_user_id})...")
    check_and_alert(target_user_id, "目標玩家", "本人")

    print(f"\n[2] 開始獲取並檢查好友名單...")
    friends = get_user_friends(target_user_id)
    print(f"共找到 {len(friends)} 位好友，開始逐一比對...")
    for index, friend in enumerate(friends, 1):
        print(f"  正在檢查好友 {index}/{len(friends)}: {friend['name']}...")
        check_and_alert(friend["id"], friend["name"], "好友")

    # 注意：追蹤者數量可能非常龐大，這裡預設只抓取前 100 名進行示範
    print(f"\n[3] 開始獲取並檢查追蹤者名單 (為避免過載，目前限制檢查前 100 名)...")
    followers = get_user_followers(target_user_id, limit=100)
    print(f"共擷取 {len(followers)} 位追蹤者，開始逐一比對...")
    for index, follower in enumerate(followers, 1):
        print(f"  正在檢查追蹤者 {index}/{len(followers)}: {follower['name']}...")
        check_and_alert(follower["id"], follower["name"], "追蹤者")

    print("\n=== 掃描比對完成 ===")

if __name__ == "__main__":
    main()