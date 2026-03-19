from flask import Blueprint

from core import data_loader


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.api_bp = Blueprint("api", __name__)
        self.selected_classes = []
        self.majors = []
        self.week_range = None  # [start_week, end_week] 或 None 表示默认最近 16 周
        self.week_extent = (0, 0)  # 缓存当前数据的 (min_week, max_week)
        self.submissions_df = None
        self.submissions_with_knowledge_df = None
        self._observers = []
        self._sync_legacy_fields()
        self.initialize()

    def _sync_legacy_fields(self):
        self.classList = self.selected_classes
        self.class_df_filtered_majors = self.submissions_df
        self.data_with_title_knowledge = self.submissions_with_knowledge_df

    def initialize(self):
        self.selected_classes = ["Class1"]
        student_df = data_loader.load_data(data_loader.STUDENT_INFO_PATH)
        self.majors = student_df["major"].unique().tolist()
        self.submissions_df = data_loader.load_data(data_loader.SUBMISSIONS_FILE_PATH)
        self.set_submissions_with_knowledge_df(self.merge_submissions_with_titles())

    def merge_submissions_with_titles(self):
        return data_loader.process_non_numeric_values(
            data_loader.merge_dataframes_or_files(
                left_df=self.submissions_df,
                right_path=data_loader.TITLE_INFO_PATH,
                right_columns=["title_ID", "knowledge"],
                on="title_ID",
            )
        )

    # Backward-compatible name for legacy code.
    def merge_title_data(self):
        return self.merge_submissions_with_titles()

    def get_api_bp(self):
        return self.api_bp

    def get_submissions_df(self):
        return self.submissions_df

    def get_class_df_filtered_majors(self):
        return self.submissions_df

    def get_class_list(self):
        return self.selected_classes

    def get_majors(self):
        return self.majors

    def get_week_range(self):
        """返回 [start_week, end_week] 或 None（使用默认最近 16 周）。"""
        return self.week_range

    def get_week_extent(self):
        """返回当前配置数据的周范围缓存 (min_week, max_week)。"""
        return self.week_extent

    def set_week_range(self, start_week, end_week):
        self.week_range = [start_week, end_week] if start_week is not None and end_week is not None else None

    def get_submissions_with_knowledge_df(self):
        return self.submissions_with_knowledge_df

    def get_data_with_title_knowledge(self):
        return self.submissions_with_knowledge_df

    def set_class_list(self, class_list):
        self.selected_classes = class_list
        self._sync_legacy_fields()

    def set_majors(self, majors):
        self.majors = majors

    def set_submissions_df(self, submissions_df):
        self.submissions_df = submissions_df
        self._sync_legacy_fields()

    def set_class_df_filtered_majors(self, class_df_filtered_majors):
        self.set_submissions_df(class_df_filtered_majors)

    def set_submissions_with_knowledge_df(self, submissions_with_knowledge_df):
        self.submissions_with_knowledge_df = submissions_with_knowledge_df
        # 延迟导入以避免在模块加载阶段增加依赖链
        from services import week_service
        self.week_extent = week_service.get_week_extent(submissions_with_knowledge_df)
        self._sync_legacy_fields()

    def set_data_with_title_knowledge(self, data_with_title_knowledge):
        self.set_submissions_with_knowledge_df(data_with_title_knowledge)

    def add_observer(self, observer):
        self._observers.append(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.update_data(self)
