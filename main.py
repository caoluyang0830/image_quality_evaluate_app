import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re  # 处理用户名特殊字符

# 忽略无关警告（部署时更清爽）
warnings.filterwarnings("ignore")

# ========= 隐藏 Streamlit 默认 UI =========
st.markdown("""
<style>
/* 隐藏右上角的默认菜单 */
#MainMenu {visibility: hidden;}
/* 隐藏 Streamlit 页脚 */
footer {visibility: hidden;}
/* 隐藏部署状态提示 */
.deploy-status {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ========= 路径配置 =========
IMAGE_ROOT = "resultselect"
IMAGE_ROOT = os.path.normpath(IMAGE_ROOT)

# ========= 检查图像根目录 =========
if not os.path.exists(IMAGE_ROOT):
    st.error(f"""
    ❌ 图像根路径不存在: `{IMAGE_ROOT}`
    请确认：
    1. `{IMAGE_ROOT}` 文件夹已上传到应用根目录（和main.py同目录）
    2. 文件夹名称拼写正确（区分大小写）
    """)
    st.stop()

# ========= 模态选择 =========
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

# ========= 初始化SessionState =========
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""
if "user_years" not in st.session_state:  # 新增：从业年限session
    st.session_state.user_years = ""

# ========= 用户信息输入区域 =========
st.markdown("### 🧑‍💻 评分人信息（必填）")
# 修改为三列布局：姓名、机构、从业年限
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

# 新增：从业年限输入框
with col_years:
    user_years = st.number_input(
        "从业年限",
        value=int(st.session_state.user_years) if st.session_state.user_years and st.session_state.user_years.isdigit() else 0,
        min_value=0,
        max_value=40,
        step=1,
        placeholder="请输入从业年限",
        label_visibility="collapsed",
        key="input_years"
    )
    st.session_state.user_years = str(user_years)  # 存储为字符串避免类型问题

# ========= 生成用户专属CSV文件名 =========
def sanitize_filename(name):
    """清理文件名中的特殊字符，避免路径错误"""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

# 仅当用户填写姓名后才生成专属文件名
if user_name:
    sanitized_name = sanitize_filename(user_name)
    SAVE_FILE = f"{selected_modality}_{sanitized_name}_ratings.csv"
    SAVE_FILE = os.path.normpath(SAVE_FILE)
else:
    SAVE_FILE = ""

# ========= 验证用户信息 =========
# 修改验证逻辑：添加从业年限的验证
if not user_name or not user_institution or user_years == 0:
    st.warning("⚠️ 请完整填写姓名、医疗机构和从业年限（从业年限需大于0），再进行评分！")
    st.stop()

# ========= 初始化/修复用户专属CSV文件 =========
COLUMNS = [
    "name", "institution", "years_of_experience",  # 新增：从业年限列
    "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence"
]

if SAVE_FILE and not os.path.exists(SAVE_FILE):
    df_empty = pd.DataFrame(columns=COLUMNS)
    df_empty.to_csv(SAVE_FILE, index=False, encoding="utf-8")
elif SAVE_FILE and os.path.exists(SAVE_FILE):
    df_exist = pd.read_csv(SAVE_FILE, encoding="utf-8")
    missing_cols = [col for col in COLUMNS if col not in df_exist.columns]
    if missing_cols:
        for col in missing_cols:
            df_exist[col] = "" if col != "years_of_experience" else 0  # 从业年限默认0
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
            image_list.append({
                "modality": selected_modality,
                "method": method,
                "filename": f,
                "filepath": os.path.normpath(os.path.join(method_path, f))
            })

if not image_list:
    st.error(f"❌ 模态 `{selected_modality}` 下未找到图片（支持jpg/jpeg/png格式）！")
    st.stop()

# ========= 跳过已评分图片 =========
rated_set = set()
if SAVE_FILE and os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8")
    df_rated = df_rated.fillna("")
    if not df_rated.empty:
        rated_set = set(
            df_rated["filename"] + "_" + df_rated["method"]
        )

while st.session_state.idx < len(image_list):
    img_info = image_list[st.session_state.idx]
    key = f'{img_info["filename"]}_{img_info["method"]}'
    if key in rated_set:
        st.session_state.idx += 1
    else:
        break

# ========= 主UI =========
# 修改欢迎信息：显示从业年限
st.markdown(f"""
    <h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>
    <p style="color:#666;">{user_name}（{user_institution} | 从业{user_years}年）专属评分表 | 采用MOS评分（1-5分）</p>
""", unsafe_allow_html=True)

# 显示进度
total = len(image_list)
completed = len(rated_set) if rated_set else 0
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前进度：{completed}/{total} 张（{progress:.1%}）")

# ========= 评分逻辑 =========
if st.session_state.idx >= len(image_list):
    # 修改完成信息：显示从业年限
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
            new_row = {
                "name": user_name,
                "institution": user_institution,
                "years_of_experience": user_years,  # 新增：保存从业年限
                "modality": img_info["modality"],
                "method": img_info["method"],
                "filename": img_info["filename"],
                "sharpness": ratings["sharpness"],
                "artifact": ratings["artifact"],
                "naturalness": ratings["naturalness"],
                "diagnostic_confidence": ratings["diagnostic_confidence"]
            }

            df_new = pd.DataFrame([new_row])
            df_new.to_csv(
                SAVE_FILE,
                mode="a",
                header=False,
                index=False,
                encoding="utf-8"
            )

            st.toast(f"✅ 已保存：{img_info['filename']}", icon="✅")
            st.session_state.idx += 1
            st.rerun()

# ========= 评分数据管理（仅个人专属）=========
st.markdown("---")
st.subheader("📥 我的评分数据管理")

if SAVE_FILE and os.path.exists(SAVE_FILE):
    # 读取个人专属数据
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8")
    df_download = df_download.fillna("")

    # 个人数据统计（新增从业年限显示）
    st.info(f"""
    📋 我的评分统计：
    - 总评分记录：{len(df_download)} 条
    - 涉及方法：{df_download['method'].nunique()} 种
    - 个人信息：{user_name} | {user_institution} | 从业{user_years}年
    - 最后更新：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
    - 数据文件：`{os.path.basename(SAVE_FILE)}`
    """)

    # 数据预览（显示从业年限列，隐藏method列）
    st.markdown("### 🔍 我的评分数据预览")
    df_preview = df_download.drop(columns=["method"])
    st.dataframe(
        df_preview,
        use_container_width=True,
        hide_index=True
    )

    # 下载个人专属CSV
    with open(SAVE_FILE, "rb") as f:
        st.download_button(
            label="📤 下载我的专属评分CSV",
            data=f,
            file_name=os.path.basename(SAVE_FILE),
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )
else:
    st.warning("⚠️ 暂无您的评分数据，请先完成至少1张图片的评分")

# ========= 部署信息提示 =========
st.markdown("---")
st.markdown(f"""
    <p style="font-size:0.9em;color:#888;">
    📁 图像根目录：`{IMAGE_ROOT}` | 📝 我的专属数据文件：`{os.path.basename(SAVE_FILE) if SAVE_FILE else '未生成'}`<br>
    👤 仅展示和下载当前用户的专属评分数据 | 📅 从业年限：{user_years}年
    </p>
""", unsafe_allow_html=True)
