import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ================= 基础设置 =================
# 忽略无关警告（部署时更清爽）
warnings.filterwarnings("ignore")

# ========= 隐藏 Streamlit 默认 UI =========
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

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")

# ========= 检查图像根目录 =========
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

selected_modality = st.selectbox("📌 选择评分模态", modalities)

# ========= 初始化 SessionState =========
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""
if "user_years" not in st.session_state:
    st.session_state.user_years = ""

# ========= 用户信息输入 =========
st.markdown("### 🧑‍💻 评分人信息（必填）")
col_name, col_inst, col_years = st.columns(3, gap="medium")

with col_name:
    user_name = st.text_input(
        "姓名",
        value=st.session_state.user_name,
        placeholder="请输入您的姓名",
        label_visibility="collapsed",
        key="input_name",
    )
    st.session_state.user_name = user_name

with col_inst:
    user_institution = st.text_input(
        "医疗机构",
        value=st.session_state.user_institution,
        placeholder="请输入您的医疗机构",
        label_visibility="collapsed",
        key="input_institution",
    )
    st.session_state.user_institution = user_institution

with col_years:
    user_years_input = st.text_input(
        "从业年限",
        value=st.session_state.user_years,
        placeholder="请输入数字（0-80，支持小数）",
        label_visibility="collapsed",
        key="input_years",
        help="支持 0-80 之间的整数或小数（如 3.5）",
    )

# ========= 从业年限校验 =========
user_years = 0.0
if user_years_input.strip():
    if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
        user_years = float(user_years_input)
        user_years = max(0.0, min(80.0, user_years))
        user_years = round(user_years, 1)
    else:
        st.error("❌ 请输入有效的数字（支持小数）")

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
    st.warning("⚠️ 请输入您的姓名！")
    st.stop()
if not user_institution:
    st.warning("⚠️ 请输入您的医疗机构！")
    st.stop()
if user_years <= 0.0:
    st.warning("⚠️ 请输入有效的从业年限（需大于 0）！")
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
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)

for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if not os.path.isdir(method_path):
        continue
    for f in sorted(os.listdir(method_path)):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            image_list.append(
                {
                    "modality": selected_modality,
                    "method": method,
                    "filename": f,
                    "filepath": os.path.normpath(os.path.join(method_path, f)),
                }
            )

if not image_list:
    st.error(f"❌ 模态 {selected_modality} 下未找到图片！")
    st.stop()

# ========= 跳过已评分 =========
rated_set = set()
if SAVE_FILE and os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8").fillna("")
    if not df_rated.empty:
        rated_set = set(df_rated["filename"] + "_" + df_rated["method"])

while st.session_state.idx < len(image_list):
    info = image_list[st.session_state.idx]
    if f"{info['filename']}_{info['method']}" in rated_set:
        st.session_state.idx += 1
    else:
        break

# ========= 主界面 =========
st.markdown(
    f"""
    <h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>
    <p style='color:#666;'>
    {user_name}（{user_institution} | 从业 {user_years} 年） | MOS 1-5 分
    </p>
    """,
    unsafe_allow_html=True,
)

total = len(image_list)
completed = len(rated_set)
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前进度：{completed}/{total}（{progress:.1%}）")

# ========= 评分流程 =========
if st.session_state.idx >= len(image_list):
    st.success(f"🎉 {user_name}，您的评分已全部完成！")
    st.balloons()
else:
    info = image_list[st.session_state.idx]
    try:
        img = Image.open(info["filepath"])
        if img.mode == "RGBA":
            img = img.convert("RGB")
    except Exception as e:
        st.error(f"❌ 图片加载失败：{info['filename']} | {e}")
        st.session_state.idx += 1
        st.rerun()

    col1, col2 = st.columns([3, 4], gap="large")
    with col1:
        st.subheader("图像预览")
        st.image(img, caption=info["filename"], use_container_width=True)
        st.caption(f"第 {st.session_state.idx + 1}/{total} 张")

    with col2:
        st.subheader("📊 评分指标")
        items = [
            ("sharpness", "清晰度", "1=差，5=好"),
            ("artifact", "伪影", "1=多，5=少"),
            ("naturalness", "真实感", "1=不符合，5=符合"),
            ("diagnostic_confidence", "可诊断性", "1=不足，5=足够"),
        ]
        ratings = {}
        for k, name, desc in items:
            st.markdown(f"**{name}**")
            ratings[k] = st.slider(
                " ", 1, 5, 3, key=f"{k}_{st.session_state.idx}", label_visibility="collapsed"
            )
            st.caption(desc)
            st.markdown("---")

        if st.button("💾 保存并下一张", type="primary", use_container_width=True):
            row = {
                "name": user_name,
                "institution": user_institution,
                "years_of_experience": user_years,
                "modality": info["modality"],
                "method": info["method"],
                "filename": info["filename"],
                **ratings,
            }
            pd.DataFrame([row]).to_csv(
                SAVE_FILE, mode="a", header=False, index=False, encoding="utf-8"
            )
            st.session_state.idx += 1
            st.toast("✅ 已保存", icon="✅")
            st.rerun()

# ========= 数据下载 =========
st.markdown("---")
st.subheader("📥 我的评分数据")
if SAVE_FILE and os.path.exists(SAVE_FILE):
    df = pd.read_csv(SAVE_FILE, encoding="utf-8")
    st.dataframe(df.drop(columns=["method"]), use_container_width=True)
    with open(SAVE_FILE, "rb") as f:
        st.download_button(
            "📤 下载 CSV",
            data=f,
            file_name=os.path.basename(SAVE_FILE),
            mime="text/csv",
            use_container_width=True,
        )
else:
    st.info("暂无评分数据")
