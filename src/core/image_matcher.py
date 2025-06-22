import cv2
import numpy as np
import os
import math  # 添加缺失的导入
from PIL import Image
import time

class ImageMatcher:
    """图像匹配器类 - 支持多位置匹配、螺旋点击和优先级处理"""
    
    def __init__(self, window_manager):
        self.window_manager = window_manager
        self.template_images = {}
        self.template_priorities = {}  
        self.match_threshold = 0.7
        self.multi_match_threshold = 0.8  
        self.max_matches_per_template = 10  
        
        # 🚦 预选项相关 - 确保初始化
        self.preselect_image = None
        self.preselect_threshold = 0.8
    
        self.match_methods = {
            'TM_CCOEFF_NORMED': cv2.TM_CCOEFF_NORMED,
            'TM_CCORR_NORMED': cv2.TM_CCORR_NORMED,
            'TM_SQDIFF_NORMED': cv2.TM_SQDIFF_NORMED
        }
        self.current_method = cv2.TM_CCOEFF_NORMED
        
        # 性能优化
        self.last_screenshot_hash = None
        self.cached_results = {}
        
        self.template_cache = {}  # 模板缓存
        self.last_match_time = 0  # 上次匹配时间
        self.round_start_time = 0  # 回合开始时间
        self.round_delay = 3.0  # 回合开始后的延迟时间（秒）
        self.match_interval = 0.5  # 匹配间隔时间（秒）
        self.screenshot_interval = 0.3  # 截图间隔时间（秒）
        
    def set_template_priority(self, template_id, priority):
        """设置模板优先级"""
        self.template_priorities[template_id] = int(priority)
        
    def get_template_priority(self, template_id):
        """获取模板优先级"""
        return self.template_priorities.get(template_id, 99)  # 默认最低优先级
        
    def get_priority_sorted_templates(self):
        """获取按优先级排序的模板ID列表"""
        template_list = []
        for template_id in self.template_images.keys():
            priority = self.get_template_priority(template_id)
            template_list.append((template_id, priority))
        
        # 按优先级排序（数字越小优先级越高）
        template_list.sort(key=lambda x: x[1])
        return [template_id for template_id, _ in template_list]
        
    def set_template_image(self, template_id, image_path):
        """设置模板图像"""
        try:
            if not os.path.exists(image_path):
                print(f"图像文件不存在: {image_path}")
                return False
                
            # 使用PIL库加载图像，解决中文路径问题
            try:
                from PIL import Image
                pil_image = Image.open(image_path)
                # 转换为numpy数组
                import numpy as np
                template = np.array(pil_image)
                # 如果是RGBA格式，转换为RGB
                if template.shape[2] == 4:
                    template = template[:, :, :3]
            except Exception as e:
                print(f"使用PIL加载图像失败，尝试使用OpenCV: {e}")
                # 备用方案：使用OpenCV加载图像
                template = cv2.imread(image_path, cv2.IMREAD_COLOR)
                
            if template is None:
                print(f"无法加载图像: {image_path}")
                return False
                
            # 转换为RGB格式（OpenCV默认是BGR）
            if len(template.shape) == 3 and template.shape[2] == 3:
                if 'PIL' not in str(type(pil_image)):  # 如果不是通过PIL加载的，需要转换颜色空间
                    template_rgb = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
                else:
                    template_rgb = template  # PIL已经是RGB格式
            else:
                print(f"图像格式不支持: {image_path}, 形状: {template.shape}")
                return False
            
            # 存储模板图像
            self.template_images[template_id] = {
                'image': template_rgb,
                'path': image_path,
                'filename': os.path.basename(image_path),
                'size': template_rgb.shape[:2]  # (height, width)
            }
            
            # 清除相关缓存
            if template_id in self.cached_results:
                del self.cached_results[template_id]
            
            print(f"成功加载模板图像 {template_id}: {os.path.basename(image_path)}, 尺寸: {template_rgb.shape}")
            return True
            
        except Exception as e:
            print(f"加载模板图像失败 {template_id}: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
            return False
            
    def set_match_threshold(self, threshold):
        """设置匹配阈值"""
        try:
            self.match_threshold = max(0.0, min(1.0, float(threshold)))
            self.multi_match_threshold = max(self.match_threshold, 0.8)  # 多匹配阈值稍高
            print(f"设置匹配阈值: {self.match_threshold}")
            
            # 清除缓存
            self.cached_results.clear()
            
        except (ValueError, TypeError) as e:
            print(f"设置匹配阈值失败: {e}")
            
    def calculate_screenshot_hash(self, screenshot):
        """计算截图的简单哈希值（用于缓存）"""
        try:
            # 缩小图像并计算均值作为简单哈希
            small = cv2.resize(screenshot, (32, 32))
            return hash(small.tobytes())
        except:
            return None
            
    def find_template(self, screenshot, template_id):
        """查找单个模板"""
        if template_id not in self.template_images:
            return None
            
        try:
            template_data = self.template_images[template_id]
            template = template_data['image']
            
            # 确保截图是RGB格式
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                search_image = screenshot
            else:
                search_image = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
            
            # 执行模板匹配
            result = cv2.matchTemplate(search_image, template, self.current_method)
            
            # 根据匹配方法处理结果
            if self.current_method == cv2.TM_SQDIFF_NORMED:
                # 对于SQDIFF，值越小越好
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                best_confidence = 1.0 - min_val
                best_location = min_loc
                threshold = 1.0 - self.match_threshold
            else:
                # 对于其他方法，值越大越好
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                best_confidence = max_val
                best_location = max_loc
                threshold = self.match_threshold
            
            # 获取模板尺寸
            template_height, template_width = template.shape[:2]
            
            # 查找所有匹配位置
            all_positions = []
            if self.current_method == cv2.TM_SQDIFF_NORMED:
                locations = np.where(result <= threshold)
            else:
                locations = np.where(result >= threshold)
            
            # 处理所有匹配位置
            for pt in zip(*locations[::-1]):  # 切换x,y坐标
                confidence = result[pt[1], pt[0]]
                if self.current_method == cv2.TM_SQDIFF_NORMED:
                    confidence = 1.0 - confidence
                
                # 修改中心点计算方式，使用整数计算避免浮点误差
                center_x = pt[0] + template_width // 2
                center_y = pt[1] + template_height // 2
                
                # 只添加置信度足够高的匹配
                if confidence >= self.match_threshold:
                    all_positions.append((center_x, center_y, confidence))
            
            # 去除重复的匹配（距离太近的视为同一个）
            filtered_positions = self.filter_nearby_matches(all_positions, min_distance=template_width//3)
            
            # 按置信度排序并限制数量
            filtered_positions.sort(key=lambda x: x[2], reverse=True)
            filtered_positions = filtered_positions[:self.max_matches_per_template]
            
            # 准备返回结果
            if filtered_positions:
                # 最佳匹配（置信度最高的）
                best_match = filtered_positions[0]
                best_position = (best_match[0], best_match[1])
                best_confidence = best_match[2]
                
                # 所有匹配位置（只返回坐标）
                all_match_positions = [(pos[0], pos[1]) for pos in filtered_positions]
                
                priority = self.get_template_priority(template_id)
                
                return {
                    'found': True,
                    'template_id': template_id,
                    'priority': priority,
                    'position': best_position,
                    'confidence': best_confidence,
                    'all_positions': all_match_positions,
                    'match_count': len(all_match_positions),
                    'template_size': (template_width, template_height)
                }
            else:
                priority = self.get_template_priority(template_id)
                return {
                    'found': False,
                    'template_id': template_id,
                    'priority': priority,
                    'position': None,
                    'confidence': 0.0,
                    'all_positions': [],
                    'match_count': 0,
                    'template_size': (template_width, template_height)
                }
                
        except Exception as e:
            print(f"模板匹配异常 {template_id}: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
            return {
                'found': False,
                'template_id': template_id,
                'priority': self.get_template_priority(template_id),
                'position': None,
                'confidence': 0.0,
                'all_positions': [],
                'match_count': 0,
                'error': str(e)
            }
            
    def filter_nearby_matches(self, positions, min_distance=30):
        """过滤距离太近的匹配点"""
        if not positions:
            return []
            
        filtered = []
        
        # 按置信度排序
        sorted_positions = sorted(positions, key=lambda x: x[2], reverse=True)
        
        for current in sorted_positions:
            current_x, current_y, current_conf = current
            
            # 检查是否与已选择的点距离太近
            is_far_enough = True
            for selected in filtered:
                selected_x, selected_y, selected_conf = selected
                distance = math.sqrt((current_x - selected_x)**2 + (current_y - selected_y)**2)
                
                # 如果距离太近，且当前点的置信度不比已选点高很多，则跳过
                if distance < min_distance:
                    # 只有当当前点的置信度比已选点高20%以上时才替换
                    if current_conf <= selected_conf * 1.2:
                        is_far_enough = False
                        break
            
            if is_far_enough:
                filtered.append(current)
                
        return filtered
        
    def find_all_templates(self, screenshot):
        """查找所有模板 - 按优先级顺序处理"""
        results = {}
        
        if not self.template_images:
            return results
            
        try:
            # 计算截图哈希用于缓存
            screenshot_hash = self.calculate_screenshot_hash(screenshot)
            
            # 获取按优先级排序的模板
            priority_sorted_templates = self.get_priority_sorted_templates()
            
            for template_id in priority_sorted_templates:
                try:
                    # 检查缓存
                    cache_key = (template_id, screenshot_hash)
                    if cache_key in self.cached_results:
                        results[template_id] = self.cached_results[cache_key]
                        continue
                    
                    # 执行匹配
                    result = self.find_template(screenshot, template_id)
                    
                    if result:
                        results[template_id] = result
                        
                        # 缓存结果
                        if screenshot_hash:
                            self.cached_results[cache_key] = result
                        
                        # 如果是高优先级模板匹配成功，可以提前返回
                        priority = result.get('priority', 99)
                        if result.get('found', False) and priority <= 2:
                            # 高优先级匹配成功，记录日志并继续（不中断，让控制器决定）
                            print(f"高优先级模板 {template_id}(优先级{priority}) 匹配成功")
                            
                except Exception as e:
                    print(f"处理模板 {template_id} 时出错: {e}")
                    continue
            
            # 清理过期缓存
            self.cleanup_cache()
            
        except Exception as e:
            print(f"查找所有模板时出错: {e}")
            
        return results
        
    def find_templates_by_priority(self, screenshot, max_priority=10):
        """按优先级查找模板，只处理指定优先级及以上的模板"""
        results = {}
        
        if not self.template_images:
            return results
            
        try:
            # 获取按优先级排序的模板
            priority_sorted_templates = self.get_priority_sorted_templates()
            
            for template_id in priority_sorted_templates:
                priority = self.get_template_priority(template_id)
                
                # 只处理指定优先级及以上的模板
                if priority > max_priority:
                    continue
                    
                try:
                    result = self.find_template(screenshot, template_id)
                    if result:
                        results[template_id] = result
                        
                        # 如果找到高优先级匹配，立即返回
                        if result.get('found', False) and priority <= 2:
                            print(f"找到高优先级匹配，停止处理: 模板{template_id}(优先级{priority})")
                            break
                            
                except Exception as e:
                    print(f"处理优先级模板 {template_id} 时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"按优先级查找模板时出错: {e}")
            
        return results
        
    def cleanup_cache(self):
        """清理缓存"""
        try:
            # 如果缓存太大，清理一部分
            if len(self.cached_results) > 100:
                # 保留最近的50个结果
                cache_items = list(self.cached_results.items())
                self.cached_results = dict(cache_items[-50:])
        except:
            pass
            
    def get_template_info(self, template_id):
        """获取模板信息"""
        if template_id not in self.template_images:
            return None
            
        template_data = self.template_images[template_id]
        priority = self.get_template_priority(template_id)
        
        return {
            'template_id': template_id,
            'priority': priority,
            'filename': template_data['filename'],
            'path': template_data['path'],
            'size': template_data['size'],
            'loaded': True
        }
        
    def get_all_templates_info(self):
        """获取所有模板信息"""
        templates_info = []
        
        # 按优先级排序
        priority_sorted_templates = self.get_priority_sorted_templates()
        
        for template_id in priority_sorted_templates:
            info = self.get_template_info(template_id)
            if info:
                templates_info.append(info)
                
        return templates_info
        
    def remove_template(self, template_id):
        """移除模板"""
        try:
            if template_id in self.template_images:
                del self.template_images[template_id]
                
            if template_id in self.template_priorities:
                del self.template_priorities[template_id]
                
            # 清理相关缓存
            cache_keys_to_remove = [key for key in self.cached_results.keys() if key[0] == template_id]
            for key in cache_keys_to_remove:
                del self.cached_results[key]
                
            print(f"已移除模板 {template_id}")
            return True
            
        except Exception as e:
            print(f"移除模板失败 {template_id}: {e}")
            return False
            
    def clear_all_templates(self):
        """清除所有模板"""
        self.template_images.clear()
        self.template_priorities.clear()
        self.cached_results.clear()
        print("已清除所有模板")
        
    def get_statistics(self):
        """获取统计信息"""
        total_templates = len(self.template_images)
        priority_distribution = {}
        
        for template_id in self.template_images.keys():
            priority = self.get_template_priority(template_id)
            if priority not in priority_distribution:
                priority_distribution[priority] = 0
            priority_distribution[priority] += 1
            
        return {
            'total_templates': total_templates,
            'priority_distribution': priority_distribution,
            'cache_size': len(self.cached_results),
            'match_threshold': self.match_threshold,
            'multi_match_threshold': self.multi_match_threshold,
            'max_matches_per_template': self.max_matches_per_template
        }
        
    def set_match_method(self, method_name):
        """设置匹配方法"""
        if method_name in self.match_methods:
            self.current_method = self.match_methods[method_name]
            # 清除缓存
            self.cached_results.clear()
            print(f"设置匹配方法: {method_name}")
            return True
        else:
            print(f"不支持的匹配方法: {method_name}")
            return False
            
    def get_available_methods(self):
        """获取可用的匹配方法"""
        return list(self.match_methods.keys())
        
    def validate_templates(self):
        """验证所有模板的有效性"""
        invalid_templates = []
        
        for template_id, template_data in self.template_images.items():
            try:
                path = template_data['path']
                if not os.path.exists(path):
                    invalid_templates.append(template_id)
                    continue
                    
                # 尝试重新加载图像
                img = cv2.imread(path, cv2.IMREAD_COLOR)
                if img is None:
                    invalid_templates.append(template_id)
                    
            except Exception as e:
                print(f"验证模板 {template_id} 时出错: {e}")
                invalid_templates.append(template_id)
                
        # 移除无效模板
        for template_id in invalid_templates:
            self.remove_template(template_id)
            
        if invalid_templates:
            print(f"移除了 {len(invalid_templates)} 个无效模板: {invalid_templates}")
            
        return len(invalid_templates) == 0
    
    def set_preselect_image(self, image_path):
        """设置预选项图片"""
        try:
            if not os.path.exists(image_path):
                print(f"预选项图像文件不存在: {image_path}")
                return False
                
            # 使用PIL库加载图像，解决中文路径问题
            try:
                from PIL import Image
                pil_image = Image.open(image_path)
                # 转换为numpy数组
                import numpy as np
                preselect_img = np.array(pil_image)
                # 如果是RGBA格式，转换为RGB
                if preselect_img.shape[2] == 4:
                    preselect_img = preselect_img[:, :, :3]
            except Exception as e:
                print(f"[预选项] 使用PIL加载图像失败，尝试使用OpenCV: {e}")
                # 备用方案：使用OpenCV加载图像
                preselect_img = cv2.imread(image_path, cv2.IMREAD_COLOR)
            
            if preselect_img is None:
                print(f"无法加载预选项图像: {image_path}")
                return False
            
            # 转换为RGB格式
            if len(preselect_img.shape) == 3 and preselect_img.shape[2] == 3:
                if 'PIL' not in str(type(pil_image)):  # 如果不是通过PIL加载的，需要转换颜色空间
                    preselect_rgb = cv2.cvtColor(preselect_img, cv2.COLOR_BGR2RGB)
                else:
                    preselect_rgb = preselect_img  # PIL已经是RGB格式
            else:
                print(f"[预选项] 图像格式不支持: {image_path}, 形状: {preselect_img.shape}")
                return False
            
            self.preselect_image = {
                'image': preselect_rgb,
                'path': image_path,
                'filename': os.path.basename(image_path),
                'size': preselect_rgb.shape[:2]  # (height, width)
            }
            
            print(f"[预选项] 成功加载预选项图像: {os.path.basename(image_path)}, 尺寸: {preselect_rgb.shape}")
            return True
            
        except Exception as e:
            print(f"[预选项] 加载预选项图像失败: {e}")
            import traceback
            print(f"[预选项] 预选项错误详情: {traceback.format_exc()}")
            return False

    def clear_preselect_image(self):
        """清除预选项图片"""
        self.preselect_image = None
        print("[预选项] 已清除预选项图像")

    def set_preselect_threshold(self, threshold):
        """设置预选项阈值"""
        try:
            self.preselect_threshold = max(0.0, min(1.0, float(threshold)))
            print(f"[预选项] 预选项阈值设置为: {self.preselect_threshold}")
        except Exception as e:
            print(f"[预选项] 设置预选项阈值失败: {e}")

    def find_preselect_image(self, screenshot):
        """查找预选项图片 - 最高优先级匹配"""
        if not self.preselect_image:
            print("[预选项] 预选项图像未设置")
            return None
            
        try:
            preselect_template = self.preselect_image['image']
            
            # 确保截图是RGB格式
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                search_image = screenshot
            else:
                search_image = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
            
            print(f"[预选项] 开始预选项匹配: 模板尺寸={preselect_template.shape}, 截图尺寸={search_image.shape}, 阈值={self.preselect_threshold}")
            
            # 执行模板匹配
            result = cv2.matchTemplate(search_image, preselect_template, self.current_method)
            
            # 根据匹配方法处理结果
            if self.current_method == cv2.TM_SQDIFF_NORMED:
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                best_confidence = 1.0 - min_val
                best_location = min_loc
                threshold = 1.0 - self.preselect_threshold
                found = min_val <= threshold
                print(f"[预选项] SQDIFF方法: min_val={min_val}, threshold={threshold}, found={found}")
            else:
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                best_confidence = max_val
                best_location = max_loc
                threshold = self.preselect_threshold
                found = max_val >= threshold
                print(f"[预选项] {self.current_method}方法: max_val={max_val}, threshold={threshold}, found={found}")
        
            # 计算中心点位置
            template_height, template_width = preselect_template.shape[:2]
            center_x = best_location[0] + template_width // 2
            center_y = best_location[1] + template_height // 2
            
            # 详细的调试信息
            print(f"[预选项] 预选项匹配结果: 置信度={best_confidence:.3f}, 位置=({center_x}, {center_y}), 找到={found}")
            
            return {
                'found': found,
                'position': (center_x, center_y),
                'confidence': best_confidence,
                'template_size': (template_width, template_height),
                'threshold_used': threshold,
                'raw_confidence': max_val if self.current_method != cv2.TM_SQDIFF_NORMED else min_val
            }
            
        except Exception as e:
            print(f"[预选项] 预选项匹配异常: {e}")
            import traceback
            print(f"[预选项] 预选项错误详情: {traceback.format_exc()}")
            return {
                'found': False,
                'position': None,
                'confidence': 0.0,
                'error': str(e)
            }

    def match_template(self, template_path, threshold=0.8, max_retries=3, retry_interval=0.5):
        """匹配模板图片"""
        try:
            current_time = time.time()
            
            # 检查是否在回合开始后的延迟时间内
            if self.round_start_time > 0 and current_time - self.round_start_time < self.round_delay:
                print(f"[图像匹配] 回合开始后延迟中: {self.round_delay - (current_time - self.round_start_time):.1f}秒")
                return None
                
            # 检查匹配间隔
            if current_time - self.last_match_time < self.match_interval:
                return None
                
            # 检查截图间隔
            if current_time - self.last_match_time < self.screenshot_interval:
                return None
                
            self.last_match_time = current_time
            
            # 获取窗口截图
            screenshot = self.window_manager.get_window_screenshot()
            if screenshot is None:
                return None
                
            # 获取模板图片
            template = self.get_template(template_path)
            if template is None:
                return None
                
            # 执行模板匹配
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                # 计算中心点坐标
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                print(f"[图像匹配] 匹配成功: {template_path}, 相似度={max_val:.2f}, 位置=({center_x}, {center_y})")
                return (center_x, center_y)
            else:
                print(f"[图像匹配] 匹配失败: {template_path}, 相似度={max_val:.2f}")
                return None
                
        except Exception as e:
            print(f"[图像匹配] 匹配异常: {e}")
            return None
            
    def start_new_round(self):
        """开始新的回合"""
        self.round_start_time = time.time()
        print(f"[图像匹配] 开始新回合，延迟时间: {self.round_delay}秒")
        
    def end_round(self):
        """结束当前回合"""
        self.round_start_time = 0
        print("[图像匹配] 回合结束")

    def load_templates_from_directory(self, directory_path, priority, folder_name=None):
        """从文件夹加载模板图像，所有图片使用相同的优先级
        
        Args:
            directory_path: 文件夹路径
            priority: 所有图片的优先级
            folder_name: 文件夹名称（可选，用于显示）
            
        Returns:
            tuple: (成功加载的图片数量, 加载失败的图片数量, 文件夹信息)
        """
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                print(f"文件夹不存在或不是有效目录: {directory_path}")
                return 0, 0, None
            
            # 获取文件夹中的所有图片文件
            image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
            image_files = []
            
            for file in os.listdir(directory_path):
                file_path = os.path.join(directory_path, file)
                if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in image_extensions:
                    image_files.append(file_path)
            
            if not image_files:
                print(f"文件夹中没有找到图片文件: {directory_path}")
                return 0, 0, None
            
            # 按文件名排序
            image_files.sort()
            
            # 找到当前最大的模板ID
            current_max_id = 0
            for template_id in self.template_images.keys():
                if isinstance(template_id, int) and template_id > current_max_id:
                    current_max_id = template_id
            
            # 加载图片
            success_count = 0
            failed_count = 0
            template_ids = []
            
            for i, image_path in enumerate(image_files):
                template_id = current_max_id + i + 1
                
                if self.set_template_image(template_id, image_path):
                    self.set_template_priority(template_id, priority)  # 所有图片使用相同的优先级
                    template_ids.append(template_id)
                    success_count += 1
                    print(f"从文件夹加载模板 {template_id}: {os.path.basename(image_path)}, 优先级: {priority}")
                else:
                    failed_count += 1
                    print(f"从文件夹加载模板失败: {image_path}")
            
            # 如果未提供文件夹名称，则使用路径的最后一部分
            if folder_name is None:
                folder_name = os.path.basename(directory_path)
                if not folder_name:  # 如果是根目录
                    folder_name = directory_path
            
            folder_info = {
                'path': directory_path,
                'name': folder_name,
                'priority': priority,
                'template_ids': template_ids,
                'count': success_count
            }
                
            print(f"从文件夹加载完成: {directory_path}, 成功: {success_count}, 失败: {failed_count}")
            return success_count, failed_count, folder_info
            
        except Exception as e:
            print(f"从文件夹加载模板失败: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
            return 0, 0, None