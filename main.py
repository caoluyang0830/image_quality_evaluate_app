import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ================= 基础设置 =================
warnings.filterwarnings("ignore")

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .deploy-status {visibility: hidden;}
    .stTextInput > div > div > input:focus { box-shadow: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========= 语言选择 =========
LANG = st.selectbox("🌐 Language / 语言", ["中文", "English"], index=0)

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
        "save_next": "💾 保存评分",
        "saved": "✅ 已保存",
        "finished": "🎉 您的评分已全部完成！",
        "download_title": "📥 我的评分数据",
        "download": "📤 下载 CSV",
        "no_data": "暂无评分数据",
        "mos": "MOS 1-5 分",
        "sharpness": ("清晰度", "1=差，5=好"),
        "artifact": ("伪影", "1=多，5=少"),
        "naturalness": ("真实感", "1=不符合，5=符合"),
        "diagnostic": ("可诊断性", "1=不足，5=足够"),
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
        "save_next": "💾 Save Rating",
        "saved": "✅ Saved",
        "finished": "🎉 All images have been rated!",
        "download_title": "📥 My Rating Data",
        "download": "📤 Download CSV",
        "no_data": "No rating data yet",
        "mos": "MOS 1–5",
        "sharpness": ("Sharpness", "1=Bad, 5=Good"),
        "artifact": ("Artifacts", "1=Many, 5=Few"),
        "naturalness": ("Naturalness", "1=Unrealistic, 5=Realistic"),
        "diagnostic": ("Diagnostic Confidence", "1=Low, 5=High"),
    },
}

T = TEXT[LANG]

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")
if not os.path.exists(IMAGE_ROOT):
    st.error(f"❌ 图像根路径不存在: {IMAGE_ROOT}")
    st.stop()

# ========= 模态选择 =========
modalities = []
for m in sorted(os.listdir(IMAGE_ROOT)):
    m_path = os.path.join(IMAGE_ROOT, m)
    if not os.path.isdir(m_path):
        continue
    has_images = any(
        f.lower().endswith((".jpg", ".jpeg", ".png"))
        for root, _, files in os.walk(m_path)
        for f in files
    )
    if has_images:
        modalities.append(m)

if not modalities:
    st.error(f"❌ {IMAGE_ROOT} 目录下未找到包含图片的模态文件夹！")
    st.stop()

selected_modality = st.selectbox(T["select_modality"], modalities)

# ========= 初始化 SessionState =========
for key in ["user_name", "user_institution", "user_years", "selected_image_idx"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "user" in key else 0

# ========= 用户信息输入 =========
st.markdown(f"### {T['rater_info']}")
col_name, col_inst, col_years = st.columns(3, gap="medium")
with col_name:
    st.caption(T['name'])
    user_name = st.text_input("", value=st.session_state.user_name, placeholder=T["name"], label_visibility="collapsed")
    st.session_state.user_name = user_name
with col_inst:
    st.caption(T['institution'])
    user_institution = st.text_input("", value=st.session_state.user_institution, placeholder=T["institution"], label_visibility="collapsed")
    st.session_state.user_institution = user_institution
with col_years:
    st.caption(T['years'])
    user_years_input = st.text_input("", value=st.session_state.user_years, placeholder=T["years_placeholder"], label_visibility="collapsed", help=T["years_help"])

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

# ========= 生成用户专属 CSV =========
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()
SAVE_FILE = os.path.normpath(f"{selected_modality}_{sanitize_filename(user_name)}_ratings.csv")

COLUMNS = [
    "name", "institution", "years_of_experience", "modality", "method",
    "filename", "sharpness", "artifact", "naturalness", "diagnostic_confidence"
]

if not os.path.exists(SAVE_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8")

# ========= 加载图像列表 =========
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)
for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if not os.path.isdir(method_path):
        continue
    for f in sorted(os.listdir(method_path)):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            image_list.append({"modality": selected_modality, "method": method, "filename": f, "filepath": os.path.join(method_path, f)})

if not image_list:
    st.error(f"❌ 模态 {selected_modality} 下未找到图片！")
    st.stop()

# ========= 左侧图像列表 =========
st.sidebar.subheader("📂 图像列表")
image_options = [f"图像{i+1}" for i in range(len(image_list))]
selected_image_name = st.sidebar.selectbox("选择图像", image_options, index=st.session_state.selected_image_idx)
st.session_state.selected_image_idx = image_options.index(selected_image_name)
info = image_list[st.session_state.selected_image_idx]

# ========= 主界面 =========
st.markdown(f"<h2>🧑‍⚕️ {selected_modality} {T['title']}</h2>", unsafe_allow_html=True)

# 加载已评分集合，用于进度条
if os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8")
    rated_set = set(df_rated["filename"] + "_" + df_rated["method"])
else:
    rated_set = set()

progress_val = len(rated_set)/len(image_list) if image_list else 0
st.progress(progress_val, text=f"{T['progress']}：{len(rated_set)}/{len(image_list)}")

try:
    img = Image.open(info["filepath"])
    if img.mode == "RGBA":
        img = img.convert("RGB")
except Exception as e:
    st.error(f"❌ 图片加载失败：{info['filename']} | {e}")

col1, col2 = st.columns([3, 4], gap="large")
with col1:
    st.subheader(T["preview"])
    st.image(img, caption=f"{selected_image_name} ({info['filename']})", use_container_width=True)
    st.caption(f"{st.session_state.selected_image_idx + 1}/{len(image_list)}")

with col2:
    st.subheader(T["score_title"])
    metrics = ["sharpness", "artifact", "naturalness", "diagnostic_confidence"]
    ratings = {}
    for metric in metrics:
        key = f"{metric}_{st.session_state.selected_image_idx}"
        ratings[metric] = st.slider(metric, 1, 5, value=st.session_state.get(key, 3), key=key)

    # ===== 保存并覆盖已评分行 =====
    if st.button(T["save_next"], type="primary", use_container_width=True):
        row = {
            "name": user_name,
            "institution": user_institution,
            "years_of_experience": user_years,
            "modality": info["modality"],
            "method": info["method"],
            "filename": info["filename"],
            **ratings
        }

        # 读取 CSV
        if os.path.exists(SAVE_FILE):
            df = pd.read_csv(SAVE_FILE, encoding="utf-8")
        else:
            df = pd.DataFrame(columns=COLUMNS)

        uid = f"{info['filename']}_{info['method']}"
        existing_uids = (df["filename"] + "_" + df["method"]).values

        if uid in existing_uids:
            # 更新原行
            idx = df.index[df["filename"] + "_" + df["method"] == uid][0]
            for col in ratings:
                df.at[idx, col] = ratings[col]
            # 更新用户信息
            df.at[idx, "name"] = user_name
            df.at[idx, "institution"] = user_institution
            df.at[idx, "years_of_experience"] = user_years
        else:
            # 新行追加
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        df.to_csv(SAVE_FILE, index=False, encoding="utf-8")
        st.toast(T["saved"], icon="✅")

        # 跳到下一张
        st.session_state.selected_image_idx = min(st.session_state.selected_image_idx + 1, len(image_list)-1)
        st.rerun()

# ========= 数据下载 =========
st.markdown("---")
st.subheader(T["download_title"])
if os.path.exists(SAVE_FILE):
    df = pd.read_csv(SAVE_FILE, encoding="utf-8")
    st.dataframe(df.drop(columns=["method"]), use_container_width=True)
    with open(SAVE_FILE, "rb") as f:
        st.download_button(T["download"], data=f, file_name=os.path.basename(SAVE_FILE), mime="text/csv", use_container_width=True)
else:
    st.info(T["no_data"])
