# Image Matcher App

## 项目简介
Image Matcher App 是一个基于 Python 的图像匹配应用程序，旨在帮助用户在指定的窗口中查找和匹配图像。该应用程序具有友好的用户界面，支持多种设置和功能，适合需要自动化图像处理的用户。

## 项目结构
```
image-matcher-app
├── src
│   ├── main.py                # 应用程序入口点
│   ├── ui                     # 用户界面模块
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口类
│   │   └── components          # 界面组件
│   │       ├── __init__.py
│   │       ├── window_selector.py  # 目标窗口选择组件
│   │       ├── image_settings.py    # 图片设置组件
│   │       ├── control_settings.py   # 控制设置组件
│   │       ├── hotkey_settings.py     # 快捷键设置组件
│   │       └── log_output.py          # 日志输出组件
│   ├── core                   # 核心功能模块
│   │   ├── __init__.py
│   │   ├── window_manager.py   # 窗口管理类
│   │   ├── image_matcher.py    # 图片匹配类
│   │   └── controller.py        # 控制器类
│   └── utils                  # 工具模块
│       ├── __init__.py
│       ├── config.py           # 配置管理
│       └── logger.py           # 日志记录功能
├── assets
│   └── icons                  # 图标资源
├── config
│   └── settings.json          # 配置设置
├── requirements.txt           # 项目依赖
└── README.md                  # 项目文档
```

## 功能特性
- **目标窗口选择**: 用户可以从下拉框中选择目标窗口，并实时显示窗口 ID。
- **图片设置**: 用户可以选择初始图片作为匹配模板。
- **控制设置**: 用户可以设置鼠标点击的左/右键以及点击间隔时间。
- **快捷键设置**: 用户可以为开始和暂停操作设置快捷键。
- **运行日志**: 应用程序会实时输出操作日志，便于用户查看。

## 安装与运行
1. 克隆该项目到本地：
   ```
   git clone <repository-url>
   ```
2. 进入项目目录：
   ```
   cd image-matcher-app
   ```
3. 安装依赖：
   ```
   pip install -r requirements.txt
   ```
4. 运行应用程序：
   ```
   python src/main.py
   ```

## 贡献
欢迎任何形式的贡献！请提交问题或拉取请求。

## 许可证
该项目遵循 MIT 许可证。