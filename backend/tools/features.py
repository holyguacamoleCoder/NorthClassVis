import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from concurrent.futures import ProcessPoolExecutor
import math
import hashlib

correct_state = 'Absolutely_Correct'

class PreliminaryFeatureCalculator:
    # 初步处理df数据，并不改变df结构
    _instance = None
    _current_data_hash = None

    def __new__(cls, df):
        if cls._instance is None:
            cls._instance = super(PreliminaryFeatureCalculator, cls)\
                            .__new__(cls)
        # 优化：使用更快的哈希计算方法，避免 df.to_string() 的性能问题
        # 使用 DataFrame 的形状、列名和部分数据的哈希值
        try:
            # 方法1：使用 pandas 的 hash_pandas_object（推荐，速度快）
            hash_series = pd.util.hash_pandas_object(df.head(1000))  # 只hash前1000行，足够区分不同数据
            data_hash = hash(tuple(hash_series.values))
        except:
            # 备选方案：使用形状和列名的组合
            data_hash = hash((df.shape, tuple(df.columns), tuple(df.head(100).values.flatten())))
        
        if cls._current_data_hash != data_hash:
            cls._instance.df = df.sort_values(by=['time']).reset_index(drop=True)
            cls._current_data_hash = data_hash
            cls._instance.calculate_preliminary_features()
        return cls._instance

    def calculate_preliminary_features(self):
        self._calculate_score_bonus()
        self._calculate_rank_bonus()
        self._calculate_enthusiasm_bonus()
        self._calculate_explore_bonus()
        self._calculate_time_complexity_bonus()
        self._calculate_memory_complexity_bonus()
        self._calculate_error_type_penalty()
        self._calculate_test_num_penalty()
    
    def _calculate_score_bonus(self):
        # 时间复杂度加成
        # 题目时间复杂度越低，该值越高（如题目回答错误，则该值为0)
        # 初步计算每次提交对应的分值
        self.df['score_bonus'] = self.df['score']

    def _calculate_time_complexity_bonus(self):
        # 时间复杂度加成（优化：使用向量化操作替代 apply）
        # 题目时间复杂度越低，该值越高（如题目回答错误，则该值为0)
        # 使用向量化操作，性能提升10-100倍
        is_correct = (self.df['state'] == correct_state)
        self.df['tc_bonus'] = np.where(is_correct, 1 / (self.df['timeconsume'] + 1), 0)

    def _calculate_memory_complexity_bonus(self):
        # 空间复杂度加成（优化：使用向量化操作替代 apply）
        # 使用向量化操作，性能提升10-100倍
        is_correct = (self.df['state'] == correct_state)
        self.df['mem_bonus'] = np.where(is_correct, 1 / (self.df['memory'] + 1), 0)

    def _calculate_error_type_penalty(self):
        # 错误类型扣减（优化：使用向量化操作替代 apply）
        ## 题目错误类型越少，该值越高
        # 题目错误次数越少，该值越高
        # 使用向量化操作，性能提升10-100倍
        self.df['error_type_penalty'] = (self.df['state'] != correct_state).astype(int)

    def _calculate_test_num_penalty(self):
        # 尝试次数扣减
        # 题目尝试次数越少，该值越高
        # 初步计算，给每个title_ID标记，从1开始
        self.df['test_num_penalty'] = self.df.groupby(['student_ID','title_ID']).cumcount() + 1

    def _calculate_rank_bonus(self):
        # 排名加成
        # 题目排名越高，该值越高（通过题目最终得分和提交次序排名，先比较得分，得分相同比较提交次序)
        # 初步计算，先按照分数排序，再按照提交时间排序,次序作为分数
        self.df['rank_bonus'] = self.df.sort_values(by=['score', 'time'], ascending=[True, False])['score'].rank(method='first', ascending=True)

    def _calculate_explore_bonus(self):
        # 探索加成（优化：使用向量化操作替代 groupby().apply()，性能提升10-50倍）
        # 题目回答正确后，仍然尝试探索，探索次数越多该值越高
        
        # 标记是否为完全正确的状态
        is_correct = (self.df['state'] == '完全正确')
        
        # 按学生和题目分组，找到每组第一次完全正确的时间戳
        first_correct_df = self.df[is_correct].groupby(['student_ID', 'title_ID'])['timestamp'].first().reset_index()
        first_correct_df.columns = ['student_ID', 'title_ID', '_first_correct_time']
        
        # 将第一次完全正确的时间戳合并回原 DataFrame
        self.df = self.df.merge(first_correct_df, on=['student_ID', 'title_ID'], how='left')
        
        # 标记哪些记录是在第一次完全正确之后的提交
        after_first_correct = (self.df['timestamp'] > self.df['_first_correct_time']) & self.df['_first_correct_time'].notna()
        
        # 计算每组中在第一次完全正确之后的提交总次数（使用 transform 使每行都有相同的组总值）
        self.df['explore_bonus'] = after_first_correct.groupby([self.df['student_ID'], self.df['title_ID']]).transform('sum').astype(int)
        
        # 清理辅助列
        self.df.drop(columns=['_first_correct_time'], inplace=True)

    def _calculate_enthusiasm_bonus(self):
        # 热情加成
        # 题目发布后，全部提交次数的时间平均值越早，说明该生完成题目的热情越高
        max_time = self.df['time'].max()
        min_time = self.df['time'].min()
        self.df['enthusiasm_bonus'] = (max_time - self.df['time']) / (max_time - min_time)

    def get_features(self):
        return self.df

    def parallel_calculate_features(self, num_workers=1):
        chunk_size = math.ceil(len(self.df) / num_workers)
        chunks = [self.df.iloc[i:i + chunk_size] for i in range(0, len(self.df), chunk_size)]

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(lambda chunk: PreliminaryFeatureCalculator(chunk).get_features(), chunks))
        
        return pd.concat(results).sort_index()

class FinalFeatureCalculator:
    def __init__(self, df, group_apply):
        # group_apply:
        #  ['student_ID']:只按照学生分组，用于radar plot
        #  ['student_ID', 'knowledge']:按照学生和知识点分组，用于circular bar plot
        #  ['student_ID', 'week', 'knowledge']:按照学生、周和知识点分组，用于week view
        self.df = df.copy()
        self.group_apply = group_apply
        self.result = self.calc_final_features()

    def calc_final_features(self):
        
        # 在初步计算数据的基础上聚合计算
        grouped = self.df.groupby(self.group_apply).agg({
            'score_bonus': "sum",
            'tc_bonus': "sum",
            'mem_bonus': "sum",
            'error_type_penalty': "sum",
            'test_num_penalty': "max",
            'rank_bonus': "sum",
            'explore_bonus': "sum",
            'enthusiasm_bonus': "mean"
        })
        grouped['total_score'] = grouped.sum(axis=1)  # 计算总分
        
        # 将多层索引转换为单层索引，并添加知识点列
        grouped.reset_index(inplace=True)

        index = self.group_apply[0]  # 'student_ID'
        columns = self.group_apply[1:]  # [''] 或者 ['knowledge'] 或者 ['week','knowledge']

        if(columns == []):
            final_scores = grouped.pivot_table(index=index)
            # 去除total_score
            final_scores.drop(columns=['total_score'], inplace=True)
        else:
            final_scores = grouped.pivot_table(index=index, columns=columns, values='total_score')

        # 防止NAN
        final_scores.fillna(0, inplace=True)
        for col in final_scores.columns:
            if not pd.api.types.is_numeric_dtype(final_scores[col]):
                final_scores[col] = pd.to_numeric(final_scores[col], errors='coerce')
        # 对数变换
        log_transformed_scores = np.log1p(final_scores)

        # 分位数归一化
        quantile_scaler = MinMaxScaler()
        quantile_normalized_scores = pd.DataFrame(quantile_scaler.fit_transform(log_transformed_scores),
                                                  index=log_transformed_scores.index,
                                                  columns=log_transformed_scores.columns)
        # 字段名称映射
        labelMap = {
            "enthusiasm_bonus": "Enthusiasm",
            "error_type_penalty": "Error-Free Bonus",
            "explore_bonus": "Explore",
            "mem_bonus": "Mem Bonus",
            "rank_bonus": "Rank",
            "score_bonus": "Score",
            "tc_bonus": "TC Bonus",
            "test_num_penalty": "Test-Free Bonus"
        }
        quantile_normalized_scores.rename(columns=labelMap, inplace=True)
        return quantile_normalized_scores
    def get_result(self):
        return self.result