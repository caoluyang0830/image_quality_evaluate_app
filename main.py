import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings

# 忽略无关警告（部署时更清爽）
warnings.filterwarnings("ignore")

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="centered",
    initial_sidebar_state="collapsed"  # 隐藏侧边栏，更简洁
)

# ========= 路径配置（适配 Streamlit Cloud）=========
# 图像根目录（需和main.py同目录上传到GitHub）
IMAGE_ROOT = "resultselect2"
# 确保路径兼容Windows/Linux
IMAGE_ROOT = os.path.normpath(IMAGE_ROOT)

# ========= 检查图像根目录 =========
if not os.path.exists(IMAGE_ROOT):
    st.error(f"""
    ❌ 图像根路径不存在: `{IMAGE_ROOT}`
    请确认：
    1. `{IMAGE_ROOT}` 文件夹已上传到GitHub仓库（和main.py同目录）
    2. 文件夹名称拼写正确（区分大小写）
    """)
    st.stop()

# ========= 模态选择 =========
# 筛选有效模态文件夹
modalities = []
for m in sorted(os.listdir(IMAGE_ROOT)):
    m_path = os.path.join(IMAGE_ROOT, m)
    if os.path.isdir(m_path):
        # 检查该模态下是否有图片
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
SAVE_FILE = f"{selected_modality}_ratings.csv"
SAVE_FILE = os.path.normpath(SAVE_FILE)

# ========= 初始化/修复评分CSV文件 =========
# 定义完整列名（包含新增的姓名、医疗机构）
COLUMNS = [
    "name", "institution", "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence"
]

# 初始化或修复CSV文件（解决新旧文件兼容问题）
if os.path.exists(SAVE_FILE):
    # 读取现有CSV并修复列
    df_exist = pd.read_csv(SAVE_FILE, encoding="utf-8")
    # 检查缺失的列并补充
    missing_cols = [col for col in COLUMNS if col not in df_exist.columns]
    if missing_cols:
        for col in missing_cols:
            df_exist[col] = ""  # 缺失列填充空值
        # 重新保存修复后的CSV
        df_exist = df_exist[COLUMNS]  # 保证列顺序一致
        df_exist.to_csv(SAVE_FILE, index=False, encoding="utf-8")
else:
    # 首次运行创建空CSV
    df_empty = pd.DataFrame(columns=COLUMNS)
    df_empty.to_csv(SAVE_FILE, index=False, encoding="utf-8")

# ========= 加载图像列表 =========
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)

# 遍历该模态下的所有方法文件夹
for method in sorted(os.listdir(modality_path)):
    method_path = os.path.join(modality_path, method)
    if not os.path.isdir(method_path):
        continue

    # 遍历方法文件夹下的图片
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

# ========= 初始化SessionState =========
if "idx" not in st.session_state:
    st.session_state.idx = 0
# 保存用户信息，避免刷新丢失
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""

# ========= 安全加载已评分数据并跳过已评分图片 =========
# 安全读取修复后的CSV
df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8")
# 处理空值（避免拼接时出现NaN）
df_rated = df_rated.fillna("")

# 生成已评分集合（增加空值判断，避免KeyError）
rated_set = set()
if not df_rated.empty:
    # 只处理有姓名的有效记录（旧记录无姓名则不跳过）
    valid_rated = df_rated[df_rated["name"] != ""]
    if not valid_rated.empty:
        rated_set = set(
            valid_rated["filename"] + "_" + valid_rated["method"] + "_" + valid_rated["name"]
        )

# 自动跳过当前用户已评分的图片（多人区分）
while st.session_state.idx < len(image_list):
    img_info = image_list[st.session_state.idx]
    # 仅当用户已输入姓名时才跳过已评分图片
    if st.session_state.user_name:
        key = f'{img_info["filename"]}_{img_info["method"]}_{st.session_state.user_name}'
        if key in rated_set:
            st.session_state.idx += 1
        else:
            break
    else:
        break

# ========= 主UI =========
st.markdown(f"""
    <h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>
    <p style="color:#666;">采用MOS评分（1-5分），所有评分完成后可下载完整数据</p>
""", unsafe_allow_html=True)

# ========= 新增：用户信息输入区域 =========
st.markdown("### 🧑‍💻 评分人信息（必填）")
col_name, col_institution = st.columns(2, gap="medium")
with col_name:
    user_name = st.text_input(
        "姓名",
        value=st.session_state.user_name,
        placeholder="请输入您的姓名",
        label_visibility="collapsed",
        key="input_name"
    )
    st.session_state.user_name = user_name  # 同步到SessionState

with col_institution:
    user_institution = st.text_input(
        "医疗机构",
        value=st.session_state.user_institution,
        placeholder="请输入您的医疗机构",
        label_visibility="collapsed",
        key="input_institution"
    )
    st.session_state.user_institution = user_institution  # 同步到SessionState

# 验证用户信息是否填写
if not user_name or not user_institution:
    st.warning("⚠️ 请先填写姓名和医疗机构信息，再进行评分！")
    st.stop()

# 显示进度
total = len(image_list)
# 计算当前用户已完成的数量（安全处理）
if not df_rated.empty:
    completed = len(df_rated[(df_rated["name"] == user_name) & (df_rated["institution"] == user_institution)])
else:
    completed = 0
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前用户进度：{completed}/{total} 张（{progress:.1%}）")

# ========= 评分逻辑 =========
if st.session_state.idx >= len(image_list):
    # 所有图片评分完成
    st.success(f"🎉 {user_name}（{user_institution}），您的所有图像评分已完成！")
    st.balloons()  # 庆祝动画
else:
    # 显示当前图片和评分项
    img_info = image_list[st.session_state.idx]

    # 尝试加载图片（处理损坏图片）
    try:
        img = Image.open(img_info["filepath"])
        # 处理RGBA图片（避免显示异常）
        if img.mode == "RGBA":
            img = img.convert("RGB")
    except Exception as e:
        st.error(f"❌ 图片加载失败：{img_info['filename']}（错误：{str(e)}）")
        st.session_state.idx += 1
        st.rerun()

    # 左右布局：图片 + 评分
    col1, col2 = st.columns([3, 4], gap="large")

    with col1:
        st.subheader(f"图像预览")
        st.image(
            img,
            caption=f"{img_info['method']} / {img_info['filename']}",
            use_container_width=True,
            clamp=True  # 防止超大图片溢出
        )
        st.caption(f"当前：第 {st.session_state.idx + 1}/{total} 张")

    with col2:
        st.subheader("📊 评分指标")

        # 定义评分项配置（简化代码）
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

        # 存储评分结果
        ratings = {}

        # 生成评分滑块
        for item in rating_items:
            st.markdown(f"<b>{item['name']}</b>", unsafe_allow_html=True)
            col_slider, col_desc = st.columns([4, 6])
            with col_slider:
                ratings[item["key"]] = st.slider(
                    label=" ",  # 隐藏默认标签（用自定义标签）
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
            type="primary",  # 强调按钮
            use_container_width=True  # 全屏按钮
        )

        if save_btn:
            # 构造新行数据（新增：姓名、医疗机构）
            new_row = {
                "name": user_name,
                "institution": user_institution,
                "modality": img_info["modality"],
                "method": img_info["method"],
                "filename": img_info["filename"],
                "sharpness": ratings["sharpness"],
                "artifact": ratings["artifact"],
                "naturalness": ratings["naturalness"],
                "diagnostic_confidence": ratings["diagnostic_confidence"]
            }

            # 追加到CSV（避免重复写入表头）
            df_new = pd.DataFrame([new_row])
            df_new.to_csv(
                SAVE_FILE,
                mode="a",
                header=False,
                index=False,
                encoding="utf-8"
            )

            # 提示保存成功
            st.toast(f"✅ 已保存：{img_info['filename']}", icon="✅")

            # 跳转到下一张
            st.session_state.idx += 1
            st.rerun()

# ========= 下载CSV按钮（核心功能）=========
st.markdown("---")
st.subheader("📥 评分数据管理")

if os.path.exists(SAVE_FILE):
    # 读取当前评分数据（安全处理）
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8")
    df_download = df_download.fillna("")  # 处理空值

    # 显示数据统计（新增：多用户维度）
    valid_records = df_download[df_download["name"] != ""]
    total_users = valid_records["name"].nunique() if not valid_records.empty else 0
    st.info(f"""
    📋 数据统计：
    - 总评分记录：{len(df_download)} 条
    - 有效用户评分记录：{len(valid_records)} 条
    - 参与评分人数：{total_users} 人
    - 涉及方法：{df_download['method'].nunique()} 种
    - 最后更新：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
    """)

    # 可选：按用户筛选数据预览
    st.markdown("### 🔍 数据预览")
    user_list = ["全部"] + list(valid_records["name"].unique()) if not valid_records.empty else ["全部"]
    selected_user = st.selectbox("选择查看用户", user_list, key="preview_user")
    
    if selected_user != "全部" and not valid_records.empty:
        df_preview = valid_records[valid_records["name"] == selected_user]
    else:
        df_preview = df_download

    st.dataframe(
        df_preview,
        use_container_width=True,
        hide_index=True
    )

    # 下载按钮
    with open(SAVE_FILE, "rb") as f:
        st.download_button(
            label="📤 下载完整评分CSV",
            data=f,
            file_name=SAVE_FILE,
            mime="text/csv",
            use_container_width=True,
            type="secondary"
        )

else:
    st.warning("⚠️ 暂无评分数据，请先完成至少1张图片的评分")

# ========= 部署信息提示 =========
st.markdown("---")
st.markdown(f"""
    <p style="font-size:0.9em;color:#888;">
    📁 图像根目录：`{IMAGE_ROOT}` | 📝 数据文件：`{SAVE_FILE}`<br>
    🚀 部署环境：Streamlit Community Cloud | 👥 支持多用户评分
    </p>
""", unsafe_allow_html=True)
