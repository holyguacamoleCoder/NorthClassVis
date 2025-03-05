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
        self.all_class_df = None
        self.merged_process_data = None

        self.initialize()

    def initialize(self):
        self.classList = ['Class1']
        self.majors = fs.load_data(fs.studentFilename)['major'].unique().tolist()
        self.all_class_df = fs.load_data(fs.classFilename)
        self.merged_process_data = self.merge_process_data()

    def merge_process_data(self):
        return fs.process_non_numeric_values(
            fs.merge_df_or_file(
                df1=self.all_class_df, 
                filename2=fs.titleFilename,
                filter_col2=['title_ID', 'knowledge'],
                on='title_ID')
            )

    # Getters
    def get_api_bp(self):
        return self.api_bp

    def get_all_class_df(self):
        return self.all_class_df

    def get_class_list(self):
        return self.classList
    
    def get_majors(self):
        return self.majors

    def get_merged_process_data(self):
        return self.merged_process_data

    # Setters
    def set_all_class_df(self, all_class_df):
        self.all_class_df = all_class_df
        self.merged_process_data = self.merge_process_data()

    def set_class_list(self, class_list):
        self.classList = class_list

    def set_majors(self, majors):
        self.majors = majors

    def set_merged_process_data(self, merged_process_data):
        self.merged_process_data = merged_process_data