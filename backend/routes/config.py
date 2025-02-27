from flask import Blueprint
from tools import fileSystem as fs

class Config:
    def __init__(self):
        # 创建蓝图对象
        self.api_bp = Blueprint('api', __name__)
        # 配置总处理文件类型
        self.all_class_df = fs.load_data(fs.classFilename)
        self.classList = []
        self.merged_process_data = None

        self.initialize()

    def initialize(self):
        for i in range(1, 16):
            self.classList.append({"checked": False, "text": f"Class{i}", 'id': i})
        self.classList[0]['checked'] = True
        self.merged_process_data = self.merge_process_data()

    def merge_process_data(self):
        return fs.process_non_numeric_values(fs.merge_data(self.all_class_df, fs.titleFilename))