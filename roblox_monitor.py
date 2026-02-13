# 修改後的關鍵函數：自動分頁掃描全部好友
def get_user_friends(user_id, cookie=None):
    friends = []
    cursor = "" # 這是分頁的鑰匙
    
    # 準備 Headers，如果提供 Cookie 則代入
    headers = {}
    if cookie:
        headers["Cookie"] = f".ROBLOSECURITY={cookie}"
    
    while cursor is not None:
        # 加上 cursor 參數，讓 API 知道要從哪裡繼續抓
        url = f"https://friends.roblox.com/v1/users/{user_id}/friends?limit=100"
        if cursor:
            url += f"&cursor={cursor}"
            
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # 將這 100 人加入總名單
                friends.extend([{"id": u["id"], "name": u["name"]} for u in data.get("data", [])])
                
                # 取得下一頁的標記，如果沒有下一頁了，cursor 會變為 None
                cursor = data.get("nextPageCursor")
                
                # 為了避免被鎖 IP，每次換頁稍微停頓
                time.sleep(0.3) 
            elif response.status_code == 429:
                # 觸發頻率限制，休息久一點再重試
                time.sleep(5)
                continue
            else:
                break
        except Exception:
            break
            
    return friends