# ====================== 左侧图像列表 ======================
st.sidebar.subheader(T["image_list"])
image_ids = [f"{img['filename']}_{img['method']}" for img in image_list]

labels = []
for idx, uid in enumerate(image_ids):
    label = f"图像{idx+1}" if LANG=="中文" else f"Image {idx+1}"
    if uid in rated_set: label += " ✅"
    labels.append(label)

# 安全检查 session_state.selected_image_id
if st.session_state.selected_image_id not in image_ids:
    st.session_state.selected_image_id = image_ids[0]

# radio 使用唯一 ID，绑定 session_state
selected_id = st.sidebar.radio(
    T["select_image"],
    options=image_ids,
    format_func=lambda uid: labels[image_ids.index(uid)],
    key="selected_image_id"
)

# 获取选中图像信息
selected_idx = image_ids.index(selected_id)
info = image_list[selected_idx]

# ====================== 保存评分 ======================
submitted = st.form_submit_button(T["save_next"])
if submitted:
    row = {
        "name": st.session_state.user_name,
        "institution": st.session_state.user_institution,
        "years_of_experience": user_years,
        "modality": info["modality"],
        "method": info["method"],
        "filename": info["filename"],
        **ratings
    }

    # 读取 CSV
    if os.path.exists(SAVE_FILE):
        df = pd.read_csv(SAVE_FILE, encoding="utf-8")
    else:
        df = pd.DataFrame(columns=COLUMNS)

    uid = f"{info['filename']}_{info['method']}"
    existing_uids = (df["filename"] + "_" + df["method"]).values
    if uid in existing_uids:
        idx = df.index[df["filename"] + "_" + df["method"] == uid][0]
        for col in ratings:
            df.at[idx, col] = ratings[col]
        df.at[idx, "name"] = st.session_state.user_name
        df.at[idx, "institution"] = st.session_state.user_institution
        df.at[idx, "years_of_experience"] = user_years
    else:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    df.to_csv(SAVE_FILE, index=False, encoding="utf-8")
    st.toast(T["saved"], icon="✅")
