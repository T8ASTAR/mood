import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

# 1. 页面基本配置
st.set_page_config(page_title="发票对账极简版", layout="wide")

# 自定义极简样式
st.markdown("""
    <style>
    .stMetric { background-color: #fcfcfc; padding: 15px; border-radius: 12px; border: 1px solid #f0f0f0; }
    .new-badge { background-color: #007bff; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 5px; }
    .stExpander { border: none !important; box-shadow: none !important; background-color: #fafafa !important; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# 2. 核心解析引擎
def extract_invoice_info(file):
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            content = page.extract_text()
            if content: full_text += content
        
        try:
            # 提取金额 (价税合计小写)
            amt_match = re.search(r"（小写）¥?\s*([\d\.]+)", full_text)
            amount = float(amt_match.group(1)) if amt_match else 0.0
            
            # 提取日期
            date_match = re.search(r"日期\s*[:：]\s*(\d{4})年(\d{2})月(\d{2})日", full_text)
            inv_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else "未知日期"

            # 提取销方与购方 (根据发票版式，购方在前，销方在后)
            lines = [l.strip() for l in full_text.split('\n') if "名称" in l]
            buyer, seller = "未知购方", "未知销方"
            if len(lines) >= 2:
                buyer = lines[0].split(":")[-1].split("：")[-1].strip()
                seller = lines[1].split(":")[-1].split("：")[-1].strip()

            # 提取项目/工程名称
            project = "未命名项目"
            # 增加对“工程名称”的识别支持
            for kw in ["项目名称", "工程名称", "项目", "工程"]:
                p_match = re.search(f"{kw}[:：]\s*([^\n]+)", full_text)
                if p_match:
                    raw_p = p_match.group(1).strip()
                    # 剔除后面可能跟着的地址信息
                    project = re.split(r"项目地址|项目地点|施工地点|工程地址|地址", raw_p)[0].strip(" :,，：")
                    break

            return {
                "销方": seller, "购方": buyer, "项目": project, 
                "日期": inv_date, "金额": amount, "已收": 0.0, 
                "文件名": file.name, "时间戳": datetime.now()
            }
        except Exception:
            return None

# 3. 数据持久化初始化
if 'db' not in st.session_state:
    st.session_state.db = []
if 'last_upload' not in st.session_state:
    st.session_state.last_upload = []

# 4. 侧边栏：上传与查重
with st.sidebar:
    st.title("📂 档案柜")
    files = st.file_uploader("批量拖入 PDF 发票", type="pdf", accept_multiple_files=True)
    
    if files:
        if st.button("开始同步数据"):
            new_list = []
            duplicates = 0
            for f in files:
                # 查重逻辑：基于文件名
                if any(d['文件名'] == f.name for d in st.session_state.db):
                    duplicates += 1
                else:
                    data = extract_invoice_info(f)
                    if data:
                        st.session_state.db.append(data)
                        new_list.append(f.name)
            
            st.session_state.last_upload = new_list
            if new_list: st.success(f"成功录入 {len(new_list)} 张新发票")
            if duplicates: st.warning(f"跳过 {duplicates} 张重复发票")

    st.divider()
    # 文件夹导航（一级目录）
    if st.session_state.db:
        all_sellers = sorted(list(set(d["销方"] for d in st.session_state.db)))
        current_seller = st.radio("选择管理主体", all_sellers)
    else:
        current_seller = None

# 5. 主界面内容展示
if current_seller:
    st.title(f"🏢 {current_seller}")
    
    # 筛选当前销方下的数据
    seller_data = [d for d in st.session_state.db if d["销方"] == current_seller]
    
    # 按购方分组（二级目录）
    for buyer in sorted(list(set(d["购方"] for d in seller_data))):
        with st.expander(f"🤝 购方：{buyer}", expanded=True):
            invoices = [d for d in seller_data if d["购方"] == buyer]
            
            # 顶部统计指标
            total_amt = sum(i["金额"] for i in invoices)
            total_paid = sum(i["已收"] for i in invoices)
            
            c_m1, c_m2, c_m3 = st.columns(3)
            c_m1.metric("应收总额", f"¥{total_amt:,.2f}")
            c_m2.metric("已收合计", f"¥{total_paid:,.2f}")
            c_m3.metric("待收余款", f"¥{total_amt - total_paid:,.2f}", 
                      delta=-(total_amt - total_paid) if (total_amt - total_paid) > 0 else None)
            
            st.write("")
            
            # 逐行明细（三级目录/项目）
            for inv in invoices:
                # 定位数据在全局列表中的位置
                idx = st.session_state.db.index(inv)
                is_new = inv['文件名'] in st.session_state.last_upload
                
                row_cols = st.columns([3, 2, 2, 1])
                
                with row_cols[0]:
                    new_tag = '<span class="new-badge">NEW</span>' if is_new else ''
                    st.markdown(f"**{inv['项目']}** {new_tag}", unsafe_allow_html=True)
                    st.caption(f"日期: {inv['日期']} | 文件: {inv['文件名']}")
                
                with row_cols[1]:
                    # 录入核销
                    paid_val = st.number_input("实收到账", value=inv["已收"], key=f"pay_{idx}", step=100.0)
                    st.session_state.db[idx]["已收"] = paid_val
                
                balance = inv["金额"] - paid_val
                with row_cols[2]:
                    if balance <= 0:
                        st.markdown("<p style='color:green; font-weight:bold; margin-top:10px;'>✅ 已结清</p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='color:orange; margin-top:10px;'>待收: ¥{balance:,.2f}</p>", unsafe_allow_html=True)
                
                with row_cols[3]:
                    if st.button("🗑️", key=f"del_{idx}"):
                        st.session_state.db.pop(idx)
                        st.rerun()
                st.divider()

else:
    st.info("👋 欢迎！请在左侧批量上传发票 PDF 开始管理。")

# 6. 导出功能
if st.sidebar.button("📤 导出 CSV 报表"):
    if st.session_state.db:
        export_df = pd.DataFrame(st.session_state.db)
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("下载文件", data=csv, file_name="invoice_ledger.csv")
