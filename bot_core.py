import win32api
import win32con
import pyautogui
import cv2
import numpy as np
from win32 import win32gui
import time
import random
import os
import sys
from pynput import keyboard

from game_ocr import GameOCR, load_skill_config, ROI

TEXT = {
    "receive": "领取",
    "continue": "点击屏幕继续",
    "huanqiu": "寰球救援",
    "in_huanqiu_team": "难度",
    "leave": "离开",
    "exit": "退出",
    "return": "返回",
    "sure": "确定",
    "auto_close": "自动关闭",
    "choose_skill": "选择技能",
    "think_tank": "智库",
    "open_skills": "已激活技能",
    "battle": "战斗",
    "card_normal": "普通",
    "card_start": "开始游戏",
    "orange_start": "开始游戏",
    "start_game_button": "开始游戏",
    "start_challenge": "开始挑战",
    "base": "基地",
    "experience": "历练大厅",
    "huanqiu_challenge": "寰球救援",
    "huanqiu_invite": "邀请",
    "huanqiu_post_recruitment": "发布招募",
    "expedition_challenge": "挑战",
    "expedition_continue": "点击空白处继续",
    "expedition_difficulty": "困难",
    "expedition_fast_join": "快速加入",
    "expedition_health_100": "100%",
    "expedition_normal": "普通",
    "expedition_ready": "准备",
    "expedition_team": "远征一队",
    "expedition_team_2": "远征二队",
    "expedition_team_hall": "组队大厅",
    "battling_skip": "点击空白处跳过",
    "battling_elite": "精英掉落",
    "grade_level": "等级提升",
    "home_close_text": "已置换",
}


class GameBotCore:
    def __init__(
        self,
        game_title="游戏窗口标题",
        battle_time=0,
        max_battle_count=0,
        mode=0,
        priority_skills=None,
        rich_mode=0,
        wait_time=60,
        quick_exit=False,
        init_ocr=True,
    ):
        self.running = True
        self.hotkey_listener = None
        self.game_title = game_title
        self.battle_time = battle_time
        self.current_battle_time = 0
        self.max_battle_count = max_battle_count
        self.game_window = None
        self.screenshot_dir = "screenshots"
        self.priority_skills = priority_skills if priority_skills else []
        self.rich_mode = rich_mode
        self.quick_exit = quick_exit
        self.on_battle_count_changed = None
        self.expedition_in_team_max_time = time.time() + wait_time
        self.wait_time = wait_time
        self.battle_count = 0
        self.last_battle_count_time = 0

        if getattr(sys, "frozen", False):
            self.template_dir = os.path.join(sys._MEIPASS, "templates")
        else:
            self.template_dir = "templates"

        self.mode = mode

        self.template_cache = {}
        self._preload_templates()

        self._screenshot_bgr = None
        self._screenshot_time = 0
        self._screenshot_ttl = 0.1

        os.makedirs(self.screenshot_dir, exist_ok=True)

        self.skills = load_skill_config()
        self.ocr = None
        if init_ocr:
            self.ocr = GameOCR(cache_ttl=0.3, skills=self.skills)
            self.ocr.add_whitelist(list(TEXT.values()))

    def _preload_templates(self):
        if not os.path.exists(self.template_dir):
            print(f"模板目录不存在: {self.template_dir}")
            return
        loaded_count = 0
        for filename in os.listdir(self.template_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                template_path = os.path.join(self.template_dir, filename)
                template = cv2.imread(template_path)
                if template is not None:
                    self.template_cache[filename] = template
                    loaded_count += 1
        print(f"模板预加载完成: {loaded_count} 个模板已加载到内存")

    # —— 窗口管理 ——
    def find_game_window(self):
        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            self.game_window = (left, top, right - left, bottom - top)
            print(f"找到游戏窗口: {self.game_window}")
            return True
        else:
            print("未找到游戏窗口")
            return False

    def resize_game_window(self, width=542, height=1010):
        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            client_rect = win32gui.GetClientRect(hwnd)
            client_width = client_rect[2] - client_rect[0]
            client_height = client_rect[3] - client_rect[1]
            border_width = (right - left) - client_width
            border_height = (bottom - top) - client_height
            window_width = width + border_width
            window_height = height + border_height
            win32gui.MoveWindow(hwnd, left, top, window_width, window_height, True)
            self.game_window = (left, top, width, height)
            print(f"游戏窗口已调整为: {self.game_window}")
            return True
        else:
            print("未找到游戏窗口，无法调整大小")
            return False

    def find_fullscreen_window(self):
        try:
            width, height = pyautogui.size()
            left, top = 0, 0
            self.game_window = (left, top, width, height)
            print(f"全屏幕窗口: {self.game_window}")
            return True
        except Exception as e:
            print(f"获取屏幕尺寸时出错: {e}")
            try:
                width = win32gui.GetSystemMetrics(0)
                height = win32gui.GetSystemMetrics(1)
                left, top = 0, 0
                self.game_window = (left, top, width, height)
                print(f"使用备用方法获取全屏幕窗口: {self.game_window}")
                return True
            except Exception as e2:
                print(f"备用方法也失败: {e2}")
                return False

    # —— 截图 ——
    def take_screenshot(self, force_new=False):
        now = time.time()
        if not force_new and self._screenshot_bgr is not None:
            if (now - self._screenshot_time) <= self._screenshot_ttl:
                return self._screenshot_bgr
        if not self.game_window:
            if not self.find_game_window():
                return None
        screenshot = pyautogui.screenshot(region=self.game_window)
        self._screenshot_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        self._screenshot_time = now
        return self._screenshot_bgr

    def save_screenshot(self, filename=None):
        img = self.take_screenshot()
        if img is not None:
            if not filename:
                filename = f"{self.screenshot_dir}/{int(time.time())}.png"
            cv2.imwrite(filename, img)
            print(f"截图已保存: {filename}")
            return filename
        return None

    # —— 点击 ——
    def click(self, x, y, duration=0.2, human_like=True):
        if human_like:
            x += random.randint(-5, 5)
            y += random.randint(-5, 5)
            duration += random.uniform(-0.1, 0.1)
            duration = max(0.1, duration)
        pyautogui.moveTo(x, y, duration=duration)
        pyautogui.click()
        print(f"点击位置: ({x}, {y})")

    def click_fast(self, x, y):
        win32api.SetCursorPos((int(x), int(y)))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def click_fast_batch(self, positions):
        for x, y in positions:
            win32api.SetCursorPos((int(x), int(y)))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05)

    def press_key(self, key, presses=1, interval=0.1, human_like=True):
        if human_like:
            interval += random.uniform(-0.05, 0.05)
            interval = max(0.05, interval)
        pyautogui.press(key, presses=presses, interval=interval)
        print(f"按下按键: {key}")

    # —— 模板匹配（仅图标类保留）——
    def find_template(self, template_name, threshold=0.8):
        if template_name in self.template_cache:
            template = self.template_cache[template_name]
        else:
            template_path = os.path.join(self.template_dir, template_name)
            template = cv2.imread(template_path)
            if template is not None:
                self.template_cache[template_name] = template
        if template is None:
            print(f"无法加载模板: {template_name}")
            return None
        img = self.take_screenshot()
        if img is None:
            return None
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            h, w = template.shape[:2]
            center_x = self.game_window[0] + max_loc[0] + w // 2
            center_y = self.game_window[1] + max_loc[1] + h // 2
            return (center_x, center_y)
        return None

    def find_all_templates(self, template_name, threshold=0.8):
        if template_name in self.template_cache:
            template = self.template_cache[template_name]
        else:
            template_path = os.path.join(self.template_dir, template_name)
            template = cv2.imread(template_path)
            if template is not None:
                self.template_cache[template_name] = template
        if template is None:
            print(f"无法加载模板: {template_name}")
            return []
        img = self.take_screenshot()
        if img is None:
            return []
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        matches = []
        h, w = template.shape[:2]
        for pt in zip(*locations[::-1]):
            center_x = self.game_window[0] + pt[0] + w // 2
            center_y = self.game_window[1] + pt[1] + h // 2
            matches.append((center_x, center_y))
        return matches

    def click_template(self, template_name, sleep_after=0.05):
        pos = self.find_template(template_name)
        if pos:
            self.click(*pos)
            if sleep_after > 0:
                time.sleep(sleep_after)
            return True
        return False

    def click_first_template(self, template_names, sleep_after=0.05):
        for template_name in template_names:
            pos = self.find_template(template_name)
            if pos:
                self.click(*pos)
                if sleep_after > 0:
                    time.sleep(sleep_after)
                return True
        return False

    # —— OCR 识别（坐标自动转屏幕绝对坐标）——
    def find_text(self, text, threshold=0.8, roi=None, correct_ratio=0.8):
        img = self.take_screenshot()
        if img is None:
            return None
        pos = self.ocr.find_text(img, text, threshold, roi=roi, correct_ratio=correct_ratio)
        if pos:
            return (self.game_window[0] + pos[0], self.game_window[1] + pos[1])
        return None

    def find_all_text(self, text, threshold=0.8, roi=None, correct_ratio=0.8):
        img = self.take_screenshot()
        if img is None:
            return []
        positions = self.ocr.find_all_text(
            img, text, threshold, roi=roi, correct_ratio=correct_ratio
        )
        return [
            (self.game_window[0] + x, self.game_window[1] + y) for x, y in positions
        ]

    def find_texts_batch(self, texts, threshold=0.8, roi=None, correct_ratio=0.8):
        img = self.take_screenshot()
        if img is None:
            return {}
        results = self.ocr.find_texts_batch(
            img, texts, threshold, roi=roi, correct_ratio=correct_ratio
        )
        return {
            t: [(self.game_window[0] + x, self.game_window[1] + y) for x, y in pts]
            for t, pts in results.items()
        }

    def click_text(self, text, sleep_after=0.05, roi=None, threshold=0.8):
        pos = self.find_text(text, threshold=threshold, roi=roi)
        if pos:
            self.click(*pos)
            if sleep_after > 0:
                time.sleep(sleep_after)
            return True
        return False

    def click_first_text(self, texts, sleep_after=0.05, roi=None, threshold=0.8):
        for text in texts:
            if self.click_text(text, sleep_after=sleep_after, roi=roi, threshold=threshold):
                return True
        return False

    # —— 通用状态判断 ——
    def find_click_receive(self):
        self.click_text(TEXT["receive"])

    def find_click_im(self):
        self.click_template("im.png")

    def find_click_continue(self):
        self.click_text(TEXT["continue"])

    def find_team_up(self):
        return self.find_template("recruitment-1.png")

    def find_click_recruitment(self):
        while True and self.running:
            team_up = self.find_team_up()
            if not team_up:
                recruitments = ["recruitment.png"]
                in_recruitment = False
                for recruitment in recruitments:
                    xy = self.find_template(recruitment)
                    if xy:
                        self.click(*xy)
                        in_recruitment = True
                        break
                if not in_recruitment:
                    print("未找到招募页面")
                    break
            self.find_click_reconnection()
            for i in range(20):
                try:
                    huanqiu_positions = self.find_all_text(TEXT["huanqiu"])
                    if huanqiu_positions:
                        positions = []
                        for pos in huanqiu_positions:
                            pos = (pos[0] + 150, pos[1])
                            positions.append(pos)
                        if positions:
                            positions.reverse()
                            self.click_fast_batch(positions)
                    else:
                        leave_button = self.find_leave_button()
                        if leave_button:
                            if not self.find_in_huanqiu_team():
                                self.click(*leave_button)
                                time.sleep(0.04)
                                self.find_click_sure()
                except:
                    print("查找环球按钮时出错")
                else:
                    print("未找到招募页面")

    def find_in_huanqiu_team(self):
        if self.find_text(TEXT["in_huanqiu_team"]):
            return True
        return False

    def find_click_home_close(self):
        if self.click_first_template(
            ["home-close.png", "home-close-1.png", "home-close-2.png"]
        ):
            return
        self.click_text(TEXT["home_close_text"])

    def find_click_close(self):
        if self.click_first_template(["close.png"]):
            return True
        return self.click_first_text(
            [TEXT["auto_close"], TEXT["battling_elite"]]
        )

    def find_click_reconnection(self):
        self.click_text("重新连接")

    def find_huanqiu(self):
        return self.find_text(TEXT["huanqiu"])

    def find_click_start_button(self):
        return self.click_text(TEXT["battle"])

    def find_click_sure(self):
        self.click_text(TEXT["sure"])

    def find_click_auto_close(self):
        self.click_text(TEXT["auto_close"])

    def _skill_name_to_text(self, name):
        for s in self.skills:
            if s.get("name") == name:
                return s.get("text", name)
        return name

    def find_click_skill(self):
        self.click_text(TEXT["think_tank"])
        if not self.find_text(TEXT["choose_skill"], roi=ROI["center_dialog"]):
            return None

        skill_texts = [s.get("text") for s in self.skills if s.get("text")]
        priority_texts = [
            self._skill_name_to_text(n) for n in self.priority_skills if n
        ]
        all_texts = priority_texts + [t for t in skill_texts if t not in priority_texts]

        results = self.find_texts_batch(
            all_texts, roi=ROI["skill_area"], correct_ratio=0.6
        )
        for text in all_texts:
            for pos in results.get(text, []):
                self.click(*pos)
        return None

    def find_battling(self):
        pos = self.find_template("battling.png")
        if pos:
            if not self.current_battle_time:
                self.current_battle_time = time.time()
            return pos
        texts = [
            TEXT["battling_skip"],
            TEXT["battling_elite"],
            TEXT["auto_close"],
            TEXT["choose_skill"],
            TEXT["open_skills"],
        ]
        results = self.find_texts_batch(texts)
        for t in texts:
            if results.get(t):
                if not self.current_battle_time:
                    self.current_battle_time = time.time()
                return results[t][0]
        return None

    def find_click_dont_battle_return(self):
        self.click_template("return-1.png")

    def find_click_return(self):
        return_button = self.find_text(TEXT["return"])
        if return_button:
            self.current_battle_time = 0
            if self.mode not in [2, 3]:
                self.battle_count_add()
            self.click(*return_button)
            print(f"战斗次数: {self.battle_count}")
            time.sleep(0.1)

    def battle_count_add(self):
        now = time.time()
        if now - self.last_battle_count_time >= 5:
            self.battle_count += 1
            self.last_battle_count_time = now
            if self.on_battle_count_changed:
                self.on_battle_count_changed(self.battle_count)

    def find_stop(self):
        stop = self.find_template("battling.png")
        if stop:
            return stop
        return None

    def force_click_stop(self):
        (left, top, width, height) = self.game_window
        stop_left = left + 50
        stop_top = top + 85
        stop = (stop_left, stop_top)
        print(f"强制点击停止按钮: {stop}")
        self.click(*stop)

    def should_exit_battle(self):
        if (
            self.battle_time > 0
            and self.current_battle_time
            and time.time() - self.current_battle_time > self.battle_time
        ):
            return True
        if self.mode == 1 and self.quick_exit:
            return True
        return False

    def find_click_exit(self):
        self.click_text(TEXT["exit"])

    def find_click_card(self):
        pos = self.find_text(TEXT["card_normal"])
        if pos:
            self.click(*pos)
            time.sleep(0.2)
            start = self.find_text(TEXT["card_start"])
            if start:
                self.click(*start)
                time.sleep(0.1)

    def find_click_orange_start_game(self):
        self.click_text(TEXT["orange_start"])

    def find_expedition_team(self):
        pos = self.find_first_text(
            [TEXT["expedition_team"], TEXT["expedition_team_2"]]
        )
        return pos is not None

    def find_first_text(self, texts, roi=None, threshold=0.8):
        for text in texts:
            pos = self.find_text(text, threshold=threshold, roi=roi)
            if pos:
                return pos
        return None

    def find_click_base(self):
        self.click_text(TEXT["base"])

    def find_base(self):
        return self.find_text(TEXT["base"])

    def find_click_experience(self):
        self.click_text(TEXT["experience"])

    def find_click_expedition_challenge(self):
        self.click_text(TEXT["expedition_challenge"])

    def find_expedition_difficulty(self):
        if self.find_text(TEXT["expedition_difficulty"]):
            return True
        return False

    def find_expedition_normal(self):
        if self.find_text(TEXT["expedition_normal"]):
            return True
        return False

    def find_click_expedition_team_hall(self):
        self.click_text(TEXT["expedition_team_hall"])

    def find_click_expedition_fast_join(self):
        self.click_text(TEXT["expedition_fast_join"])

    def find_expedition_tickets(self):
        tickets_icon = ["expedition-tickets.png"]
        for icon in tickets_icon:
            tickets = self.find_template(icon)
            if tickets:
                return True
        return False

    def click_expedition_fast_join(self):
        self.find_click_expedition_team_hall()
        self.find_click_expedition_fast_join()
        time.sleep(1)
        self.expedition_in_team_max_time = time.time() + self.wait_time

    def find_click_expedition_ready(self):
        ready = self.find_text(TEXT["expedition_ready"])
        if ready:
            self.click(*ready)
            time.sleep(0.1)

    def find_expedition_personnels(self):
        personnel_icon = ["expedition-personnel.png"]
        for icon in personnel_icon:
            personnels = self.find_all_templates(icon, 0.9)
            return len(personnels)

    def find_expedition_exit(self):
        exit_icon = ["expedition-exit.png"]
        for icon in exit_icon:
            exit_pos = self.find_template(icon)
            if exit_pos:
                return exit_pos
        return None

    def find_leave_button(self):
        return self.find_text(TEXT["leave"])

    def find_click_huanqiu_challenge(self):
        self.click_text(TEXT["huanqiu_challenge"])

    def find_huanqiu_invite(self):
        return self.find_text(TEXT["huanqiu_invite"])

    def find_click_huanqiu_post_recruitment(self):
        self.click_text(TEXT["huanqiu_post_recruitment"])

    def find_click_start_game_button(self):
        self.click_text(TEXT["start_game_button"])

    def find_expedition_vice_captain(self):
        vice_captain_icon = ["expedition-vice-captain.png"]
        for icon in vice_captain_icon:
            vice_captain = self.find_template(icon)
            if vice_captain:
                return True
        return False

    def find_expedition_vice_captain_tag(self):
        vice_captain_tag_icon = ["expedition-vice-captain-tag.png"]
        for icon in vice_captain_tag_icon:
            vice_captain_tag = self.find_template(icon)
            if vice_captain_tag:
                return True
        return False

    def find_expedition_elite_tag(self):
        elite_tag_icon = ["expedition-elite-tag.png"]
        for icon in elite_tag_icon:
            elite_tag = self.find_template(icon)
            if elite_tag:
                return elite_tag
        return None

    def find_click_start_challenge(self):
        self.click_text(TEXT["start_challenge"])

    def find_expedition_health_100s(self):
        return self.find_all_text(TEXT["expedition_health_100"])

    def find_click_expedition_continue(self):
        self.click_text(TEXT["expedition_continue"])

    def find_click_think_tank(self):
        self.click_text(TEXT["think_tank"])

    def expedition_in_team(self, in_expedition):
        if not in_expedition:
            self.click_expedition_fast_join()
        else:
            tickets = self.find_expedition_tickets()
            if tickets and self.rich_mode == 1:
                self.click_expedition_fast_join()
            else:
                if self.rich_mode == 0:
                    vice_captain = self.find_expedition_vice_captain()
                    base_button = self.find_base()
                    if not vice_captain and not base_button:
                        self.find_click_start_game_button()
                self.find_click_expedition_ready()
                self.find_click_sure()

    # —— 快捷键 ——
    def on_hotkey(self, key):
        try:
            if key == keyboard.Key.esc:
                print("检测到ESC键，正在停止脚本...")
                self.running = False
                if self.hotkey_listener:
                    self.hotkey_listener.stop()
                return False
        except AttributeError:
            pass
        return True

    def setup_hotkey(self):
        print("已设置快捷键: ESC键 - 停止脚本")
        self.hotkey_listener = keyboard.Listener(on_release=self.on_hotkey)
        self.hotkey_listener.start()
