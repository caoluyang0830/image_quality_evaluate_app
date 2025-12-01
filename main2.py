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
IMAGE_ROOT = "resultselect"
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

# ========= 初始化评分CSV文件 =========
# 定义列名
COLUMNS = [
    "modality", "method", "filename",
    "sharpness", "artifact", "naturalness", "diagnostic_confidence"
]

# 首次运行创建空CSV
if not os.path.exists(SAVE_FILE):
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

# ========= 跳过已评分图片 =========
# 加载已评分数据
df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8") if os.path.exists(SAVE_FILE) else pd.DataFrame(columns=COLUMNS)
rated_set = set(df_rated["filename"] + "_" + df_rated["method"]) if not df_rated.empty else set()

# 自动跳过已评分的图片
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
    <p style="color:#666;">采用MOS评分（1-5分），所有评分完成后可下载完整数据</p>
""", unsafe_allow_html=True)

# 显示进度
total = len(image_list)
completed = len(rated_set)
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"进度：{completed}/{total} 张（{progress:.1%}）")

# ========= 评分逻辑 =========
if st.session_state.idx >= len(image_list):
    # 所有图片评分完成
    st.success("🎉 所有图像评分已完成！")
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
            # 构造新行数据
            new_row = {
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
    # 读取当前评分数据
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8")

    # 显示数据统计
    st.info(f"""
    📋 数据统计：
    - 已评分图片：{len(df_download)} 张
    - 涉及方法：{df_download['method'].nunique()} 种
    - 最后更新：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
    """)

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

    # 可选：显示数据预览
    with st.expander("🔍 查看评分数据预览", expanded=False):
        st.dataframe(
            df_download,
            use_container_width=True,
            hide_index=True
        )
else:
    st.warning("⚠️ 暂无评分数据，请先完成至少1张图片的评分")

# ========= 部署信息提示 =========
st.markdown("---")
st.markdown(f"""
    <p style="font-size:0.9em;color:#888;">
    📁 图像根目录：`{IMAGE_ROOT}` | 📝 数据文件：`{SAVE_FILE}`<br>
    🚀 部署环境：Streamlit Community Cloud
    </p>
""", unsafe_allow_html=True)