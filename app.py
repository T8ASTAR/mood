import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime, timedelta

# 1. 页面基本配置
st.set_page_config(page_title="发票管理中心", layout="wide")
DB_FILE = "invoice_ledger_v5.csv"

if 'font_size' not in st.session_state:
    st.session_state.font_size = 14

st.markdown(f"""
    <style>
    html, body, [class*="st-"] {{ font-size: {st.session_state.font_size}px !important; }}
    .stMetric {{ padding: 5px; border-radius: 5px; border: 1px solid #eee; }}
    .pin-icon {{ color: #ff4b4b; margin-right: 5px; }}
    .search-mode {{ background-color: #fff3e0; padding: 10px; border-radius: 8px; border-left: 5px solid #ff9800; margin-bottom: 20px; }}
    </style>
""", unsafe_allow_html=True)

# 2. 数据库读写
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            if '备注' not in df.columns: df['备注'] = ""
            return df.fillna("").to_dict('records')
        except: return []
    return []

def save_data(data):
    if data:
        df = pd.DataFrame(data)
        df = df.sort_values(by="日期", ascending=False)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return df.to_dict('records')
    return []

# 3. 解析逻辑
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "".join([p.extract_text() or "" for p in pdf.pages])
        try:
            amt_m = re.search(r"（小写）¥?\s*([\d\.]+)", text)
            amt = float(amt_m.group(1)) if amt_m else 0.0
            dt_m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", text)
            dt = f"{dt_m.group(1)}-{dt_m.group(2)}-{dt_m.group(3)}" if dt_m else datetime.now().strftime("%Y-%m-%d")
            
            names = re.findall(r"名称\s*[:：]\s*([^\n\s]+)", text)
            buyer = names[0] if len(names) > 0 else "待输入购方"
            seller = names[1] if len(names) > 1 else "待输入销方"
            
            project = "待输入项目"
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", text)
                if p_match:
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址", p_match.group(1))[0].strip(" :,，：")
                    break
            
            return {"销方": seller, "购方": buyer, "项目": project, "日期": dt, "金额": amt, "已收": 0.0, "文件名": file.name, "备注": ""}
        except: return None

# 4. 初始化
if 'db' not in st.session_state: st.session_state.db = load_data()
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

# 5. 侧边栏
with st.sidebar:
    st.title("📂 发票管理中心")
    
    # --- 新增：全局检索与高级筛选 ---
    st.subheader("🔍 快速检索")
    search_customer = st.text_input("客户名称搜索", placeholder="输入客户关键词，一键直达...")
    
    # 日期区间逻辑
    today = datetime.now().date()
    last_year = today - timedelta(days=365)
    
    # 快捷按钮：点击后更新 session_state 中的默认日期
    if st.button("📅 一键选择近一年"):
        st.session_state.date_filter = (last_year, today)
        
    default_dates = st.session_state.get('date_filter', (last_year, today))
    
    selected_dates = st.date_input(
        "选择开票日期区间", 
        value=default_dates,
        max_value=today + timedelta(days=365) # 允许选到未来一年防错
    )
    # 把用户的选择写回 state，保持状态
    st.session_state.date_filter = selected_dates 
    st.divider()
    # ------------------------------
    
    st.subheader("⚙️ 界面设置")
    col_fs1, col_fs2 = st.columns(2)
    if col_fs1.button("➕ 字体变大"): st.session_state.font_size += 1; st.rerun()
    if col_fs2.button("➖ 字体变小"): st.session_state.font_size = max(10, st.session_state.font_size - 1); st.rerun()
    st.divider()
    
    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if uploaded_files and st.button("🚀 确认录入"):
        new_entries = []
        for f in uploaded_files:
            res = parse_pdf(f)
            if res and not any(d['文件名'] == res['文件名'] for d in st.session_state.db):
                new_entries.append(res)
        if new_entries:
            st.session_state.db.extend(new_entries)
            st.session_state.db = save_data(st.session_state.db)
        st.session_state.uploader_key += 1
        st.rerun()

    # 如果没有搜索客户，才显示常规的销方文件夹
    if not search_customer and st.session_state.db:
        sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        selected_seller = st.radio("📁 销方文件夹", sellers)
    else:
        selected_seller = None

# --- 核心过滤逻辑 ---
filtered_db = st.session_state.db

# 1. 应用日期过滤
if len(selected_dates) == 2:
    start_d, end_d = selected_dates
    start_str = start_d.strftime("%Y-%m-%d")
    end_str = end_d.strftime("%Y-%m-%d")
    filtered_db = [d for d in filtered_db if start_str <= d["日期"] <= end_str]
elif len(selected_dates) == 1:
    start_str = selected_dates[0].strftime("%Y-%m-%d")
    filtered_db = [d for d in filtered_db if d["日期"] >= start_str]

# 2. 应用客户搜索过滤
if search_customer:
    filtered_db = [d for d in filtered_db if search_customer in d["购方"]]

# 6. 主界面渲染
# 模式 A：全局搜索模式
if search_customer:
    st.markdown(f"<div class='search-mode'><h3>🔍 搜索结果：包含 '{search_customer}' 的所有发票</h3></div>", unsafe_allow_html=True)
    
    if not filtered_db:
        st.info("没有找到符合该客户名称及日期区间的记录。")
    else:
        # 在搜索模式下，直接按客户展示，并在内部标明是哪个销方开的票
        for buyer in sorted(list(set(d["购方"] for d in filtered_db))):
            buyer_invoices = [d for d in filtered_db if d["购方"] == buyer]
            has_note = any(inv.get("备注", "") != "" for inv in buyer_invoices)
            pin = "📌 " if has_note else ""
            total_bal = sum(i["金额"] - i["已收"] for i in buyer_invoices)
            
            with st.expander(f"{pin}客户：{buyer} {' (✅ 已结清)' if total_bal <= 0 else ''}", expanded=True):
                # 统计
                t_amt = sum(i["金额"] for i in buyer_invoices)
                t_paid = sum(i["已收"] for i in buyer_invoices)
                c1, c2, c3 = st.columns(3)
                c1.metric("查出总额", f"¥{t_amt:,.2f}")
                c2.metric("已收合计", f"¥{t_paid:,.2f}")
                c3.metric("待收余款", f"¥{total_bal:,.2f}")
                st.divider()
                
                # 明细渲染代码块 (抽离复用)
                for inv in buyer_invoices:
                    try:
                        g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                    except StopIteration: continue

                    col_main, col_side = st.columns([6, 2])
                    with col_main:
                        # 搜索模式下，显示是哪个文件夹（销方）里的票
                        st.caption(f"🏢 所属销方：{inv['销方']}")
                        sub_c1, sub_c2 = st.columns(2)
                        new_proj = sub_c1.text_input("项目名称", value=inv["项目"], key=f"p_s_{g_idx}")
                        new_note = sub_c2.text_input("备注栏", value=inv.get("备注", ""), key=f"n_s_{g_idx}")
                        
                        sub_c3, sub_c4, sub_c5 = st.columns([2, 2, 2])
                        new_date = sub_c3.text_input("日期", value=inv["日期"], key=f"d_s_{g_idx}")
                        new_paid = sub_c4.number_input("实收", value=float(inv["已收"]), key=f"v_s_{g_idx}")
                        new_total = sub_c5.number_input("总额", value=float(inv["金额"]), key=f"t_s_{g_idx}")
                    
                    with col_side:
                        st.write(" ")
                        st.write(" ")
                        st.caption(f"📄 {inv['文件名']}")
                        if st.button("🗑️ 删除", key=f"del_s_{g_idx}"):
                            st.session_state.db.pop(g_idx); save_data(st.session_state.db); st.rerun()

                    if (new_proj != inv["项目"] or new_date != inv["日期"] or new_paid != inv["已收"] or new_total != inv["金额"] or new_note != inv.get("备注", "")):
                        st.session_state.db[g_idx].update({"项目": new_proj, "日期": new_date, "已收": new_paid, "金额": new_total, "备注": new_note})
                        save_data(st.session_state.db)
                        if new_note != inv.get("备注", ""): st.rerun()
                    st.markdown("---")

# 模式 B：常规文件夹模式
elif selected_seller:
    st.title(f"🏢 {selected_seller}")
    current_data = [d for d in filtered_db if d["销方"] == selected_seller]
    
    if not current_data:
        st.info("当前所选日期区间内，该销方没有发票记录。")
        
    for buyer in sorted(list(set(d["购方"] for d in current_data))):
        buyer_invoices = [d for d in current_data if d["购方"] == buyer]
        has_note = any(inv.get("备注", "") != "" for inv in buyer_invoices)
        pin = "📌 " if has_note else ""
        total_bal = sum(i["金额"] - i["已收"] for i in buyer_invoices)
        
        with st.expander(f"{pin}客户：{buyer} {' (✅ 已结清)' if total_bal <= 0 else ''}", expanded=total_bal > 0):
            t_amt = sum(i["金额"] for i in buyer_invoices)
            t_paid = sum(i["已收"] for i in buyer_invoices)
            c1, c2, c3 = st.columns(3)
            c1.metric("累计应收", f"¥{t_amt:,.2f}")
            c2.metric("已收", f"¥{t_paid:,.2f}")
            c3.metric("待收", f"¥{total_bal:,.2f}")
            st.divider()
            
            for inv in buyer_invoices:
                try:
                    g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                except StopIteration: continue

                col_main, col_side = st.columns([6, 2])
                with col_main:
                    sub_c1, sub_c2 = st.columns(2)
                    new_proj = sub_c1.text_input("项目名称", value=inv["项目"], key=f"p_{g_idx}")
                    new_note = sub_c2.text_input("备注栏", value=inv.get("备注", ""), key=f"n_{g_idx}")
                    
                    sub_c3, sub_c4, sub_c5 = st.columns([2, 2, 2])
                    new_date = sub_c3.text_input("日期", value=inv["日期"], key=f"d_{g_idx}")
                    new_paid = sub_c4.number_input("实收", value=float(inv["已收"]), key=f"v_{g_idx}")
                    new_total = sub_c5.number_input("总额", value=float(inv["金额"]), key=f"t_{g_idx}")
                
                with col_side:
                    st.write(" ")
                    st.caption(f"📄 {inv['文件名']}")
                    if st.button("🗑️ 删除", key=f"del_{g_idx}"):
                        st.session_state.db.pop(g_idx); save_data(st.session_state.db); st.rerun()

                if (new_proj != inv["项目"] or new_date != inv["日期"] or new_paid != inv["已收"] or new_total != inv["金额"] or new_note != inv.get("备注", "")):
                    st.session_state.db[g_idx].update({"项目": new_proj, "日期": new_date, "已收": new_paid, "金额": new_total, "备注": new_note})
                    save_data(st.session_state.db)
                    if new_note != inv.get("备注", ""): st.rerun()
                st.markdown("---")
else:
    st.info("👈 请在左侧上传发票或使用检索功能。")
