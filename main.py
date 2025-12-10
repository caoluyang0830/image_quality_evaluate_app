import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re
from datetime import datetime
import uuid
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from io import StringIO

# 忽略无关警告
warnings.filterwarnings("ignore")

# ========= 隐藏 Streamlit 默认 UI =========
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.deploy-status {visibility: hidden;}
.stTextInput > div > div > input:focus {
    box-shadow: none;
}
</style>
""", unsafe_allow_html=True)

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ========= 配置 ==========
GOOGLE_DRIVE_FOLDER_ID = "1_7HhWjfEK65YfsjOWR-kNrN0ogJCr2Zq"
IMAGE_ROOT = "resultselect"
IMAGE_ROOT = os.path.normpath(IMAGE_ROOT)

# ========= 初始化 Google Drive 客户端（OAuth） =========
@st.cache_resource(show_spinner=False)
def init_google_drive():
    """初始化 Google Drive 客户端（OAuth）"""
    try:
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()  # 弹出浏览器授权 Google 账户
        drive = GoogleDrive(gauth)
        return drive
    except Exception as e:
        st.error(f"❌ 谷歌云盘连接失败：{str(e)}")
        st.stop()

drive = init_google_drive()

# ========= 检查图像根目录 =========
if not os.path.exists(IMAGE_ROOT):
    st.error(f"❌ 图像根路径不存在: `{IMAGE_ROOT}`")
    st.stop()

# ========= 模态选择 =========
modalities = []
for m in sorted(os.listdir(IMAGE_ROOT)):
    m_path = os.path.join(IMAGE_ROOT, m)
    if os.path.isdir(m_path):
        has_images = any(
            f.lower().endswith((".jpg", ".jpeg", ".png")) 
            for root, _, files in os.walk(m_path) 
            for f in files
        )
        if has_images:
            modalities.append(m)

if not modalities:
    st.error(f"❌ `{IMAGE_ROOT}` 目录下未找到包含图片的模态文件夹！")
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
if "submission_id" not in st.session_state:
    st.session_state.submission_id = str(uuid.uuid4())

# ========= 用户信息输入 =========
st.markdown("### 🧑‍💻 评分人信息（必填）")
col_name, col_institution, col_years = st.columns(3, gap="medium")
with col_name:
    user_name = st.text_input("姓名", value=st.session_state.user_name, placeholder="请输入您的姓名", label_visibility="collapsed")
    st.session_state.user_name = user_name

with col_institution:
    user_institution = st.text_input("医疗机构", value=st.session_state.user_institution, placeholder="请输入您的医疗机构", label_visibility="collapsed")
    st.session_state.user_institution = user_institution

with col_years:
    user_years_input = st.text_input("从业年限", value=st.session_state.user_years, placeholder="请输入数字（0-80，支持小数）", label_visibility="collapsed")
    user_years = 0.0
    if user_years_input.strip():
        if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
            user_years = max(0.0, min(80.0, float(user_years_input)))
        else:
            st.error("❌ 请输入有效的数字（支持小数）")
    st.session_state.user_years = str(user_years)

# 验证用户信息
if not user_name or not user_institution or user_years <= 0.0:
    st.warning("⚠️ 请填写完整有效的用户信息！")
    st.stop()

# ========= 数据列定义 =========
COLUMNS = [
    "submission_id", "name", "institution", "years_of_experience",
    "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence",
    "submit_time"
]

# ========= 加载图像列表 =========
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)
for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if os.path.isdir(method_path):
        for f in sorted(os.listdir(method_path)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                image_list.append({
                    "modality": selected_modality,
                    "method": method,
                    "filename": f,
                    "filepath": os.path.normpath(os.path.join(method_path, f))
                })

if not image_list:
    st.error(f"❌ 模态 `{selected_modality}` 下未找到图片！")
    st.stop()

# ========= 跳过已评分图片 =========
def get_rated_files_from_drive():
    rated_set = set()
    try:
        sanitized_name = re.sub(r'[\\/:*?"<>|]', '_', user_name).strip()
        query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title contains '{sanitized_name}' and title contains '{st.session_state.submission_id[:8]}' and mimeType='text/csv'"
        file_list = drive.ListFile({"q": query}).GetList()
        for file in file_list:
            csv_content = file.GetContentString()
            df = pd.read_csv(StringIO(csv_content), encoding="utf-8")
            df_current = df[
                (df["name"] == user_name) &
                (df["institution"] == user_institution) &
                (df["submission_id"] == st.session_state.submission_id)
            ]
            if not df_current.empty:
                rated_set.update(df_current["filename"] + "_" + df_current["method"])
    except Exception as e:
        st.warning(f"⚠️ 读取已评分记录失败：{str(e)}")
    return rated_set

rated_set = get_rated_files_from_drive()

while st.session_state.idx < len(image_list):
    img_info = image_list[st.session_state.idx]
    key = f'{img_info["filename"]}_{img_info["method"]}'
    if key in rated_set:
        st.session_state.idx += 1
    else:
        break

# ========= 主 UI =========
st.markdown(f"<h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>", unsafe_allow_html=True)
total = len(image_list)
completed = len(rated_set) if rated_set else 0
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前进度：{completed}/{total} 张（{progress:.1%}）")

if st.session_state.idx >= len(image_list):
    st.success(f"🎉 {user_name} 的所有图像评分已完成！")
    st.balloons()
else:
    img_info = image_list[st.session_state.idx]
    try:
        img = Image.open(img_info["filepath"])
        if img.mode == "RGBA":
            img = img.convert("RGB")
    except Exception as e:
        st.error(f"❌ 图片加载失败：{img_info['filename']}（错误：{str(e)}）")
        st.session_state.idx += 1
        st.rerun()

    col1, col2 = st.columns([3, 4], gap="large")
    with col1:
        st.subheader("图像预览")
        st.image(img, caption=f"{img_info['filename']}", use_container_width=True, clamp=True)
        st.caption(f"当前：第 {st.session_state.idx + 1}/{total} 张")

    with col2:
        st.subheader("📊 评分指标")
        rating_items = [
            {"key": "sharpness", "name": "视觉清晰度 / Sharpness", "desc": "结构边缘是否清晰，细节保留情况（1=差，5=好）"},
            {"key": "artifact", "name": "伪影 / Artifact", "desc": "条纹、噪声、重影等伪影多少（1=多，5=少）"},
            {"key": "naturalness", "name": "真实感 / Naturalness", "desc": "是否符合临床经验（1=不符合，5=非常符合）"},
            {"key": "diagnostic_confidence", "name": "可诊断性 / Diagnostic confidence", "desc": "是否支持临床判断（1=不足，5=足够）"}
        ]
        ratings = {}
        for item in rating_items:
            st.markdown(f"<b>{item['name']}</b>", unsafe_allow_html=True)
            col_slider, col_desc = st.columns([4,6])
            with col_slider:
                ratings[item["key"]] = st.slider(label=" ", min_value=1, max_value=5, value=3, key=f"{item['key']}_{st.session_state.idx}", label_visibility="collapsed")
            with col_desc:
                st.markdown(f"<span style='font-size:0.9em;color:#666;'>{item['desc']}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        save_btn = st.button("💾 保存并下一张", type="primary", use_container_width=True)

        if save_btn:
            new_row = {
                "submission_id": st.session_state.submission_id,
                "name": user_name,
                "institution": user_institution,
                "years_of_experience": user_years,
                "modality": img_info["modality"],
                "method": img_info["method"],
                "filename": img_info["filename"],
                "sharpness": ratings["sharpness"],
                "artifact": ratings["artifact"],
                "naturalness": ratings["naturalness"],
                "diagnostic_confidence": ratings["diagnostic_confidence"],
                "submit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            df_new = pd.DataFrame([new_row])

            try:
                date_str = datetime.now().strftime("%Y%m%d")
                sanitized_name = re.sub(r'[\\/:*?"<>|]', '_', user_name).strip()
                drive_filename = f"{selected_modality}_{date_str}_{sanitized_name}_{st.session_state.submission_id[:8]}.csv"
                query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title='{drive_filename}' and mimeType='text/csv'"
                existing_files = drive.ListFile({"q": query}).GetList()

                if existing_files:
                    existing_file = existing_files[0]
                    csv_content = existing_file.GetContentString()
                    df_exist = pd.read_csv(StringIO(csv_content), encoding="utf-8")
                    df_combined = pd.concat([df_exist, df_new], ignore_index=True)
                    csv_buffer = StringIO()
                    df_combined.to_csv(csv_buffer, index=False, encoding="utf-8")
                    existing_file.SetContentString(csv_buffer.getvalue())
                    existing_file.Upload()
                else:
                    csv_buffer = StringIO()
                    df_new.to_csv(csv_buffer, index=False, encoding="utf-8")
                    drive_file = drive.CreateFile({
                        "title": drive_filename,
                        "parents":[{"id": GOOGLE_DRIVE_FOLDER_ID}],
                        "mimeType":"text/csv"
                    })
                    drive_file.SetContentString(csv_buffer.getvalue())
                    drive_file.Upload()

                st.toast(f"✅ 已保存：{img_info['filename']}", icon="✅")
                st.session_state.idx += 1
                st.rerun()
            except Exception as e:
                st.error(f"❌ 保存失败：{str(e)}，请重试！")
                st.stop()

st.markdown("---")
st.markdown(f"<p style='font-size:0.9em;color:#888;'>📁 图像根目录：`{IMAGE_ROOT}` | 📝 评分数据已自动同步至谷歌云盘</p>", unsafe_allow_html=True)
