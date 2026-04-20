import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

# 页面配置
st.set_page_config(page_title="发票管理助手", layout="wide", initial_sidebar_state="expanded")

# --- 增强版解析函数 ---
def parse_invoice_pdf(file):
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                full_text += content
        
        try:
            # 1. 提取金额
            amt_match = re.search(r"（小写）¥?\s*([\d\.]+)", full_text)
            amount = float(amt_match.group(1)) if amt_match else 0.0
            
            # 2. 提取日期
            date_match = re.search(r"日期\s*:\s*(\d{4})年(\d{2})月(\d{2})日", full_text)
            inv_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "未知日期"

            # 3. 提取销方与购方 (改进版：根据纳税人识别号位置定位)
            lines = full_text.split('\n')
            buyer, seller = "未知购方", "未知销方"
            
            # 寻找包含“名称”的行
            name_lines = [l for l in lines if "名称" in l]
            if len(name_lines) >= 2:
                # 第一行通常是购方，第二行通常是销方
                buyer = name_lines[0].split(":")[-1].split("：")[-1].strip()
                seller = name_lines[1].split(":")[-1].split("：")[-1].strip()

            # 4. 提取项目名称 (优先匹配备注栏)
            project = "未命名项目"
            if "项目名称" in full_text:
                # 截取项目名称字样后的内容直到换行
                p_match = re.search(r"项目名称[:：]\s*([^\n]+)", full_text)
                if p_match:
                    project = p_match.group(1).split("项目地址")[0].strip() # 剔除后面可能连带的地址

            return {
                "销方": seller,
                "购方": buyer,
                "项目": project,
                "日期": inv_date,
                "金额": amount,
                "已收": 0.0,
                "文件名": file.name
            }
        except Exception as e:
            return None

# --- 数据管理 ---
if 'invoice_db' not in st.session_state:
    st.session_state.invoice_db = []

# --- 侧边栏：上传与文件夹切换 ---
with st.sidebar:
    st.title("📂 发票归档中心")
    
    # 批量上传
    uploaded_files = st.file_uploader("批量上传发票 (PDF)", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        if st.button("🚀 批量识别并归类"):
            count = 0
            for f in uploaded_files:
                # 检查是否已存在，避免重复录入
                if not any(d.get('文件名') == f.name for d in st.session_state.invoice_db):
                    res = parse_invoice_pdf(f)
                    if res:
                        st.session_state.invoice_db.append(res)
                        count += 1
            st.success(f"成功识别并归类 {count} 张发票！")

    st.divider()
    
    # 文件夹式导航
    if st.session_state.invoice_db:
        all_sellers = sorted(list(set(d["销方"] for d in st.session_state.invoice_db)))
        st.subheader("📁 销方文件夹")
        selected_folder = st.radio("选择查看的主体", all_sellers)
    else:
        selected_folder = None
        st.info("待录入...")

# --- 主界面：文件夹内容展示 ---
if selected_folder:
    st.title(f"📂 销方：{selected_folder}")
    
    # 筛选当前销方的数据
    current_data = [d for d in st.session_state.invoice_db if d["销方"] == selected_folder]
    
    # 按购方进行二级归类
    buyers_in_folder = sorted(list(set(d["购方"] for d in current_data)))
    
    for buyer in buyers_in_folder:
        with st.expander(f"🏢 购方：{buyer}", expanded=True):
            # 找出该销方下、该购方的所有发票
            invoices = [d for d in current_data if d["购方"] == buyer]
            
            # 购方汇总统计
            total_amt = sum(inv["金额"] for inv in invoices)
            total_paid = sum(inv["已收"] for inv in invoices)
            total_bal = total_amt - total_paid
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("累计应收", f"¥{total_amt:,.2f}")
            col_m2.metric("已收合计", f"¥{total_paid:,.2f}")
            col_m3.metric("待收余额", f"¥{total_bal:,.2f}", delta=-total_bal if total_bal > 0 else "已清结")
            
            st.divider()
            
            # 发票明细（项目级）
            for inv in invoices:
                # 在全局数据库中找到这个 inv 的索引，以便修改
                idx = st.session_state.invoice_db.index(inv)
                
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    st.markdown(f"**项目：{inv['项目']}**")
                    st.caption(f"📅 {inv['日期']} | 📄 {inv['文件名']}")
                
                with c2:
                    val = st.number_input(f"录入到账 (总¥{inv['金额']:,.2f})", 
                                          value=inv["已收"], 
                                          key=f"val_{idx}",
                                          step=100.0)
                    st.session_state.invoice_db[idx]["已收"] = val
                
                bal = inv["金额"] - val
                with c3:
                    if bal <= 0:
                        st.markdown("<h3 style='color:#28a745; margin:0;'>✅ 结清</h3>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='color:#ffc107; margin:0;'>待支付：<b>¥{bal:,.2f}</b></p>", unsafe_allow_html=True)
                
                with c4:
                    if st.button("删除", key=f"del_{idx}"):
                        st.session_state.invoice_db.pop(idx)
                        st.rerun()
                st.write("") # 增加行间距

else:
    # 空白状态提示
    st.markdown("""
    ### 👋 欢迎使用极简发票对账系统
    1. 请在左侧上传一份或多份 **PDF 电子发票**。
    2. 点击 **“批量识别并归类”**。
    3. 系统会自动根据销方（如毅兴、旭达）创建文件夹。
    """)
