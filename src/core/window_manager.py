import subprocess
from PIL import Image, ImageGrab
import numpy as np
import pyautogui
import os
import platform
import win32gui
import win32ui
import win32con
import win32api
import win32process
import time
import ctypes

class WindowManager:
    """窗口管理器 - 处理窗口操作和后台点击"""
    
    def __init__(self):
        self.target_window_handle = None
        self.target_window_id = None
        
        # 禁用pyautogui的安全模式
        pyautogui.FAILSAFE = False
        
        print("[窗口管理器] 初始化完成")

    def get_window_list(self):
        """获取所有可见窗口的列表"""
        windows = []
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title.strip():  # 只显示有标题的窗口
                    windows.append((hwnd, window_title))
            return True
        
        try:
            win32gui.EnumWindows(enum_windows_callback, windows)
            print(f"[窗口管理器] 找到 {len(windows)} 个可见窗口")
            return windows
        except Exception as e:
            print(f"[窗口管理器] 获取窗口列表失败: {e}")
            return []

    def set_target_window(self, window_id):
        """设置目标窗口"""
        try:
            print(f"[窗口管理器] 设置目标窗口: {window_id}")
            
            # 验证窗口ID
            if not win32gui.IsWindow(window_id):
                print(f"[窗口管理器] 无效的窗口ID: {window_id}")
                return False
            
            self.target_window_id = window_id
            self.target_window_handle = window_id
            
            # 获取窗口信息进行验证
            try:
                window_title = win32gui.GetWindowText(window_id)
                window_rect = win32gui.GetWindowRect(window_id)
                is_visible = win32gui.IsWindowVisible(window_id)
                
                print(f"[窗口管理器] 窗口信息: 标题='{window_title}', 矩形={window_rect}, 可见={is_visible}")
                
                if window_rect[2] - window_rect[0] <= 0 or window_rect[3] - window_rect[1] <= 0:
                    print(f"[窗口管理器] 警告: 窗口尺寸无效")
                    
            except Exception as e:
                print(f"[窗口管理器] 获取窗口信息失败: {e}")
            
            print(f"[窗口管理器] 目标窗口设置成功: {window_id}")
            return True
            
        except Exception as e:
            print(f"[窗口管理器] 设置目标窗口失败: {e}")
            self.target_window_id = None
            self.target_window_handle = None
            return False

    def get_window_screenshot(self):
        """获取窗口截图 - 支持最小化和被遮挡的窗口"""
        if not self.target_window_handle:
            print("[窗口管理器] 未设置目标窗口句柄")
            return None

        try:
            # 检查窗口是否存在和有效
            if not win32gui.IsWindow(self.target_window_handle):
                print(f"[窗口管理器] 目标窗口句柄无效: {self.target_window_handle}")
                return None

            # 获取窗口矩形
            window_rect = win32gui.GetWindowRect(self.target_window_handle)
            left, top, right, bottom = window_rect
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                print(f"[窗口管理器] 窗口尺寸无效: {width}x{height}")
                return None

            # 获取客户区矩形
            client_rect = win32gui.GetClientRect(self.target_window_handle)
            client_width = client_rect[2]
            client_height = client_rect[3]

            # 计算边框和标题栏的偏移
            border_width = ((right - left) - client_width) // 2
            title_height = (bottom - top) - client_height - border_width

            try:
                # 获取窗口DC
                hwnd_dc = win32gui.GetWindowDC(self.target_window_handle)
                try:
                    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                    save_dc = mfc_dc.CreateCompatibleDC()
                    save_bitmap = win32ui.CreateBitmap()
                    save_bitmap.CreateCompatibleBitmap(mfc_dc, client_width, client_height)
                    save_dc.SelectObject(save_bitmap)

                    # 使用BitBlt替代PrintWindow，确保能捕获最小化窗口
                    save_dc.BitBlt((0, 0), (client_width, client_height), mfc_dc, (border_width, title_height), win32con.SRCCOPY)
                    
                    # 获取位图数据
                    bmp_str = save_bitmap.GetBitmapBits(True)
                    
                    # 清理资源
                    win32gui.DeleteObject(save_bitmap.GetHandle())
                    save_dc.DeleteDC()
                    mfc_dc.DeleteDC()
                    
                    # 转换为numpy数组
                    img_array = np.frombuffer(bmp_str, dtype='uint8')
                    img_array.shape = (client_height, client_width, 4)
                    
                    # 转换为RGB格式
                    img_rgb = img_array[:, :, [2, 1, 0]]  # BGR -> RGB
                    
                    print(f"[窗口管理器] 截图成功: {client_width}x{client_height}")
                    return img_rgb
                finally:
                    win32gui.ReleaseDC(self.target_window_handle, hwnd_dc)
            except Exception as e:
                print(f"[窗口管理器] BitBlt方法失败: {e}")

            print("[窗口管理器] 所有截图方法都失败")
            return None
            
        except Exception as e:
            print(f"[窗口管理器] 截图异常: {e}")
            import traceback
            print(f"[窗口管理器] 详细错误: {traceback.format_exc()}")
            return None
        
    def get_window_state(self):
        """获取窗口状态"""
        if not self.target_window_handle:
            return "未设置"
        
        try:
            # 检查窗口是否存在
            if not win32gui.IsWindow(self.target_window_handle):
                return "不存在"
            
            # 检查窗口是否可见
            if not win32gui.IsWindowVisible(self.target_window_handle):
                return "隐藏"
            
            # 检查窗口是否最小化
            if win32gui.IsIconic(self.target_window_handle):
                return "最小化"
            
            # 检查窗口是否最大化 - 使用兼容的方法
            try:
                # 尝试使用 GetWindowPlacement 代替 IsZoomed
                placement = win32gui.GetWindowPlacement(self.target_window_handle)
                if placement and len(placement) >= 2 and placement[1] == win32con.SW_SHOWMAXIMIZED:
                    return "最大化"
            except AttributeError:
                # 如果 GetWindowPlacement 也不可用，使用简单判断
                screen_rect = (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
                window_rect = win32gui.GetWindowRect(self.target_window_handle)
                if window_rect[0] <= 0 and window_rect[1] <= 0 and \
                   abs(window_rect[2] - screen_rect[2]) < 20 and abs(window_rect[3] - screen_rect[3]) < 20:
                    return "最大化"
            
            # 检查窗口是否在前台
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd != self.target_window_handle:
                return "被遮挡"
            
            # 如果都不是上述情况，则窗口处于正常显示状态
            return "正常显示"
        
        except Exception as e:
            print(f"[窗口管理器] 获取窗口状态失败: {e}")
            return "未知"
    
    def click_at_position(self, x, y, button="left", window_relative=True):
        """在指定位置点击 - 纯后台实现，在目标窗口客户区域内点击"""
        if not self.target_window_handle:
            print("[窗口管理器] 未设置目标窗口")
            return False
        
        try:
            if window_relative:
                # 添加实际点击坐标的输出
                print(f"[窗口管理器] 收到点击请求: 原始坐标=({x}, {y}), 按键={button}")
                
                # 获取客户区信息用于调试
                client_rect = win32gui.GetClientRect(self.target_window_handle)
                print(f"[窗口管理器] 客户区大小: {client_rect}")
                
                # 将浮点数坐标转换为整数 - 使用int而非round，避免四舍五入导致的偏移
                x = int(x)
                y = int(y)
                
                # 添加坐标修正 - 如果目标窗口需要偏移修正，在这里调整
                # x += 偏移值X  # 例如: x += 5
                # y += 偏移值Y  # 例如: y += 10
                
                print(f"[窗口管理器] 实际点击坐标: ({x}, {y}), 按键={button}")
                
                # 方法1: 使用PostMessage方法（异步消息，不阻塞）
                try:
                    # 构造鼠标消息参数
                    lParam = win32api.MAKELONG(x, y)
                    
                    if button == "left":
                        down_msg = win32con.WM_LBUTTONDOWN
                        up_msg = win32con.WM_LBUTTONUP
                        btn_down = win32con.MK_LBUTTON
                    else:
                        down_msg = win32con.WM_RBUTTONDOWN
                        up_msg = win32con.WM_RBUTTONUP
                        btn_down = win32con.MK_RBUTTON
                    
                    # 发送鼠标按下和抬起消息
                    win32gui.PostMessage(self.target_window_handle, down_msg, btn_down, lParam)
                    time.sleep(0.05)
                    
                    win32gui.PostMessage(self.target_window_handle, up_msg, 0, lParam)
                    time.sleep(0.05)
                    
                    print(f"[窗口管理器] PostMessage点击完成: ({x}, {y})")
                    return True
                    
                except Exception as e:
                    print(f"[窗口管理器] PostMessage方法失败: {e}")
                
                # 方法2: 使用SendMessage方法（同步消息，更可靠但可能阻塞）
                try:
                    # 构造鼠标消息参数
                    lParam = win32api.MAKELONG(x, y)
                    
                    if button == "left":
                        down_msg = win32con.WM_LBUTTONDOWN
                        up_msg = win32con.WM_LBUTTONUP
                        btn_down = win32con.MK_LBUTTON
                    else:
                        down_msg = win32con.WM_RBUTTONDOWN
                        up_msg = win32con.WM_RBUTTONUP
                        btn_down = win32con.MK_RBUTTON
                    
                    # 发送鼠标按下和抬起消息
                    print(f"[窗口管理器] 发送鼠标按下消息(SendMessage): {down_msg}, 参数={lParam}")
                    win32gui.SendMessage(self.target_window_handle, down_msg, btn_down, lParam)
                    time.sleep(0.05)
                    
                    print(f"[窗口管理器] 发送鼠标抬起消息(SendMessage): {up_msg}, 参数={lParam}")
                    win32gui.SendMessage(self.target_window_handle, up_msg, 0, lParam)
                    time.sleep(0.05)
                    
                    print(f"[窗口管理器] SendMessage点击完成: ({x}, {y})")
                    return True
                    
                except Exception as e:
                    print(f"[窗口管理器] SendMessage方法失败: {e}")
                
                print(f"[窗口管理器] 所有点击方法都失败")
                return False
            else:
                # 绝对坐标模式 - 转换为窗口相对坐标
                try:
                    # 获取窗口客户区位置
                    client_rect = win32gui.GetClientRect(self.target_window_handle)
                    window_rect = win32gui.GetWindowRect(self.target_window_handle)
                    
                    # 计算边框和标题栏的偏移
                    border_width = ((window_rect[2] - window_rect[0]) - client_rect[2]) // 2
                    title_height = (window_rect[3] - window_rect[1]) - client_rect[3] - border_width
                    
                    # 将屏幕坐标转换为窗口客户区坐标
                    relative_x = x - (window_rect[0] + border_width)
                    relative_y = y - (window_rect[1] + title_height)
                    
                    print(f"[窗口管理器] 坐标转换: 屏幕({x}, {y}) -> 窗口内({relative_x}, {relative_y})")
                    
                    # 使用窗口相对坐标进行点击
                    return self.click_at_position(relative_x, relative_y, button, True)
                    
                except Exception as e:
                    print(f"[窗口管理器] 坐标转换失败: {e}")
                    return False
                    
        except Exception as e:
            print(f"[窗口管理器] 点击失败: {e}")
            import traceback
            print(f"[窗口管理器] 错误详情: {traceback.format_exc()}")
            return False


