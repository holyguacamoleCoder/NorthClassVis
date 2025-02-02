# NorthClassVision

ChinaVis 2024数据可视化竞赛作品复现

## 项目简介

本项目是2024年数据可视化竞赛的参赛作品，旨在基于可视化作品上学习**提升前端渲染效率**与**后端计算效率**的方法。项目使用了flask、Vue(包含Vuex)等技术，以及D3.js可视化库。

优化方法目前正在学习：

1. 数据分块渲染（参考go语言以及d3的增量渲染）
2. 数据并行计算（py的concurrent库）
3. ...

## 项目结构

项目包含以下主要文件和目录：
NorthClassVision/
├── data/
│   ├── Data_SubmitRecord/
│   ├── Data_StudentInfo.csv
│   ├── Data_TitleInfo.csv
│   └── first_dataDes.docx
├── backend/
│   ├── test/
│   │   ├── time_measure.py
│   │   └──mock_data.py
│   ├── utils/
│   │   ├── fs.py
│   │   └── utils.py
│   ├── routes.py
│   └── app.py
├── frontend/
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
│   ├── vue.config.js
│   └── yarn.lock
└── README.md

## 如何运行

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
yarn serve
```

7. 打开浏览器，访问 `http://localhost:8080` 查看可视化效果。
