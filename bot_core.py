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
    "recruitment": "招募",
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
    "join_button": "加人》",  # 招募频道 ticket「加入》」按钮（OCR 实测多误识为「加人》」，按此匹配最稳）
    "wait_start": "等待开始",  # 成功加入寰球队伍后的房间界面标志（房主未开始时显示）
    "mercenary_queue": "佣兵列队",  # 房主开始战斗后界面显示（确认已进入战斗）；注意游戏原文是「列队」非「队列」
    "congrats": "恭喜获得",  # 战斗结算界面标志（出现=战斗结束，可点返回领取奖励）
    "multi_challenge": "多人挑战",  # 招募频道 ticket 卡片文字（抢票页确认标志 + 点击目标）
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
        self.grab_count = 0  # 抢到票次数（每次成功加入队伍+1）
        self.on_grab_count_changed = None  # 抢票次数变化回调（GUI刷新用）
        self.on_log = None  # 日志回调（GUI实时显示当前步骤用），签名 on_log(text)

        # 主流程公共模块开关：True=跳过 main_loop 中的公共操作与战斗循环，
        # 直接进入模式分发（方法定义仍保留在 bot_core，需要时改 False 即可恢复）
        self.skip_public_ops = True

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

    def _log(self, text):
        """统一日志输出：同时打印到控制台并触发 on_log 回调（供 GUI 实时显示）。"""
        print(text, flush=True)
        if self.on_log:
            try:
                self.on_log(text)
            except Exception:
                pass

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
            # SetForegroundWindow 在调用进程非前台时会抛 pywintypes.error，
            # 但窗口已存在、矩形也能取到，不应因此中断整个流程，故容错处理。
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"SetForegroundWindow 失败(可忽略): {e}")
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            self.game_window = (left, top, right - left, bottom - top)
            print(f"找到游戏窗口: {self.game_window}")
            return True
        else:
            print("未找到游戏窗口")
            return False

    def resize_game_window(self, width=542, height=1010, move_to_origin=False):
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
            if move_to_origin:
                left, top = 0, 0
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

    def save_screenshot(self, filename=None, force_new=False):
        img = self.take_screenshot(force_new=force_new)
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
        # 注意：win32api.mouse_event 对部分游戏（含本作）无效，
        # 点击事件不被接收。这里改用 pyautogui 真实模拟点击确保生效。
        for x, y in positions:
            pyautogui.click(int(x), int(y))
            time.sleep(0.05)

    def press_key(self, key, presses=1, interval=0.1, human_like=True):
        if human_like:
            interval += random.uniform(-0.05, 0.05)
            interval = max(0.05, interval)
        pyautogui.press(key, presses=presses, interval=interval)
        print(f"按下按键: {key}")

    # —— 模板匹配（仅图标类保留）——
    def find_template(self, template_name, threshold=0.8, roi=None, force_shot=False):
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
        img = self.take_screenshot(force_new=force_shot)
        if img is None:
            return None
        # ROI 裁剪：只在指定区域匹配，避免全图扫描误匹配（如聊天图标匹配到货币图标）
        offset_x, offset_y = 0, 0
        work = img
        if roi is not None:
            x1, y1, x2, y2 = roi
            hh, ww = img.shape[:2]
            x1 = max(0, min(int(x1), ww))
            y1 = max(0, min(int(y1), hh))
            x2 = max(0, min(int(x2), ww))
            y2 = max(0, min(int(y2), hh))
            if x2 <= x1 or y2 <= y1:
                return None
            work = img[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1
        result = cv2.matchTemplate(work, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            h, w = template.shape[:2]
            center_x = self.game_window[0] + max_loc[0] + w // 2 + offset_x
            center_y = self.game_window[1] + max_loc[1] + h // 2 + offset_y
            return (center_x, center_y)
        return None

    def find_all_templates(self, template_name, threshold=0.8, roi=None, nms_dist=20):
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
        h, w = template.shape[:2]
        # ROI 裁剪：只在指定区域匹配，大幅提速
        offset_x, offset_y = 0, 0
        work = img
        if roi is not None:
            x1, y1, x2, y2 = roi
            hh, ww = img.shape[:2]
            x1 = max(0, min(int(x1), ww))
            y1 = max(0, min(int(y1), hh))
            x2 = max(0, min(int(x2), ww))
            y2 = max(0, min(int(y2), hh))
            if x2 <= x1 or y2 <= y1:
                return []
            work = img[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1
        result = cv2.matchTemplate(work, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        # 非极大值抑制：相邻匹配点合并为一个（避免同一按钮返回大量重叠坐标）
        matches = []
        nms2 = nms_dist * nms_dist
        for pt in zip(*locations[::-1]):
            cx = self.game_window[0] + pt[0] + w // 2 + offset_x
            cy = self.game_window[1] + pt[1] + h // 2 + offset_y
            if all((cx - px) ** 2 + (cy - py) ** 2 > nms2 for px, py in matches):
                matches.append((cx, cy))
        return matches

    def click_template(self, template_name, sleep_after=0.05, roi=None):
        pos = self.find_template(template_name, roi=roi)
        if pos:
            self.click(*pos)
            if sleep_after > 0:
                time.sleep(sleep_after)
            return True
        return False

    def click_first_template(self, template_names, sleep_after=0.05, roi=None):
        for template_name in template_names:
            pos = self.find_template(template_name, roi=roi)
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
        self.click_text(TEXT["receive"], roi=ROI["top_buttons"])

    def find_click_im(self):
        """点击聊天图标(气泡)打开聊天框。
        resize 后聊天气泡固定在窗口内坐标 (514,575)，匹配度0.998稳定命中。
        优先模板匹配(强制新截图，避免缓存旧帧)；匹配不到则点确认的固定坐标兜底。
        点击统一用 pyautogui.click(无随机偏移)，避免 self.click 的 ±5px 偏移点偏小图标。
        返回是否点击(True=已点击，False=未点击)。
        """
        import pyautogui
        # 模板匹配：强制取最新帧，避免 take_screenshot 缓存返回旧界面
        pos = self.find_template("im.png", force_shot=True)
        if pos:
            pyautogui.click(int(pos[0]), int(pos[1]))
            return True
        # 兜底：聊天气泡固定坐标(窗口内 514,575)→转屏幕绝对坐标
        if self.game_window:
            sx = self.game_window[0] + 514
            sy = self.game_window[1] + 575
            pyautogui.click(int(sx), int(sy))
            return True
        return False

    def find_click_continue(self):
        self.click_text(TEXT["continue"], roi=ROI["settle_area"])

    def find_team_up(self):
        """检查招募频道标签是否可见（用于判断聊天框是否打开）。"""
        return self.find_text(TEXT["recruitment"], roi=ROI["chat_channels"])

    def find_click_recruitment(self):
        """点击招募频道标签，切换到招募频道。
        招募标签是聊天框打开后固定的 UI 元素（实测在 102,304），
        OCR 对这种小标签识别不稳定，故 OCR 找不到时退化为点固定坐标。
        """
        pos = self.find_text(TEXT["recruitment"], roi=ROI["chat_channels"])
        if pos:
            self.click(*pos)
        else:
            # OCR 识别不到（小标签识别不稳定），退化为点击实测固定位置
            self.click(102, 304)

    def find_click_huanqiu_ticket(self, deadline=None):
        """抢寰球救援 ticket（固定坐标无限点击法）。
        流程：
        1. 切到招募频道后（由 huanqiu_mode._open_recruitment_channel 完成），
           用模板匹配(multi_challenge.png, ~40ms)定位页面上「多人挑战」文字坐标，
           定位到 3 个即确认已在抢票页，记录这 3 个固定坐标。
           （改用模板匹配代替 OCR：OCR 定位要 5.6s，模板匹配仅 42ms，快 130 倍且更可靠）
        2. 无限循环点击这 3 个坐标（不做新票/死票判定、不识别数字），直到抢成功返回 True。
           抢成功的判断：出现「等待开始」(进入队伍房间) 或「佣兵列队」(已进入战斗)，
           满足任一即视为抢到票。
        3. deadline 超时返回 False。

        说明：「等待开始」(小ROI,~400ms) 每轮都查；「佣兵列队」(小ROI,~1s) 每8轮查一次。
        点击「多人挑战」文字坐标本身即可触发加入（实测该位置可加入）。
        """
        round_cnt = 0
        click_targets = None  # 记录的 3 个「多人挑战」固定坐标
        locate_deadline = time.time() + 30  # 最多等 30s 定位到 3 个坐标
        SKILL_CHECK_EVERY = 8  # 每隔8轮才查一次「佣兵列队」(ROI较慢)，平衡效率与覆盖

        while self.running:
            if deadline is not None and time.time() > deadline:
                self._log(f"[抢ticket] 抢票超时(轮{round_cnt})，退出抢票循环")
                return False
            round_cnt += 1

            # 阶段1：模板匹配定位「多人挑战」坐标，确认在抢票页
            if click_targets is None:
                positions = self.find_all_templates(
                    "multi_challenge.png", threshold=0.8, roi=ROI["multi_challenge"]
                )
                if len(positions) >= 3:
                    # 按 y 降序（底部=最新=优先点击）
                    click_targets = sorted(positions, key=lambda p: p[1], reverse=True)[:3]
                    self._log(
                        f"[抢ticket] ✓ 已在抢票页，记录3个「多人挑战」坐标: {click_targets}"
                    )
                else:
                    if time.time() > locate_deadline:
                        self._log(
                            f"[抢ticket] 30s内未定位到3个「多人挑战」(仅{len(positions)}个)，"
                            f"按现有坐标继续抢"
                        )
                        click_targets = sorted(
                            positions, key=lambda p: p[1], reverse=True
                        ) if positions else [(280, 395), (280, 550), (280, 700)]
                    else:
                        self._log(
                            f"[抢ticket] 等待抢票页加载(定位到{len(positions)}个「多人挑战」)..."
                        )
                        time.sleep(0.5)
                        continue

            # 阶段2：无限循环点击固定坐标，直到抢成功
            # 2a. 判断是否抢成功：
            #   - 「等待开始」(小ROI,~400ms) 每轮都查（抢票主标志：进入队伍房间）
            #   - 「佣兵队列」(大ROI,~1s) 每 SKILL_CHECK_EVERY 轮才查一次
            #     （房主已开战进入战斗状态，与"进入战斗"判断条件一致）
            #     满足任一即视为抢到票
            wait_start = self.find_text(TEXT["wait_start"], roi=ROI["room_status"])
            if wait_start:
                self._log(f"[抢ticket] 轮{round_cnt} ✓ 抢到！检测到「等待开始」@{wait_start}")
                self.grab_count += 1
                if self.on_grab_count_changed:
                    self.on_grab_count_changed(self.grab_count)
                return True
            if round_cnt % SKILL_CHECK_EVERY == 0:
                mercenary = self.find_text(TEXT["mercenary_queue"], roi=ROI["battle_check"])
                if mercenary:
                    self._log(
                        f"[抢ticket] 轮{round_cnt} ✓ 抢到！检测到「佣兵队列」@{mercenary}（已进入战斗）"
                    )
                    self.grab_count += 1
                    if self.on_grab_count_changed:
                        self.on_grab_count_changed(self.grab_count)
                    return True
            # 2b. 点击记录的 3 个固定坐标
            for x, y in click_targets:
                pyautogui.click(int(x), int(y))
            # 低频日志
            if round_cnt % 10 == 0:
                self._log(
                    f"[抢ticket] 轮{round_cnt} 点击{len(click_targets)}个固定坐标 {click_targets}"
                )
        # running 被置 False（ESC/停止）退出循环
        self._log(f"[抢ticket] 抢票循环被中断(轮{round_cnt})")
        return False

    # —— 环球抢票后续流程：等待战斗 / 等待结算 / 返回主页 ——
    def sleep_interruptible(self, seconds, tag=""):
        """可中断等待：分片 sleep，检测 self.running 以便 ESC 时及时退出。"""
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(min(0.5, end - time.time()))
        if tag:
            print(f"[环球] {tag} 等待{seconds}s {'完成' if self.running else '(已中断)'}", flush=True)

    def check_mercenary_queue(self):
        """检查页面是否有「佣兵队列」（房主已开始战斗的标志）。"""
        return self.find_text(TEXT["mercenary_queue"], roi=ROI["battle_check"])

    def check_congrats(self):
        """检查页面是否有「恭喜获得」（战斗结算标志）。"""
        return self.find_text(TEXT["congrats"], roi=ROI["settle_check"])

    def click_return_button(self):
        """点击结算页的「返回」按钮回到寰球救援主页。"""
        # 返回按钮一般在结算页底部偏中
        return self.click_text(TEXT["return"], roi=ROI["settle_area"]) or self.click_text(
            TEXT["return"], roi=ROI["ready_area"]
        )

    def find_in_huanqiu_team(self):
        if self.find_text(TEXT["in_huanqiu_team"], roi=ROI["top_buttons"]):
            return True
        return False

    def find_click_home_close(self):
        if self.click_first_template(
            ["home-close.png", "home-close-1.png", "home-close-2.png"]
        ):
            return
        self.click_text(TEXT["home_close_text"], roi=ROI["top_buttons"])

    def find_click_close(self):
        if self.click_first_template(["close.png"]):
            return True
        return self.click_first_text(
            [TEXT["auto_close"], TEXT["battling_elite"]], roi=ROI["center_dialog"]
        )

    def find_click_reconnection(self):
        self.click_text("重新连接")

    def find_huanqiu(self):
        return self.find_text(TEXT["huanqiu"], roi=ROI["mode_list_left"])

    def find_click_start_button(self):
        return self.click_text(TEXT["battle"], roi=ROI["bottom_menu"])

    def find_click_sure(self):
        self.click_text(TEXT["sure"], roi=ROI["center_dialog"])

    def find_click_auto_close(self):
        self.click_text(TEXT["auto_close"], roi=ROI["center_dialog"])

    def _skill_name_to_text(self, name):
        for s in self.skills:
            if s.get("name") == name:
                return s.get("text", name)
        return name

    def find_click_skill(self):
        self.click_text(TEXT["think_tank"], roi=ROI["skill_area"])
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
        return_button = self.find_text(TEXT["return"], roi=ROI["top_buttons"])
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
        self.click_text(TEXT["exit"], roi=ROI["center_dialog"])

    def find_click_card(self):
        pos = self.find_text(TEXT["card_normal"], roi=ROI["difficulty_tab"])
        if pos:
            self.click(*pos)
            time.sleep(0.2)
            start = self.find_text(TEXT["card_start"], roi=ROI["start_button"])
            if start:
                self.click(*start)
                time.sleep(0.1)

    def find_click_orange_start_game(self):
        self.click_text(TEXT["orange_start"], roi=ROI["start_button"])

    def find_expedition_team(self):
        pos = self.find_first_text(
            [TEXT["expedition_team"], TEXT["expedition_team_2"]], roi=ROI["team_list"]
        )
        return pos is not None

    def find_first_text(self, texts, roi=None, threshold=0.8):
        for text in texts:
            pos = self.find_text(text, threshold=threshold, roi=roi)
            if pos:
                return pos
        return None

    def find_click_base(self):
        self.click_text(TEXT["base"], roi=ROI["bottom_menu"])

    def find_base(self):
        return self.find_text(TEXT["base"], roi=ROI["bottom_menu"])

    def find_click_experience(self):
        self.click_text(TEXT["experience"], roi=ROI["base_entry"])

    def find_click_expedition_challenge(self):
        self.click_text(TEXT["expedition_challenge"], roi=ROI["mode_action_right"])

    def find_expedition_difficulty(self):
        if self.find_text(TEXT["expedition_difficulty"], roi=ROI["difficulty_tab"]):
            return True
        return False

    def find_expedition_normal(self):
        if self.find_text(TEXT["expedition_normal"], roi=ROI["difficulty_tab"]):
            return True
        return False

    def find_click_expedition_team_hall(self):
        self.click_text(TEXT["expedition_team_hall"], roi=ROI["center_dialog"])

    def find_click_expedition_fast_join(self):
        self.click_text(TEXT["expedition_fast_join"], roi=ROI["center_dialog"])

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
        ready = self.find_text(TEXT["expedition_ready"], roi=ROI["skill_area"])
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
        return self.find_text(TEXT["leave"], roi=ROI["center_dialog"])

    def find_click_huanqiu_challenge(self):
        self.click_text(TEXT["huanqiu_challenge"], roi=ROI["mode_list_left"])

    def find_huanqiu_invite(self):
        return self.find_text(TEXT["huanqiu_invite"], roi=ROI["center_dialog"])

    def find_click_huanqiu_post_recruitment(self):
        self.click_text(TEXT["huanqiu_post_recruitment"], roi=ROI["center_dialog"])

    def find_click_start_game_button(self):
        self.click_text(TEXT["start_game_button"], roi=ROI["start_button"])

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
        self.click_text(TEXT["start_challenge"], roi=ROI["center_dialog"])

    def find_expedition_health_100s(self):
        return self.find_all_text(TEXT["expedition_health_100"], roi=ROI["team_list"])

    def find_click_expedition_continue(self):
        self.click_text(TEXT["expedition_continue"], roi=ROI["settle_area"])

    def find_click_think_tank(self):
        self.click_text(TEXT["think_tank"], roi=ROI["skill_area"])

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
