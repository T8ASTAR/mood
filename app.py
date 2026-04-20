import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime

# 1. 页面配置与持久化
st.set_page_config(page_title="发票对账管理台账", layout="wide")
DB_FILE = "invoice_ledger_v3.csv"

# 自定义样式
st.markdown("""
    <style>
    .stMetric { background-color: #fcfcfc; padding: 15px; border-radius: 12px; border: 1px solid #f0f0f0; }
    .status-new { background-color: #e3f2fd; color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 2. 数据库逻辑
def load_data():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            # 确保日期格式统一，方便排序
            return df.to_dict('records')
        except: return []
    return []

def save_data(data):
    if data:
        # 保存前进行全局日期排序（降序：最新的在最前面）
        df = pd.DataFrame(data)
        df = df.sort_values(by="日期", ascending=False)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return df.to_dict('records')
    return []

# 3. 增强型解析引擎
def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        # 合并所有页面的文本，并去除多余空格
        text = "".join([p.extract_text() or "" for p in pdf.pages])
        
        try:
            # 提取金额
            amt_m = re.search(r"（小写）¥?\s*([\d\.]+)", text)
            amt = float(amt_m.group(1)) if amt_m else 0.0
            
            # 提取日期 (识别: 2026年02月05日)
            dt_m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", text)
            dt = f"{dt_m.group(1)}-{dt_m.group(2)}-{dt_m.group(3)}" if dt_m else "9999-12-31"
            
            # 增强版：提取购方与销方名称
            # 寻找所有紧跟在“名称：”后的文本
            names = re.findall(r"名称\s*[:：]\s*([^\n\s]+)", text)
            buyer = names[0] if len(names) > 0 else "未知购方"
            seller = names[1] if len(names) > 1 else "未知销方"
            
            # 提取项目名称/工程名称
            project = "未命名项目"
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", text)
                if p_match:
                    raw_p = p_match.group(1).strip()
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址|地址", raw_p)[0].strip(" :,，：")
                    break
            
            return {"销方": seller, "购方": buyer, "项目": project, "日期": dt, "金额": amt, "已收": 0.0, "文件名": file.name}
        except: return None

# 4. 初始化
if 'db' not in st.session_state:
    st.session_state.db = load_data()
if 'new_batch' not in st.session_state:
    st.session_state.new_batch = []

# 5. 侧边栏
with st.sidebar:
    st.title("📂 发票管理中心")
    uploaded_files = st.file_uploader("批量上传 PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files and st.button("🚀 录入并自动排序"):
        batch = []
        dups = 0
        for f in uploaded_files:
            res = parse_pdf(f)
            if res:
                # 局部查重：同销方下不允许同名文件
                is_dup = any(d['文件名'] == res['文件名'] and d['销方'] == res['销方'] for d in st.session_state.db)
                if not is_dup:
                    st.session_state.db.append(res)
                    batch.append(f.name)
                else: dups += 1
        
        st.session_state.new_batch = batch
        # 存入文件时会自动执行日期排序
        st.session_state.db = save_data(st.session_state.db)
        if batch: st.success(f"成功录入 {len(batch)} 张")
        if dups: st.warning(f"跳过 {dups} 张已存在文件")

    if st.session_state.db:
        sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        selected_seller = st.radio("📁 选择销方文件夹", sellers)
    else: selected_seller = None

# 6. 主界面
if selected_seller:
    st.title(f"🏢 {selected_seller}")
    # 筛选并确保当前显示的数据也是按日期排序的
    current_list = [d for d in st.session_state.db if d["销方"] == selected_seller]
    current_list.sort(key=lambda x: x['日期'], reverse=True) # 倒序排列：新票在前
    
    for buyer in sorted(list(set(d["购方"] for d in current_list))):
        with st.expander(f"🤝 客户：{buyer}", expanded=True):
            invoices = [d for d in current_list if d["购方"] == buyer]
            
            # 统计汇总
            t_amt = sum(i["金额"] for i in invoices)
            t_paid = sum(i["已收"] for i in invoices)
            c1, c2, c3 = st.columns(3)
            c1.metric("累计应收", f"¥{t_amt:,.2f}")
            c2.metric("已到账", f"¥{t_paid:,.2f}")
            c3.metric("待收余款", f"¥{t_amt - t_paid:,.2f}")
            
            st.divider()
            for inv in invoices:
                # 获取全局索引
                g_idx = next(i for i, d in enumerate(st.session_state.db) if d['文件名'] == inv['文件名'] and d['销方'] == inv['销方'])
                is_new = inv['文件名'] in st.session_state.new_batch
                
                cols = st.columns([3, 2, 2, 1])
                with cols[0]:
                    tag = '<span class="status-new">NEW</span>' if is_new else ''
                    st.markdown(f"**{inv['项目']}** {tag}", unsafe_allow_html=True)
                    st.caption(f"🗓️ 开票日期: {inv['日期']} | 📄 {inv['文件名']}")
                
                with cols[1]:
                    new_val = st.number_input("录入实收", value=float(inv["已收"]), key=f"v_{g_idx}", step=100.0)
                    if new_val != inv["已收"]:
                        st.session_state.db[g_idx]["已收"] = new_val
                        save_data(st.session_state.db)
                
                bal = inv["金额"] - new_val
                with cols[2]:
                    color = "#28a745" if bal <= 0 else "#f39c12"
                    txt = "✅ 已结清" if bal <= 0 else f"待收: ¥{bal:,.2f}"
                    st.markdown(f"<p style='margin-top:25px; color:{color}; font-weight:bold;'>{txt}</p>", unsafe_allow_html=True)
                
                with cols[3]:
                    st.write(" ")
                    if st.button("🗑️", key=f"del_{g_idx}"):
                        st.session_state.db.pop(g_idx)
                        save_data(st.session_state.db)
                        st.rerun()
