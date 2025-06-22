import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import time
from datetime import datetime
import os
import sys
import math

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.window_manager import WindowManager
from core.image_matcher import ImageMatcher
from core.controller import Controller

class MainWindow:
    """主窗口类 - 支持多图片独立鼠标按键设置和后台操作"""
    
    def __init__(self, window_manager, controller):
        """初始化主窗口"""
        self.window_manager = window_manager
        self.controller = controller
        
        self.root = tk.Tk()
        
        # 图片设置
        self.image_paths = {}
        self.image_labels = {}
        self.button_vars = {}
        self.enabled_vars = {}
        self.priority_vars = {}
        
        # 预选项设置
        self.preselect_enabled = tk.BooleanVar(value=False)
        self.preselect_threshold = tk.StringVar(value="0.8")
        self.preselect_image_path = None
        
        # 匹配阈值
        self.threshold_var = tk.StringVar(value="0.3")
        
        # 窗口选择
        self.selected_window_id = None
        
        # 窗口状态监控
        self.window_state_timer = None
        
        # 文件夹模板管理
        self.folder_templates = {}  # 存储文件夹模板信息
        
        # 初始化界面
        self.init_ui()
        
        # 连接控制器回调
        self.controller.set_log_callback(self.log_message)
        self.controller.set_match_callback(self.on_match_found)
        
        # 开始窗口状态监控
        self.start_window_state_monitoring()
        
    def init_ui(self):
        """初始化用户界面"""
        self.root.title("自动挂机宇宙无敌螺旋究极爆炸版本OuO")
        self.root.geometry("1050x900")  # 增加窗口大小
        
        # 设置窗口图标
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "hacker.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
                print("已加载程序图标")
            else:
                print(f"未找到图标文件: {icon_path}")
        except Exception as e:
            print(f"加载图标失败: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
        
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 创建左右两栏布局
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # 1. 目标窗口选择 (左栏)
        window_frame = ttk.LabelFrame(left_frame, text="目标窗口选择", padding="5")
        window_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(window_frame, text="选择窗口:").grid(row=0, column=0, padx=(0, 5))
        
        self.window_combo = ttk.Combobox(window_frame, width=35, state="readonly")
        self.window_combo.grid(row=0, column=1, padx=(0, 5))
        self.window_combo.bind('<<ComboboxSelected>>', self.on_window_selected)
        
        self.status_label = ttk.Label(window_frame, text="未连接")
        self.status_label.grid(row=0, column=2, padx=(5, 5))
        self.update_window_status(False)
        
        refresh_btn = ttk.Button(window_frame, text="刷新", command=self.refresh_windows)
        refresh_btn.grid(row=0, column=3, padx=(5, 0))
        
        # 窗口状态显示
        ttk.Label(window_frame, text="窗口状态:").grid(row=1, column=0, padx=(0, 5), pady=(5, 0))
        self.window_state_label = ttk.Label(window_frame, text="未知", foreground="gray")
        self.window_state_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # 后台操作说明
        info_label = ttk.Label(window_frame, text="🔧 支持后台操作，多线程处理，优先级控制", 
                              foreground="blue", font=('TkDefaultFont', 8))
        info_label.grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        # 2. 预选项设置 (左栏)
        self.create_preselect_section(left_frame, row=1)
        
        # 3. 图片设置 (左栏)
        image_frame = ttk.LabelFrame(left_frame, text="单张图片设置", padding="5")
        image_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 创建表头
        ttk.Label(image_frame, text="图片", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(image_frame, text="文件", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(image_frame, text="鼠标按键", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=2, padx=5, pady=2)
        ttk.Label(image_frame, text="优先级", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(image_frame, text="启用", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=4, padx=5, pady=2)
        
        # 为每个图片创建设置行
        for i in range(1, 5):  # 支持4个图片
            self.create_image_row(image_frame, i)
        
        # 4. 全局控制设置 (左栏)
        control_frame = ttk.LabelFrame(left_frame, text="全局控制设置", padding="5")
        control_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 第一行设置
        ttk.Label(control_frame, text="全局点击间隔(秒):").grid(row=0, column=0, sticky=tk.W, pady=(5, 0))
        self.interval_var = tk.StringVar(value="1.0")
        interval_entry = ttk.Entry(control_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=0, column=1, sticky=tk.W, pady=(5, 0), padx=(5, 0))
        interval_entry.bind('<KeyRelease>', self.on_interval_changed)
        
        ttk.Label(control_frame, text="匹配阈值(0.0-1.0):").grid(row=0, column=2, sticky=tk.W, pady=(5, 0), padx=(20, 0))
        threshold_entry = ttk.Entry(control_frame, textvariable=self.threshold_var, width=10)
        threshold_entry.grid(row=0, column=3, sticky=tk.W, pady=(5, 0), padx=(5, 0))
        threshold_entry.bind('<KeyRelease>', self.on_threshold_changed)
        
        # 立即应用全局匹配阈值
        self.controller.image_matcher.set_match_threshold(0.3)
        self.log_message("全局匹配阈值已设置为: 0.3")
        
        # 第二行：多匹配点击设置
        ttk.Label(control_frame, text="多匹配模式:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.multi_match_var = tk.StringVar(value="螺旋模式")
        multi_combo = ttk.Combobox(control_frame, textvariable=self.multi_match_var, width=15, state="readonly")
        multi_combo['values'] = ("螺旋模式", "最近模式", "全部模式")
        multi_combo.grid(row=1, column=1, sticky=tk.W, pady=(5, 0), padx=(5, 0))
        multi_combo.bind('<<ComboboxSelected>>', self.on_multi_match_changed)
        
        # 性能设置
        ttk.Label(control_frame, text="匹配线程数:").grid(row=1, column=2, sticky=tk.W, pady=(5, 0), padx=(20, 0))
        self.thread_var = tk.StringVar(value="2")
        thread_combo = ttk.Combobox(control_frame, textvariable=self.thread_var, width=8, state="readonly")
        thread_combo['values'] = ("1", "2", "3", "4")
        thread_combo.grid(row=1, column=3, sticky=tk.W, pady=(5, 0), padx=(5, 0))
        thread_combo.bind('<<ComboboxSelected>>', self.on_thread_count_changed)
        
        # 第三行：后台操作模式说明
        mode_info = ttk.Label(control_frame, 
                             text="🔧 螺旋模式：从窗口中心向外螺旋点击 | 最近模式：点击最近的匹配 | 全部模式：点击所有匹配", 
                             foreground="green", font=('TkDefaultFont', 8))
        mode_info.grid(row=2, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        # 5. 控制按钮 (左栏)
        button_frame = ttk.LabelFrame(left_frame, text="控制面板", padding="5")
        button_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_btn = ttk.Button(button_frame, text="开始后台匹配 (F1)", command=self.start_matching)
        self.start_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.pause_btn = ttk.Button(button_frame, text="暂停匹配 (F2)", command=self.pause_matching, state="disabled")
        self.pause_btn.grid(row=0, column=1, padx=(0, 5))
        
        # 添加测试截图按钮
        debug_btn = ttk.Button(button_frame, text="测试截图", command=self.test_screenshot)
        debug_btn.grid(row=0, column=2, padx=(5, 0))
        
        # 性能指示器
        self.perf_label = ttk.Label(button_frame, text="FPS: --", foreground="blue")
        self.perf_label.grid(row=0, column=3, padx=(10, 0))
        
        # 状态显示
        self.status_info = ttk.Label(button_frame, text="状态: 就绪")
        self.status_info.grid(row=0, column=4, padx=(10, 0))
        
        # 全选/全不选按钮
        ttk.Button(button_frame, text="全选", command=self.select_all_images).grid(row=0, column=5, padx=(20, 5))
        ttk.Button(button_frame, text="全不选", command=self.deselect_all_images).grid(row=0, column=6, padx=(0, 5))
        
        # 6. 文件夹模板管理 (右栏)
        folder_frame = ttk.LabelFrame(right_frame, text="文件夹模板管理", padding="5")
        folder_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 添加文件夹按钮
        ttk.Button(folder_frame, text="添加文件夹", command=self.select_template_directory).grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        # 文件夹列表说明
        ttk.Label(folder_frame, text="支持多文件夹，每个文件夹内的图片保持相同优先级", 
                 foreground="blue", font=('TkDefaultFont', 8)).grid(
            row=0, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        # 文件夹列表容器
        folder_list_container = ttk.Frame(folder_frame)
        folder_list_container.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 添加滚动条
        folder_scroll = ttk.Scrollbar(folder_list_container)
        folder_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建Canvas用于滚动
        folder_canvas = tk.Canvas(folder_list_container, yscrollcommand=folder_scroll.set)
        folder_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        folder_scroll.config(command=folder_canvas.yview)
        
        # 创建内部框架用于放置文件夹列表
        self.folder_list_frame = ttk.Frame(folder_canvas)
        folder_canvas.create_window((0, 0), window=self.folder_list_frame, anchor=tk.NW)
        
        # 文件夹列表标题
        ttk.Label(self.folder_list_frame, text="文件夹", width=20, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=0, padx=5, pady=2)
        ttk.Label(self.folder_list_frame, text="优先级", width=8, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=1, padx=5, pady=2)
        ttk.Label(self.folder_list_frame, text="图片数量", width=8, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=2, padx=5, pady=2)
        ttk.Label(self.folder_list_frame, text="启用", width=6, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=3, padx=5, pady=2)
        ttk.Label(self.folder_list_frame, text="操作", width=15, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=4, padx=5, pady=2)
        
        # 设置滚动区域
        self.folder_list_frame.bind("<Configure>", lambda e: folder_canvas.configure(scrollregion=folder_canvas.bbox("all")))
        
        # 7. 运行日志 (右栏)
        log_frame = ttk.LabelFrame(right_frame, text="运行日志", padding="5")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=30, width=50)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清除日志按钮
        clear_log_btn = ttk.Button(log_frame, text="清除日志", command=self.clear_log)
        clear_log_btn.grid(row=1, column=0, sticky=tk.E, pady=(5, 0))
        
        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        left_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        folder_frame.columnconfigure(0, weight=1)
        folder_frame.rowconfigure(1, weight=1)
        
        # 初始化
        self.refresh_windows()
        self.setup_hotkeys()

    def create_preselect_section(self, parent, row):
        """创建预选项设置区域"""
        preselect_frame = ttk.LabelFrame(parent, text="🚦 进入回合设置 (最高优先级 - 匹配到时立即暂停)", padding="5")
        preselect_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 注意：预选项变量已在 __init__ 中初始化，不要重复初始化
        
        # 第一行：预选项控制
        control_row = ttk.Frame(preselect_frame)
        control_row.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 5))
        
        # 启用预选项
        preselect_check = ttk.Checkbutton(control_row, text="启用预选项", 
                                        variable=self.preselect_enabled,
                                        command=self.on_preselect_enabled_changed)
        preselect_check.grid(row=0, column=0, padx=(0, 20))
        
        # 预选项阈值
        ttk.Label(control_row, text="预选项阈值:").grid(row=0, column=1, padx=(0, 5))
        threshold_entry = ttk.Entry(control_row, textvariable=self.preselect_threshold, width=8)
        threshold_entry.grid(row=0, column=2, padx=(0, 20))
        threshold_entry.bind('<KeyRelease>', self.on_preselect_threshold_changed)
        
        # 状态显示
        self.preselect_status_label = ttk.Label(control_row, text="未启用", foreground="gray")
        self.preselect_status_label.grid(row=0, column=3, padx=(20, 0))
        
        # 第二行：图片选择和信息
        image_row = ttk.Frame(preselect_frame)
        image_row.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 5))
        
        # 选择预选项图片按钮
        select_preselect_btn = ttk.Button(image_row, text="选择预选项图片", 
                                        command=self.select_preselect_image)
        select_preselect_btn.grid(row=0, column=0, padx=(0, 10))
        
        # 图片文件名显示
        self.preselect_image_label = ttk.Label(image_row, text="未选择预选项图片", width=40)
        self.preselect_image_label.grid(row=0, column=1, padx=(0, 10), sticky=tk.W)
        
        # 清除预选项按钮
        clear_preselect_btn = ttk.Button(image_row, text="清除", 
                                       command=self.clear_preselect_image)
        clear_preselect_btn.grid(row=0, column=2, padx=(10, 0))
        
        # 第三行：说明文字
        info_row = ttk.Frame(preselect_frame)
        info_row.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 0))
        
        info_label = ttk.Label(info_row, 
                              text="🚦 预选项拥有最高优先级！当检测到预选项图片时，程序将立即暂停所有匹配和点击动作",
                              foreground="red", font=('TkDefaultFont', 8, 'bold'))
        info_label.grid(row=0, column=0, sticky=tk.W)

    def on_multi_match_changed(self, event):
        """多匹配模式变更事件"""
        mode = self.multi_match_var.get()
        # 将中文模式转换为英文
        mode_map = {
            "螺旋模式": "spiral",
            "最近模式": "nearest", 
            "全部模式": "all"
        }
        english_mode = mode_map.get(mode, "spiral")
        self.controller.set_multi_match_mode(english_mode)
        self.log_message(f"设置多匹配模式: {mode}")

    def on_thread_count_changed(self, event):
        """线程数变更事件"""
        thread_count = int(self.thread_var.get())
        self.controller.set_thread_count(thread_count)
        self.log_message(f"设置匹配线程数: {thread_count}")

    def on_priority_changed(self, image_num):
        """优先级变更事件"""
        priority = int(self.priority_vars[image_num].get())
        self.controller.set_template_priority(image_num, priority)
        self.log_message(f"图片{image_num}设置优先级: {priority}")

    def test_screenshot(self):
        """测试截图功能 - 强化预选项测试"""
        try:
            if not self.selected_window_id:
                self.log_message("请先选择目标窗口")
                return
                
            self.log_message("[预选项] 开始测试截图功能 (包含预选项测试)...")
            self.log_message(f"目标窗口ID: {self.selected_window_id}")
            
            # 验证窗口状态
            import win32gui
            if not win32gui.IsWindow(self.selected_window_id):
                self.log_message(f"错误: 窗口ID {self.selected_window_id} 无效或已关闭")
                return
            
            try:
                window_title = win32gui.GetWindowText(self.selected_window_id)
                window_rect = win32gui.GetWindowRect(self.selected_window_id)
                is_visible = win32gui.IsWindowVisible(self.selected_window_id)
                
                self.log_message(f"窗口验证: 标题='{window_title}', 矩形={window_rect}, 可见={is_visible}")
                
                if window_rect[2] - window_rect[0] <= 0 or window_rect[3] - window_rect[1] <= 0:
                    self.log_message("警告: 窗口尺寸无效，可能无法正常截图")
            except Exception as e:
                self.log_message(f"窗口信息获取失败: {e}")
            
            # 重新设置目标窗口
            self.log_message("重新设置目标窗口...")
            success = self.window_manager.set_target_window(self.selected_window_id)
            if not success:
                self.log_message("重新设置目标窗口失败")
                return
            
            # 基础测试：检查窗口管理器状态
            self.log_message(f"窗口管理器状态检查:")
            self.log_message(f"  target_window_handle: {getattr(self.window_manager, 'target_window_handle', 'None')}")
            self.log_message(f"  target_window_id: {getattr(self.window_manager, 'target_window_id', 'None')}")
            
            # 检查方法是否存在
            has_screenshot_method = hasattr(self.window_manager, 'get_window_screenshot')
            self.log_message(f"  get_window_screenshot方法存在: {has_screenshot_method}")
            
            if has_screenshot_method:
                self.log_message("调用窗口管理器截图方法...")
            else:
                self.log_message("错误: 窗口管理器缺少get_window_screenshot方法!")
                return
            
            start_time = time.time()
            screenshot = self.window_manager.get_window_screenshot()
            screenshot_time = time.time() - start_time
            
            if screenshot is not None:
                self.log_message(f"截图成功! 尺寸: {screenshot.shape}, 耗时: {screenshot_time:.3f}秒")
                
                # [预选项] 强化预选项测试
                self.log_message("[预选项] === 开始强化预选项测试 ===")
                preselect_enabled = self.preselect_enabled.get()
                preselect_path = getattr(self, 'preselect_image_path', None)
                preselect_threshold = self.preselect_threshold.get()
                
                self.log_message(f"[预选项] 预选项UI状态: 启用={preselect_enabled}, 图片路径={preselect_path}")
                self.log_message(f"[预选项] 预选项UI阈值: {preselect_threshold}")
                
                # 检查控制器状态
                controller_enabled = getattr(self.controller, 'preselect_enabled', False)
                controller_path = getattr(self.controller, 'preselect_image_path', None)
                controller_threshold = getattr(self.controller, 'preselect_threshold', 0.8)
                
                self.log_message(f"[预选项] 控制器状态: 启用={controller_enabled}, 图片路径={controller_path}")
                self.log_message(f"[预选项] 控制器阈值: {controller_threshold}")
                
                # 检查图像匹配器状态
                matcher_image = getattr(self.controller.image_matcher, 'preselect_image', None)
                matcher_threshold = getattr(self.controller.image_matcher, 'preselect_threshold', 0.8)
                
                self.log_message(f"[预选项] 图像匹配器状态: 图片已加载={matcher_image is not None}, 阈值={matcher_threshold}")
                
                if preselect_enabled and preselect_path:
                    self.log_message("[预选项] 重新完整设置预选项到控制器...")
                    
                    # 强制重新设置所有预选项参数
                    self.controller.set_preselect_enabled(True)
                    self.controller.set_preselect_threshold(float(preselect_threshold))
                    success = self.controller.set_preselect_image(preselect_path)
                    
                    self.log_message(f"[预选项] 预选项重新设置结果: {success}")
                    
                    if success:
                        # 再次检查图像匹配器状态
                        matcher_image_after = getattr(self.controller.image_matcher, 'preselect_image', None)
                        if matcher_image_after:
                            self.log_message(f"[预选项] 确认图像匹配器已加载预选项: {matcher_image_after['filename']}")
                            
                            self.log_message("[预选项] 执行预选项匹配...")
                            preselect_result = self.controller.image_matcher.find_preselect_image(screenshot)
                            
                            if preselect_result:
                                found = preselect_result.get('found', False)
                                confidence = preselect_result.get('confidence', 0)
                                position = preselect_result.get('position', 'Unknown')
                                threshold_used = preselect_result.get('threshold_used', 'Unknown')
                                raw_confidence = preselect_result.get('raw_confidence', 'Unknown')
                                
                                if found:
                                    self.log_message(f"[预选项] 预选项匹配成功! 位置: {position}, 置信度: {confidence:.3f}")
                                    self.log_message(f"[预选项] 原始置信度: {raw_confidence}, 使用阈值: {threshold_used}")
                                    self.log_message(f"[预选项] 这意味着如果在运行中，程序会立即暂停所有动作！")
                                else:
                                    self.log_message(f"[预选项] 预选项未匹配: 置信度={confidence:.3f}, 原始={raw_confidence}, 阈值={threshold_used}")
                                    self.log_message(f"[预选项] 建议降低预选项阈值或检查图片是否正确")
                            else:
                                self.log_message("[预选项] 预选项匹配返回空结果")
                        else:
                            self.log_message("[预选项] 错误: 图像匹配器中预选项图片仍为空")
                    else:
                        self.log_message("[预选项] 预选项设置失败，无法进行测试")
                        
                        # 尝试直接测试文件加载
                        self.log_message("[预选项] 尝试直接测试文件加载...")
                        try:
                            import cv2
                            test_img = cv2.imread(preselect_path, cv2.IMREAD_COLOR)
                            if test_img is not None:
                                self.log_message(f"[预选项] 文件可以直接加载: {test_img.shape}")
                            else:
                                self.log_message(f"[预选项] 文件无法直接加载: {preselect_path}")
                        except Exception as e:
                            self.log_message(f"[预选项] 直接加载测试失败: {e}")
                else:
                    if not preselect_enabled:
                        self.log_message("[预选项] 预选项未启用")
                    if not preselect_path:
                        self.log_message("[预选项] 预选项图片未选择")
                
                self.log_message("[预选项] === 预选项测试完成 ===")
                
                # 测试普通模板匹配
                if hasattr(self.controller, 'image_matcher') and self.controller.image_matcher.template_images:
                    self.log_message("测试普通模板匹配...")
                    match_start = time.time()
                    results = self.controller.image_matcher.find_all_templates(screenshot)
                    match_time = time.time() - match_start
                    self.log_message(f"匹配结果: {len(results)}个模板被处理, 耗时: {match_time:.3f}秒")
                    
                    for template_id, result in results.items():
                        if result and result.get('found'):
                            all_positions = result.get('all_positions', [])
                            confidence = result.get('confidence', 0)
                            priority = self.priority_vars.get(template_id, tk.StringVar(value="1")).get()
                            
                            if len(all_positions) > 1:
                                self.log_message(f"✓ 模板{template_id}(优先级{priority})找到{len(all_positions)}个匹配: 置信度={confidence:.3f}")
                                for i, pos in enumerate(all_positions[:3]):
                                    self.log_message(f"  位置{i+1}: {pos}")
                            else:
                                position = result.get('position')
                                self.log_message(f"✓ 模板{template_id}(优先级{priority})匹配成功: 置信度={confidence:.3f}, 位置: {position}")
                        else:
                            priority = self.priority_vars.get(template_id, tk.StringVar(value="1")).get()
                            self.log_message(f"模板{template_id}(优先级{priority})未匹配")
                else:
                    self.log_message("没有加载普通模板图像")
                
                # 测试手动点击窗口中心
                center_x, center_y = screenshot.shape[1] // 2, screenshot.shape[0] // 2
                self.log_message(f"测试手动点击截图中心: ({center_x}, {center_y})")
                manual_click = self.window_manager.click_at_position(center_x, center_y, "left")
                self.log_message(f"手动点击结果: {'成功' if manual_click else '失败'}")
                
            else:
                self.log_message("截图失败! 请检查:")
                self.log_message("1. 窗口是否仍然存在")
                self.log_message("2. 窗口是否被最小化")
                self.log_message("3. 程序是否有足够权限")
                self.log_message("4. 尝试重新选择窗口")
                
        except Exception as e:
            self.log_message(f"测试截图失败: {e}")
            import traceback
            self.log_message(f"错误详情: {traceback.format_exc()}")
    

 
    
    
    def start_window_state_monitoring(self):
        """开始窗口状态监控"""
        def update_window_state():
            try:
                if self.selected_window_id:
                    state = self.window_manager.get_window_state()
                    if state:
                        # 根据状态设置不同颜色
                        colors = {
                            "正常显示": "green",
                            "最小化": "orange", 
                            "被遮挡": "blue",
                            "最大化": "green",
                            "隐藏": "red",
                            "不存在": "red",
                            "未知": "gray",
                            "未设置": "gray"
                        }
                        color = colors.get(state, "gray")
                        self.window_state_label.config(text=state, foreground=color)
                    else:
                        self.window_state_label.config(text="未知", foreground="gray")
                else:
                    self.window_state_label.config(text="未选择", foreground="gray")
            except Exception as e:
                self.window_state_label.config(text="错误", foreground="red")
                print(f"窗口状态监控错误: {e}")
            
            # 每3秒更新一次（减少频率）
            self.window_state_timer = self.root.after(3000, update_window_state)
        
        update_window_state()

    def update_performance_display(self, fps):
        """更新性能显示"""
        try:
            def update():
                if fps > 0:
                    self.perf_label.config(text=f"FPS: {fps:.1f}")
                else:
                    self.perf_label.config(text="FPS: --")
            
            if threading.current_thread().name == 'MainThread':
                update()
            else:
                self.root.after(0, update)
        except:
            pass
        
    def create_image_row(self, parent, image_num):
        """创建图片设置行"""
        row = image_num  # 第0行是表头
        
        # 选择图片按钮
        select_btn = ttk.Button(parent, text=f"选择图片{image_num}", 
                               command=lambda: self.select_image(image_num))
        select_btn.grid(row=row, column=0, padx=5, pady=2, sticky=tk.W)
        
        # 图片文件名标签
        self.image_labels[image_num] = ttk.Label(parent, text="未选择图片", width=25)
        self.image_labels[image_num].grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
        
        # 鼠标按键选择
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=2, padx=5, pady=2)
        
        # 设置默认鼠标按键为左键
        self.button_vars[image_num] = tk.StringVar(value="left")
        
        left_radio = ttk.Radiobutton(button_frame, text="左键", 
                                   variable=self.button_vars[image_num], 
                                   value="left",
                                   command=lambda: self.on_button_changed(image_num))
        left_radio.grid(row=0, column=0, padx=(0, 5))
        
        right_radio = ttk.Radiobutton(button_frame, text="右键", 
                                    variable=self.button_vars[image_num], 
                                    value="right",
                                    command=lambda: self.on_button_changed(image_num))
        right_radio.grid(row=0, column=1)
        
        # 设置优先级
        priority_value = "1" if image_num == 1 else "2"  # 图片1优先级为1，其他为2
        self.priority_vars[image_num] = tk.StringVar(value=priority_value)
        priority_combo = ttk.Combobox(parent, textvariable=self.priority_vars[image_num], 
                                    width=8, state="readonly")
        priority_combo['values'] = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10")
        priority_combo.grid(row=row, column=3, padx=5, pady=2)
        priority_combo.bind('<<ComboboxSelected>>', lambda e: self.on_priority_changed(image_num))
        
        # 启用复选框
        self.enabled_vars[image_num] = tk.BooleanVar(value=True)
        enabled_check = ttk.Checkbutton(parent, variable=self.enabled_vars[image_num],
                                      command=lambda: self.on_enabled_changed(image_num))
        enabled_check.grid(row=row, column=4, padx=5, pady=2)
        
        # 初始化控制器设置
        self.controller.set_template_click_button(image_num, self.button_vars[image_num].get())
        self.controller.set_template_enabled(image_num, self.enabled_vars[image_num].get())
        self.controller.set_template_priority(image_num, int(self.priority_vars[image_num].get()))
        
    def setup_hotkeys(self):
        """设置全局热键"""
        try:
            import keyboard
            keyboard.add_hotkey('f1', self.start_matching)
            keyboard.add_hotkey('f2', self.pause_matching)
            self.log_message("全局热键设置成功: F1-开始, F2-暂停")
        except ImportError:
            self.log_message("keyboard模块未安装，只能使用窗口内热键")
        except Exception as e:
            self.log_message(f"全局热键设置失败: {e}")
        
    def refresh_windows(self):
        """刷新窗口列表"""
        try:
            windows = self.window_manager.get_window_list()
            window_list = [f"{title} (ID: {wid})" for wid, title in windows]
            self.window_combo['values'] = window_list
            self.log_message(f"已刷新窗口列表，找到 {len(windows)} 个窗口")
        except Exception as e:
            self.log_message(f"刷新窗口列表失败: {e}")
    
    def on_window_selected(self, event):
        """窗口选择事件"""
        try:
            selection = self.window_combo.get()
            if selection:
                import re
                match = re.search(r'ID: (\d+)', selection)
                if match:
                    window_id = int(match.group(1))
                    self.selected_window_id = window_id
                    success = self.controller.set_target_window(window_id)
                    self.update_window_status(success)
                    
                    if success:
                        self.log_message(f"已选择窗口: {selection} (支持后台操作)")
                    else:
                        self.log_message(f"选择窗口失败: {selection}")
        except Exception as e:
            self.log_message(f"窗口选择失败: {e}")
    
    def update_window_status(self, connected):
        """更新窗口状态显示"""
        if connected and self.selected_window_id:
            self.status_label.config(text=f"已连接 (ID: {self.selected_window_id})", foreground="green")
        else:
            self.status_label.config(text="未连接", foreground="red")
    
    def select_image(self, image_num):
        """选择图片"""
        try:
            file_path = filedialog.askopenfilename(
                title=f"选择图片{image_num}",
                filetypes=[
                    ("图片文件", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                    ("PNG文件", "*.png"),
                    ("JPEG文件", "*.jpg *.jpeg"),
                    ("所有文件", "*.*")
                ]
            )
            
            if file_path:
                filename = os.path.basename(file_path)
                self.image_paths[image_num] = file_path
                self.image_labels[image_num].config(text=filename)
                
                success = self.controller.set_template_image(image_num, file_path)
                if success:
                    priority = self.priority_vars[image_num].get()
                    self.log_message(f"已选择图片{image_num}: {filename} (优先级: {priority})")
                else:
                    self.log_message(f"加载图片{image_num}失败: {filename}")
        except Exception as e:
            self.log_message(f"选择图片失败: {e}")
    
    def select_preselect_image(self):
        """选择预选项图片"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择预选项图片",
                filetypes=[
                    ("图片文件", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                    ("PNG文件", "*.png"),
                    ("JPEG文件", "*.jpg *.jpeg"),
                    ("所有文件", "*.*")
                ]
            )
            
            if file_path:
                filename = os.path.basename(file_path)
                self.preselect_image_path = file_path
                self.preselect_image_label.config(text=filename)
                
                # 设置到控制器
                success = self.controller.set_preselect_image(file_path)
                if success:
                    self.log_message(f"已选择预选项图片: {filename}")
                    self.update_preselect_status()
                else:
                    self.log_message(f"加载预选项图片失败: {filename}")
                
        except Exception as e:
            self.log_message(f"选择预选项图片失败: {e}")

    def clear_preselect_image(self):
        """清除预选项图片"""
        try:
            self.preselect_image_path = None
            self.preselect_image_label.config(text="未选择预选项图片")
            self.controller.clear_preselect_image()
            self.update_preselect_status()
            self.log_message("已清除预选项图片")
        except Exception as e:
            self.log_message(f"清除预选项图片失败: {e}")

    def on_preselect_enabled_changed(self):
        """预选项启用状态变更"""
        enabled = self.preselect_enabled.get()
        self.controller.set_preselect_enabled(enabled)
        self.update_preselect_status()
        status = "启用" if enabled else "禁用"
        self.log_message(f"预选项已{status}")

    def on_preselect_threshold_changed(self, event):
        """预选项阈值变更"""
        try:
            threshold = float(self.preselect_threshold.get())
            if 0.0 <= threshold <= 1.0:
                self.controller.set_preselect_threshold(threshold)
                self.log_message(f"预选项阈值设置为: {threshold}")
        except ValueError:
            pass
        except Exception as e:
            self.log_message(f"设置预选项阈值失败: {e}")

    def update_preselect_status(self):
        """更新预选项状态显示"""
        if self.preselect_enabled.get() and self.preselect_image_path:
            self.preselect_status_label.config(text="已启用", foreground="green")
        elif self.preselect_enabled.get():
            self.preselect_status_label.config(text="已启用但未选择图片", foreground="orange")
        else:
            self.preselect_status_label.config(text="未启用", foreground="gray")
    
    def on_button_changed(self, image_num):
        """鼠标按键变更事件"""
        button = self.button_vars[image_num].get()
        self.controller.set_template_click_button(image_num, button)
        priority = self.priority_vars[image_num].get()
        self.log_message(f"图片{image_num}(优先级{priority})设置鼠标按键: {button} (后台点击)")
    
    def on_enabled_changed(self, image_num):
        """启用状态变更事件"""
        enabled = self.enabled_vars[image_num].get()
        self.controller.set_template_enabled(image_num, enabled)
        priority = self.priority_vars[image_num].get()
        status = "启用" if enabled else "禁用"
        self.log_message(f"图片{image_num}(优先级{priority}) {status}")
    
    def on_interval_changed(self, event):
        """间隔时间变更事件"""
        try:
            interval = float(self.interval_var.get())
            self.controller.set_global_click_interval(interval)
        except ValueError:
            pass
        except Exception as e:
            self.log_message(f"设置间隔时间失败: {e}")
    
    def on_threshold_changed(self, event):
        """匹配阈值变更事件"""
        try:
            threshold = float(self.threshold_var.get())
            if 0.0 <= threshold <= 1.0:
                self.controller.image_matcher.set_match_threshold(threshold)
                self.log_message(f"匹配阈值设置为: {threshold}")
        except ValueError:
            pass
        except Exception as e:
            self.log_message(f"设置匹配阈值失败: {e}")
    
    def select_all_images(self):
        """全选所有图片"""
        for image_num in self.enabled_vars:
            self.enabled_vars[image_num].set(True)
            self.controller.set_template_enabled(image_num, True)
        self.log_message("已启用所有图片")
    
    def deselect_all_images(self):
        """取消选择所有图片"""
        for image_num in self.enabled_vars:
            self.enabled_vars[image_num].set(False)
            self.controller.set_template_enabled(image_num, False)
        self.log_message("已禁用所有图片")
    
    def start_matching(self):
        """开始匹配"""
        try:
            if not self.selected_window_id:
                self.log_message("错误: 请先选择目标窗口")
                messagebox.showwarning("警告", "请先选择目标窗口")
                return
            
            # 首先确保文件夹中的模板被正确启用
            for folder_id, folder_data in self.folder_templates.items():
                if folder_data['enabled_var'].get():
                    folder_info = folder_data['info']
                    self.log_message(f"正在启用文件夹 {folder_id} 中的模板...")
                    
                    for template_id in folder_info['template_ids']:
                        # 确保template_id是整数
                        template_id = int(template_id)
                        # 检查模板是否存在于controller的设置中
                        if template_id in self.controller.template_settings:
                            self.controller.set_template_enabled(template_id, True)
                            self.log_message(f"启用模板 {template_id} (来自文件夹 {folder_id})")
                        else:
                            self.log_message(f"警告: 模板 {template_id} 不在控制器设置中")
            
            # 获取控制器中所有启用的模板
            self.log_message("正在获取所有启用的模板...")
            enabled_templates = self.controller.get_priority_sorted_templates()
            self.log_message(f"找到 {len(enabled_templates)} 个启用的模板")
            
            # 检查image_matcher中的模板
            template_images = self.controller.image_matcher.template_images
            self.log_message(f"image_matcher中有 {len(template_images)} 个模板图像")
            for tid, data in template_images.items():
                self.log_message(f"image_matcher模板 {tid}: {data['filename']}")
            
            # 检查controller中的template_settings
            template_settings = self.controller.template_settings
            self.log_message(f"controller中有 {len(template_settings)} 个模板设置")
            for tid, settings in template_settings.items():
                enabled = settings['enabled']
                priority = settings['priority']
                path = settings.get('image_path', '无')
                self.log_message(f"controller模板 {tid}: 启用={enabled}, 优先级={priority}, 路径={os.path.basename(path) if path else '无'}")
                
                # 如果路径为空，尝试从image_matcher中获取
                if not path and tid in template_images:
                    settings['image_path'] = template_images[tid]['path']
                    self.log_message(f"修复模板 {tid} 的路径: {os.path.basename(settings['image_path'])}")
            
            # 重新获取启用的模板
            enabled_templates = self.controller.get_priority_sorted_templates()
            self.log_message(f"修复后找到 {len(enabled_templates)} 个启用的模板")
            
            if not enabled_templates:
                self.log_message("错误: 没有启用的模板图像")
                messagebox.showwarning("警告", "请至少选择并启用一张图片")
                return
            
            # 设置性能监控回调
            self.controller.set_performance_callback(self.update_performance_display)
            
            # 显示启用的模板信息
            self.log_message(f"已启用 {len(enabled_templates)} 个模板:")
            for template_id in enabled_templates:
                if template_id in self.controller.template_settings:
                    settings = self.controller.template_settings[template_id]
                    priority = settings['priority']
                    button = settings['click_button']
                    folder = settings.get('folder_info', '单独图片')
                    self.log_message(f"- 模板 {template_id}: 优先级={priority}, 按键={button}, 来源={folder}")
            
            self.controller.start_matching()
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.status_info.config(text="状态: 多线程运行中")
            
            window_state = self.window_manager.get_window_state()
            mode = self.multi_match_var.get()
            thread_count = self.thread_var.get()
            
            # 显示启用图片的优先级信息
            priority_info = []
            
            # 添加单独图片信息
            for i in range(1, 5):  # 支持4个图片
                if i in self.enabled_vars and self.enabled_vars[i].get() and i in self.image_paths:
                    priority = self.priority_vars[i].get()
                    priority_info.append(f"图片{i}(优先级{priority})")
            
            # 添加文件夹信息
            for folder_id, folder_data in self.folder_templates.items():
                if folder_data['enabled_var'].get():
                    priority = folder_data['info']['priority']
                    count = folder_data['info']['count']
                    priority_info.append(f"文件夹{folder_id}(优先级{priority}, {count}张图片)")
            
            self.log_message(f"开始多线程匹配，启用图片: {', '.join(priority_info)}，模式: {mode}，线程数: {thread_count}，窗口状态: {window_state}")
        except Exception as e:
            self.log_message(f"开始匹配失败: {e}")
            import traceback
            self.log_message(f"错误详情: {traceback.format_exc()}")
    
    def pause_matching(self):
        """暂停匹配"""
        try:
            self.controller.pause_matching()
            self.start_btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            self.status_info.config(text="状态: 已暂停")
            self.perf_label.config(text="FPS: --")
        except Exception as e:
            self.log_message(f"暂停匹配失败: {e}")
    
    def on_match_found(self, template_id, result):
        """匹配找到事件"""
        try:
            all_positions = result.get('all_positions', [])
            confidence = result.get('confidence', 0)
            button = self.button_vars[template_id].get()
            priority = self.priority_vars[template_id].get()
            window_state = self.window_manager.get_window_state()
            
            if len(all_positions) > 1:
                self.log_message(f"✓ 找到{len(all_positions)}个匹配! 图片{template_id}(优先级{priority}), "
                               f"置信度: {confidence:.3f}, 执行{button}键点击, 窗口状态: {window_state}")
            else:
                position = result.get('position', 'Unknown')
                self.log_message(f"✓ 后台匹配成功! 图片{template_id}(优先级{priority}), 位置: {position}, "
                               f"置信度: {confidence:.3f}, 执行{button}键点击, 窗口状态: {window_state}")
        except Exception as e:
            self.log_message(f"处理匹配结果失败: {e}")
    
    def clear_log(self):
        """清除日志"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("日志已清除")
    
    def log_message(self, message):
        """记录日志消息 - 优化性能"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"
            
            def update_log():
                # 限制日志行数，避免内存泄漏
                current_lines = int(self.log_text.index('end-1c').split('.')[0])
                if current_lines > 1000:  # 超过1000行时清除前面的500行
                    self.log_text.delete('1.0', '500.0')
                
                self.log_text.insert(tk.END, formatted_message)
                self.log_text.see(tk.END)
            
            if threading.current_thread().name == 'MainThread':
                update_log()
            else:
                self.root.after(0, update_log)
                
        except Exception as e:
            print(f"日志输出失败: {e}")
    
    def on_closing(self):
        """窗口关闭事件"""
        try:
            # 停止窗口状态监控
            if self.window_state_timer:
                self.root.after_cancel(self.window_state_timer)
                
            self.controller.stop()
            try:
                import keyboard
                keyboard.unhook_all()
            except:
                pass
        except:
            pass
        
        self.root.destroy()
    
    def run(self):
        """运行程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def select_template_directory(self):
        """选择模板文件夹"""
        try:
            directory_path = filedialog.askdirectory(
                title="选择包含模板图片的文件夹"
            )
            
            if directory_path:
                # 获取文件夹名称
                folder_name = os.path.basename(directory_path)
                if not folder_name:  # 如果是根目录
                    folder_name = directory_path
                
                # 可以让用户自定义文件夹名称
                custom_name = simpledialog.askstring(
                    "文件夹名称", 
                    "请输入文件夹显示名称（可选）：",
                    initialvalue=folder_name
                )
                
                if custom_name:
                    folder_name = custom_name
                
                # 获取优先级
                priority = simpledialog.askinteger(
                    "设置优先级", 
                    "请输入优先级（1-99，数字越小优先级越高）：",
                    initialvalue=10,
                    minvalue=1,
                    maxvalue=99
                )
                
                if priority is None:  # 用户取消
                    return
                    
                # 加载文件夹中的模板
                success_count, failed_count, folder_info = self.controller.load_templates_from_directory(
                    directory_path, priority, folder_name)
                
                if success_count > 0 and folder_info:
                    self.log_message(f"从文件夹成功加载 {success_count} 个模板图像，优先级: {priority}")
                    
                    # 添加到文件夹列表
                    self.add_folder_to_ui(folder_info)
                    
                    messagebox.showinfo("加载成功", f"成功加载 {success_count} 个模板图像\n失败 {failed_count} 个")
                else:
                    self.log_message(f"从文件夹加载模板失败")
                    messagebox.showwarning("加载失败", "未能从文件夹加载任何模板图像")
                    
            else:
                self.log_message("取消选择模板文件夹")
            
        except Exception as e:
            self.log_message(f"选择模板文件夹失败: {e}")

    def add_folder_to_ui(self, folder_info):
        """将文件夹添加到UI界面"""
        try:
            folder_id = folder_info['name']
            row = len(self.folder_templates) + 1  # 行号从1开始
            
            # 存储文件夹信息
            self.folder_templates[folder_id] = {
                'info': folder_info,
                'enabled_var': tk.BooleanVar(value=True),
                'row': row
            }
            
            # 文件夹名称
            ttk.Label(self.folder_list_frame, text=folder_info['name'], width=20).grid(
                row=row, column=0, padx=5, pady=2)
            
            # 优先级
            priority_var = tk.StringVar(value=str(folder_info['priority']))
            priority_entry = ttk.Entry(self.folder_list_frame, textvariable=priority_var, width=8)
            priority_entry.grid(row=row, column=1, padx=5, pady=2)
            priority_entry.bind('<KeyRelease>', lambda e, fid=folder_id: self.on_folder_priority_changed(e, fid))
            self.folder_templates[folder_id]['priority_var'] = priority_var
            
            # 图片数量
            ttk.Label(self.folder_list_frame, text=str(folder_info['count']), width=8).grid(
                row=row, column=2, padx=5, pady=2)
            
            # 启用复选框
            enabled_check = ttk.Checkbutton(
                self.folder_list_frame, 
                variable=self.folder_templates[folder_id]['enabled_var'],
                command=lambda fid=folder_id: self.on_folder_enabled_changed(fid)
            )
            enabled_check.grid(row=row, column=3, padx=5, pady=2)
            
            # 操作按钮
            action_frame = ttk.Frame(self.folder_list_frame)
            action_frame.grid(row=row, column=4, padx=5, pady=2)
            
            ttk.Button(action_frame, text="查看", width=5,
                      command=lambda fid=folder_id: self.view_folder_templates(fid)).pack(side=tk.LEFT, padx=2)
            ttk.Button(action_frame, text="删除", width=5,
                      command=lambda fid=folder_id: self.remove_folder_templates(fid)).pack(side=tk.LEFT, padx=2)
            
            self.log_message(f"已添加文件夹 {folder_info['name']} 到界面，包含 {folder_info['count']} 个模板")
            
        except Exception as e:
            self.log_message(f"添加文件夹到界面失败: {e}")

    def on_folder_priority_changed(self, event, folder_id):
        """文件夹优先级变更事件"""
        try:
            priority = int(self.folder_templates[folder_id]['priority_var'].get())
            folder_info = self.folder_templates[folder_id]['info']
            
            # 更新所有属于该文件夹的模板优先级
            success_count = 0
            for template_id in folder_info['template_ids']:
                # 确保template_id是整数
                template_id = int(template_id)
                # 检查模板是否存在于controller的设置中
                if template_id in self.controller.template_settings:
                    self.controller.set_template_priority(template_id, priority)
                    success_count += 1
                else:
                    self.log_message(f"警告: 模板 {template_id} 不在控制器设置中")
            
            # 更新文件夹信息
            folder_info['priority'] = priority
            self.folder_templates[folder_id]['info'] = folder_info
            
            self.log_message(f"文件夹 {folder_id} 优先级已更新为 {priority}，成功更新 {success_count}/{folder_info['count']} 个模板")
            
        except ValueError:
            self.log_message(f"错误: 文件夹 {folder_id} 优先级必须是整数")
        except Exception as e:
            self.log_message(f"更新文件夹优先级失败: {e}")
            import traceback
            self.log_message(f"错误详情: {traceback.format_exc()}")

    def on_folder_enabled_changed(self, folder_id):
        """文件夹启用状态变更事件"""
        try:
            enabled = self.folder_templates[folder_id]['enabled_var'].get()
            folder_info = self.folder_templates[folder_id]['info']
            
            # 更新所有属于该文件夹的模板启用状态
            success_count = 0
            for template_id in folder_info['template_ids']:
                # 确保template_id是整数
                template_id = int(template_id)
                # 检查模板是否存在于controller的设置中
                if template_id in self.controller.template_settings:
                    self.controller.set_template_enabled(template_id, enabled)
                    success_count += 1
                else:
                    self.log_message(f"警告: 模板 {template_id} 不在控制器设置中")
            
            status = "启用" if enabled else "禁用"
            self.log_message(f"文件夹 {folder_id} 已{status}，成功{status} {success_count}/{folder_info['count']} 个模板")
            
        except Exception as e:
            self.log_message(f"更新文件夹启用状态失败: {e}")
            import traceback
            self.log_message(f"错误详情: {traceback.format_exc()}")

    def view_folder_templates(self, folder_id):
        """查看文件夹中的模板"""
        try:
            folder_info = self.folder_templates[folder_id]['info']
            template_ids = folder_info['template_ids']
            
            # 创建一个新窗口显示模板信息
            view_window = tk.Toplevel(self.root)
            view_window.title(f"文件夹模板: {folder_id}")
            view_window.geometry("600x400")
            
            # 创建滚动区域
            frame = ttk.Frame(view_window)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 标题
            ttk.Label(frame, text=f"文件夹: {folder_id}, 优先级: {folder_info['priority']}, 共 {len(template_ids)} 个模板",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
            
            # 创建表格
            columns = ("ID", "文件名", "尺寸", "优先级")
            tree = ttk.Treeview(frame, columns=columns, show="headings")
            
            # 设置列宽
            tree.column("ID", width=50)
            tree.column("文件名", width=200)
            tree.column("尺寸", width=100)
            tree.column("优先级", width=50)
            
            # 设置表头
            for col in columns:
                tree.heading(col, text=col)
            
            # 添加滚动条
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscroll=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 填充数据
            for template_id in template_ids:
                if template_id in self.controller.image_matcher.template_images:
                    template_data = self.controller.image_matcher.template_images[template_id]
                    filename = template_data['filename']
                    size = f"{template_data['size'][1]}x{template_data['size'][0]}"
                    priority = self.controller.template_settings[template_id]['priority']
                    
                    tree.insert("", tk.END, values=(template_id, filename, size, priority))
            
            self.log_message(f"已打开文件夹 {folder_id} 的模板查看窗口")
            
        except Exception as e:
            self.log_message(f"查看文件夹模板失败: {e}")

    def remove_folder_templates(self, folder_id):
        """移除文件夹中的所有模板"""
        try:
            if messagebox.askyesno("确认删除", f"确定要删除文件夹 {folder_id} 中的所有模板吗？"):
                folder_info = self.folder_templates[folder_id]['info']
                template_ids = folder_info['template_ids'].copy()  # 复制一份，避免在迭代过程中修改
                
                # 移除所有模板
                for template_id in template_ids:
                    self.controller.image_matcher.remove_template(template_id)
                    if template_id in self.controller.template_settings:
                        del self.controller.template_settings[template_id]
                
                # 从UI中移除
                row = self.folder_templates[folder_id]['row']
                for widget in self.folder_list_frame.grid_slaves(row=row):
                    widget.grid_forget()
                
                # 从字典中移除
                del self.folder_templates[folder_id]
                
                self.log_message(f"已删除文件夹 {folder_id} 中的所有模板，共 {len(template_ids)} 个")
                
        except Exception as e:
            self.log_message(f"删除文件夹模板失败: {e}")

def main():
    """主函数"""
    try:
        print("正在启动Image Matcher (多线程螺旋点击 + 优先级版)...")
        
        # 初始化窗口管理器
        window_manager = WindowManager()
        
        # 初始化图像匹配器
        image_matcher = ImageMatcher(window_manager)
        
        # 初始化游戏控制器
        controller = Controller(window_manager, image_matcher)
        
        # 初始化并显示主窗口
        main_window = MainWindow(window_manager, controller)
        print("程序启动成功！支持多线程螺旋点击和优先级控制")
        main_window.run()
        
    except Exception as e:
        print(f"启动应用程序时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()