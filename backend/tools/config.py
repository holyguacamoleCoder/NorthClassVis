from flask import Blueprint
from tools import fileSystem as fs


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 创建蓝图对象
        self.api_bp = Blueprint('api', __name__)
        # 配置总处理文件类型
        self.classList = []
        self.majors = []
        self.class_df_filtered_majors = None
        self.data_with_title_knowledge = None
        self._observers = []

        self.initialize()

    def initialize(self):
        self.classList = ['Class1']
        self.majors = fs.load_data(fs.studentFilename)['major'].unique().tolist()
        self.class_df_filtered_majors = fs.load_data(fs.classFilename)
        self.data_with_title_knowledge = self.merge_title_data()

    def merge_title_data(self):
        print('merge_title_data')
        return fs.process_non_numeric_values(
            fs.merge_df_or_file(
                df1=self.class_df_filtered_majors, 
                filename2=fs.titleFilename,
                filter_col2=['title_ID', 'knowledge'],
                on='title_ID')
            )

    # Getters
    def get_api_bp(self):
        return self.api_bp

    def get_class_df_filtered_majors(self):
        return self.class_df_filtered_majors

    def get_class_list(self):
        return self.classList
    
    def get_majors(self):
        return self.majors

    def get_data_with_title_knowledge(self):
        return self.data_with_title_knowledge

    # Setters
    def set_class_list(self, class_list):
        self.classList = class_list

    def set_majors(self, majors):
        self.majors = majors

    def set_class_df_filtered_majors(self, class_df_filtered_majors):
        self.class_df_filtered_majors = class_df_filtered_majors
        # self.notify_observers()
    def set_data_with_title_knowledge(self, data_with_title_knowledge):
        self.data_with_title_knowledge = data_with_title_knowledge

    # Observer methods
    def add_observer(self, observer):
        self._observers.append(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.update_data(self)