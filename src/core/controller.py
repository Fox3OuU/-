import time
import threading
import os
import math
import queue
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

class Controller:
    """控制器类 - 支持多线程匹配、螺旋点击策略和优先级控制"""
    
    def __init__(self, window_manager, image_matcher):
        self.window_manager = window_manager
        self.image_matcher = image_matcher
        
        # 控制参数
        self.is_running = False
        self.target_window_id = None
        self.global_click_interval = 1.0
        self.multi_match_mode = "spiral"  # spiral, nearest, all
        self.thread_count = 2  # 匹配线程数
        
        # 每个模板的独立设置 - 添加优先级支持
        self.template_settings = {
            1: {
                'click_button': 'left', 
                'enabled': True,
                'priority': 1,  # 新增优先级字段
                'last_click_time': 0,
                'image_path': None
            },
            2: {
                'click_button': 'right', 
                'enabled': True,
                'priority': 2,
                'last_click_time': 0,
                'image_path': None
            },
            3: {
                'click_button': 'left', 
                'enabled': True,
                'priority': 3,
                'last_click_time': 0,
                'image_path': None
            },
            4: {
                'click_button': 'right', 
                'enabled': True,
                'priority': 4,
                'last_click_time': 0,
                'image_path': None
            }
        }
        
        # 🚦 预选项设置 - 确保初始化
        self.preselect_enabled = False
        self.preselect_image_path = None
        self.preselect_threshold = 0.8
        self.preselect_detected = False  # 当前是否检测到预选项
        self.preselect_pause_mode = False  # 是否因预选项而暂停
        
        # 回调函数
        self.log_callback = None
        self.match_callback = None
        self.performance_callback = None
        
        # 线程控制
        self.matching_thread = None
        self.stop_event = threading.Event()
        self.executor = None
        
        # 性能监控
        self.last_fps_time = time.time()
        self.fps_counter = 0
        self.current_fps = 0
        
        # 结果队列
        self.result_queue = queue.Queue(maxsize=100)
        
        # 优先级管理
        self.priority_interrupt = threading.Event()  # 高优先级中断信号
        
    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback
        
    def set_match_callback(self, callback):
        """设置匹配回调函数"""
        self.match_callback = callback

    def set_performance_callback(self, callback):
        """设置性能回调函数"""
        self.performance_callback = callback
        
    def set_multi_match_mode(self, mode):
        """设置多匹配模式"""
        self.multi_match_mode = mode
        self.emit_log(f"设置多匹配模式: {mode}")

    def set_thread_count(self, count):
        """设置线程数"""
        self.thread_count = max(1, min(4, int(count)))
        self.emit_log(f"设置匹配线程数: {self.thread_count}")

    def set_template_priority(self, template_id, priority):
        """设置模板优先级"""
        if template_id in self.template_settings:
            old_priority = self.template_settings[template_id]['priority']
            self.template_settings[template_id]['priority'] = int(priority)
            self.emit_log(f"图片{template_id}优先级变更: {old_priority} -> {priority}")
            
            # 如果设置了更高的优先级（数字更小），触发优先级重新排序
            if int(priority) < old_priority:
                self.priority_interrupt.set()
        else:
            self.emit_log(f"无效的模板ID: {template_id}")
        
    def get_priority_sorted_templates(self):
        """获取按优先级排序的模板列表"""
        try:
            enabled_templates = []
            for tid, settings in self.template_settings.items():
                # 检查模板是否启用
                if settings['enabled']:
                    # 检查模板是否在image_matcher中
                    if tid in self.image_matcher.template_images:
                        enabled_templates.append((tid, settings['priority']))
                        self.emit_log(f"添加启用的模板 {tid}: 优先级={settings['priority']}")
                    else:
                        self.emit_log(f"警告: 模板 {tid} 不在image_matcher中，跳过")
                else:
                    self.emit_log(f"模板 {tid} 未启用，跳过")
            
            # 按优先级排序（数字越小优先级越高）
            enabled_templates.sort(key=lambda x: x[1])
            result = [tid for tid, _ in enabled_templates]
            
            self.emit_log(f"返回 {len(result)} 个启用的模板: {result}")
            return result
        except Exception as e:
            self.emit_log(f"获取启用模板列表失败: {e}")
            import traceback
            self.emit_log(f"错误详情: {traceback.format_exc()}")
            return []
        
    def emit_log(self, message):
        """发送日志消息"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[Controller] {message}")
            
    def emit_match(self, template_id, result):
        """发送匹配结果"""
        if self.match_callback:
            self.match_callback(template_id, result)

    def update_fps(self):
        """更新FPS计算"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.last_fps_time >= 1.0:  # 每秒更新一次
            self.current_fps = self.fps_counter / (current_time - self.last_fps_time)
            self.fps_counter = 0
            self.last_fps_time = current_time
            
            if self.performance_callback:
                self.performance_callback(self.current_fps)
        
    def set_target_window(self, window_id):
        """设置目标窗口"""
        self.target_window_id = window_id
        success = self.window_manager.set_target_window(window_id)
        if success:
            self.emit_log(f"设置目标窗口成功: {window_id}")
        else:
            self.emit_log(f"设置目标窗口失败: {window_id}")
        return success
        
    def set_template_image(self, template_id, image_path):
        """设置模板图像"""
        try:
            success = self.image_matcher.set_template_image(template_id, image_path)
            if success:
                filename = os.path.basename(image_path)
                self.template_settings[template_id]['image_path'] = image_path
                priority = self.template_settings[template_id]['priority']
                self.emit_log(f"成功加载模板图像 {template_id}: {filename} (优先级: {priority})")
            else:
                self.emit_log(f"加载模板图像失败 {template_id}")
            return success
        except Exception as e:
            self.emit_log(f"设置模板图像异常: {e}")
            return False
        
    def set_template_click_button(self, template_id, button):
        """设置指定模板的点击按键"""
        if template_id in self.template_settings:
            self.template_settings[template_id]['click_button'] = button
            priority = self.template_settings[template_id]['priority']
            self.emit_log(f"图片{template_id}(优先级{priority})设置点击按键: {button}")
        else:
            self.emit_log(f"无效的模板ID: {template_id}")
        
    def set_template_enabled(self, template_id, enabled):
        """启用/禁用指定模板"""
        try:
            if template_id in self.template_settings:
                old_enabled = self.template_settings[template_id]['enabled']
                self.template_settings[template_id]['enabled'] = enabled
                priority = self.template_settings[template_id]['priority']
                status = "启用" if enabled else "禁用"
                
                # 添加调试日志
                print(f"[调试] 设置模板 {template_id} 状态: {old_enabled} -> {enabled}")
                
                self.emit_log(f"图片{template_id}(优先级{priority}) {status}")
                return True
            else:
                self.emit_log(f"无效的模板ID: {template_id}")
                return False
        except Exception as e:
            print(f"[调试] 设置模板启用状态失败: {e}")
            import traceback
            print(f"[调试] 错误详情: {traceback.format_exc()}")
            return False
        
    def set_global_click_interval(self, interval):
        """设置全局点击间隔"""
        try:
            self.global_click_interval = max(0.1, float(interval))
            self.emit_log(f"设置全局点击间隔: {self.global_click_interval}秒")
        except (ValueError, TypeError):
            self.emit_log(f"无效的间隔时间: {interval}")
    
    def get_window_center(self):
        """获取窗口中心位置 - 基于客户区"""
        try:
            if self.window_manager.target_window_handle:
                import win32gui
                # 获取客户区矩形
                client_rect = win32gui.GetClientRect(self.window_manager.target_window_handle)
                left, top, right, bottom = client_rect
                center_x = (left + right) // 2
                center_y = (top + bottom) // 2
                print(f"窗口客户区中心: ({center_x}, {center_y}), 客户区大小: {right}x{bottom}")
                return (center_x, center_y)
            return None
        except Exception as e:
            self.emit_log(f"获取窗口中心失败: {e}")
            return None
    
    def sort_positions_spiral(self, positions, window_center):
        """按螺旋方式从窗口中心向外排序位置"""
        if not window_center or not positions:
            return positions
            
        center_x, center_y = window_center
        
        # 计算每个位置到中心的距离和角度
        position_data = []
        for pos in positions:
            x, y = pos
            # 距离中心的距离
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            # 角度
            angle = math.atan2(y - center_y, x - center_x)
            position_data.append({
                'position': pos,
                'distance': distance,
                'angle': angle
            })
        
        # 按距离排序，距离相近的按角度排序（螺旋效果）
        position_data.sort(key=lambda x: (x['distance'] // 50, x['angle']))
        
        return [item['position'] for item in position_data]
    
    def sort_positions_nearest(self, positions, window_center):
        """按距离窗口中心最近排序"""
        if not window_center or not positions:
            return positions
            
        center_x, center_y = window_center
        
        # 计算距离并排序
        position_distances = []
        for pos in positions:
            x, y = pos
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            position_distances.append((distance, pos))
        
        position_distances.sort(key=lambda x: x[0])
        return [pos for _, pos in position_distances]
        
    def start_matching(self):
        """开始匹配"""
        if self.is_running:
            self.emit_log("匹配已在运行中")
            return
            
        if not self.target_window_id:
            self.emit_log("错误: 未设置目标窗口")
            return
            
        # 检查是否有启用的模板
        enabled_templates = self.get_priority_sorted_templates()
        
        if not enabled_templates:
            self.emit_log("错误: 没有启用的模板图像")
            return
            
        # 显示优先级排序
        priority_info = []
        for tid in enabled_templates:
            priority = self.template_settings[tid]['priority']
            priority_info.append(f"图片{tid}(优先级{priority})")
        self.emit_log(f"启用的模板(按优先级排序): {' > '.join(priority_info)}")
        
        # 测试截图功能
        self.emit_log("测试窗口截图功能...")
        test_screenshot = self.window_manager.get_window_screenshot()
        if test_screenshot is None:
            self.emit_log("错误: 无法获取窗口截图")
            return
        else:
            self.emit_log(f"截图测试成功，尺寸: {test_screenshot.shape}")
            
        self.is_running = True
        self.stop_event.clear()
        self.priority_interrupt.clear()
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.thread_count)
        
        # 重置性能计数器
        self.last_fps_time = time.time()
        self.fps_counter = 0
        self.current_fps = 0
        
        # 重置最后点击时间
        for template_id in self.template_settings:
            self.template_settings[template_id]['last_click_time'] = 0
        
        self.matching_thread = threading.Thread(target=self.matching_loop, daemon=True)
        self.matching_thread.start()
        
        enabled_count = len(enabled_templates)
        self.emit_log(f"开始多线程优先级匹配... 启用模板: {enabled_count}个，线程数: {self.thread_count}，模式: {self.multi_match_mode}")
        
    def pause_matching(self):
        """暂停匹配"""
        if not self.is_running:
            self.emit_log("匹配未在运行")
            return
            
        self.is_running = False
        self.stop_event.set()
        self.priority_interrupt.set()
        
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        
        if self.matching_thread and self.matching_thread.is_alive():
            self.matching_thread.join(timeout=2)
        
        self.emit_log("已暂停多线程优先级匹配")
        
    def process_template_batch_by_priority(self, screenshot, template_ids):
        """按优先级处理一批模板匹配（在线程池中执行）"""
        results = {}
        try:
            # 按优先级排序处理
            sorted_templates = []
            for template_id in template_ids:
                if template_id in self.template_settings:
                    priority = self.template_settings[template_id]['priority']
                    sorted_templates.append((template_id, priority))
            
            # 按优先级排序（数字越小优先级越高）
            sorted_templates.sort(key=lambda x: x[1])
            
            for template_id, priority in sorted_templates:
                if not self.is_running:
                    break
                    
                if not self.template_settings[template_id]['enabled']:
                    continue
                    
                result = self.image_matcher.find_template(screenshot, template_id)
                if result and result.get('found', False):
                    # 找到高优先级匹配，立即返回
                    results[template_id] = result
                    self.emit_log(f"高优先级匹配: 图片{template_id}(优先级{priority})")
                    break  # 找到高优先级匹配后停止处理低优先级
                elif result:
                    results[template_id] = result
                    
        except Exception as e:
            print(f"优先级批处理模板匹配失败: {e}")
        
        return results
        
    def set_preselect_image(self, image_path):
        """设置预选项图片 - 强化版本"""
        try:
            print(f"[预选项] Controller: 开始设置预选项图片: {image_path}")
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                print(f"[预选项] Controller: 预选项文件不存在: {image_path}")
                return False
            
            self.preselect_image_path = image_path
            
            # 确保预选项阈值已设置
            if hasattr(self, 'preselect_threshold'):
                print(f"[预选项] Controller: 设置预选项阈值: {self.preselect_threshold}")
                self.image_matcher.set_preselect_threshold(self.preselect_threshold)
            
            success = self.image_matcher.set_preselect_image(image_path)
            if success:
                filename = os.path.basename(image_path)
                self.emit_log(f"[预选项] 成功加载预选项图片 [最高优先级]: {filename}, 阈值: {self.preselect_threshold}")
                
                # 立即测试预选项是否加载成功
                if hasattr(self.image_matcher, 'preselect_image') and self.image_matcher.preselect_image:
                    preselect_info = self.image_matcher.preselect_image
                    print(f"[预选项] Controller: 预选项图片已加载，信息: {preselect_info}")
                    self.emit_log(f"[预选项] 预选项图片信息验证: 文件={preselect_info['filename']}, 尺寸={preselect_info['size']}")
                else:
                    print(f"[预选项] Controller: 警告 - 预选项图片加载后无法访问")
            else:
                self.emit_log(f"[预选项] 加载预选项图片失败: {os.path.basename(image_path)}")
                
            return success
        except Exception as e:
            self.emit_log(f"[预选项] 设置预选项图片异常: {e}")
            import traceback
            print(f"[预选项] Controller预选项错误详情: {traceback.format_exc()}")
            return False

    def clear_preselect_image(self):
        """清除预选项图片"""
        self.preselect_image_path = None
        self.preselect_detected = False
        self.preselect_pause_mode = False
        self.image_matcher.clear_preselect_image()
        self.emit_log("[预选项] 已清除预选项图片")

    def set_preselect_enabled(self, enabled):
        """设置预选项启用状态"""
        self.preselect_enabled = enabled
        if not enabled:
            self.preselect_detected = False
            self.preselect_pause_mode = False
            self.emit_log(f"[预选项] 预选项已{'启用' if enabled else '禁用'} [最高优先级]")
        else:
            self.emit_log(f"[预选项] 预选项已启用 [最高优先级] - 将在所有匹配前优先检查")

    def set_preselect_threshold(self, threshold):
        """设置预选项阈值"""
        self.preselect_threshold = max(0.0, min(1.0, float(threshold)))
        self.image_matcher.set_preselect_threshold(self.preselect_threshold)
        self.emit_log(f"[预选项] 预选项阈值设置为: {self.preselect_threshold} [最高优先级]")

    def check_preselect_condition(self, screenshot):
        """检查预选项条件 - 强化调试版本"""
        if not self.preselect_enabled:
            return False
            
        if not self.preselect_image_path:
            return False
        
        try:
            # 验证预选项图片是否已加载
            if not hasattr(self.image_matcher, 'preselect_image') or not self.image_matcher.preselect_image:
                print(f"[预选项] 预选项图片未正确加载，尝试重新加载...")
                success = self.image_matcher.set_preselect_image(self.preselect_image_path)
                if not success:
                    print(f"[预选项] 重新加载预选项图片失败")
                    return False
            
            print(f"[预选项] 开始检查预选项条件...")
            
            # 检查预选项图片
            preselect_result = self.image_matcher.find_preselect_image(screenshot)
            
            if preselect_result is None:
                print(f"[预选项] 预选项匹配返回空结果")
                return False
            
            found = preselect_result.get('found', False)
            confidence = preselect_result.get('confidence', 0)
            position = preselect_result.get('position', 'Unknown')
            threshold_used = preselect_result.get('threshold_used', 'Unknown')
            
            print(f"[预选项] 预选项检查结果: found={found}, confidence={confidence:.3f}, threshold={threshold_used}")
            
            if found:
                # 检测到预选项图片
                if not self.preselect_detected:
                    self.preselect_detected = True
                    self.preselect_pause_mode = True
                    self.emit_log(f"[预选项] [最高优先级] 检测到预选项图片! 位置: {position}, 置信度: {confidence:.3f} - 立即暂停所有动作")
                    
                return True  # 返回True表示需要暂停
            else:
                # 没有检测到预选项图片
                if self.preselect_detected:
                    self.preselect_detected = False
                    self.preselect_pause_mode = False
                    self.emit_log(f"[预选项] [最高优先级] 预选项图片消失 - 恢复匹配和点击动作 (最后置信度: {confidence:.3f})")
                
                return False  # 返回False表示可以继续
                
        except Exception as e:
            print(f"[预选项] 检查预选项时出错: {e}")
            import traceback
            print(f"[预选项] 预选项检查错误详情: {traceback.format_exc()}")
            self.emit_log(f"[预选项] 检查预选项时出错: {e}")
            return False

    def matching_loop(self):
        """匹配循环 - 预选项拥有最高优先级，检测到预选项时停止所有普通图片匹配"""
        self.emit_log(f"多线程优先级匹配循环开始运行... 模式: {self.multi_match_mode}, 线程数: {self.thread_count}")
        self.emit_log(f"[预选项] 预选项状态: {'启用' if self.preselect_enabled else '禁用'}")
        loop_count = 0
        last_preselect_check = 0  # 上次预选项检查时间
        preselect_check_interval = 0.15  # 预选项检查间隔（秒）
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                loop_count += 1
                current_time = time.time()
                
                # 更新FPS计算
                self.update_fps()
                
                # 获取窗口截图
                screenshot_start = time.time()
                screenshot = self.window_manager.get_window_screenshot()
                screenshot_time = time.time() - screenshot_start
                
                if screenshot is None:
                    if loop_count % 10 == 1:
                        self.emit_log("获取截图失败，等待0.5秒后重试")
                    time.sleep(0.5)
                    continue
                
                # [预选项] 第一优先级：检查预选项条件（最高优先级！）
                if self.preselect_enabled and self.preselect_image_path:
                    # 控制预选项检查频率
                    if current_time - last_preselect_check >= preselect_check_interval:
                        last_preselect_check = current_time
                        preselect_result = self.image_matcher.find_preselect_image(screenshot)
                        
                        if preselect_result and preselect_result.get('found', False):
                            # 检测到预选项图片（进入回合），立即暂停所有动作
                            position = preselect_result.get('position')
                            confidence = preselect_result.get('confidence', 0)
                            
                            if not self.preselect_detected:
                                self.preselect_detected = True
                                self.preselect_pause_mode = True
                                self.emit_log(f"[预选项] [最高优先级] 检测到预选项图片! 位置: {position}, 置信度: {confidence:.3f} - 进入回合，立即暂停所有匹配")
                                # 进入回合时，等待较长时间确保状态稳定
                                time.sleep(0.5)
                            
                            # 每10次循环输出一次状态
                            if loop_count % 10 == 1:
                                self.emit_log(f"[预选项] [最高优先级] 回合中 - 保持暂停状态 (置信度: {confidence:.3f})")
                            
                            # 在回合中，直接跳过所有其他处理
                            time.sleep(0.2)  # 增加回合中的等待时间
                            continue
                        else:
                            # 没有检测到预选项图片
                            if self.preselect_detected:
                                # 回合结束，等待较长时间确保状态完全转换
                                time.sleep(0.5)
                                self.preselect_detected = False
                                self.preselect_pause_mode = False
                                self.emit_log(f"[预选项] [最高优先级] 回合结束 - 恢复匹配和点击动作")
                                # 回合结束后，等待较长时间再开始新一轮匹配
                                time.sleep(0.3)
                                continue
                
                # 如果预选项启用且检测到（回合中），直接跳过所有后续处理
                if self.preselect_enabled and (self.preselect_detected or self.preselect_pause_mode):
                    time.sleep(0.2)  # 增加回合中的等待时间
                    continue
                
                # 只有在回合外（没有检测到预选项）时才处理普通模板
                if loop_count % 30 == 1:
                    self.emit_log(f"回合外匹配运行中... 第{loop_count}次, FPS: {self.current_fps:.1f}")
                
                # 获取当前按优先级排序的启用模板
                enabled_templates = self.get_priority_sorted_templates()
                if not enabled_templates:
                    time.sleep(0.5)
                    continue
                
                if loop_count % 50 == 1:  # 减少日志频率
                    self.emit_log(f"获取截图成功，尺寸: {screenshot.shape}, 耗时: {screenshot_time:.3f}秒")
                
                # 继续处理普通模板的匹配逻辑...
                # 按优先级分组处理模板
                high_priority_templates = [tid for tid in enabled_templates if self.template_settings[tid]['priority'] <= 2]
                low_priority_templates = [tid for tid in enabled_templates if self.template_settings[tid]['priority'] > 2]
                
                # 优先处理高优先级模板
                match_start = time.time()
                found_high_priority = False
                
                if high_priority_templates:
                    # 高优先级模板并行处理
                    high_priority_batches = []
                    batch_size = max(1, len(high_priority_templates) // self.thread_count)
                    for i in range(0, len(high_priority_templates), batch_size):
                        batch = high_priority_templates[i:i + batch_size]
                        high_priority_batches.append(batch)
                    
                    high_priority_futures = []
                    for batch in high_priority_batches:
                        if not self.is_running:
                            break
                        future = self.executor.submit(self.process_template_batch_by_priority, screenshot, batch)
                        high_priority_futures.append(future)
                    
                    # 收集高优先级结果
                    for future in concurrent.futures.as_completed(high_priority_futures, timeout=0.8):
                        try:
                            batch_results = future.result(timeout=0.3)
                            if batch_results:
                                # 找到高优先级匹配，立即处理
                                for template_id, result in batch_results.items():
                                    if result and result.get('found', False):
                                        # 再次检查是否进入回合
                                        if self.preselect_enabled and self.preselect_detected:
                                            self.emit_log(f"图片{template_id}匹配被跳过: 检测到回合状态")
                                            continue
                                        
                                        if self.handle_multiple_matches(template_id, result):
                                            self.emit_match(template_id, result)
                                            found_high_priority = True
                                            break
                            if found_high_priority:
                                break
                        except concurrent.futures.TimeoutError:
                            continue
                        except Exception as e:
                            if loop_count % 20 == 1:
                                self.emit_log(f"高优先级匹配任务异常: {e}")
                            continue
                
                # 如果没有高优先级匹配，处理低优先级模板
                if not found_high_priority and low_priority_templates and self.is_running:
                    # 再次检查是否进入回合
                    if self.preselect_enabled and self.preselect_detected:
                        time.sleep(0.2)  # 增加回合中的等待时间
                        continue
                        
                    low_priority_batches = []
                    batch_size = max(1, len(low_priority_templates) // max(1, self.thread_count - 1))
                    for i in range(0, len(low_priority_templates), batch_size):
                        batch = low_priority_templates[i:i + batch_size]
                        low_priority_batches.append(batch)
                    
                    low_priority_futures = []
                    for batch in low_priority_batches:
                        if not self.is_running:
                            break
                        future = self.executor.submit(self.process_template_batch_by_priority, screenshot, batch)
                        low_priority_futures.append(future)
                    
                    # 收集低优先级结果
                    for future in concurrent.futures.as_completed(low_priority_futures, timeout=0.5):
                        try:
                            batch_results = future.result(timeout=0.2)
                            if batch_results:
                                # 按优先级顺序处理结果
                                for template_id in enabled_templates:  # 已排序
                                    if template_id in batch_results:
                                        result = batch_results[template_id]
                                        if result and result.get('found', False):
                                            # 再次检查是否进入回合
                                            if self.preselect_enabled and self.preselect_detected:
                                                self.emit_log(f"图片{template_id}匹配被跳过: 检测到回合状态")
                                                continue
                                            
                                            if self.handle_multiple_matches(template_id, result):
                                                self.emit_match(template_id, result)
                                                break  # 找到一个匹配后停止
                        except concurrent.futures.TimeoutError:
                            continue
                        except Exception as e:
                            if loop_count % 20 == 1:
                                self.emit_log(f"低优先级匹配任务异常: {e}")
                            continue
                
                match_time = time.time() - match_start
                
                if loop_count % 50 == 1:
                    priority_status = "高优先级匹配" if found_high_priority else "低优先级匹配" if low_priority_templates else "无匹配"
                    self.emit_log(f"回合外匹配完成: {priority_status}, 耗时: {match_time:.3f}秒")
                
                # 检查优先级中断信号
                if self.priority_interrupt.is_set():
                    self.priority_interrupt.clear()
                    self.emit_log("优先级设置变更，重新排序模板")
                
                # 控制循环频率
                if found_high_priority:
                    time.sleep(0.3)  # 高优先级匹配成功后等待更长时间
                else:
                    time.sleep(0.25)  # 没有匹配时也增加等待时间
                    
            except Exception as e:
                self.emit_log(f"优先级匹配过程出错: {e}")
                import traceback
                self.emit_log(f"错误详情: {traceback.format_exc()}")
                time.sleep(1)
                
        self.emit_log("多线程优先级匹配循环结束")
    
    def handle_multiple_matches(self, template_id, result):
        """处理多个匹配结果"""
        if not result['found'] or not result['all_positions']:
            return False
            
        positions = result['all_positions']
        button = self.template_settings[template_id]['click_button']
        priority = self.template_settings[template_id]['priority']
        
        # 获取窗口中心点
        window_center = self.get_window_center()
        if not window_center:
            self.emit_log("无法获取窗口中心点")
            return False
            
        # 根据多匹配模式处理
        if self.multi_match_mode == "spiral":
            # 按螺旋方式排序
            sorted_positions = self.sort_positions_spiral(positions, window_center)
            for i, pos in enumerate(sorted_positions):
                click_type = f"螺旋{i+1}/{len(sorted_positions)}"
                if self.perform_click(template_id, pos, button, priority, click_type):
                    return True
                    
        elif self.multi_match_mode == "nearest":
            # 按最近距离排序
            sorted_positions = self.sort_positions_nearest(positions, window_center)
            for i, pos in enumerate(sorted_positions):
                click_type = f"最近{i+1}/{len(sorted_positions)}"
                if self.perform_click(template_id, pos, button, priority, click_type):
                    return True
                    
        elif self.multi_match_mode == "all":
            # 点击所有匹配位置
            success = False
            for i, pos in enumerate(positions):
                click_type = f"全部{i+1}/{len(positions)}"
                if self.perform_click(template_id, pos, button, priority, click_type):
                    success = True
                    time.sleep(0.1)  # 短暂延迟，避免点击过快
            return success
            
        return False
    
    def perform_click(self, template_id, position, button, priority, click_type=""):
        """执行点击操作 - 使用窗口相对坐标"""
        try:
            if not position:
                self.emit_log(f"图片{template_id}点击失败: 无效的位置")
                return False
                
            x, y = position
            
            # 添加期望点击坐标的日志输出
            self.emit_log(f"图片{template_id}(优先级{priority})期望点击坐标: ({x}, {y}) {click_type}")
            
            # 检查是否在回合中
            if self.preselect_enabled and self.preselect_detected:
                self.emit_log(f"图片{template_id}点击被跳过: 当前在回合中")
                return False
            
            # 检查点击间隔
            current_time = time.time()
            last_click_time = self.template_settings[template_id]['last_click_time']
            if current_time - last_click_time < self.global_click_interval:
                self.emit_log(f"图片{template_id}点击被跳过: 未达到点击间隔 ({self.global_click_interval}秒)")
                return False
            
            # 确保使用窗口相对坐标
            success = self.window_manager.click_at_position(x, y, button, window_relative=True)
            
            if success:
                self.emit_log(f"图片{template_id}(优先级{priority})点击成功: ({x}, {y}) {click_type}")
                # 更新最后点击时间
                self.template_settings[template_id]['last_click_time'] = current_time
            else:
                self.emit_log(f"图片{template_id}(优先级{priority})点击失败: ({x}, {y}) {click_type}")
            
            return success
            
        except Exception as e:
            self.emit_log(f"点击操作异常: {e}")
            import traceback
            self.emit_log(f"点击错误详情: {traceback.format_exc()}")
            return False
        
    def get_template_settings(self):
        """获取所有模板设置"""
        return self.template_settings.copy()
        
    def get_status(self):
        """获取控制器状态 - 增加预选项信息"""
        enabled_templates = self.get_priority_sorted_templates()
        enabled_count = len(enabled_templates)
        
        # 获取优先级分布
        priority_distribution = {}
        for tid in enabled_templates:
            priority = self.template_settings[tid]['priority']
            if priority not in priority_distribution:
                priority_distribution[priority] = 0
            priority_distribution[priority] += 1
        
        return {
            'is_running': self.is_running,
            'target_window': self.target_window_id,
            'global_interval': self.global_click_interval,
            'enabled_templates': enabled_count,
            'multi_match_mode': self.multi_match_mode,
            'thread_count': self.thread_count,
            'current_fps': self.current_fps,
            'template_settings': self.template_settings,
            'priority_distribution': priority_distribution,
            'priority_sorted_templates': enabled_templates,
            # 新增预选项状态
            'preselect_enabled': self.preselect_enabled,
            'preselect_detected': self.preselect_detected,
            'preselect_pause_mode': self.preselect_pause_mode,
            'preselect_image_path': self.preselect_image_path
        }
        
    def stop(self):
        """停止控制器"""
        self.pause_matching()

    def load_templates_from_directory(self, directory_path, priority, folder_name=None):
        """从文件夹加载模板图像"""
        try:
            success_count, failed_count, folder_info = self.image_matcher.load_templates_from_directory(
                directory_path, priority, folder_name)
            
            if success_count > 0 and folder_info:
                self.emit_log(f"从文件夹成功加载 {success_count} 个模板图像: {folder_info['name']} (优先级: {priority})")
                
                # 更新模板设置
                for template_id in folder_info['template_ids']:
                    # 确保template_id是一个整数
                    template_id = int(template_id)
                    
                    # 检查模板是否在image_matcher中
                    if template_id not in self.image_matcher.template_images:
                        self.emit_log(f"警告: 模板 {template_id} 不在image_matcher中")
                        continue
                    
                    # 获取图片路径
                    image_path = self.image_matcher.template_images[template_id]['path']
                    
                    if template_id not in self.template_settings:
                        # 为新加载的模板创建设置
                        self.template_settings[template_id] = {
                            'click_button': 'left', 
                            'enabled': True,  # 默认启用
                            'priority': priority,
                            'last_click_time': 0,
                            'image_path': image_path,  # 确保设置正确的路径
                            'folder_info': folder_info['name']  # 记录所属文件夹
                        }
                        self.emit_log(f"添加模板设置 {template_id}: 优先级={priority}, 按键=left, 路径={os.path.basename(image_path)}")
                    else:
                        # 更新现有设置
                        self.template_settings[template_id]['priority'] = priority
                        self.template_settings[template_id]['enabled'] = True
                        self.template_settings[template_id]['image_path'] = image_path
                        self.template_settings[template_id]['folder_info'] = folder_info['name']
                        self.emit_log(f"更新模板设置 {template_id}: 优先级={priority}, 路径={os.path.basename(image_path)}")
            
            if failed_count > 0:
                self.emit_log(f"从文件夹加载失败 {failed_count} 个模板图像")
            
            return success_count, failed_count, folder_info
            
        except Exception as e:
            self.emit_log(f"从文件夹加载模板异常: {e}")
            import traceback
            self.emit_log(f"错误详情: {traceback.format_exc()}")
            return 0, 0, None