import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ================= 基础设置 =================
warnings.filterwarnings("ignore")

# ========= 页面配置 =========
st.set_page_config(
    page_title="Image MOS Scoring System",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ========= 隐藏 Streamlit 默认 UI =========
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .deploy-status {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= 语言选择 =========
lang = st.selectbox("🌐 Language / 语言", ["中文", "English"], index=0)
LANG = "zh" if lang == "中文" else "en"

# ========= 多语言文本 =========
TEXT = {
    "zh": {
        "select_modality": "📌 选择评分模态",
        "user_info": "🧑‍💻 评分人信息（必填）",
        "name": "姓名",
        "institution": "医疗机构",
        "years": "从业年限（年）",
        "years_ph": "如 3 或 3.5",
        "system_title": "图像多指标主观评分系统",
        "mos": "采用 MOS 评分（1–5 分）",
        "preview": "图像预览",
        "metrics": "📊 评分指标",
        "save": "💾 保存并下一张",
        "finish": "🎉 所有图像已评分完成！",
        "sharpness": "视觉清晰度",
        "artifact": "伪影",
        "naturalness": "真实感",
        "diagnostic": "可诊断性",
    },
    "en": {
        "select_modality": "📌 Select Modality",
        "user_info": "🧑‍💻 Rater Information (Required)",
        "name": "Name",
        "institution": "Institution",
        "years": "Years of Experience",
        "years_ph": "e.g. 3 or 3.5",
        "system_title": "Multi-metric Image Subjective Scoring System",
        "mos": "MOS rating (1–5)",
        "preview": "Image Preview",
        "metrics": "📊 Rating Metrics",
        "save": "💾 Save & Next",
        "finish": "🎉 All images have been rated!",
        "sharpness": "Sharpness",
        "artifact": "Artifact",
        "naturalness": "Naturalness",
        "diagnostic": "Diagnostic Confidence",
    },
}

def t(key):
    return TEXT[LANG].get(key, key)

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")
if not os.path.exists(IMAGE_ROOT):
    st.error(f"Image root not found: {IMAGE_ROOT}")
    st.stop()

# ========= 模态选择 =========
modalities = [m for m in os.listdir(IMAGE_ROOT) if os.path.isdir(os.path.join(IMAGE_ROOT, m))]
selected_modality = st.selectbox(t("select_modality"), modalities)

# ========= Session =========
for k in ["idx", "user_name", "user_inst", "user_years"]:
    if k not in st.session_state:
        st.session_state[k] = "" if "user" in k else 0

# ========= 用户信息 =========
st.markdown(f"### {t('user_info')}")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"**{t('name')}**")
    st.session_state.user_name = st.text_input("", st.session_state.user_name, placeholder=t("name"), label_visibility="collapsed")

with col2:
    st.markdown(f"**{t('institution')}**")
    st.session_state.user_inst = st.text_input("", st.session_state.user_inst, placeholder=t("institution"), label_visibility="collapsed")

with col3:
    st.markdown(f"**{t('years')}**")
    st.session_state.user_years = st.text_input("", st.session_state.user_years, placeholder=t("years_ph"), label_visibility="collapsed")

# ========= 校验 =========
if not st.session_state.user_name or not st.session_state.user_inst:
    st.stop()

# ========= CSV =========
def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '_', name)

SAVE_FILE = f"{selected_modality}_{safe(st.session_state.user_name)}.csv"

COLUMNS = ["name", "institution", "years", "modality", "method", "filename", "sharpness", "artifact", "naturalness", "diagnostic"]
if not os.path.exists(SAVE_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False)

# ========= 图像列表 =========nimages = []
for method in os.listdir(os.path.join(IMAGE_ROOT, selected_modality)):
    p = os.path.join(IMAGE_ROOT, selected_modality, method)
    if not os.path.isdir(p):
        continue
    for f in os.listdir(p):
        if f.lower().endswith(("png", "jpg", "jpeg")):
            images.append({"method": method, "file": f, "path": os.path.join(p, f)})

# ========= 主界面 =========
st.markdown(f"## 🧑‍⚕️ {selected_modality} {t('system_title')}")
st.caption(t("mos"))

if st.session_state.idx >= len(images):
    st.success(t("finish"))
    st.stop()

img_info = images[st.session_state.idx]
img = Image.open(img_info["path"])

c1, c2 = st.columns([3, 4])
with c1:
    st.subheader(t("preview"))
    st.image(img, use_container_width=True)

with c2:
    st.subheader(t("metrics"))
    ratings = {}
    for k in ["sharpness", "artifact", "naturalness", "diagnostic"]:
        ratings[k] = st.slider(t(k), 1, 5, 3)

    if st.button(t("save"), type="primary"):
        row = {
            "name": st.session_state.user_name,
            "institution": st.session_state.user_inst,
            "years": st.session_state.user_years,
            "modality": selected_modality,
            "method": img_info["method"],
            "filename": img_info["file"],
            **ratings,
        }
        pd.DataFrame([row]).to_csv(SAVE_FILE, mode="a", header=False, index=False)
        st.session_state.idx += 1
        st.rerun()
