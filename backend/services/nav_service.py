from core import data_loader


def apply_nav_config(config, classes, majors, week_range=None):
    contacted_df = data_loader.load_submissions_by_classes(
        data_loader.SUBMISSIONS_DIR,
        classes,
    )
    merged_df = data_loader.merge_dataframes_or_files(
        left_df=contacted_df,
        right_path=data_loader.STUDENT_INFO_PATH,
        on="student_ID",
        right_columns=["student_ID", "major"],
    )
    filtered_df = merged_df[merged_df["major"].isin(majors)]

    config.set_class_list(classes)
    config.set_majors(majors)
    config.set_submissions_df(filtered_df)
    config.set_submissions_with_knowledge_df(config.merge_submissions_with_titles())

    if week_range is not None and isinstance(week_range, list) and len(week_range) >= 2:
        start_w, end_w = int(week_range[0]), int(week_range[1])
        min_w, max_w = config.get_week_extent()
        if start_w <= end_w and min_w <= start_w and end_w <= max_w:
            config.set_week_range(start_w, end_w)
        else:
            config.set_week_range(None, None)

    config.notify_observers()
