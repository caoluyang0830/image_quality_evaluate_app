import streamlit as st
from PIL import Image
import os
import pandas as pd
import warnings
import re

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

st.set_page_config(
    page_title="图像多指标主观评分系统",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========= 语言选择 =========
# 语言选择放在前面，避免切换语言后状态异常
if "LANG" not in st.session_state:
    st.session_state["LANG"] = "中文"

def update_lang():
    st.session_state["selected_image_idx"] = 0  # 切换语言时重置图像选择索引

LANG = st.selectbox("🌐 Language / 语言", ["中文", "English"], 
                   index=0 if st.session_state["LANG"] == "中文" else 1,
                   on_change=update_lang)
st.session_state["LANG"] = LANG

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
        "save_next": "💾 保存评分并下一张",
        "save_only": "💾 仅保存",
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
        "modality_select": "选择模态 / Select Modality",
        "image_load_fail": "图片加载失败",
        "no_modalities": "未找到任何模态文件夹",
        "go_next": "前往下一张",
        "go_prev": "返回上一张"
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
        "save_next": "💾 Save & Next",
        "save_only": "💾 Save Only",
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
        "modality_select": "Select Modality / 选择模态",
        "image_load_fail": "Image load failed",
        "no_modalities": "No modality folders found",
        "go_next": "Go to next",
        "go_prev": "Go to previous"
    }
}

T = TEXT[LANG]

# ========= 路径配置 =========
IMAGE_ROOT = os.path.normpath("resultselect")
if not os.path.exists(IMAGE_ROOT):
    st.error(f"❌ {T['image_load_fail']}: {IMAGE_ROOT}")
    st.stop()

# ========= 模态选择 =========
modalities = [m for m in sorted(os.listdir(IMAGE_ROOT)) if os.path.isdir(os.path.join(IMAGE_ROOT, m))]
if not modalities:
    st.error(f"❌ {T['no_modalities']}")
    st.stop()

# 初始化模态选择状态
if "selected_modality" not in st.session_state:
    st.session_state["selected_modality"] = modalities[0]

def update_modality():
    st.session_state["selected_image_idx"] = 0  # 切换模态时重置图像选择索引

selected_modality = st.selectbox(T["modality_select"], modalities,
                               index=modalities.index(st.session_state["selected_modality"]),
                               on_change=update_modality)
st.session_state["selected_modality"] = selected_modality

# ========= 初始化 SessionState =========
required_keys = ["user_name", "user_institution", "user_years", "selected_image_idx"]
for key in required_keys:
    if key not in st.session_state:
        st.session_state[key] = "" if "user" in key else 0

# ========= 用户信息输入 =========
st.markdown(f"### {T['rater_info']}")
col_name, col_inst, col_years = st.columns(3, gap="medium")
with col_name:
    st.caption(T['name'])
    user_name = st.text_input("name_input", value=st.session_state.user_name, 
                             placeholder=T["name"], label_visibility="collapsed")
    st.session_state.user_name = user_name.strip()  # 去除前后空格
with col_inst:
    st.caption(T['institution'])
    user_institution = st.text_input("inst_input", value=st.session_state.user_institution, 
                                    placeholder=T["institution"], label_visibility="collapsed")
    st.session_state.user_institution = user_institution.strip()  # 去除前后空格
with col_years:
    st.caption(T['years'])
    user_years_input = st.text_input("years_input", value=st.session_state.user_years, 
                                    placeholder=T["years_placeholder"], label_visibility="collapsed", 
                                    help=T["years_help"])

# ========= 从业年限校验 =========
user_years = 0.0
years_error = False
if user_years_input.strip():
    if re.match(r'^-?\d+(\.\d+)?$', user_years_input):
        user_years = float(user_years_input)
        if user_years < 0 or user_years > 80:
            st.error(T["years_error"])
            years_error = True
        else:
            user_years = round(user_years, 1)
    else:
        st.error(T["years_error"])
        years_error = True
st.session_state.user_years = str(user_years) if user_years > 0 else ""

# ========= 用户信息校验 =========
valid_user_info = True
if not st.session_state.user_name:
    st.warning(T["name_warn"])
    valid_user_info = False
if not st.session_state.user_institution:
    st.warning(T["inst_warn"])
    valid_user_info = False
if years_error or user_years <= 0.0:
    st.warning(T["years_warn"])
    valid_user_info = False

if not valid_user_info:
    st.stop()

# ========= 用户专属 CSV =========
def sanitize_filename(name):
    """安全处理文件名，避免特殊字符问题"""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip() or "unknown_user"

SAVE_FILE = os.path.normpath(f"{sanitize_filename(selected_modality)}_{sanitize_filename(st.session_state.user_name)}_ratings.csv")
COLUMNS = ["name", "institution", "years_of_experience", "modality", "method", 
          "filename", "sharpness", "artifact", "naturalness", "diagnostic_confidence",
          "rating_time"]  # 增加评分时间列

# 确保CSV文件存在且格式正确
if not os.path.exists(SAVE_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")  # 使用utf-8-sig支持中文
else:
    # 检查CSV列是否完整
    try:
        df_existing = pd.read_csv(SAVE_FILE, encoding="utf-8-sig")
        missing_cols = [col for col in COLUMNS if col not in df_existing.columns]
        if missing_cols:
            # 添加缺失的列
            for col in missing_cols:
                df_existing[col] = "" if col == "rating_time" else 0
            df_existing.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")
    except Exception as e:
        st.error(f"❌ CSV文件损坏，正在创建新文件: {e}")
        pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")

# ========= 加载图像列表 =========
image_list = []
modality_path = os.path.join(IMAGE_ROOT, selected_modality)
try:
    for method in sorted(os.listdir(modality_path)):
        method_path = os.path.join(modality_path, method)
        if not os.path.isdir(method_path):
            continue
        # 获取所有支持的图片格式
        for f in sorted(os.listdir(method_path)):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff")):
                filepath = os.path.join(method_path, f)
                # 检查文件是否可读
                if os.path.getsize(filepath) > 0:
                    image_list.append({
                        "modality": selected_modality,
                        "method": method,
                        "filename": f,
                        "filepath": filepath
                    })
except Exception as e:
    st.error(f"❌ 读取图像列表失败: {e}")
    st.stop()

if not image_list:
    st.error(f"❌ {T['no_data']} in {selected_modality}!")
    st.stop()

# 确保选中的图像索引有效
if st.session_state.selected_image_idx >= len(image_list):
    st.session_state.selected_image_idx = 0

# ========= 已评分集合 =========
try:
    df_rated = pd.read_csv(SAVE_FILE, encoding="utf-8-sig")
    # 清理无效数据
    df_rated = df_rated.dropna(subset=["filename", "method"])
    rated_set = set(df_rated["filename"] + "_" + df_rated["method"])
except Exception as e:
    st.warning(f"⚠️ 读取已评分数据失败，重新开始: {e}")
    rated_set = set()
    pd.DataFrame(columns=COLUMNS).to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")

# ========= 左侧图像列表 =========
st.sidebar.subheader(T["image_list"])
labels = []
for idx, img_info in enumerate(image_list):
    uid = f"{img_info['filename']}_{img_info['method']}"
    label = f"图像{idx+1}" if LANG == "中文" else f"Image {idx+1}"
    label += f" - {img_info['method']}"  # 显示方法名称
    if uid in rated_set:
        label += " ✅"
    labels.append(label)

# 图像选择单选框
selected_label = st.sidebar.radio(
    T["select_image"],
    labels,
    index=st.session_state.selected_image_idx,
    key="selected_image_idx"
)

# 获取当前选择的图像信息
current_idx = st.session_state.selected_image_idx
if 0 <= current_idx < len(image_list):
    info = image_list[current_idx]
else:
    info = image_list[0]
    st.session_state.selected_image_idx = 0

# ========= 导航按钮 =========
def go_prev():
    if st.session_state.selected_image_idx > 0:
        st.session_state.selected_image_idx -= 1

def go_next():
    if st.session_state.selected_image_idx < len(image_list) - 1:
        st.session_state.selected_image_idx += 1

col_prev, col_next = st.sidebar.columns(2)
with col_prev:
    st.button(T["go_prev"], on_click=go_prev, disabled=current_idx == 0)
with col_next:
    st.button(T["go_next"], on_click=go_next, disabled=current_idx == len(image_list) - 1)

# ========= 主界面 =========
st.markdown(f"<h2>🧑‍⚕️ {selected_modality} - {T['title']}</h2>", unsafe_allow_html=True)
progress_val = len(rated_set) / len(image_list) if image_list else 0
st.progress(progress_val, text=f"{T['progress']}：{len(rated_set)}/{len(image_list)} ({progress_val:.1%})")

# 检查是否所有图像都已评分
if len(rated_set) == len(image_list) and len(image_list) > 0:
    st.success(T["finished"], icon="🎉")

# 加载并显示图像
img = None
try:
    img = Image.open(info["filepath"]).convert("RGB")
except Exception as e:
    st.error(f"❌ {T['image_load_fail']}: {info['filename']} | {str(e)[:100]}")
    # 移除损坏的图像
    st.warning(f"⚠️ 移除损坏的图像: {info['filename']}")
    image_list.pop(current_idx)
    if current_idx >= len(image_list) and len(image_list) > 0:
        st.session_state.selected_image_idx = len(image_list) - 1
    st.rerun()

# 主内容布局
col1, col2 = st.columns([3, 4], gap="large")
with col1:
    st.subheader(T["preview"])
    if img:
        # 优化图像显示，限制最大高度
        max_height = 600
        if img.height > max_height:
            scale = max_height / img.height
            new_width = int(img.width * scale)
            img_resized = img.resize((new_width, max_height))
            st.image(img_resized, caption=f"{labels[current_idx]} ({info['filename']})", use_container_width=True)
        else:
            st.image(img, caption=f"{labels[current_idx]} ({info['filename']})", use_container_width=True)
    st.caption(f"{current_idx + 1}/{len(image_list)} | {T['select_image']}: {info['method']}")

with col2:
    st.subheader(T["score_title"])
    # 评分表单
    with st.form("rating_form", clear_on_submit=False):
        items = [
            {"key": "sharpness", "name": T['sharpness'][0], "desc": T['sharpness'][1]},
            {"key": "artifact", "name": T['artifact'][0], "desc": T['artifact'][1]},
            {"key": "naturalness", "name": T['naturalness'][0], "desc": T['naturalness'][1]},
            {"key": "diagnostic_confidence", "name": T['diagnostic'][0], "desc": T['diagnostic'][1]},
        ]
        
        ratings = {}
        # 检查是否已有评分，加载历史评分
        uid = f"{info['filename']}_{info['method']}"
        initial_values = {}
        
        if uid in rated_set and 'df_rated' in locals():
            try:
                rated_row = df_rated[(df_rated["filename"] == info["filename"]) & 
                                   (df_rated["method"] == info["method"])].iloc[0]
                for item in items:
                    initial_values[item['key']] = rated_row[item['key']] if item['key'] in rated_row else 3
            except:
                initial_values = {item['key']: 3 for item in items}
        else:
            initial_values = {item['key']: 3 for item in items}
        
        # 创建评分滑块
        for item in items:
            st.markdown(f"**{item['name']}**")
            key = f"rating_{item['key']}_{current_idx}"
            ratings[item['key']] = st.slider(
                item['key'],
                min_value=1,
                max_value=5,
                value=initial_values[item['key']],
                key=key,
                label_visibility="collapsed"
            )
            st.caption(item['desc'])
            st.markdown("---")
        
        # 表单按钮
        col_save, col_save_next = st.columns(2)
        with col_save:
            submit_save = st.form_submit_button(T["save_only"])
        with col_save_next:
            submit_save_next = st.form_submit_button(T["save_next"])
        
        # 处理表单提交
        if submit_save or submit_save_next:
            from datetime import datetime
            
            # 构建评分数据
            row = {
                "name": st.session_state.user_name,
                "institution": st.session_state.user_institution,
                "years_of_experience": user_years,
                "modality": info["modality"],
                "method": info["method"],
                "filename": info["filename"],
                "rating_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **ratings
            }
            
            # 读取现有数据
            try:
                df = pd.read_csv(SAVE_FILE, encoding="utf-8-sig")
            except:
                df = pd.DataFrame(columns=COLUMNS)
            
            # 检查是否已存在该图像的评分
            uid = f"{info['filename']}_{info['method']}"
            existing_mask = (df["filename"] == info["filename"]) & (df["method"] == info["method"])
            
            if existing_mask.any():
                # 更新现有评分
                df.loc[existing_mask, :] = pd.Series(row)
            else:
                # 添加新评分
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            
            # 保存数据
            try:
                df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")
                st.toast(T["saved"], icon="✅")
                
                # 更新已评分集合
                rated_set.add(uid)
                
                # 如果是保存并下一张，且不是最后一张
                if submit_save_next and current_idx < len(image_list) - 1:
                    st.session_state.selected_image_idx += 1
                    st.rerun()
            except Exception as e:
                st.error(f"❌ 保存失败: {e}")

# ========= 数据下载 =========
st.markdown("---")
st.subheader(T["download_title"])

try:
    df_download = pd.read_csv(SAVE_FILE, encoding="utf-8-sig")
    if not df_download.empty:
        # 显示数据预览（可选显示method列）
        show_method = st.checkbox("显示方法列 / Show Method Column", value=False)
        display_cols = df_download.columns.tolist()
        if not show_method and "method" in display_cols:
            display_cols.remove("method")
        
        st.dataframe(df_download[display_cols], use_container_width=True, height=300)
        
        # 下载按钮
        with open(SAVE_FILE, "rb") as f:
            st.download_button(
                label=T["download"],
                data=f,
                file_name=os.path.basename(SAVE_FILE),
                mime="text/csv",
                use_container_width=True
            )
        
        # 显示统计信息
        st.markdown(f"### 📈 统计信息 / Statistics")
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric("总图像数 / Total Images", len(image_list))
        with col_stats2:
            st.metric("已评分 / Rated", len(rated_set))
        with col_stats3:
            st.metric("完成率 / Completion", f"{progress_val:.1%}")
    else:
        st.info(T["no_data"])
except Exception as e:
    st.error(f"❌ 读取评分数据失败: {e}")
    st.info(T["no_data"])
