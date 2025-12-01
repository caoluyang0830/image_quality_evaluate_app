import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re  # 新增：处理用户名特殊字符

# 忽略无关警告（部署时更清爽）
warnings.filterwarnings("ignore")

# ========= 新增：隐藏 Streamlit 默认 UI（去掉 GitHub 链接核心） =========
st.markdown("""
<style>
/* 隐藏右上角的默认菜单（包含 GitHub 链接） */
#MainMenu {visibility: hidden;}
/* 隐藏 Streamlit 页脚（包含平台标识/链接） */
footer {visibility: hidden;}
/* 隐藏部署状态提示（若有） */
.deploy-status {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="centered",
    initial_sidebar_state="collapsed"  # 隐藏侧边栏，更简洁
)

# ========= 路径配置（适配 Streamlit Cloud）=========
# 图像根目录（移除了 GitHub 注释）
IMAGE_ROOT = "resultselect"
# 确保路径兼容Windows/Linux
IMAGE_ROOT = os.path.normpath(IMAGE_ROOT)

# ========= 检查图像根目录 =========
if not os.path.exists(IMAGE_ROOT):
    st.error(f"""
    ❌ 图像根路径不存在: `{IMAGE_ROOT}`
    请确认：
    1. `{IMAGE_ROOT}` 文件夹已上传到应用根目录（和main.py同目录）
    2. 文件夹名称拼写正确（区分大小写）
    """)  # 修改：去掉了 "GitHub仓库" 相关描述
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

# ========= 初始化SessionState =========
if "idx" not in st.session_state:
    st.session_state.idx = 0
# 保存用户信息，避免刷新丢失
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""

# ========= 新增：用户信息输入区域（提前，用于生成专属文件名）=========
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

# ========= 核心修改：生成用户专属CSV文件名 =========
def sanitize_filename(name):
    """清理文件名中的特殊字符，避免路径错误"""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

# 仅当用户填写姓名后才生成专属文件名
if user_name:
    # 生成用户专属文件名：模态_用户名_ratings.csv（清理特殊字符）
    sanitized_name = sanitize_filename(user_name)
    SAVE_FILE = f"{selected_modality}_{sanitized_name}_ratings.csv"
    SAVE_FILE = os.path.normpath(SAVE_FILE)
else:
    SAVE_FILE = ""  # 未填写姓名时暂不生成

# ========= 验证用户信息是否填写 =========
if not user_name or not user_institution:
    st.warning("⚠️ 请先填写姓名和医疗机构信息，再进行评分！")
    st.stop()

# ========= 初始化/修复用户专属评分CSV文件 =========
# 定义完整列名（包含姓名、医疗机构）
COLUMNS = [
    "name", "institution", "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence"
]

# 初始化或修复当前用户的专属CSV文件
if SAVE_FILE and not os.path.exists(SAVE_FILE):
    # 首次运行创建空CSV（用户专属）
    df_empty = pd.DataFrame(columns=COLUMNS)
    df_empty.to_csv(SAVE_FILE, index=False, encoding="utf-8")
elif SAVE_FILE and os.path.exists(SAVE_FILE):
    # 读取现有用户专属CSV并修复列
    df_exist = pd.read_csv(SAVE_FILE, encoding="utf-8")
    # 检查缺失的列并补充
    missing_cols = [col for col in COLUMNS if col not in df_exist.columns]
    if missing_cols:
        for col in missing_cols:
            df_exist[col] = ""  # 缺失列填充空值
        # 重新保存修复后的CSV
        df_exist = df_exist[COLUMNS]  # 保证列顺序一致
        df_exist.to_csv(SAVE_FILE, index=False, encoding="utf-8")

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

# ========= 安全加载当前用户已评分数据并跳过已评分图片 =========
rated_set = set()
if SAVE_FILE and os.path.exists(SAVE_FILE):
    # 仅读取当前用户的专属CSV
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8")
    df_rated = df_rated.fillna("")  # 处理空值
    
    # 生成当前用户已评分集合
    if not df_rated.empty:
        rated_set = set(
            df_rated["filename"] + "_" + df_rated["method"]
        )

# 自动跳过当前用户已评分的图片
while st.session_state.idx < len(image_list):
    img_info = image_list[st.session_state.idx]
    key = f'{img_info["filename"]}_{img_info["method"]}'
    if key in rated_set:
        st.session_state.idx += 1
    else:
        break

# ========= 主UI =========
st.markdown(f"""
    <h2>🧑‍⚕️ {selected_modality} 图像多指标主观评分系统</h2>
    <p style="color:#666;">{user_name}（{user_institution}）专属评分表 | 采用MOS评分（1-5分）</p>
""", unsafe_allow_html=True)

# 显示进度
total = len(image_list)
# 计算当前用户已完成的数量
completed = len(rated_set) if rated_set else 0
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"当前进度：{completed}/{total} 张（{progress:.1%}）")

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
            # 构造新行数据（当前用户专属）
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

            # 追加到当前用户的专属CSV
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

# ========= 下载CSV按钮（当前用户专属 + 可选汇总）=========
st.markdown("---")
st.subheader("📥 评分数据管理")

# 1. 当前用户专属数据展示与下载
if SAVE_FILE and os.path.exists(SAVE_FILE):
    # 读取当前用户的专属评分数据（完整数据，包含method列）
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8")
    df_download = df_download.fillna("")  # 处理空值

    # 显示当前用户数据统计
    st.info(f"""
    📋 {user_name} 专属评分统计：
    - 总评分记录：{len(df_download)} 条
    - 涉及方法：{df_download['method'].nunique()} 种
    - 最后更新：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
    - 数据文件：`{os.path.basename(SAVE_FILE)}`
    """)

    # 数据预览（仅当前用户）- 临时移除method列
    st.markdown("### 🔍 我的评分数据预览")
    # 核心修改：预览时删除method列，不修改原数据
    df_preview = df_download.drop(columns=["method"])
    st.dataframe(
        df_preview,  # 展示去掉method列的版本
        use_container_width=True,
        hide_index=True
    )

    # 下载当前用户专属CSV（原数据，包含method列）
    with open(SAVE_FILE, "rb") as f:
        st.download_button(
            label="📤 下载我的专属评分CSV",
            data=f,
            file_name=os.path.basename(SAVE_FILE),
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )

    # 2. 可选：管理员汇总所有用户数据（新增）
    st.markdown("### 📊 所有用户数据汇总（管理员用）")
    # 查找当前模态下所有用户的评分文件
    all_user_files = []
    for f in os.listdir("."):
        if f.startswith(f"{selected_modality}_") and f.endswith("_ratings.csv"):
            all_user_files.append(f)
    
    if all_user_files:
        # 汇总所有用户数据（完整数据，包含method列）
        df_all = pd.DataFrame()
        for file in all_user_files:
            df_temp = pd.read_csv(file, encoding="utf-8").fillna("")
            df_all = pd.concat([df_all, df_temp], ignore_index=True)
        
        # 显示汇总统计
        total_users = df_all["name"].nunique() if not df_all.empty else 0
        st.info(f"""
        📈 汇总统计：
        - 参与评分人数：{total_users} 人
        - 总评分记录：{len(df_all)} 条
        """)

        # 预览汇总数据（临时移除method列）
        if st.checkbox("查看所有用户汇总数据"):
            df_all_preview = df_all.drop(columns=["method"])  # 核心修改
            st.dataframe(df_all_preview, use_container_width=True, hide_index=True)
        
        # 下载汇总CSV（原数据，包含method列）
        all_csv_name = f"{selected_modality}_所有用户评分汇总.csv"
        csv_all = df_all.to_csv(index=False, encoding="utf-8")  # 完整数据保存
        st.download_button(
            label="📤 下载所有用户评分汇总CSV",
            data=csv_all,
            file_name=all_csv_name,
            mime="text/csv",
            use_container_width=True,
            type="secondary"
        )
    else:
        st.warning("⚠️ 暂未找到其他用户的评分数据")
else:
    st.warning("⚠️ 暂无您的评分数据，请先完成至少1张图片的评分")

# ========= 部署信息提示 =========
st.markdown("---")
st.markdown(f"""
    <p style="font-size:0.9em;color:#888;">
    📁 图像根目录：`{IMAGE_ROOT}` | 📝 您的专属数据文件：`{os.path.basename(SAVE_FILE) if SAVE_FILE else '未生成'}`<br>
    👥 每个评分人拥有独立评分表，数据互不干扰
    </p>
""", unsafe_allow_html=True)
