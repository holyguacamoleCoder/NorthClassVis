import os
import pandas as pd

# 获取数据目录
current_file_dir = os.path.dirname(os.path.abspath(__file__)) # 获取当前文件位置
current_dir = os.path.dirname(current_file_dir)               # 获取当前文件所在目录路径/utils
parent_dir = os.path.dirname(current_dir)                     # 获取当前文件所在目录路径/utils的父目录路径/backend
data_dir = os.path.join(current_dir, '../data/')              # 数据路径

# 获取数据文件
class_dir = os.path.join(data_dir, 'Data_SubmitRecord/')
classFilename = os.path.join(class_dir, 'SubmitRecord-Class1.csv') # 提交记录表格
titleFilename = os.path.join(data_dir, 'Data_TitleInfo.csv')       # 题目信息表格
studentFilename = os.path.join(data_dir, 'Data_StudentInfo.csv')   # 学生信息表格

# 加载数据
def load_data(filename):
    try:
        df = pd.read_csv(filename)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

# 拼接文件为新df
def contact_df(classDir, classList):
    return pd.concat(
        (load_data(os.path.join(classDir,'SubmitRecord-' + class_i + '.csv')) for class_i in classList),
        axis=0)

# 合并数据题目和提交记录
def merge_df_or_file(df1=None, df2=None, filename1=None, filename2=None, on=None, filter_col1=None, filter_col2=None):
    f1 = df1 if df1 is not None else load_data(filename1)
    f2 = df2 if df2 is not None else load_data(filename2)
    f1 = f1[filter_col1] if filter_col1 is not None else f1
    f2 = f2[filter_col2] if filter_col2 is not None else f2
    merged_data = pd.merge(f1, f2, on=on, how='left')
    return merged_data

# 处理非数字值
def process_non_numeric_values(df):
    # 将非数字值转换为NaN
    df['timeconsume'] = pd.to_numeric(df['timeconsume'], errors='coerce')
    df['memory'] = pd.to_numeric(df['memory'], errors='coerce')
    
    # 使用组内平均值填充NaN
    df['timeconsume'] = df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: x.fillna(x.mean()))
    df['memory'] = df.groupby(['student_ID', 'knowledge'])['memory'].transform(lambda x: x.fillna(x.mean()))

    return df

