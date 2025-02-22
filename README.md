# NorthClassVision

ChinaVis 2024数据可视化竞赛作品复现

## 项目简介

本项目是2024年数据可视化竞赛的参赛作品非1:1复现(仅有大致原作成品参考，无原型图、设计稿等)，旨在基于可视化作品学习**D3.js框架**、**前端渲染**与**后端计算**的相关知识，同时学习到一些简单的软件设计方法。项目主要使用flask、Vue2(包含Vuex)等技术, 还涉及简单的pytest用法。

笔者目前正在学习, 学习记录、学习资源见**notes**文件夹

## 项目结构

项目包含以下核心文件和目录：

```
NorthClassVision/
├── data/ # 数据集文件夹
│   ├── Data_SubmitRecord/
│   ├── Data_StudentInfo.csv
│   ├── Data_TitleInfo.csv
│   └── first_dataDes.docx
├── backend/  # 后端代码
│   ├── test/ # 测试文件
│   │   ├── time_measure.py
│   │   └──mock_data.py
│   ├── routes/ # 路由实现
│   ├── tools/ # 工具函数实现
│   ├── main_routes.py # flask路由综合配置
│   └── app.py
├── frontend/ # 前端代码
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── router/
│   │   ├── store/
│   │   ├── views/
│   │   └── App.vue
│   ├── .gitignore
│   ├── babel.config.js
│   ├── package.json
│   ├── README.md
│   └── vue.config.js
├── notes/ # 学习笔记
│   ├── study_recourse.md
│   ├── D3_study.md
│   └── optimization_journey.md
├── problem.md # 竞赛内容，含官方数据集下载链接
└── README.md
```

## 如何运行

0. 参见**problem.md**前往官网下载数据集，放置在data文件夹下

1. 克隆项目到本地：

```bash
git clone https://github.com/holyguacamoleCoder/NorthClassVision.git
```

2. 进入项目目录：

```bash
cd NorthClassVision
```

3. 安装后端依赖：

```bash
pip install -r requirements.txt
```

4. 启动后端服务：

```bash
cd backend
flask run
```

5. 安装前端依赖

```bash
cd ../frontend
npm install
```

6. 启动前端服务：

```bash
cd ../frontend
npm run serve
```

7. 打开浏览器，访问 `http://localhost:8080` 查看可视化效果。

## 样式预览



