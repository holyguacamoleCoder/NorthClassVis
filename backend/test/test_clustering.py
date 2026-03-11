import sys
import os
import pytest
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__)) # 获取当前文件的目录
backend_dir = os.path.dirname(current_dir)      # 获取 backend 目录的路径
sys.path.append(backend_dir)                      # 将 tools 目录添加到 sys.path
from domain.algorithms.kmeans import MyKMeans
from domain.clustering import ClusterAnalysis

# 示例数据
@pytest.fixture
def students_data():
  data = {
    'student1': {'math': 88, 'science': 92, 'english': 85},
    'student2': {'math': 75, 'science': 80, 'english': 78},
    'student3': {'math': 95, 'science': 90, 'english': 92},
    'student4': {'math': 60, 'science': 65, 'english': 68}
    }
  return data 


# 测试 extract_features 方法
def test_extract_features(students_data):
    cluster_analysis = ClusterAnalysis(students_data)
    features_array = cluster_analysis.extract_features(students_data)
    expected_features = np.array([
        [88, 92, 85],
        [75, 80, 78],
        [95, 90, 92],
        [60, 65, 68]
    ])
    assert np.array_equal(features_array, expected_features)

# 测试 create_cluster_model 方法
def test_create_cluster_model(students_data):
    cluster_analysis = ClusterAnalysis(students_data, n_clusters=2)
    kmeans = cluster_analysis.create_cluster_model(method="kmeans", n_clusters=2)
    assert isinstance(kmeans, MyKMeans)
    assert kmeans.n_clusters == 2

# 测试 get_student_clusters 方法
def test_get_student_clusters(students_data):
    cluster_analysis = ClusterAnalysis(students_data, n_clusters=2)
    student_clusters = cluster_analysis.get_student_clusters()
    assert isinstance(student_clusters, dict)
    assert len(student_clusters) == 4
    for student_id, info in student_clusters.items():
        assert 'knowledge' in info
        assert 'cluster' in info
        assert isinstance(info['cluster'], int)

# 测试 get_cluster_center_students_ID 方法
def test_get_cluster_center_students_ID(students_data):
    cluster_analysis = ClusterAnalysis(students_data, n_clusters=2)
    cluster_center_students = cluster_analysis.get_cluster_center_students_ID()
    assert isinstance(cluster_center_students, list)
    assert len(cluster_center_students) == 2
    for student in cluster_center_students:
        assert 'student_ID' in student
        assert 'cluster' in student
        assert isinstance(student['cluster'], int)

# 测试 get_cluster_centers 方法
def test_get_cluster_centers(students_data):
    cluster_analysis = ClusterAnalysis(students_data, n_clusters=2)
    cluster_centers = cluster_analysis.get_cluster_centers()
    assert isinstance(cluster_centers, dict)
    assert len(cluster_centers) == 2
    for cluster_id, info in cluster_centers.items():
        assert 'cluster' in info
        assert 'knowledge' in info
        assert isinstance(info['cluster'], int)
        assert isinstance(info['knowledge'], dict)