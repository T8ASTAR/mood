import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

# 页面配置：极简 B 端风格
st.set_page_config(page_title="发票对账管理系统", layout="wide")

# --- 核心解析逻辑 ---
def extract_invoice_info(file):
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text()
        
        try:
            # 1. 提取金额（价税合计小写）
            amount_match = re.search(r"（小写）¥?([\d\.]+)", full_text)
            amount = float(amount_match.group(1)) if amount_match else 0.0
            
            # 2. 提取日期
            date_match = re.search(r"开票日期:(\d{4})年(\d{2})月(\d{2})日", full_text)
            inv_date = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))) if date_match else datetime.now()

            # 3. 提取销方与购方 (通过关键词匹配)
            # 逻辑：通常发票左侧为购买方，右侧为销售方
            names = re.findall(r"名称\s*:\s*([^\n\s]+)", full_text)
            buyer = names[0] if len(names) > 0 else "未知购方"
            seller = names[1] if len(names) > 1 else "未知销方"

            # 4. 提取项目名称 (针对您备注栏的特定格式)
            project = "未命名项目"
            if "项目名称:" in full_text:
                project = full_text.split("项目名称:")[1].split("\n")[0].strip()
            elif "项目名称：" in full_text:
                project = full_text.split("项目名称：")[1].split("\n")[0].strip()

            return {
                "销方": seller,
                "购方": buyer,
                "项目": project,
                "日期": inv_date,
                "金额": amount,
                "已收": 0.0
            }
        except Exception as e:
            st.error(f"解析出错，请检查PDF格式: {e}")
            return None

# --- 数据持久化 (Session State) ---
if 'db' not in st.session_state:
    st.session_state.db = []

# --- 界面布局 ---
st.sidebar.title("🛠️ 管理面板")

# 上传模块
uploaded_pdf = st.sidebar.file_uploader("上传发票 (PDF)", type="pdf")
if uploaded_pdf:
    if st.sidebar.button("确认录入数据"):
        data = extract_invoice_info(uploaded_pdf)
        if data:
            st.session_state.db.append(data)
            st.sidebar.success("已识别并录入！")

# 目录切换
if st.session_state.db:
    sellers = list(set(d["销方"] for d in st.session_state.db))
    current_seller = st.sidebar.radio("选择管理主体（销方）", sellers)
else:
    current_seller = None
    st.info("💡 请先在左侧上传 PDF 发票以开始。")

# --- 主展示区 ---
if current_seller:
    st.title(f"🏢 {current_seller} - 对账台账")
    
    # 过滤数据
    df_all = pd.DataFrame(st.session_state.db)
    df_seller = df_all[df_all["销方"] == current_seller]
    
    # 按购方分组显示
    for buyer in df_seller["购方"].unique():
        with st.expander(f"🤝 客户：{buyer}", expanded=True):
            sub_df = df_seller[df_seller["购方"] == buyer]
            
            # 统计
            total_amt = sub_df["金额"].sum()
            total_paid = sub_df["已收"].sum()
            balance = total_amt - total_paid
            
            m1, m2, m3 = st.columns(3)
            m1.metric("累计金额", f"¥{total_amt:,.2f}")
            m2.metric("已收金额", f"¥{total_paid:,.2f}")
            m3.metric("剩余未收", f"¥{balance:,.2f}", delta=-balance if balance > 0 else "已清", delta_color="inverse")
            
            st.markdown("---")
            
            # 项目详情行
            for idx, row in sub_df.iterrows():
                cols = st.columns([3, 2, 2, 1])
                with cols[0]:
                    st.write(f"**项目：**{row['项目']}")
                    st.caption(f"开票日期: {row['日期'].strftime('%Y-%m-%d')}")
                
                with cols[1]:
                    # 核销输入
                    new_paid = st.number_input(f"实际到账 (总¥{row['金额']:,.2f})", 
                                             value=row["已收"], 
                                             key=f"pay_{idx}")
                    # 同步到内存
                    st.session_state.db[idx]["已收"] = new_paid
                
                row_balance = row["金额"] - new_paid
                with cols[2]:
                    if row_balance <= 0:
                        st.markdown("<h3 style='color:green; margin:0;'>✅ 结清</h3>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"待收: <b style='color:orange;'>¥{row_balance:,.2f}</b>", unsafe_allow_html=True)
                
                with cols[3]:
                    if st.button("删除", key=f"del_{idx}"):
                        st.session_state.db.pop(idx)
                        st.rerun()

# 导出功能
if st.sidebar.button("📥 导出全部台账"):
    if st.session_state.db:
        export_df = pd.DataFrame(st.session_state.db)
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("点击下载 CSV", data=csv, file_name="invoice_summary.csv", mime="text/csv")
