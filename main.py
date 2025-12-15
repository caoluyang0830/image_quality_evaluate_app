import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

# ================= 基础设置 =================
warnings.filterwarnings("ignore")

# ========= 隐藏 Streamlit 默认 UI =========
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .deploy-status {visibility: hidden;}
    .stTextInput > div > div > input:focus { box-shadow: none; }
    .image-item {
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .image-item:hover {
        background-color: #f0f2f6;
    }
    .image-item.selected {
        background-color: #e6f7ff;
        border: 2px solid #1890ff;
    }
    .image-item.rated {
        border-left: 4px solid #52c41a;
    }
    .image-thumbnail {
        width: 100%;
        height: 80px;
        object-fit: cover;
        border-radius: 4px;
        margin-bottom: 4px;
    }
    .image-filename {
        font-size: 0.85rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .image-method {
        font-size: 0.75rem;
        color: #666;
    }
    .scrollable-list {
        max-height: calc(100vh - 300px);
        overflow-y: auto;
        padding-right: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= 页面配置 =========
st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",  # 改为宽布局以适应左右分栏
    initial_sidebar_state="collapsed",
)

# ========= 语言选择 =========
LANG = st.selectbox("🌐 Language / 语言", ["中文", "English"], index=0)

# ========= 多语言文本 =========
TEXT = {
    "中文": {
        "title": "图像多指标主观评分系统",
        "select_modality": "📌 选择评分模态",
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
        "save_next": "💾 保存并下一张",
        "saved": "✅ 已保存",
        "finished": "🎉 您的评分已全部完成！",
        "download_title": "📥 我的评分数据",
        "download": "📤 下载 CSV",
        "no_data": "暂无评分数据",
        "mos": "MOS 1-5 分",
        "sharpness": ("清晰度", "1=差，5=好"),
        "artifact": ("伪影", "1=多，5=少"),
        "naturalness": ("真实感", "1=不符合，5=符合"),
        "diagnostic": ("可诊断性", "1=不足，5=足够"),
        "image_list": "📋 图像列表",
        "total_images": "总图像数",
        "completed_images": "已完成",
        "filter_images": "筛选",
        "all_images": "全部",
        "unrated_images": "未评分",
        "rated_images": "已评分",
        "click_to_select": "点击选择图像进行评分",
        "method_label": "方法：",
        "selected_image": "当前选择：",
    },
    "English": {
        "title": "Multi-Metric Image Subjective Scoring System",
        "select_modality": "📌 Select Modality",
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
        "save_next": "💾 Save & Next",
        "saved": "✅ Saved",
        "finished": "🎉 All images have been rated!",
        "download_title": "📥 My Rating Data",
        "download": "📤 Download CSV",
        "no_data": "No rating data yet",
        "mos": "MOS 1–5",
        "sharpness": ("Sharpness", "1=Bad, 5=Good"),
        "artifact": ("Artifacts", "1=Many, 5=Few"),
        "naturalness": ("Naturalness", "1=Unrealistic, 5=Realistic"),
        "diagnostic": ("Diagnostic Confidence", "1=Low, 5=High"),
        "image_list": "📋 Image List",
        "total_images": "Total Images",
        "completed_images": "Completed",
        "filter_images": "Filter",
        "all_images": "All",
        "unrated_images": "Unrated",
        "rated_images": "Rated",
        "click_to_select": "Click to select image for rating",
        "method_label": "Method:",
        "selected_image": "Currently Selected:",
    },
}

T = TEXT[LANG]

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")

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

selected_modality = st.selectbox(T["select_modality"], modalities)

# ========= 初始化 SessionState =========
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_institution" not in st.session_state:
    st.session_state.user_institution = ""
if "user_years" not in st.session_state:
    st.session_state.user_years = ""
if "image_filter" not in st.session_state:
    st.session_state.image_filter = "all"  # all, unrated, rated

# ========= 用户信息输入 =========
st.markdown(f"### {T['rater_info']}")
col_name, col_inst, col_years = st.columns(3, gap="medium")

with col_name:
    st.caption(T['name'])  # 小标题
    user_name = st.text_input(
        "",
        value=st.session_state.user_name,
        placeholder=T["name"],
        label_visibility="collapsed",
        key="input_name",
    )
    st.session_state.user_name = user_name

with col_inst:
    st.caption(T['institution'])
    user_institution = st.text_input(
        "",
        value=st.session_state.user_institution,
        placeholder=T["institution"],
        label_visibility="collapsed",
        key="input_institution",
    )
    st.session_state.user_institution = user_institution

with col_years:
    st.caption(T['years'])
    user_years_input = st.text_input(
        "",
        value=st.session_state.user_years,
        placeholder=T["years_placeholder"],
        label_visibility="collapsed",
        key="input_years",
        help=T["years_help"],
    )

# ========= 从业年限校验 =========
user_years = 0.0
if user_years_input.strip():
    if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
        user_years = float(user_years_input)
        user_years = max(0.0, min(80.0, user_years))
        user_years = round(user_years, 1)
    else:
        st.error(T["years_error"])

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
    st.warning(T["name_warn"])
    st.stop()
if not user_institution:
    st.warning(T["inst_warn"])
    st.stop()
if user_years <= 0.0:
    st.warning(T["years_warn"])
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
            image_id = f"{method}_{f}"  # 唯一标识
            image_list.append(
                {
                    "id": image_id,
                    "modality": selected_modality,
                    "method": method,
                    "filename": f,
                    "filepath": os.path.normpath(os.path.join(method_path, f)),
                }
            )

if not image_list:
    st.error(f"❌ 模态 {selected_modality} 下未找到图片！")
    st.stop()

# ========= 获取已评分图像集合 =========
rated_set = set()
if SAVE_FILE and os.path.exists(SAVE_FILE):
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8").fillna("")
    if not df_rated.empty:
        rated_set = set(df_rated["filename"] + "_" + df_rated["method"])

# ========= 筛选图像列表 =========
def filter_images(images, filter_type, rated_set):
    if filter_type == "all":
        return images
    elif filter_type == "rated":
        return [img for img in images if f"{img['filename']}_{img['method']}" in rated_set]
    elif filter_type == "unrated":
        return [img for img in images if f"{img['filename']}_{img['method']}" not in rated_set]
    return images

# ========= 确保当前选中的图像有效 =========
current_image_id = image_list[st.session_state.idx]["id"] if image_list else ""
if st.session_state.idx >= len(image_list) or st.session_state.idx < 0:
    st.session_state.idx = 0

# ========= 主页面布局 =========
st.markdown(
    f"""
    <h2>🧑‍⚕️ {selected_modality} {T['title']}</h2>
    <p style='color:#666;'>
    {user_name}（{user_institution} | {user_years} yrs） | {T['mos']}
    </p>
    """,
    unsafe_allow_html=True,
)

# 进度条
total = len(image_list)
completed = len(rated_set)
progress = completed / total if total > 0 else 0
st.progress(progress, text=f"{T['progress']}：{completed}/{total}（{progress:.1%}）")

# 左右分栏：左侧图像列表，右侧评分区域
col_list, col_main = st.columns([1, 2.5], gap="large")

with col_list:
    st.subheader(T["image_list"])
    st.caption(T["click_to_select"])
    
    # 筛选器
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        st.caption(T["filter_images"])
    with filter_col2:
        image_filter = st.selectbox(
            "",
            [T["all_images"], T["unrated_images"], T["rated_images"]],
            index=["all", "unrated", "rated"].index(st.session_state.image_filter),
            label_visibility="collapsed",
            key="image_filter_select"
        )
        
        # 更新筛选状态
        if image_filter == T["all_images"]:
            st.session_state.image_filter = "all"
        elif image_filter == T["unrated_images"]:
            st.session_state.image_filter = "unrated"
        elif image_filter == T["rated_images"]:
            st.session_state.image_filter = "rated"
    
    st.markdown("---")
    
    # 筛选后的图像列表
    filtered_images = filter_images(image_list, st.session_state.image_filter, rated_set)
    
    # 显示统计信息
    st.caption(f"{T['total_images']}: {len(filtered_images)}")
    st.caption(f"{T['completed_images']}: {len([img for img in filtered_images if f"{img['filename']}_{img['method']}" in rated_set])}")
    
    st.markdown("---")
    
    # 可滚动的图像列表
    with st.container():
        st.markdown('<div class="scrollable-list">', unsafe_allow_html=True)
        
        for i, img_info in enumerate(filtered_images):
            is_rated = f"{img_info['filename']}_{img_info['method']}" in rated_set
            is_selected = img_info["id"] == image_list[st.session_state.idx]["id"]
            
            # 图像缩略图
            try:
                thumbnail = Image.open(img_info["filepath"])
                if thumbnail.mode == "RGBA":
                    thumbnail = thumbnail.convert("RGB")
                # 调整缩略图大小
                thumbnail.thumbnail((150, 100))
            except:
                thumbnail = None
            
            # 图像项容器
            item_class = "image-item"
            if is_selected:
                item_class += " selected"
            if is_rated:
                item_class += " rated"
            
            st.markdown(f'<div class="{item_class}" id="img_{img_info["id"]}">', unsafe_allow_html=True)
            
            # 显示缩略图
            if thumbnail:
                st.image(thumbnail, use_container_width=True, output_format="PNG", caption="", key=f"thumb_{img_info['id']}")
            else:
                st.markdown('<div style="height:80px; background:#f5f5f5; border-radius:4px; display:flex; align-items:center; justify-content:center; color:#999;">📷</div>', unsafe_allow_html=True)
            
            # 显示文件名和方法
            st.markdown(f'<div class="image-filename">{img_info["filename"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="image-method">{T["method_label"]} {img_info["method"]}</div>', unsafe_allow_html=True)
            
            # 显示状态标签
            if is_rated:
                st.markdown('<span style="color:#52c41a; font-size:0.7rem;">✅ 已评分</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="color:#faad14; font-size:0.7rem;">⏳ 未评分</span>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 点击事件：通过按钮模拟（Streamlit没有直接的div点击事件）
            if st.button(
                "select",
                key=f"btn_{img_info['id']}",
                label_visibility="collapsed",
                style={"display": "none"}  # 隐藏实际按钮
            ):
                # 找到原始列表中的索引
                original_idx = next((idx for idx, img in enumerate(image_list) if img["id"] == img_info["id"]), 0)
                st.session_state.idx = original_idx
                st.rerun()
            
            # 添加分隔线
            if i < len(filtered_images) - 1:
                st.markdown('<hr style="margin:8px 0; border-color:#eee;">', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

with col_main:
    # 显示当前选择的图像信息
    current_img = image_list[st.session_state.idx]
    st.markdown(f"<p style='color:#666;'>{T['selected_image']} {current_img['filename']} ({current_img['method']})</p>", unsafe_allow_html=True)
    
    # 检查是否所有图像都已评分
    if completed == total:
        st.success(T["finished"])
        st.balloons()
    else:
        # 加载并显示当前图像
        try:
            img = Image.open(current_img["filepath"])
            if img.mode == "RGBA":
                img = img.convert("RGB")
        except Exception as e:
            st.error(f"❌ 图片加载失败：{current_img['filename']} | {e}")
            # 自动跳转到下一张
            st.session_state.idx = (st.session_state.idx + 1) % len(image_list)
            st.rerun()
        
        # 图像预览区域
        st.subheader(T["preview"])
        st.image(img, caption=current_img["filename"], use_container_width=True)
        st.caption(f"[{st.session_state.idx + 1}/{total}] {T['method_label']} {current_img['method']}")
        
        st.markdown("---")
        
        # 评分区域
        st.subheader(T["score_title"])
        items = [
            ("sharpness", *T["sharpness"]),
            ("artifact", *T["artifact"]),
            ("naturalness", *T["naturalness"]),
            ("diagnostic_confidence", *T["diagnostic"]),
        ]
        ratings = {}
        
        for k, name, desc in items:
            st.markdown(f"**{name}**")
            # 检查是否已评分，如果已评分则显示之前的分数
            default_value = 3
            if SAVE_FILE and os.path.exists(SAVE_FILE):
                df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8").fillna("")
                mask = (df_rated["filename"] == current_img["filename"]) & (df_rated["method"] == current_img["method"])
                if not df_rated[mask].empty:
                    rated_value = df_rated[mask][k].iloc[0]
                    if isinstance(rated_value, (int, float)) and not pd.isna(rated_value):
                        default_value = int(rated_value)
            
            ratings[k] = st.slider(
                " ", 1, 5, default_value, 
                key=f"{k}_{current_img['id']}", 
                label_visibility="collapsed"
            )
            st.caption(desc)
            st.markdown("---")
        
        # 保存按钮
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button(T["save_next"], type="primary", use_container_width=True):
                # 检查是否已存在该图像的评分，如果存在则更新，否则添加
                if SAVE_FILE and os.path.exists(SAVE_FILE):
                    df = pd.read_csv(SAVE_FILE, encoding="utf-8")
                    mask = (df["filename"] == current_img["filename"]) & (df["method"] == current_img["method"])
                    
                    row = {
                        "name": user_name,
                        "institution": user_institution,
                        "years_of_experience": user_years,
                        "modality": current_img["modality"],
                        "method": current_img["method"],
                        "filename": current_img["filename"],
                        **ratings,
                    }
                    
                    if not df[mask].empty:
                        # 更新现有评分
                        df.loc[mask, list(ratings.keys())] = list(ratings.values())
                        df.to_csv(SAVE_FILE, index=False, encoding="utf-8")
                    else:
                        # 添加新评分
                        pd.DataFrame([row]).to_csv(
                            SAVE_FILE, mode="a", header=False, index=False, encoding="utf-8"
                        )
                else:
                    # 保存新评分
                    row = {
                        "name": user_name,
                        "institution": user_institution,
                        "years_of_experience": user_years,
                        "modality": current_img["modality"],
                        "method": current_img["method"],
                        "filename": current_img["filename"],
                        **ratings,
                    }
                    pd.DataFrame([row]).to_csv(SAVE_FILE, mode="a", header=False, index=False, encoding="utf-8")
                
                st.toast(T["saved"], icon="✅")
                
                # 自动跳转到下一张未评分的图像
                next_idx = (st.session_state.idx + 1) % len(image_list)
                current_filter = st.session_state.image_filter
                
                if current_filter == "unrated":
                    # 在未评分列表中找下一张
                    unrated_images = [i for i, img in enumerate(image_list) if f"{img['filename']}_{img['method']}" not in rated_set]
                    if unrated_images:
                        current_pos = unrated_images.index(st.session_state.idx) if st.session_state.idx in unrated_images else -1
                        next_pos = (current_pos + 1) % len(unrated_images)
                        next_idx = unrated_images[next_pos]
                
                st.session_state.idx = next_idx
                st.rerun()

# ========= 数据下载 =========
st.markdown("---")
st.subheader(T["download_title"])
if SAVE_FILE and os.path.exists(SAVE_FILE):
    df = pd.read_csv(SAVE_FILE, encoding="utf-8")
    st.dataframe(df.drop(columns=["method"]), use_container_width=True)
    with open(SAVE_FILE, "rb") as f:
        st.download_button(
            T["download"],
            data=f,
            file_name=os.path.basename(SAVE_FILE),
            mime="text/csv",
            use_container_width=True,
        )
else:
    st.info(T["no_data"])

# ========= 点击列表项的JavaScript处理 =========
st.markdown(
    """
    <script>
    // 为每个图像项添加点击事件
    document.addEventListener('DOMContentLoaded', function() {
        const imageItems = document.querySelectorAll('.image-item');
        imageItems.forEach(item => {
            item.addEventListener('click', function() {
                const imgId = this.id.split('_')[1];
                const button = document.querySelector(`button[data-testid="stButton"][key="btn_${imgId}"]`);
                if (button) {
                    button.click();
                }
            });
        });
    });
    </script>
    """,
    unsafe_allow_html=True,
)
