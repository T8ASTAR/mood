import streamlit as st
import pandas as pd

# 设置网页标题
st.set_page_config(page_title="发票税点整合系统", layout="wide")
st.title("📑 发票进账管理系统 (毅兴/旭达)")

# 1. 模拟数据库 (在实际应用中会连接数据库，这里使用 Session State 模拟)
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=[
        "所属公司", "开票日期", "项目名称", "税率", "应收总额", "已进账", "剩余未进", "状态"
    ])

# 2. 上传区域
st.sidebar.header("数据导入")
uploaded_files = st.sidebar.file_uploader("上传发票 (图片或PDF)", accept_multiple_files=True)

if uploaded_files:
    # 提示：实际开发时，这里会调用 OCR API (如百度/阿里)
    # 以下为模拟 OCR 识别后的自动填充逻辑
    if st.sidebar.button("开始自动识别"):
        new_record = {
            "所属公司": "毅兴机械", 
            "开票日期": "2026-04-14",
            "项目名称": "象山县海塘安澜项目",
            "税率": "13%",
            "应收总额": 74025.00,
            "已进账": 0.0,
            "剩余未进": 74025.00,
            "状态": "⏳ 待处理"
        }
        st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_record])], ignore_index=True)
        st.success("识别成功！已归类至：毅兴机械")

# 3. 数据展示与交互
st.header("📊 本月发票明细")
if not st.session_state.data.empty:
    # 让用户可以编辑“已进账”这一列
    edited_df = st.data_editor(
        st.session_state.data,
        column_config={
            "已进账": st.column_config.NumberColumn("已进账金额", min_value=0, format="¥%.2f"),
        },
        disabled=["所属公司", "开票日期", "项目名称", "税率", "应收总额", "剩余未进", "状态"],
        num_rows="dynamic"
    )

    # 4. 自动计算结清逻辑
    for index, row in edited_df.iterrows():
        remaining = row["应收总额"] - row["已进账"]
        edited_df.at[index, "剩余未进"] = remaining
        if remaining <= 0:
            edited_df.at[index, "状态"] = "✅ 已结清"
        else:
            edited_df.at[index, "状态"] = f"❌ 欠款: ¥{remaining}"
    
    st.session_state.data = edited_df
    st.dataframe(st.session_state.data, use_container_width=True)

    # 5. 统计汇总
    total_unpaid = st.session_state.data["剩余未进"].sum()
    st.metric(label="总剩余未进账额", value=f"¥ {total_unpaid:,.2f}")
else:
    st.info("暂无数据，请在左侧上传发票。")
