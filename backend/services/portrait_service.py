def get_cluster_everyone(feature_factory):
    student_clusters = feature_factory.cluster_analysis.get_student_clusters()
    return {student_id: data["cluster"] for student_id, data in student_clusters.items()}


def get_cluster_center_students(feature_factory):
    target_students = feature_factory.cluster_analysis.get_cluster_center_students_ID()
    result = {}
    for student_info in target_students:
        student_id = student_info["student_ID"]
        cluster_index = student_info["cluster"]
        knowledge = feature_factory.feature_knowledge.loc[student_id].to_dict()
        bonus = feature_factory.feature_bonus.loc[student_id].to_dict()
        result[student_id] = {
            "cluster": cluster_index,
            "knowledge": knowledge,
            "bonus": bonus,
        }
    return result


def get_display_students(feature_factory, student_ids):
    result = {}
    for student_id in student_ids:
        try:
            knowledge = feature_factory.feature_knowledge.loc[student_id].to_dict()
            bonus = feature_factory.feature_bonus.loc[student_id].to_dict()
            result[student_id] = {
                "knowledge": knowledge,
                "bonus": bonus,
            }
        except KeyError:
            result[student_id] = {"error": f"Student ID {student_id} not found."}
    return result
