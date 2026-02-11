import streamlit as st
import requests
import time
import pandas as pd
import re

# ================= 配置區 =================
REQUEST_DELAY = 0.5  
# ==========================================

st.set_page_config(page_title="Roblox 戰情監控系統 v2.0", page_icon="🛡️", layout="wide")

# ================= 自訂 CSS 升級 =================
st.markdown("""
    <style>
    /* 全域風格 */
    .main { background-color: #0e1117; }
    
    /* 現代化卡片容器 */
    .stMetric { background: #1a1c24; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    
    /* 警報卡片設計 */
    .alert-card {
        background: linear-gradient(145deg, #1e1e26, #16161d);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        border-left: 5px solid #ff4b4b;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    /* 標籤設計 */
    .badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 5px;
    }
    
    .section-header {
        color: #888;
        font-size: 12px;
        letter-spacing: 1px;
        margin-bottom: 10px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }
    
    /* 滾動條美化 */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# ================= 工具函數 (邏輯維持) =================
# [保留您原始的 API 函數：resolve_user_input, get_user_groups 等...]
# [為節省篇幅，此處假設函數已定義]

# === UI 組件：優化後的警報卡片 ===
def draw_enhanced_alert_card(data):
    """
    優化後的資訊排版：
    左側：頭像
    中間：基本資訊與身分標籤
    右側：核心風險與同盟深度分析
    """
    with st.container():
        st.markdown(f"""
        <div class="alert-card">
            <div style="display: flex; gap: 20px; align-items: start;">
                <img src="{data['avatar']}" style="width: 80px; border-radius: 50%; border: 2px solid #ff4b4b;">
                <div style="flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin: 0; color: #fff;">{data['user_name']}</h3>
                        <span style="color: #888; font-family: monospace;">ID: {data['user_id']}</span>
                    </div>
                    <div style="margin-top: 5px;">
                        <span class="badge" style="background: #333; color: #ff4b4b;">來源: {data['relation']}</span>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <div class="section-header">🏴 核心預警社群 (MATCHED)</div>
                        {" ".join([format_badge_html(g, "core") for g in data["core"]])}
                    </div>
                    
                    {f'''
                    <div style="margin-top: 15px;">
                        <div class="section-header">🔗 深度關聯情報 (ALLIES)</div>
                        {" ".join([format_badge_html(a, a["type"]) for a in data["allies"]])}
                    </div>
                    ''' if data["allies"] else ""}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ================= 主介面排版 =================
def main():
    # --- 標題區 ---
    c1, c2 = st.columns([1, 4])
    with c1:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Roblox_player_icon_black.svg/512px-Roblox_player_icon_black.svg.png", width=80)
    with c2:
        st.title("Roblox 深度情報監控中心")
        st.caption("Intelligence & Surveillance Dashboard v2.0")

    # --- 側邊欄優化 ---
    with st.sidebar:
        st.header("⚙️ 監控參數")
        with st.expander("🛡️ 高風險社群名單", expanded=True):
            warning_input = st.text_area("輸入群組 IDs (逗號分隔)", value="11826423, 36093699", height=150)
            WARNING_GROUP_IDS = {int(gid.strip()) for gid in warning_input.split(',') if gid.strip().isdigit()}
        
        st.divider()
        st.metric("當前監控社群", f"{len(WARNING_GROUP_IDS)} 處")
        
        if st.button("🗑️ 清除快取", use_container_width=True):
            st.session_state.group_roles_cache = {}
            st.session_state.group_allies_cache = {}
            st.rerun()

    if not WARNING_GROUP_IDS:
        st.warning("⚠️ 請先於側邊欄設定高風險社群 ID 名單。")
        return

    # --- 主功能區標籤 ---
    tab1, tab2, tab3 = st.tabs(["👤 目標個案追蹤", "🛡️ 群組滲透排查", "📊 統計概覽"])

    with tab1:
        col_l, col_r = st.columns([2, 1])
        with col_l:
            u_in = st.text_input("輸入玩家名稱或 ID", placeholder="Ex: Builderman")
        with col_r:
            scan_mode = st.multiselect("掃描深度", ["好友", "關注中", "粉絲"], default=["好友"])
        
        scan_all = st.checkbox("完整掃描（可能耗時較長）")
        
        if st.button("🎯 啟動深度監控", type="primary", use_container_width=True):
            uid, uname = resolve_user_input(u_in)
            if not uid: 
                st.error("❌ 無法解析目標玩家。")
            else:
                with st.status(f"正在分析 {uname} 的社交網路...", expanded=True) as status:
                    # 本體檢查
                    st.write("正在掃描本體風險...")
                    alert = fetch_alert_data(uid, uname, "監控目標", WARNING_GROUP_IDS)
                    if alert: draw_enhanced_alert_card(alert)
                    
                    # 社交圈檢查
                    for mode_key in scan_mode:
                        m_map = {"好友": "friends", "關注中": "followings", "粉絲": "followers"}
                        st.write(f"正在掃描 {mode_key} 列表...")
                        limit = None if scan_all else 50
                        social = get_user_social(uid, m_map[mode_key], limit)
                        for p in social:
                            alert = fetch_alert_data(p["id"], p["name"], mode_key, WARNING_GROUP_IDS)
                            if alert: draw_enhanced_alert_card(alert)
                    
                    status.update(label="✅ 掃描任務完成", state="complete", expanded=False)

    with tab2:
        st.info("此模組用於針對特定群組的所有成員進行交叉比對。")
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            gid_in = st.text_input("目標群組 ID", key="g_in_v2")
        with g_col2:
            if st.button("📥 抓取群組架構", use_container_width=True):
                # 邏輯維持...
                pass

        # [其餘群組排查 UI 邏輯比照 Tab 1 風格優化]

    with tab3:
        st.empty() # 可放置目前的快取數據統計或掃描歷史紀錄

if __name__ == "__main__":
    main()