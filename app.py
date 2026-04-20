import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="财务发票整合系统", layout="wide")
st.title("📂 毅兴/旭达 - 发票进账管理系统")

if 'db' not in st.session_state:
    st.session_state.db = pd.DataFrame()

# --- 侧边栏 ---
st.sidebar.header("📥 数据导入")
import_type = st.sidebar.radio("选择导入方式", ["上传历史 Excel", "上传新发票(图片/PDF)"])

if import_type == "上传历史 Excel":
    uploaded_excel = st.sidebar.file_uploader("选择 Excel 文件", type=["xlsx"])
    if uploaded_excel and st.sidebar.button("开始整合"):
        # 读取所有 Sheet
        sheets = pd.read_excel(uploaded_excel, sheet_name=None, header=None)
        all_data = []
        for sheet_name, df in sheets.items():
            if sheet_name in ["旭达", "毅兴"]:
                # 1. 寻找表头行
                header_idx = -1
                for i, row in df.iterrows():
                    if "公司名称" in row.values:
                        header_idx = i
                        # 找到表头后，清理列名空格
                        df.columns = [str(c).strip() for c in row.values]
                        break
                
                if header_idx != -1:
                    # 2. 截取数据并处理合并单元格
                    data_df = df.iloc[header_idx + 1:].copy()
                    
                    # 关键逻辑：处理公司名称合并单元格（向下填充）
                    data_df['公司名称'] = data_df['公司名称'].replace(r'^\s*$', np.nan, regex=True).ffill()
                    
                    # 3. 强制转换金额列为数字，避免计算报错
                    for col in ['金额', '汇入金额', '余额']:
                        if col in data_df.columns:
                            data_df[col] = pd.to_numeric(data_df[col], errors='coerce').fillna(0)
                    
                    # 4. 优化后的过滤逻辑：
                    # 只要“公司名称”不为空 且 (“金额”不为0 或 “汇入金额”不为0)，就视为有效行
                    # “项目名称”为空也没关系
                    valid_mask = (data_df['公司名称'].notna()) & ((data_df['金额'] != 0) | (data_df['汇入金额'] != 0))
                    data_df = data_df[valid_mask]
                    
                    # 5. 如果“项目名称”确实为空，填充为空字符串避免显示 NaN
                    if '项目名称' in data_df.columns:
                        data_df['项目名称'] = data_df['项目名称'].fillna("")
                    
                    # 只取需要的列
                    target_cols = ['公司名称', '开票时间', '项目名称', '金额', '汇入金额', '余额']
                    existing_cols = [c for c in target_cols if c in data_df.columns]
                    
                    final_df = data_df[existing_cols].copy()
                    final_df['所属销售方'] = sheet_name
                    all_data.append(final_df)
        
        if all_data:
            st.session_state.db = pd.concat(all_data, ignore_index=True)
            st.sidebar.success("Excel 整合成功！已保留无项目名称的有效行。")

elif import_type == "上传新发票(图片/PDF)":
    invoice_file = st.sidebar.file_uploader("上传发票文件", type=["png", "jpg", "pdf"])
    if invoice_file and st.sidebar.button("自动识别并入库"):
        # 模拟识别，项目名称设为空进行测试
        new_data = {
            "公司名称": "识别到的购买方", 
            "开票时间": "2026/04/20", 
            "项目名称": "", # 这里允许为空
            "金额": 10000.0, 
            "汇入金额": 0.0, 
            "余额": 10000.0, 
            "所属销售方": "毅兴"
        }
        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([new_data])], ignore_index=True)
        st.sidebar.success("发票识别已完成")

# --- 主界面 ---
if not st.session_state.db.empty:
    target_folder = st.selectbox("选择管理主体", ["全部", "毅兴", "旭达"])
    view_df = st.session_state.db.copy()
    if target_folder != "全部":
        view_df = view_df[view_df['所属销售方'] == target_folder]

    st.subheader(f"📊 {target_folder} 明细")
    
    # 确保显示前数据类型正确
    view_df['金额'] = pd.to_numeric(view_df['金额'], errors='coerce').fillna(0)
    view_df['汇入金额'] = pd.to_numeric(view_df['汇入金额'], errors='coerce').fillna(0)

    # 渲染编辑表格
    edited_df = st.data_editor(
        view_df,
        column_config={
            "金额": st.column_config.NumberColumn("发票金额", format="¥%.2f"),
            "汇入金额": st.column_config.NumberColumn("已收金额", format="¥%.2f"),
            "余额": st.column_config.NumberColumn("剩余未收", format="¥%.2f"),
            "项目名称": st.column_config.TextColumn("项目名称", help="如果没有项目名称可留空"),
        },
        disabled=["公司名称", "开票时间", "金额", "余额", "所属销售方"],
        use_container_width=True,
        key="data_editor_updated"
    )

    # 动态计算余额
    edited_df['余额'] = edited_df['金额'] - edited_df['汇入金额']
    
    st.divider()
    st.metric("当前页面总欠款", f"¥ {edited_df['余额'].sum():,.2f}")
    
    if st.button("💾 保存当前修改"):
        st.session_state.db.update(edited_df)
        st.success("数据已成功同步到系统！")
else:
    st.info("请先导入数据以开始管理。")
