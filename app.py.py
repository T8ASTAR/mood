import streamlit as st
import pandas as pd

st.set_page_config(page_title="毅兴&旭达发票整合系统", layout="wide")
st.title("📂 历史数据整合与发票管理系统")

# 初始化数据库
if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame()

# --- 侧边栏：数据导入 ---
st.sidebar.header("📥 数据导入")
import_type = st.sidebar.radio("选择导入方式", ["上传历史 Excel", "上传新发票(图片/PDF)"])

if import_type == "上传历史 Excel":
    uploaded_excel = st.sidebar.file_uploader("选择你之前的 Excel 文件", type=["xlsx"])
    if uploaded_excel and st.sidebar.button("整合 Excel 数据"):
        # 同时读取两个 Sheet
        sheets = pd.read_excel(uploaded_excel, sheet_name=None) # sheet_name=None 会读取所有标签
        all_data = []
        for sheet_name, df in sheets.items():
            if sheet_name in ["旭达", "毅兴"]:
                # 清洗数据：只保留你截图中的核心列，并统一命名
                df = df[['公司名称', '开票时间', '项目名称', '金额', '汇入金额', '余额']].copy()
                df['所属公司'] = sheet_name
                all_data.append(df)
        
        if all_data:
            st.session_state.db = pd.concat(all_data, ignore_index=True)
            st.sidebar.success("Excel 历史记录整合成功！")

elif import_type == "上传新发票(图片/PDF)":
    invoice_file = st.sidebar.file_uploader("上传新发票", type=["png", "jpg", "pdf"])
    if invoice_file and st.sidebar.button("自动识别并入库"):
        # 这里模拟 OCR 识别逻辑
        new_data = {
            "公司名称": "浙江省围海建设集团", # 识别结果
            "开票时间": "2026/4/14",
            "项目名称": "象山县海塘安澜项目",
            "金额": 74025.00,
            "汇入金额": 0.0,
            "余额": 74025.00,
            "所属公司": "毅兴" # 根据识别到的销售方自动判定
        }
        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([new_data])], ignore_index=True)
        st.sidebar.success("新发票已自动录入！")

# --- 主界面：数据管理 ---
st.header("📊 数据总览")

if not st.session_state.db.empty:
    # 筛选器：按公司查看
    company_filter = st.multiselect("查看公司", options=["旭达", "毅兴"], default=["旭达", "毅兴"])
    display_df = st.session_state.db[st.session_state.db['所属公司'].isin(company_filter)]

    # 可编辑表格：直接修改“汇入金额”
    edited_df = st.data_editor(
        display_df,
        column_config={
            "金额": st.column_config.NumberColumn("发票金额", format="¥%.2f"),
            "汇入金额": st.column_config.NumberColumn("汇入金额", format="¥%.2f"),
            "余额": st.column_config.NumberColumn("剩余未进", format="¥%.2f"),
        },
        disabled=["公司名称", "开票时间", "项目名称", "金额", "余额", "所属公司"],
        use_container_width=True
    )

    # 逻辑计算：更新余额与自动结清
    # 当你在网页上修改“汇入金额”时，余额会自动变
    edited_df['余额'] = edited_df['金额'] - edited_df['汇入金额']
    
    # 统计板块
    col1, col2 = st.columns(2)
    with col1:
        st.metric("总待入账金额 (旭达)", f"¥ {edited_df[edited_df['所属公司']=='旭达']['余额'].sum():,.2f}")
    with col2:
        st.metric("总待入账金额 (毅兴)", f"¥ {edited_df[edited_df['所属公司']=='毅兴']['余额'].sum():,.2f}")

    if st.button("保存修改"):
        st.session_state.db.update(edited_df)
        st.success("数据已同步！")
else:
    st.info("请先从左侧导入历史 Excel 表格或上传新发票。")