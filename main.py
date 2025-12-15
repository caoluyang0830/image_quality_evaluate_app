import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ========= set_page_config 必须最先 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

# ========= 语言选择 =========
LANG = st.selectbox("🌐 Language / 语言", ["中文", "English"], index=0)

TEXT = {
    "中文": {
        "title": "图像多指标主观评分系统",
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
        "download_title": "📥 我的评分数据",
        "download": "📤 下载 CSV",
        "no_data": "暂无评分数据",
        "sharpness": ("视觉清晰度 / Sharpness", "结构边缘是否清晰，细节保留情况（1=差，5=好）"),
        "artifact": ("伪影 / Artifact", "条纹、噪声、重影等伪影多少（1=多，5=少）"),
        "naturalness": ("真实感 / Naturalness", "是否符合临床经验（1=不符合，5=非常符合）"),
        "diagnostic": ("可诊断性 / Diagnostic confidence", "是否支持临床判断（1=不足，5=足够）"),
        "image_list": "📂 图像列表",
        "select_image": "选择图像",
    },
    "English": {
        "title": "Multi-Metric Image Subjective Scoring System",
        "rater_info": "🧑‍💻 Rater Information (Required)",
        "name": "Name",
        "institution": "Institution",
        "years": "Years of Experience",
        "years_placeholder": "e.g., 3.2",
        "years_help": "Supports numbers between 0–80",
        "years_error": "❌ Please enter a valid number",
        "name_warn": "⚠️ Please enter your name!",
        "inst_warn": "⚠️ Please enter your institution!",
        "years_warn": "⚠️ Years of experience must be > 0!",
        "progress": "Progress",
        "preview": "Image Preview",
        "score_title": "📊 Scoring Metrics",
        "save_next": "💾 Save Rating",
        "saved": "✅ Saved",
        "download_title": "📥 My Rating Data",
        "download": "📤 Download CSV",
        "no_data": "No rating data yet",
        "sharpness": ("Sharpness", "Are edges clear and details preserved?"),
        "artifact": ("Artifact", "How many artifacts?"),
        "naturalness": ("Naturalness", "Does it match clinical experience?"),
        "diagnostic": ("Diagnostic confidence", "Is it sufficient for diagnosis?"),
        "image_list": "📂 Image List",
        "select_image": "Select Image",
    },
}

T = TEXT[LANG]

# ========= 路径 =========
IMAGE_ROOT = "resultselect"
if not os.path.exists(IMAGE_ROOT):
    st.error(f"❌ 图像根路径不存在: {IMAGE_ROOT}")
    st.stop()

# ========= 模态 =========
modalities = sorted([m for m in os.listdir(IMAGE_ROOT) if os.path.isdir(os.path.join(IMAGE_ROOT, m))])
selected_modality = st.selectbox(T["title"], modalities)

# ========= SessionState =========
for k in ["user_name", "user_institution", "user_years", "selected_image_idx"]:
    if k not in st.session_state:
        st.session_state[k] = "" if "user" in k else 0

# ========= 用户信息 =========
st.markdown(f"### {T['rater_info']}")
c1, c2, c3 = st.columns(3)
with c1:
    st.caption(T["name"])
    st.session_state.user_name = st.text_input("", st.session_state.user_name)
with c2:
    st.caption(T["institution"])
    st.session_state.user_institution = st.text_input("", st.session_state.user_institution)
with c3:
    st.caption(T["years"])
    user_years_input = st.text_input("", st.session_state.user_years, help=T["years_help"])

# ========= 年限校验 =========
if user_years_input.strip() and re.match(r'^\d+(\.\d+)?$', user_years_input):
    user_years = float(user_years_input)
else:
    st.warning(T["years_error"])
    st.stop()

if not st.session_state.user_name:
    st.warning(T["name_warn"]); st.stop()
if not st.session_state.user_institution:
    st.warning(T["inst_warn"]); st.stop()
if user_years <= 0:
    st.warning(T["years_warn"]); st.stop()

# ========= CSV =========
def sanitize(s): return re.sub(r'[\\/:*?"<>|]', "_", s)
SAVE_FILE = f"{selected_modality}_{sanitize(st.session_state.user_name)}.csv"
COLUMNS = ["name","institution","years","modality","method","filename",
           "sharpness","artifact","naturalness","diagnostic_confidence"]
if not os.path.exists(SAVE_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False)

# ========= 图像 =========
image_list = []
for method in sorted(os.listdir(os.path.join(IMAGE_ROOT, selected_modality))):
    mp = os.path.join(IMAGE_ROOT, selected_modality, method)
    if not os.path.isdir(mp): continue
    for f in sorted(os.listdir(mp)):
        if f.lower().endswith((".jpg",".png",".jpeg")):
            image_list.append({"method":method,"filename":f,"path":os.path.join(mp,f)})

df = pd.read_csv(SAVE_FILE)
rated = set(df["filename"] + "_" + df["method"])

# ========= sidebar =========
st.sidebar.subheader(T["image_list"])
labels = []
for i, info in enumerate(image_list):
    tag = f"{info['filename']}_{info['method']}"
    lb = f"{i+1}"
    if tag in rated: lb += " ✅"
    labels.append(lb)

indices = list(range(len(image_list)))
idx = st.sidebar.radio(T["select_image"], indices,
                       index=st.session_state.selected_image_idx,
                       format_func=lambda i: labels[i])
st.session_state.selected_image_idx = idx
info = image_list[idx]

# ========= 主界面 =========
st.progress(len(rated)/len(image_list))
img = Image.open(info["path"]).convert("RGB")

col1, col2 = st.columns([3,4])
with col1:
    st.image(img, use_container_width=True)
with col2:
    with st.form("rate"):
        r = {
            "sharpness": st.slider("Sharpness",1,5,3),
            "artifact": st.slider("Artifact",1,5,3),
            "naturalness": st.slider("Naturalness",1,5,3),
            "diagnostic_confidence": st.slider("Diagnostic",1,5,3),
        }
        if st.form_submit_button(T["save_next"]):
            row = {
                "name":st.session_state.user_name,
                "institution":st.session_state.user_institution,
                "years":user_years,
                "modality":selected_modality,
                "method":info["method"],
                "filename":info["filename"],
                **r
            }
            uid = info["filename"]+"_"+info["method"]
            if uid in rated:
                df.loc[(df["filename"]+"_"+df["method"])==uid, list(r.keys())] = list(r.values())
            else:
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_csv(SAVE_FILE, index=False)
            st.toast(T["saved"], icon="✅")

# ========= 下载 =========
st.markdown("---")
st.subheader(T["download_title"])
st.dataframe(df, use_container_width=True)
st.download_button(T["download"], df.to_csv(index=False), file_name=SAVE_FILE)
