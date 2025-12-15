import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

warnings.filterwarnings("ignore")

# 页面配置
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

# ========= 文本字典 =========
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
        "finished": "🎉 您的评分已全部完成！",
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
        "sharpness": ("Sharpness / 视觉清晰度", "Are structure edges clear and details preserved? (1=Bad, 5=Good)"),
        "artifact": ("Artifact / 伪影", "How many stripes, noise, ghosting artifacts? (1=Many, 5=Few)"),
        "naturalness": ("Naturalness / 真实感", "Does it match clinical experience? (1=Unrealistic, 5=Very realistic)"),
        "diagnostic": ("Diagnostic confidence / 可诊断性", "Is it sufficient for clinical judgment? (1=Low, 5=High)"),
        "image_list": "📂 Image List",
        "select_image": "Select Image",
    }
}

T = TEXT[LANG]

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")
if not os.path.exists(IMAGE_ROOT):
    st.error(f"❌ 图像根路径不存在: {IMAGE_ROOT}")
    st.stop()

# ========= 模态选择 =========
modalities = [m for m in sorted(os.listdir(IMAGE_ROOT)) if os.path.isdir(os.path.join(IMAGE_ROOT, m))]
selected_modality = st.selectbox(T["title"], modalities)

# ========= 初始化 SessionState =========
for key in ["user_name", "user_institution", "user_years", "selected_image_idx"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "user" in key else 0

# ========= 用户信息输入 =========
st.markdown(f"### {T['rater_info']}")
col_name, col_inst, col_years = st.columns(3, gap="medium")
with col_name:
    st.caption(T['name'])
    st.session_state.user_name = st.text_input("", value=st.session_state.user_name, placeholder=T["name"], label_visibility="collapsed")
with col_inst:
    st.caption(T['institution'])
    st.session_state.user_institution = st.text_input("", value=st.session_state.user_institution, placeholder=T["institution"], label_visibility="collapsed")
with col_years:
    st.caption(T['years'])
    user_years_input = st.text_input("", value=st.session_state.user_years, placeholder=T["years_placeholder"], label_visibility="collapsed", help=T["years_help"])

user_years = 0.0
if user_years_input.strip() and re.match(r'^-?\d+(\.\d+)?$', user_years_input):
    user_years = round(max(0.0, min(80.0, float(user_years_input))),1)
else:
    if user_years_input.strip():
        st.error(T["years_error"])
st.session_state.user_years = str(user_years)

if not st.session_state.user_name: st.warning(T["name_warn"]); st.stop()
if not st.session_state.user_institution: st.warning(T["inst_warn"]); st.stop()
if user_years <= 0.0: st.warning(T["years_warn"]); st.stop()

# ========= 用户专属 CSV =========
def sanitize_filename(name): return re.sub(r'[\\/:*?"<>|]', '_', name).strip()
SAVE_FILE = os.path.normpath(f"{selected_modality}_{sanitize_filename(st.session_state.user_name)}_ratings.csv")
COLUMNS = ["name","institution","years_of_experience","modality","method","filename","sharpness","artifact","naturalness","diagnostic_confidence"]
if not os.path.exists(SAVE_FILE): pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8")

# ========= 加载图像列表 =========
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)
for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if not os.path.isdir(method_path): continue
    for f in sorted(os.listdir(method_path)):
        if f.lower().endswith((".jpg",".jpeg",".png")):
            image_list.append({"modality": selected_modality,"method":method,"filename":f,"filepath":os.path.join(method_path,f)})

if not image_list:
    st.error(f"❌ 模态 {selected_modality} 下未找到图片！")
    st.stop()

# ========= 已评分集合 =========
if os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8")
    rated_set = set(df_rated["filename"] + "_" + df_rated["method"])
else:
    rated_set = set()

# ========= 左侧图像列表 =========
st.sidebar.subheader(T["image_list"])
labels = []
for idx,img_info in enumerate(image_list):
    uid = f"{img_info['filename']}_{img_info['method']}"
    label = f"图像{idx+1}" if LANG=="中文" else f"Image {idx+1}"
    if uid in rated_set: label += " ✅"
    labels.append(label)

# 确保 session_state 合法
if not isinstance(st.session_state.selected_image_idx,int) or st.session_state.selected_image_idx>=len(labels):
    st.session_state.selected_image_idx=0

selected_label = st.sidebar.radio(
    T["select_image"],
    labels,
    index=st.session_state.selected_image_idx,
    key="selected_image_idx"
)
info = image_list[st.session_state.selected_image_idx]

# ========= 主界面 =========
st.markdown(f"<h2>🧑‍⚕️ {selected_modality} {T['title']}</h2>", unsafe_allow_html=True)
progress_val = len(rated_set)/len(image_list) if image_list else 0
st.progress(progress_val, text=f"{T['progress']}：{len(rated_set)}/{len(image_list)}")

try:
    img = Image.open(info["filepath"]).convert("RGB")
except Exception as e:
    st.error(f"❌ 图片加载失败：{info['filename']} | {e}")

col1,col2 = st.columns([3,4], gap="large")
with col1:
    st.subheader(T["preview"])
    st.image(img, caption=f"{labels[st.session_state.selected_image_idx]} ({info['filename']})", use_container_width=True)
    st.caption(f"{st.session_state.selected_image_idx+1}/{len(image_list)}")

with col2:
    st.subheader(T["score_title"])
    with st.form("rating_form"):
        items = [
            {"key": "sharpness", "name": T['sharpness'][0], "desc": T['sharpness'][1]},
            {"key": "artifact", "name": T['artifact'][0], "desc": T['artifact'][1]},
            {"key": "naturalness", "name": T['naturalness'][0], "desc": T['naturalness'][1]},
            {"key": "diagnostic_confidence", "name": T['diagnostic'][0], "desc": T['diagnostic'][1]},
        ]
        ratings = {}
        for item in items:
            key = f"{item['key']}_{st.session_state.selected_image_idx}"
            st.markdown(f"**{item['name']}**")
            ratings[item['key']] = st.slider(" ",1,5,value=st.session_state.get(key,3), key=key, label_visibility="collapsed")
            st.caption(item['desc'])
            st.markdown("---")

        submitted = st.form_submit_button(T["save_next"])
        if submitted:
            row = {
                "name":st.session_state.user_name,
                "institution":st.session_state.user_institution,
                "years_of_experience":user_years,
                "modality":info["modality"],
                "method":info["method"],
                "filename":info["filename"],
                **ratings
            }
            if os.path.exists(SAVE_FILE): df=pd.read_csv(SAVE_FILE, encoding="utf-8")
            else: df=pd.DataFrame(columns=COLUMNS)

            uid=f"{info['filename']}_{info['method']}"
            existing_uids = (df["filename"]+"_"+df["method"]).values
            if uid in existing_uids:
                idx=df.index[df["filename"]+"_"+df["method"]==uid][0]
                for col in ratings: df.at[idx,col]=ratings[col]
                df.at[idx,"name"]=st.session_state.user_name
                df.at[idx,"institution"]=st.session_state.user_institution
                df.at[idx,"years_of_experience"]=user_years
            else:
                df=pd.concat([df,pd.DataFrame([row])],ignore_index=True)
            df.to_csv(SAVE_FILE,index=False,encoding="utf-8")
            st.toast(T["saved"], icon="✅")

# ========= 数据下载 =========
st.markdown("---")
st.subheader(T["download_title"])
if os.path.exists(SAVE_FILE):
    df=pd.read_csv(SAVE_FILE, encoding="utf-8")
    st.dataframe(df.drop(columns=["method"]), use_container_width=True)
    with open(SAVE_FILE,"rb") as f:
        st.download_button(T["download"], data=f, file_name=os.path.basename(SAVE_FILE), mime="text/csv", use_container_width=True)
else:
    st.info(T["no_data"])
