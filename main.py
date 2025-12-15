import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ================= 基础设置 =================
warnings.filterwarnings("ignore")

# ========= 隐藏 Streamlit 默认 UI =========
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .deploy-status {visibility: hidden;}
    .stTextInput > div > div > input:focus { box-shadow: none; }
    .stSelectbox > div > div > select:focus { box-shadow: none; }
    .completed-item { background-color: #f0f9f0; border-left: 3px solid #22c55e; }
    .pending-item { background-color: #f8fafc; border-left: 3px solid #64748b; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========= 语言选择 =========
LANG = st.selectbox("🌐 Language / 语言", ["中文", "English"], index=0)

# ========= 多语言文本 =========
TEXT = {
    "中文": {
        "title": "图像多指标主观评分系统",
        "select_modality": "📌 选择评分模态",
        "rater_info": "🧑‍💻 评分人信息（必填）",
        "name": "姓名",
        "institution": "医疗机构",
        "years": "从业年限（年）",
        "years_placeholder": "如 3.2",
        "years_help": "支持 0-80 之间的整数或小数（如 3.5）",
        "years_error": "❌ 请输入有效的数字（支持小数）",
        "name_warn": "⚠️ 请输入您的姓名！",
        "inst_warn": "⚠️ 请输入您的医疗机构！",
        "years_warn": "⚠️ 请输入有效的从业年限（需大于 0）！",
        "progress": "当前进度",
        "preview": "图像预览",
        "score_title": "📊 评分指标",
        "save": "💾 保存评分",
        "saved": "✅ 评分已保存",
        "updated": "✅ 评分已更新",
        "finished": "🎉 所有图像已完成评分！",
        "download_title": "📥 我的评分数据",
        "download": "📤 下载 CSV",
        "no_data": "暂无评分数据",
        "mos": "MOS 1-5 分",
        "sharpness": ("清晰度", "1=差，5=好"),
        "artifact": ("伪影", "1=多，5=少"),
        "naturalness": ("真实感", "1=不符合，5=符合"),
        "diagnostic": ("可诊断性", "1=不足，5=足够"),
        "select_image": "🖼️ 选择要评分的图像",
        "image_list": "图像列表",
        "method": "方法",
        "status": "状态",
        "completed": "已完成",
        "pending": "待评分",
        "no_images": "暂无可用图像",
        "current_image": "当前评分图像",
        "edit_rating": "📝 修改历史评分",
        "filter": "🔍 筛选",
        "all": "全部",
        "show_completed": "显示已完成",
        "show_pending": "显示待评分"
    },
    "English": {
        "title": "Multi-Metric Image Subjective Scoring System",
        "select_modality": "📌 Select Modality",
        "rater_info": "🧑‍💻 Rater Information (Required)",
        "name": "Name",
        "institution": "Institution",
        "years": "Years of Experience",
        "years_placeholder": "e.g., 3.2",
        "years_help": "Supports numbers between 0–80 (e.g., 3.5)",
        "years_error": "❌ Please enter a valid number",
        "name_warn": "⚠️ Please enter your name!",
        "inst_warn": "⚠️ Please enter your institution!",
        "years_warn": "⚠️ Years of experience must be > 0!",
        "progress": "Progress",
        "preview": "Image Preview",
        "score_title": "📊 Scoring Metrics",
        "save": "💾 Save Rating",
        "saved": "✅ Rating saved",
        "updated": "✅ Rating updated",
        "finished": "🎉 All images have been rated!",
        "download_title": "📥 My Rating Data",
        "download": "📤 Download CSV",
        "no_data": "No rating data yet",
        "mos": "MOS 1–5",
        "sharpness": ("Sharpness", "1=Bad, 5=Good"),
        "artifact": ("Artifacts", "1=Many, 5=Few"),
        "naturalness": ("Naturalness", "1=Unrealistic, 5=Realistic"),
        "diagnostic": ("Diagnostic Confidence", "1=Low, 5=High"),
        "select_image": "🖼️ Select Image to Rate",
        "image_list": "Image List",
        "method": "Method",
        "status": "Status",
        "completed": "Completed",
        "pending": "Pending",
        "no_images": "No images available",
        "current_image": "Current Image",
        "edit_rating": "📝 Edit Previous Rating",
        "filter": "🔍 Filter",
        "all": "All",
        "show_completed": "Show Completed",
        "show_pending": "Show Pending"
    },
}

T = TEXT[LANG]

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")

if not os.path.exists(IMAGE_ROOT):
    st.error(
        f"""
        ❌ 图像根路径不存在: {IMAGE_ROOT}
        请确认：
        1. {IMAGE_ROOT} 文件夹已上传到应用根目录（和 main.py 同目录）
        2. 文件夹名称拼写正确（区分大小写）
        """
    )
    st.stop()

# ========= 模态选择 =========
modalities = []
for m in sorted(os.listdir(IMAGE_ROOT)):
    m_path = os.path.join(IMAGE_ROOT, m)
    if not os.path.isdir(m_path):
        continue
    has_images = False
    for root, _, files in os.walk(m_path):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                has_images = True
                break
        if has_images:
            break
    if has_images:
        modalities.append(m)

if not modalities:
    st.error(f"❌ {IMAGE_ROOT} 目录下未找到包含图片的模态文件夹！")
    st.stop()

selected_modality = st.selectbox(T["select_modality"], modalities)

# ========= 初始化 SessionState =========
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""
if "user_years" not in st.session_state:
    st.session_state.user_years = ""
if "selected_image_id" not in st.session_state:
    st.session_state.selected_image_id = None
if "filter_status" not in st.session_state:
    st.session_state.filter_status = "all"

# ========= 用户信息输入 =========
st.markdown(f"### {T['rater_info']}")
col_name, col_inst, col_years = st.columns(3, gap="medium")

with col_name:
    st.caption(T['name'])  # 小标题
    user_name = st.text_input(
        "",
        value=st.session_state.user_name,
        placeholder=T["name"],
        label_visibility="collapsed",
        key="input_name",
    )
    st.session_state.user_name = user_name

with col_inst:
    st.caption(T['institution'])
    user_institution = st.text_input(
        "",
        value=st.session_state.user_institution,
        placeholder=T["institution"],
        label_visibility="collapsed",
        key="input_institution",
    )
    st.session_state.user_institution = user_institution

with col_years:
    st.caption(T['years'])
    user_years_input = st.text_input(
        "",
        value=st.session_state.user_years,
        placeholder=T["years_placeholder"],
        label_visibility="collapsed",
        key="input_years",
        help=T["years_help"],
    )

# ========= 从业年限校验 =========
user_years = 0.0
if user_years_input.strip():
    if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
        user_years = float(user_years_input)
        user_years = max(0.0, min(80.0, user_years))
        user_years = round(user_years, 1)
    else:
        st.error(T["years_error"])

st.session_state.user_years = str(user_years)

# ========= 生成用户专属 CSV =========
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

if user_name:
    SAVE_FILE = os.path.normpath(
        f"{selected_modality}_{sanitize_filename(user_name)}_ratings.csv"
    )
else:
    SAVE_FILE = ""

# ========= 用户信息校验 =========
if not user_name:
    st.warning(T["name_warn"])
    st.stop()
if not user_institution:
    st.warning(T["inst_warn"])
    st.stop()
if user_years <= 0.0:
    st.warning(T["years_warn"])
    st.stop()

# ========= 初始化 / 修复 CSV =========
COLUMNS = [
    "name",
    "institution",
    "years_of_experience",
    "modality",
    "method",
    "filename",
    "sharpness",
    "artifact",
    "naturalness",
    "diagnostic_confidence",
]

if SAVE_FILE and not os.path.exists(SAVE_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8")
elif SAVE_FILE and os.path.exists(SAVE_FILE):
    df_exist = pd.read_csv(SAVE_FILE, encoding="utf-8")
    for col in COLUMNS:
        if col not in df_exist.columns:
            df_exist[col] = 0.0 if col == "years_of_experience" else ""
    df_exist = df_exist[COLUMNS]
    df_exist.to_csv(SAVE_FILE, index=False, encoding="utf-8")

# ========= 加载图像列表 =========
def load_all_images(modality_path):
    """加载所有图像并生成唯一ID"""
    image_list = []
    for method in sorted(os.listdir(modality_path)):
        method_path = os.path.join(modality_path, method)
        if not os.path.isdir(method_path):
            continue
        for f in sorted(os.listdir(method_path)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                image_id = f"{method}_{f}"  # 唯一标识
                image_list.append(
                    {
                        "id": image_id,
                        "modality": selected_modality,
                        "method": method,
                        "filename": f,
                        "filepath": os.path.normpath(os.path.join(method_path, f)),
                        "status": "pending"  # 默认待评分
                    }
                )
    return image_list

# 加载所有图像
modality_path = os.path.join(IMAGE_ROOT, selected_modality)
all_images = load_all_images(modality_path)

if not all_images:
    st.error(f"❌ 模态 {selected_modality} 下未找到图片！")
    st.stop()

# ========= 加载已评分数据 =========
rated_data = {}  # 存储已评分数据，key: image_id, value: 评分字典
df_rated = pd.DataFrame(columns=COLUMNS)

if SAVE_FILE and os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8").fillna("")
    if not df_rated.empty:
        # 更新图像状态
        for img in all_images:
            mask = (df_rated["method"] == img["method"]) & (df_rated["filename"] == img["filename"])
            if mask.any():
                img["status"] = "completed"
                # 存储评分数据
                rated_row = df_rated[mask].iloc[0]
                rated_data[img["id"]] = {
                    "sharpness": int(rated_row["sharpness"]) if rated_row["sharpness"] != "" else 3,
                    "artifact": int(rated_row["artifact"]) if rated_row["artifact"] != "" else 3,
                    "naturalness": int(rated_row["naturalness"]) if rated_row["naturalness"] != "" else 3,
                    "diagnostic_confidence": int(rated_row["diagnostic_confidence"]) if rated_row["diagnostic_confidence"] != "" else 3,
                }

# ========= 计算进度 =========
total_images = len(all_images)
completed_count = sum(1 for img in all_images if img["status"] == "completed")
progress = completed_count / total_images if total_images > 0 else 0

# ========= 主界面标题 =========
st.markdown(
    f"""
    <h2>🧑‍⚕️ {selected_modality} {T['title']}</h2>
    <p style='color:#666;'>
    {user_name}（{user_institution} | {user_years} yrs） | {T['mos']}
    </p>
    """,
    unsafe_allow_html=True,
)

# 进度条
st.progress(progress, text=f"{T['progress']}：{completed_count}/{total_images}（{progress:.1%}）")

if completed_count == total_images:
    st.success(T["finished"])
    st.balloons()

# ========= 主要内容区 =========
col_sidebar, col_main = st.columns([1, 3], gap="large")

with col_sidebar:
    st.subheader(T["image_list"])
    
    # 筛选器
    filter_option = st.radio(
        T["filter"],
        [T["all"], T["show_pending"], T["show_completed"]],
        index=0,
        key="image_filter"
    )
    
    # 根据筛选条件过滤图像
    filtered_images = []
    if filter_option == T["show_pending"]:
        filtered_images = [img for img in all_images if img["status"] == "pending"]
    elif filter_option == T["show_completed"]:
        filtered_images = [img for img in all_images if img["status"] == "completed"]
    else:
        filtered_images = all_images
    
    # 图像选择下拉框
    if filtered_images:
        # 生成选项：显示状态、方法、文件名
        options = []
        for img in filtered_images:
            status_text = T["completed"] if img["status"] == "completed" else T["pending"]
            status_color = "✅" if img["status"] == "completed" else "⏳"
            option_text = f"{status_color} {img['method']} - {img['filename']}"
            options.append(option_text)
        
        selected_idx = st.selectbox(
            T["select_image"],
            range(len(filtered_images)),
            format_func=lambda i: options[i],
            key="image_selector"
        )
        
        selected_image = filtered_images[selected_idx]
        st.session_state.selected_image_id = selected_image["id"]
    else:
        st.info(T["no_images"])
        selected_image = None

with col_main:
    if selected_image:
        st.subheader(T["current_image"])
        
        # 显示图像信息
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric(T["method"], selected_image["method"])
        with col_info2:
            status_text = T["completed"] if selected_image["status"] == "completed" else T["pending"]
            st.metric(T["status"], status_text)
        with col_info3:
            st.metric("ID", selected_image["id"][:20] + "..." if len(selected_image["id"]) > 20 else selected_image["id"])
        
        st.markdown("---")
        
        # 图像预览和评分区
        col_preview, col_rating = st.columns([2, 2], gap="large")
        
        with col_preview:
            st.subheader(T["preview"])
            try:
                img = Image.open(selected_image["filepath"])
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                st.image(img, caption=selected_image["filename"], use_container_width=True)
            except Exception as e:
                st.error(f"❌ 图片加载失败：{selected_image['filename']} | {e}")
        
        with col_rating:
            st.subheader(T["score_title"])
            
            # 获取已有的评分（如果存在）
            default_ratings = rated_data.get(selected_image["id"], {
                "sharpness": 3,
                "artifact": 3,
                "naturalness": 3,
                "diagnostic_confidence": 3
            })
            
            # 评分滑块
            items = [
                ("sharpness", *T["sharpness"]),
                ("artifact", *T["artifact"]),
                ("naturalness", *T["naturalness"]),
                ("diagnostic_confidence", *T["diagnostic"]),
            ]
            
            ratings = {}
            for k, name, desc in items:
                st.markdown(f"**{name}**")
                ratings[k] = st.slider(
                    " ", 
                    min_value=1, 
                    max_value=5, 
                    value=default_ratings[k],
                    key=f"{k}_{selected_image['id']}", 
                    label_visibility="collapsed"
                )
                st.caption(desc)
                st.markdown("---")
            
            # 保存评分按钮
            if st.button(T["save"], type="primary", use_container_width=True):
                # 准备数据行
                new_row = {
                    "name": user_name,
                    "institution": user_institution,
                    "years_of_experience": user_years,
                    "modality": selected_image["modality"],
                    "method": selected_image["method"],
                    "filename": selected_image["filename"],
                    **ratings,
                }
                
                # 读取现有数据
                df = pd.read_csv(SAVE_FILE, encoding="utf-8")
                
                # 检查是否已存在该图像的评分
                mask = (df["method"] == selected_image["method"]) & (df["filename"] == selected_image["filename"])
                
                if mask.any():
                    # 更新现有评分
                    df.loc[mask, list(ratings.keys())] = pd.Series(ratings)
                    df.loc[mask, ["name", "institution", "years_of_experience"]] = [
                        user_name, user_institution, user_years
                    ]
                    message = T["updated"]
                else:
                    # 添加新评分
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    message = T["saved"]
                
                # 保存到CSV
                df.to_csv(SAVE_FILE, index=False, encoding="utf-8")
                
                # 更新内存中的评分数据
                rated_data[selected_image["id"]] = ratings
                selected_image["status"] = "completed"
                
                # 显示成功消息并刷新
                st.toast(message, icon="✅")
                st.rerun()
    else:
        st.info(T["no_images"])

# ========= 数据下载区 =========
st.markdown("---")
st.subheader(T["download_title"])

if SAVE_FILE and os.path.exists(SAVE_FILE):
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8")
    if not df_download.empty:
        st.dataframe(df_download, use_container_width=True)
        
        # 统计信息
        st.markdown("### 📈 统计摘要")
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric(T["progress"], f"{completed_count}/{total_images}")
        with col_stats2:
            st.metric("平均清晰度", f"{df_download['sharpness'].mean():.2f}")
        with col_stats3:
            st.metric("平均可诊断性", f"{df_download['diagnostic_confidence'].mean():.2f}")
        
        # 下载按钮
        with open(SAVE_FILE, "rb") as f:
            st.download_button(
                T["download"],
                data=f,
                file_name=os.path.basename(SAVE_FILE),
                mime="text/csv",
                use_container_width=True,
            )
    else:
        st.info(T["no_data"])
else:
    st.info(T["no_data"])
