def get_cluster_everyone(feature_factory):
    student_clusters = feature_factory.cluster_analysis.get_student_clusters()
    return {student_id: data["cluster"] for student_id, data in student_clusters.items()}


def _valid_portrait_student_ids(feature_factory) -> set[str]:
    knowledge_index = {str(i) for i in feature_factory.feature_knowledge.index}
    bonus_index = {str(i) for i in feature_factory.feature_bonus.index}
    return knowledge_index & bonus_index


def _fallback_representative(
    feature_factory,
    cluster_index: int,
    valid_ids: set[str],
) -> str | None:
    """Pick any cluster member that has portrait feature rows."""
    clusters = feature_factory.cluster_analysis.get_student_clusters()
    for student_id, info in clusters.items():
        if int(info["cluster"]) != int(cluster_index):
            continue
        sid = str(student_id)
        if sid in valid_ids:
            return sid
    return None


def get_cluster_center_students(feature_factory):
    valid_ids = _valid_portrait_student_ids(feature_factory)
    target_students = feature_factory.cluster_analysis.get_cluster_center_students_ID(
        valid_student_ids=valid_ids,
    )
    result = {}
    for student_info in target_students:
        student_id = str(student_info["student_ID"])
        cluster_index = student_info["cluster"]
        if student_id not in valid_ids:
            alt = _fallback_representative(feature_factory, cluster_index, valid_ids)
            if alt is None:
                continue
            student_id = alt
        try:
            knowledge = feature_factory.feature_knowledge.loc[student_id].to_dict()
            bonus = feature_factory.feature_bonus.loc[student_id].to_dict()
        except KeyError:
            continue
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
