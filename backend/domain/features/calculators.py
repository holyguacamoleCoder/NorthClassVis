"""
特征计算：初步特征与最终聚合特征。
PreliminaryFeatureCalculator 为单例 + 按数据哈希失效；FinalFeatureCalculator 按分组键聚合。
"""
import math
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

# 提交「完全正确」状态，用于加成/扣减判断
CORRECT_SUBMISSION_STATE = "Absolutely_Correct"
correct_state = CORRECT_SUBMISSION_STATE  # 兼容旧名

FEATURE_LABEL_MAP = {
    "enthusiasm_bonus": "Enthusiasm",
    "error_type_penalty": "Error-Free Bonus",
    "explore_bonus": "Explore",
    "mem_bonus": "Mem Bonus",
    "rank_bonus": "Rank",
    "score_bonus": "Score",
    "tc_bonus": "TC Bonus",
    "test_num_penalty": "Test-Free Bonus",
}


class PreliminaryFeatureCalculator:
    """初步处理 df，不改变行结构，仅增加特征列。单例 + 按数据哈希失效。"""
    _instance = None
    _current_data_hash = None

    def __new__(cls, df):
        if cls._instance is None:
            cls._instance = super(PreliminaryFeatureCalculator, cls).__new__(cls)
        try:
            hash_series = pd.util.hash_pandas_object(df.head(1000))
            data_hash = hash(tuple(hash_series.values))
        except Exception:
            data_hash = hash((df.shape, tuple(df.columns), tuple(df.head(100).values.flatten())))
        if cls._current_data_hash != data_hash:
            cls._instance.df = df.sort_values(by=["time"]).reset_index(drop=True)
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
        self.df["score_bonus"] = self.df["score"]

    def _calculate_time_complexity_bonus(self):
        is_correct = self.df["state"] == correct_state
        self.df["tc_bonus"] = np.where(is_correct, 1 / (self.df["timeconsume"] + 1), 0)

    def _calculate_memory_complexity_bonus(self):
        is_correct = self.df["state"] == correct_state
        self.df["mem_bonus"] = np.where(is_correct, 1 / (self.df["memory"] + 1), 0)

    def _calculate_error_type_penalty(self):
        self.df["error_type_penalty"] = (self.df["state"] != correct_state).astype(int)

    def _calculate_test_num_penalty(self):
        self.df["test_num_penalty"] = self.df.groupby(["student_ID", "title_ID"]).cumcount() + 1

    def _calculate_rank_bonus(self):
        time_max = self.df["time"].max()
        time_min = self.df["time"].min()
        time_range = time_max - time_min if time_max != time_min else 1
        sort_key = self.df["score"].values + (
            1 - (self.df["time"].values - time_min) / time_range
        ) * 0.000001
        self.df["rank_bonus"] = pd.Series(sort_key, index=self.df.index).rank(
            method="first", ascending=True
        )

    def _calculate_explore_bonus(self):
        is_correct = (self.df["state"] == "完全正确") | (
            self.df["state"] == "Absolutely_Correct"
        )
        first_correct_df = (
            self.df[is_correct]
            .groupby(["student_ID", "title_ID"])["time"]
            .first()
            .reset_index()
        )
        first_correct_df.columns = ["student_ID", "title_ID", "_first_correct_time"]
        self.df = self.df.merge(first_correct_df, on=["student_ID", "title_ID"], how="left")
        after_first_correct = (
            (self.df["time"] > self.df["_first_correct_time"])
            & self.df["_first_correct_time"].notna()
        )
        self.df["explore_bonus"] = (
            after_first_correct.groupby([self.df["student_ID"], self.df["title_ID"]])
            .transform("sum")
            .astype(int)
        )
        self.df.drop(columns=["_first_correct_time"], inplace=True)

    def _calculate_enthusiasm_bonus(self):
        max_time = self.df["time"].max()
        min_time = self.df["time"].min()
        self.df["enthusiasm_bonus"] = (max_time - self.df["time"]) / (max_time - min_time)

    def get_features(self):
        return self.df

    def parallel_calculate_features(self, num_workers=1):
        chunk_size = math.ceil(len(self.df) / num_workers)
        chunks = [
            self.df.iloc[i : i + chunk_size]
            for i in range(0, len(self.df), chunk_size)
        ]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = list(
                executor.map(
                    lambda chunk: PreliminaryFeatureCalculator(chunk).get_features(),
                    chunks,
                )
            )
        return pd.concat(results).sort_index()


class FinalFeatureCalculator:
    """在初步特征基础上按分组键聚合，并做对数变换与归一化。"""

    def __init__(self, df, group_apply):
        # group_apply: ['student_ID'] | ['student_ID','knowledge'] | ['student_ID','week','knowledge']
        self.df = df  # 不 copy：calc_final_features 只读 groupby，不修改 df
        self.group_apply = group_apply
        self.result = self.calc_final_features()

    def calc_final_features(self):
        grouped = self.df.groupby(self.group_apply).agg({
            "score_bonus": "sum",
            "tc_bonus": "sum",
            "mem_bonus": "sum",
            "error_type_penalty": "sum",
            "test_num_penalty": "max",
            "rank_bonus": "sum",
            "explore_bonus": "sum",
            "enthusiasm_bonus": "mean",
        })
        grouped["total_score"] = grouped.sum(axis=1)
        grouped.reset_index(inplace=True)

        index = self.group_apply[0]
        columns = self.group_apply[1:]

        if not columns:
            final_scores = grouped.pivot_table(index=index)
            final_scores.drop(columns=["total_score"], inplace=True)
        else:
            final_scores = grouped.pivot_table(
                index=index, columns=columns, values="total_score"
            )

        final_scores.fillna(0, inplace=True)
        for col in final_scores.columns:
            if not pd.api.types.is_numeric_dtype(final_scores[col]):
                final_scores[col] = pd.to_numeric(final_scores[col], errors="coerce")
        # 内存友好：float32 + 单数组复用，减少 pivot/log/缩放 的中间大对象
        index = final_scores.index
        columns = final_scores.columns
        X = np.log1p(final_scores.values).astype(np.float32)
        del final_scores  # 尽早释放，便于 GC
        min_ = X.min(axis=0)
        max_ = X.max(axis=0)
        den = np.where(max_ - min_ == 0, 1, max_ - min_)
        X -= min_
        X /= den
        result = pd.DataFrame(X, index=index, columns=columns)
        result.rename(columns=FEATURE_LABEL_MAP, inplace=True)
        return result

    def get_result(self):
        return self.result


__all__ = [
    "CORRECT_SUBMISSION_STATE",
    "FEATURE_LABEL_MAP",
    "PreliminaryFeatureCalculator",
    "FinalFeatureCalculator",
    "correct_state",
]
