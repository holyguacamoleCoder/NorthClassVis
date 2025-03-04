import os
import sys
import pandas as pd
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__)) # 获取当前文件的目录
backend_dir = os.path.dirname(current_dir)      # 获取 backend 目录的路径
sys.path.append(backend_dir)                      # 将 tools 目录添加到 sys.path
from tools.fileSystem import load_data, contact_data, merge_data, process_non_numeric_values

# 测试 load_data 函数
@pytest.fixture
def test_csv(tmp_path):
    file_path = tmp_path / "test_data.csv"
    file_path.write_text("id,name\n1,Alice\n2,Bob")
    return file_path
def test_load_data(test_csv):
    df = load_data(test_csv)
    assert isinstance(df, pd.DataFrame)
    assert df.equals(pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}))

# 测试 contact_data 函数
# 创建一个临时的CSV文件用于测试 contact_data
@pytest.fixture
def test_class_list(tmp_path):
    class_list = [{'text': 'Class1', 'checked': True}, {'text': 'Class2', 'checked': False}]
    for class_i in class_list:
        if class_i['checked']:
            file_path = tmp_path / f"SubmitRecord-{class_i['text']}.csv"
            file_path.write_text("id,title_ID\n1,101\n2,102")
    return class_list, tmp_path
# 测试 contact_data 函数
def test_contact_data(test_class_list):
    class_list, tmp_path = test_class_list
    df = contact_data(tmp_path, class_list)
    expected_df = pd.DataFrame({"id": [1, 2], "title_ID": [101, 102]})
    assert df.equals(expected_df)

# 测试 merge_data 函数
@pytest.fixture
def test_csv1(tmp_path):
    file_path = tmp_path / "test_data1.csv"
    file_path.write_text("id,title_ID\n1,101\n2,102")
    return str(file_path)

@pytest.fixture
def test_csv2(tmp_path):
    file_path = tmp_path / "test_data2.csv"
    file_path.write_text("title_ID,knowledge\n101,Math\n102,Science")
    return str(file_path)
def test_merge_data(test_csv1, test_csv2):
    merged_df = merge_data(test_csv1, test_csv2)
    expected_df = pd.DataFrame({
        "id": [1, 2],
        "title_ID": [101, 102],
        "knowledge": ["Math", "Science"]
    })
    assert merged_df.equals(expected_df)

@pytest.fixture
def test_df():
    data = {
        'student_ID': [1, 1, 2, 2],
        'knowledge': ['Math', 'Math', 'Science', 'Science'],
        'timeconsume': [10.0, 10.0, 20.0, 30.0],
        'memory': [100.0, 200.0, 250.0, 300.0]
    }
    return pd.DataFrame(data)
def test_process_non_numeric_values(test_df):
    processed_df = process_non_numeric_values(test_df)
    expected_data = {
        'student_ID': [1, 1, 2, 2],
        'knowledge': ['Math', 'Math', 'Science', 'Science'],
        'timeconsume': [10.0, 10.0, 20.0, 30.0],
        'memory': [100.0, 200.0, 250.0, 300.0]
    }
    expected_df = pd.DataFrame(expected_data)
    assert processed_df.equals(expected_df)