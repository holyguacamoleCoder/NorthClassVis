# ------------学生服务部分----------------


def build_student_tree(df, student_info):
    root = {"name": "Root", "children": []}
    students = df["student_ID"].unique()

    for student in students:
        student_data = df[df["student_ID"] == student]
        major = student_info[student_info["student_ID"] == student]["major"].iloc[0]

        student_node = {
            "name": str(student),
            "class": student_data["class"].iloc[0],
            "major": major,
            "children": [],
        }

        titles = student_data["title_ID"].unique()
        for title in titles:
            title_data = student_data[student_data["title_ID"] == title]
            title_node = {"name": str(title), "children": []}

            states = title_data["state"].unique()
            for state in states:
                state_data = title_data[title_data["state"] == state]
                state_node = {
                    "name": state,
                    "times": len(state_data),
                    "value": int(state_data["score"].max()),
                }
                title_node["children"].append(state_node)

            if title_node["children"]:
                student_node["children"].append(title_node)

        if student_node["children"]:
            root["children"].append(student_node)

    return root


def transform_data(df, student_info):
    return build_student_tree(df, student_info)
