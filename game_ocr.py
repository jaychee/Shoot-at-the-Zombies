import os
import json
import time
import hashlib
import cv2
import numpy as np
from difflib import SequenceMatcher

try:
    from paddleocr import PaddleOCR

    _PADDLE_AVAILABLE = True
except Exception:
    _PADDLE_AVAILABLE = False


GAME_WINDOW_W = 542
GAME_WINDOW_H = 1010

ROI = {
    # —— 通用区域（多界面共享）——
    "full": (0, 0, GAME_WINDOW_W, GAME_WINDOW_H),            # 全屏兜底
    "top_buttons": (0, 0, GAME_WINDOW_W, 200),               # 顶部状态/活动/领取弹窗（实测活动banner y<200）
    "bottom_menu": (0, 955, GAME_WINDOW_W, GAME_WINDOW_H),   # 底部主菜单7按钮（实测 y≈974-998，5%面积）
    "center_dialog": (80, 300, 462, 700),                    # 中央弹窗（确定/领取/选择技能，通用）
    "settle_area": (80, 600, 462, 900),                      # 结算区（点击屏幕继续/跳过，推断）
    # —— 大厅专用 ——
    "difficulty_tab": (150, 240, 400, 290),                  # 大厅难度tab 普通/精英（实测 y≈262，2%面积）
    "start_button": (180, 800, 380, 860),                    # 大厅开始游戏按钮（实测 215-343,810-845，2%面积）
    # —— 基地专用 ——
    "base_entry": (40, 520, 230, 600),                       # 基地-历练大厅入口（实测 105-198,545-572）
    "expedition_fort": (250, 690, 380, 750),                 # 基地-远征堡垒入口（实测 263-361,707-738）
    # —— 历练大厅/模式列表专用 ——
    "mode_list_left": (30, 440, 170, 900),                   # 模式列表左侧入口名（寰球救援99,476/远征100,654）
    "mode_action_right": (300, 380, 480, 830),               # 模式列表右侧操作（挑战/难度选择，y=405-804）
    # —— 聊天/招募频道专用（环球抢ticket流程）——
    "chat_channels": (70, 280, 140, 800),                    # 聊天左侧频道标签列（招募102,304等纵向排列）
    "ticket_area": (200, 260, 360, 780),                     # 招募频道聊天流的ticket文字（寰球救援ticket x227-345,y300-630）
    "ticket_digit": (255, 370, 305, 745),                    # ticket 卡片人数数字区（唯一ID，实测 x≈276 y≈395/551/707；用于差分快速检测新票）
    "multi_challenge": (230, 335, 410, 690),                 # ticket 卡片「多人挑战」文字区（实测3张卡片文字 x245-396 y342-674；缩小ROI加速定位）
    "join_button": (400, 290, 500, 740),                     # ticket 卡片右侧「加入》」按钮列（实测 x≈448，y随卡片滚动；上限740排除底部「快速加入」）
    "room_status": (200, 810, 360, 860),                     # 队伍房间「等待开始」标志区（抢成功后显示，y≈829；缩窄ROI加速OCR至~100ms）
    "ready_area": (0, 750, 542, 950),                        # 准备按钮区（抢成功后队伍页面底部）
    "battle_check": (430, 920, 558, 1010),                    # 「佣兵列队」标志区（右下角，实测文字中心约(494,969)；抢票成功/进入战斗判断用）
    "settle_check": (0, 200, 542, 600),                      # 结算界面标志区（「恭喜获得」在结算页中上部显示）
    "invite_check": (430, 630, 545, 680),                    # 「输人邀请码」标志区（点ticket失败弹出，实测文字box x446-529 y642-663；出现=抢票失败需重试）
    "disconnect_check": (150, 380, 400, 520),                # 「掉线了」弹窗文字区（掉线弹窗一般在屏幕中部；出现=战斗中掉线）
    "confirm_button": (180, 540, 380, 640),                  # 掉线弹窗「确认」按钮区（弹窗中部按钮，与「掉线了」文字同弹窗）
    # —— 战斗专用 ——
    "skill_area": (0, 700, GAME_WINDOW_W, GAME_WINDOW_H),    # 底部技能区（战斗中选技能）
    # —— 组队/远征（队伍列表）——
    "team_list": (0, 200, GAME_WINDOW_W, 800),               # 队伍列表（组队/远征，保留）
}

BUTTON_TEXTS = [
    "基地", "历练大厅", "寰球救援", "挑战", "开始游戏", "开始挑战",
    "确定", "取消", "领取", "退出", "返回", "离开", "准备",
    "快速加入", "组队大厅", "发布招募", "邀请", "普通", "困难",
    "重新连接", "继续", "自动关闭", "选择技能", "智库",
    "点击空白处继续", "点击空白处跳过", "点击屏幕继续",
    "远征一队", "远征二队", "100%", "已激活技能", "等级提升",
    "战斗", "精英掉落",
    # 招募频道 ticket 卡片的「加入》」按钮（OCR 常误识为「加人》」，两种写法都收录）
    "加入》", "加人》",
    # 成功加入队伍后的房间界面标志 / 战斗结算标志 / 抢票失败标志 / 掉线标志
    "等待开始", "佣兵列队", "恭喜获得", "输人邀请码", "输入邀请码",
    "掉线了", "掉线了，点击确定重试", "确定",
    # 招募频道 ticket 卡片中的「多人挑战」文字（抢票页确认标志 + 点击目标）
    "多人挑战",
]


def load_skill_config(config_path=None):
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config", "skill_config.json"
        )
    skills = []
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            skills = data.get("skills", [])
    except Exception as e:
        print(f"加载技能配置失败: {e}")
    return skills


class GameOCR:
    def __init__(self, cache_ttl=0.3, skills=None, whitelist_texts=None):
        self._cache_ttl = cache_ttl
        self._cache = {}
        self.skills = skills if skills is not None else load_skill_config()
        self._whitelist = self._build_whitelist(whitelist_texts)
        self.ocr = None
        self._init_paddle()

    def _init_paddle(self):
        if not _PADDLE_AVAILABLE:
            print("PaddleOCR 未安装，OCR 功能不可用，请执行 pip install paddlepaddle paddleocr")
            return
        try:
            # 兼容 PaddleOCR 2.7.x（PP-OCRv4 mobile）。
            # 2.x 与 3.x 参数名不同，这里统一用 2.x 参数名：
            #   use_angle_cls / det_db_* / drop_score / ocr_version
            self.ocr = PaddleOCR(
                use_angle_cls=False,        # 游戏文字基本水平，关闭角度分类省耗时
                lang="ch",
                use_gpu=False,
                show_log=False,
                ocr_version="PP-OCRv4",     # 轻量 mobile 版（~15MB）
                # 检测参数：游戏文字较小且密集，针对性调整
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                det_db_unclip_ratio=1.8,    # 放大文本框，覆盖游戏描边字
                det_limit_side_len=960,
                det_limit_type="max",
                # 识别参数
                drop_score=0.5,             # 丢弃低置信度结果
            )
            print("PaddleOCR 初始化完成")
        except Exception as e:
            print(f"PaddleOCR 初始化失败: {e}")
            self.ocr = None

    def _build_whitelist(self, extra_texts=None):
        whitelist = set()
        for s in self.skills:
            whitelist.add(s.get("text", ""))
        whitelist.update(BUTTON_TEXTS)
        if extra_texts:
            whitelist.update(extra_texts)
        whitelist.discard("")
        return whitelist

    def add_whitelist(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        self._whitelist.update(texts)

    def reload_skills(self, skills):
        self.skills = skills
        self._whitelist = self._build_whitelist()

    def _preprocess(self, image):
        return image

    def _correct_text(self, raw_text, max_ratio=0.8):
        raw = raw_text.strip()
        if not raw:
            return None, 0.0
        if raw in self._whitelist:
            return raw, 1.0
        best, best_ratio = None, 0.0
        raw_len = len(raw)
        for w in self._whitelist:
            w_len = len(w)
            if abs(w_len - raw_len) > max(w_len, raw_len) * 0.3:
                continue
            ratio = SequenceMatcher(None, raw, w).ratio()
            if ratio > best_ratio:
                best, best_ratio = w, ratio
        if best_ratio >= max_ratio:
            return best, best_ratio
        for w in self._whitelist:
            if len(raw) > len(w) and w in raw:
                return w, 0.9
        return None, best_ratio

    def _image_hash(self, image):
        return hashlib.md5(image.tobytes()).hexdigest()

    def _raw_ocr(self, image):
        if self.ocr is None:
            return []
        try:
            # PaddleOCR 2.x：ocr.ocr(img, cls=False) -> [[[box4点], (text, score)], ...]
            result = self.ocr.ocr(image, cls=False)
        except Exception as e:
            print(f"OCR 识别出错: {e}")
            return []
        items = []
        if not result:
            return items
        for page in result:
            if not page:
                continue
            for line in page:
                # line = [box, (text, score)]
                if not line or len(line) < 2:
                    continue
                box, text_score = line[0], line[1]
                text = text_score[0] if text_score else ""
                conf = float(text_score[1]) if len(text_score) > 1 else 0.0
                if not text:
                    continue
                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]
                cx = (min(xs) + max(xs)) / 2.0
                cy = (min(ys) + max(ys)) / 2.0
                items.append(
                    {
                        "text": text,
                        "box": [[float(p[0]), float(p[1])] for p in box],
                        "confidence": conf,
                        "cx": cx,
                        "cy": cy,
                    }
                )
        return items

    def recognize(self, image, roi=None, correct_ratio=0.8):
        if image is None:
            return []

        offset_x, offset_y = 0, 0
        work = image
        if roi is not None:
            x1, y1, x2, y2 = roi
            h, w = image.shape[:2]
            x1 = max(0, min(int(x1), w))
            y1 = max(0, min(int(y1), h))
            x2 = max(0, min(int(x2), w))
            y2 = max(0, min(int(y2), h))
            if x2 <= x1 or y2 <= y1:
                return []
            work = image[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        preprocessed = self._preprocess(work)
        key = self._image_hash(preprocessed)

        now = time.time()
        raw_items = None
        cached = self._cache.get(key)
        if cached is not None:
            items, ts = cached
            if now - ts <= self._cache_ttl:
                raw_items = items
        if raw_items is None:
            raw_items = self._raw_ocr(preprocessed)
            self._cache[key] = (raw_items, now)
            self._cleanup_cache(now)

        corrected = []
        for item in raw_items:
            text, ratio = self._correct_text(item["text"], max_ratio=correct_ratio)
            if text:
                corrected.append({**item, "text": text, "correct_ratio": ratio})

        return self._shift_items(corrected, offset_x, offset_y)

    def _shift_items(self, items, offset_x, offset_y):
        if offset_x == 0 and offset_y == 0:
            return items
        shifted = []
        for item in items:
            shifted.append(
                {
                    **item,
                    "cx": item["cx"] + offset_x,
                    "cy": item["cy"] + offset_y,
                    "box": [[p[0] + offset_x, p[1] + offset_y] for p in item["box"]],
                }
            )
        return shifted

    def _cleanup_cache(self, now):
        if len(self._cache) < 64:
            return
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > self._cache_ttl]
        for k in expired:
            self._cache.pop(k, None)

    def _match_ratio(self, item_text, target):
        if not target:
            return 0.0
        if target in item_text:
            return 1.0
        return SequenceMatcher(None, item_text, target).ratio()

    def find_text(self, image, target_text, threshold=0.8, roi=None, correct_ratio=0.8):
        items = self.recognize(image, roi=roi, correct_ratio=correct_ratio)
        target = target_text.strip()
        best = None
        best_ratio = 0.0
        for item in items:
            ratio = self._match_ratio(item["text"], target)
            if ratio >= threshold and ratio > best_ratio:
                best = (item["cx"], item["cy"])
                best_ratio = ratio
        return best

    def find_all_text(self, image, target_text, threshold=0.8, roi=None, correct_ratio=0.8):
        items = self.recognize(image, roi=roi, correct_ratio=correct_ratio)
        target = target_text.strip()
        matches = []
        for item in items:
            ratio = self._match_ratio(item["text"], target)
            if ratio >= threshold:
                matches.append((item["cx"], item["cy"]))
        return matches

    def find_all_digits(self, image, roi=None, min_len=2):
        """识别图像中的纯数字串（用于 ticket 人数ID，唯一标识一张票）。
        直接走原始OCR（不经白名单纠正，因数字不在白名单），返回 [(cx, cy, text), ...]，
        坐标已按 roi 偏移回原图。
        """
        offset_x, offset_y = 0, 0
        work = image
        if roi is not None:
            x1, y1, x2, y2 = roi
            h, w = image.shape[:2]
            x1 = max(0, min(int(x1), w))
            y1 = max(0, min(int(y1), h))
            x2 = max(0, min(int(x2), w))
            y2 = max(0, min(int(y2), h))
            if x2 <= x1 or y2 <= y1:
                return []
            work = image[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1
        raw_items = self._raw_ocr(work)
        results = []
        for item in raw_items:
            txt = item["text"].strip()
            # 仅保留数字（允许少量误识混入，但主体须为数字）
            digits = "".join(c for c in txt if c.isdigit())
            if len(digits) >= min_len:
                results.append(
                    (int(item["cx"]) + offset_x, int(item["cy"]) + offset_y, digits)
                )
        return results

    def find_texts_batch(self, image, target_texts, threshold=0.8, roi=None, correct_ratio=0.8):
        items = self.recognize(image, roi=roi, correct_ratio=correct_ratio)
        targets = [t.strip() for t in target_texts if t and t.strip()]
        results = {}
        for target in targets:
            results[target] = []
        for item in items:
            for target in targets:
                ratio = self._match_ratio(item["text"], target)
                if ratio >= threshold:
                    results[target].append((item["cx"], item["cy"]))
        return results

    def read_region(self, image, x, y, w, h):
        if image is None:
            return ""
        items = self.recognize(image, roi=(x, y, x + w, y + h))
        items_sorted = sorted(items, key=lambda it: (it["cy"], it["cx"]))
        return "".join(it["text"] for it in items_sorted)
