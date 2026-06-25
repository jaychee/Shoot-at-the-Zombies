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
    "skill_area": (0, 700, GAME_WINDOW_W, GAME_WINDOW_H),
    "top_buttons": (0, 0, GAME_WINDOW_W, 120),
    "center_dialog": (80, 300, 462, 700),
    "team_list": (0, 200, GAME_WINDOW_W, 800),
    "full": (0, 0, GAME_WINDOW_W, GAME_WINDOW_H),
}

BUTTON_TEXTS = [
    "基地", "历练大厅", "寰球救援", "挑战", "开始游戏", "开始挑战",
    "确定", "取消", "领取", "退出", "返回", "离开", "准备",
    "快速加入", "组队大厅", "发布招募", "邀请", "普通", "困难",
    "重新连接", "继续", "自动关闭", "选择技能", "智库",
    "点击空白处继续", "点击空白处跳过", "点击屏幕继续",
    "远征一队", "远征二队", "100%", "已激活技能", "等级提升",
    "战斗", "精英掉落",
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
            self.ocr = PaddleOCR(
                use_angle_cls=False,
                lang="ch",
                use_gpu=False,
                show_log=False,
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                det_db_unclip_ratio=1.8,
                det_limit_side_len=960,
                det_limit_type="max",
                rec_image_shape="3,48,320",
                drop_score=0.5,
            )
            print("PaddleOCR(PP-OCRv4 mobile) 初始化完成")
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
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

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
            result = self.ocr.ocr(image, cls=False)
        except Exception as e:
            print(f"OCR 识别出错: {e}")
            return []
        items = []
        if not result:
            return items
        for line in result:
            if not line:
                continue
            for box, (text, conf) in line:
                if not text:
                    continue
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                cx = (min(xs) + max(xs)) / 2.0
                cy = (min(ys) + max(ys)) / 2.0
                items.append(
                    {"text": text, "box": box, "confidence": float(conf), "cx": cx, "cy": cy}
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
