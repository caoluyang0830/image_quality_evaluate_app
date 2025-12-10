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
# 新增谷歌认证相关导入
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

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

# ========= 关键配置（替换为你的信息！）=========
GOOGLE_DRIVE_FOLDER_ID = "1_7HhWjfEK65YfsjOWR-kNrN0ogJCr2Zq"  # 你提供的文件夹ID
GOOGLE_SERVICE_ACCOUNT_KEY = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_KEY")

# 图像根目录
IMAGE_ROOT = "resultselect"
IMAGE_ROOT = os.path.normpath(IMAGE_ROOT)

# ========= 修复：初始化 Google Drive 客户端（正确认证方式）=========
@st.cache_resource(show_spinner=False)
def init_google_drive():
    """初始化谷歌云盘客户端（基于 google-auth 正确认证）"""
    if not GOOGLE_DRIVE_FOLDER_ID or not GOOGLE_SERVICE_ACCOUNT_KEY:
        st.error("❌ 谷歌云盘配置不完整，请检查文件夹ID和服务账号密钥！")
        st.stop()

    try:
        # 1. 解析服务账号JSON密钥
        import json
        service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
        
        # 2. 定义需要的权限范围（最小权限原则）
        SCOPES = ["https://www.googleapis.com/auth/drive.file"]  # 仅允许操作上传的文件
        
        # 3. 创建服务账号凭证
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )
        
        # 4. 验证凭证（若过期则刷新）
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        # 5. 初始化 pydrive2 的 GoogleAuth 对象
        gauth = GoogleAuth()
        gauth.credentials = creds  # 直接传入已创建的凭证
        gauth.Authorize()  # 授权
        
        # 6. 创建 GoogleDrive 客户端
        drive = GoogleDrive(gauth)
        return drive

    except Exception as e:
        st.error(f"❌ 谷歌云盘连接失败：{str(e)}")
        st.stop()

# 初始化客户端
drive = init_google_drive()

# ========= 以下代码完全不变（从之前的代码复制即可）=========
# 检查图像根目录
if not os.path.exists(IMAGE_ROOT):
    st.error(f"""
    ❌ 图像根路径不存在: `{IMAGE_ROOT}`
    请确认：
    1. `{IMAGE_ROOT}` 文件夹已上传到应用根目录
    2. 文件夹名称拼写正确（区分大小写）
    """)
    st.stop()

# 模态选择
modalities = []
for m in sorted(os.listdir(IMAGE_ROOT)):
    m_path = os.path.join(IMAGE_ROOT, m)
    if os.path.isdir(m_path):
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
    st.error(f"❌ `{IMAGE_ROOT}` 目录下未找到包含图片的模态文件夹！")
    st.stop()

selected_modality = st.selectbox("📌 选择评分模态", modalities)

# 初始化 SessionState
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""
if "user_years" not in st.session_state:
    st.session_state.user_years = ""
if "submission_id" not in st.session_state:
    st.session_state.submission_id = str(uuid.uuid4())  # 唯一会话ID

# 用户信息输入区域
st.markdown("### 🧑‍💻 评分人信息（必填）")
col_name, col_institution, col_years = st.columns(3, gap="medium")
with col_name:
    user_name = st.text_input(
        "姓名",
        value=st.session_state.user_name,
        placeholder="请输入您的姓名",
        label_visibility="collapsed",
        key="input_name"
    )
    st.session_state.user_name = user_name

with col_institution:
    user_institution = st.text_input(
        "医疗机构",
        value=st.session_state.user_institution,
        placeholder="请输入您的医疗机构",
        label_visibility="collapsed",
        key="input_institution"
    )
    st.session_state.user_institution = user_institution

# 从业年限（支持小数，纯文本输入）
with col_years:
    user_years_input = st.text_input(
        "从业年限",
        value=st.session_state.user_years,
        placeholder="请输入数字（0-80，支持小数）",
        label_visibility="collapsed",
        key="input_years",
        help="支持0-80之间的整数或小数（如3.5）"
    )
    
    # 验证输入
    user_years = 0.0
    if user_years_input.strip():
        if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
            user_years = float(user_years_input)
            user_years = max(0.0, min(80.0, user_years))  # 限制范围
            user_years = round(user_years, 1)
        else:
            st.error("❌ 请输入有效的数字（支持小数）")
    st.session_state.user_years = str(user_years)

# 验证用户信息
if not user_name:
    st.warning("⚠️ 请输入您的姓名！")
    st.stop()
if not user_institution:
    st.warning("⚠️ 请输入您的医疗机构！")
    st.stop()
if user_years <= 0.0:
    st.warning("⚠️ 请输入有效的从业年限（需大于0）！")
    st.stop()

# 数据列定义
COLUMNS = [
    "submission_id", "name", "institution", "years_of_experience",
    "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence",
    "submit_time"
]

# 加载图像列表
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)

for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if not os.path.isdir(method_path):
        continue
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

# 跳过已评分图片（从谷歌云盘读取）
def get_rated_files_from_drive():
    """从谷歌云盘获取当前医生已评分的文件"""
    rated_set = set()
    try:
        # 搜索当前医生的评分文件
        sanitized_name = re.sub(r'[\\/:*?"<>|]', '_', user_name).strip()
        query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title contains '{sanitized_name}' and title contains '{st.session_state.submission_id[:8]}' and mimeType='text/csv'"
        file_list = drive.ListFile({"q": query}).GetList()

        for file in file_list:
            # 下载文件并解析
            csv_content = file.GetContentString()
            df = pd.read_csv(StringIO(csv_content), encoding="utf-8")
            # 筛选当前医生的记录
            df_current = df[
                (df["name"] == user_name) &
                (df["institution"] == user_institution) &
                (df["submission_id"] == st.session_state.submission_id)
            ]
            if not df_current.empty:
                rated_set.update(df_current["filename"] + "_" + df_current["method"])
    except Exception as e:
        st.warning(f"⚠️ 读取已评分记录失败：{str(e)}，可能会重复评分")
    return rated_set

rated_set = get_rated_files_from_drive()

# 跳过已评分图片
while st.session_state.idx < len(image_list):
    img_info = image_list[st.session_state.idx]
    key = f'{img_info["filename"]}_{img_info["method"]}'
    if key in rated_set:
        st.session_state.idx += 1
    else:
        break

# 主 UI
st.markdown(f"""
    <h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>
    <p style="color:#666;">{user_name}（{user_institution} | 从业{user_years}年）专属评分表 | 采用MOS评分（1-5分）</p>
""", unsafe_allow_html=True)

# 显示进度
total = len(image_list)
completed = len(rated_set) if rated_set else 0
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前进度：{completed}/{total} 张（{progress:.1%}）")

# 评分逻辑
if st.session_state.idx >= len(image_list):
    st.success(f"🎉 {user_name}（{user_institution} | 从业{user_years}年），您的所有图像评分已完成！")
    st.balloons()
else:
    img_info = image_list[st.session_state.idx]

    # 加载图片
    try:
        img = Image.open(img_info["filepath"])
        if img.mode == "RGBA":
            img = img.convert("RGB")
    except Exception as e:
        st.error(f"❌ 图片加载失败：{img_info['filename']}（错误：{str(e)}）")
        st.session_state.idx += 1
        st.rerun()

    # 左右布局
    col1, col2 = st.columns([3, 4], gap="large")

    with col1:
        st.subheader(f"图像预览")
        st.image(
            img,
            caption=f"{img_info['filename']}",
            use_container_width=True,
            clamp=True
        )
        st.caption(f"当前：第 {st.session_state.idx + 1}/{total} 张")

    with col2:
        st.subheader("📊 评分指标")

        # 评分项配置
        rating_items = [
            {
                "key": "sharpness",
                "name": "视觉清晰度 / Sharpness",
                "desc": "结构边缘是否清晰，细节保留情况（1=差，5=好）"
            },
            {
                "key": "artifact",
                "name": "伪影 / Artifact",
                "desc": "条纹、噪声、重影等伪影多少（1=多，5=少）"
            },
            {
                "key": "naturalness",
                "name": "真实感 / Naturalness",
                "desc": "是否符合临床经验（1=不符合，5=非常符合）"
            },
            {
                "key": "diagnostic_confidence",
                "name": "可诊断性 / Diagnostic confidence",
                "desc": "是否支持临床判断（1=不足，5=足够）"
            }
        ]

        ratings = {}
        # 生成评分滑块
        for item in rating_items:
            st.markdown(f"<b>{item['name']}</b>", unsafe_allow_html=True)
            col_slider, col_desc = st.columns([4, 6])
            with col_slider:
                ratings[item["key"]] = st.slider(
                    label=" ",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"{item['key']}_{st.session_state.idx}",
                    label_visibility="collapsed"
                )
            with col_desc:
                st.markdown(f"<span style='font-size:0.9em;color:#666;'>{item['desc']}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

        # 保存按钮
        st.markdown("<br>", unsafe_allow_html=True)
        save_btn = st.button(
            "💾 保存并下一张",
            type="primary",
            use_container_width=True
        )

        if save_btn:
            # 构建评分数据
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

            # 核心：上传到谷歌云盘
            try:
                # 定义云盘文件名（按日期+医生+会话ID分类）
                date_str = datetime.now().strftime("%Y%m%d")
                sanitized_name = re.sub(r'[\\/:*?"<>|]', '_', user_name).strip()
                drive_filename = f"{selected_modality}_{date_str}_{sanitized_name}_{st.session_state.submission_id[:8]}.csv"

                # 搜索云盘中是否已存在该文件
                query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and title='{drive_filename}' and mimeType='text/csv'"
                existing_files = drive.ListFile({"q": query}).GetList()

                if existing_files:
                    # 若文件存在，追加数据
                    existing_file = existing_files[0]
                    # 下载原有内容
                    csv_content = existing_file.GetContentString()
                    df_exist = pd.read_csv(StringIO(csv_content), encoding="utf-8")
                    # 合并数据
                    df_combined = pd.concat([df_exist, df_new], ignore_index=True)
                    # 覆盖上传
                    csv_buffer = StringIO()
                    df_combined.to_csv(csv_buffer, index=False, encoding="utf-8")
                    existing_file.SetContentString(csv_buffer.getvalue())
                    existing_file.Upload()
                else:
                    # 若文件不存在，创建新文件
                    csv_buffer = StringIO()
                    df_new.to_csv(csv_buffer, index=False, encoding="utf-8")
                    # 创建云盘文件
                    drive_file = drive.CreateFile({
                        "title": drive_filename,
                        "parents": [{"id": GOOGLE_DRIVE_FOLDER_ID}],
                        "mimeType": "text/csv"
                    })
                    drive_file.SetContentString(csv_buffer.getvalue())
                    drive_file.Upload()

                # 提示成功并跳转下一张
                st.toast(f"✅ 已保存：{img_info['filename']}", icon="✅")
                st.session_state.idx += 1
                st.rerun()

            except Exception as e:
                st.error(f"❌ 保存失败：{str(e)}，请重试！")
                st.stop()

# 部署信息提示（隐藏下载按钮）
st.markdown("---")
st.markdown(f"""
    <p style="font-size:0.9em;color:#888;">
    📁 图像根目录：`{IMAGE_ROOT}` | 📝 评分数据已自动同步至谷歌云盘<br>
    👤 仅展示当前用户的评分进度 | 📅 从业年限：{user_years}年
    </p>
""", unsafe_allow_html=True)
