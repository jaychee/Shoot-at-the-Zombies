# OCR 文字识别集成 + 架构重构计划

## 目标
为 Shoot-at-the-Zombies 项目完成两项升级：
1. **集成 PaddleOCR**，替换所有文字类模板匹配（含技能图标、基地图标），仅保留纯图标类模板匹配。
2. **重构架构**，`game_bot.py` 仅作为程序入口与主流程调度，各游戏模式（寰球、主线、远征）拆分为独立模块。

## 四大调整说明（本次新增）

### 调整 1：架构重构 —— 模式模块化
`game_bot.py` 现状是一个 1300+ 行的"大杂烩"：窗口管理、截图、点击、模板匹配、所有模式的业务逻辑、GUI 全部塞在 `GameBot` / `GameBotGUI` 两个类里。重构后职责分离：

| 模块 | 职责 |
|------|------|
| `game_bot.py` | **仅**程序入口 + GUI + 主流程调度（公共操作 + 战斗循环 + 分发到模式模块） |
| `bot_core.py` | **新增** —— GameBotCore 基类：窗口管理、截图、点击、模板匹配、OCR 识别、通用状态判断（所有模式共享） |
| `modes/huanqiu_mode.py` | **新增** —— 寰球模式专属逻辑 |
| `modes/mainline_mode.py` | **新增** —— 主线模式专属逻辑 |
| `modes/expedition_mode.py` | **新增** —— 远征模式专属逻辑（普通/超级） |

### 调整 2：技能识别改为 OCR + 配置文件驱动
原 `SKILL_LIST` 硬编码 14 个技能的模板文件名，改用 OCR 识别技能名称文字，识别目标文字从配置文件 `config/skill_config.json` 读取。

### 调整 3：base.png / base-2.png 改为 OCR
原 `base.png` / `base-2.png` 作为图标模板匹配，现映射为 OCR 识别文字 **"基地"**，归入文字类。

### 调整 4：PaddleOCR 针对游戏场景的效率优化
从模型、参数、ROI、预处理、缓存五个维度优化，把单次识别从 ~300ms 降到 ~80-150ms，详见 Step 1。

---

## 模板分析结果（更新后）

### 文字类模板（OCR 替换，约 45 个）
| 模板 | OCR 目标文字 | 说明 |
|------|-------------|------|
| `auto-close.png` | 自动关闭 / 继续 | |
| `battling-3.png` | 点击空白处跳过 | |
| `battling-4.png` | 精英掉落 | |
| `battling-5.png` | 寰球救援-难度 | |
| `card-normal.png` / `card-normal-1.png` | 普通 | |
| `card-start.png` | 开始游戏 | |
| `choose-skill.png` / `choose-skill-1.png` | 选择技能 | |
| `click-continue.png` | 点击屏幕继续 | |
| `exit.png` | 退出 | |
| `expedition-challenge.png` / `-1.png` | 挑战 | |
| `expedition-continue.png` | 点击空白处继续 | |
| `expedition-difficulty.png` | 困难 | |
| `expedition-fast-join.png` | 快速加入 | |
| `expedition-health-100.png` | 100% | |
| `expedition-normal.png` | 普通 | |
| `expedition-ready.png` | 准备 | |
| `expedition-team.png` / `-2.png` | 远征一队 / 远征二队 | |
| `expedition-team-hall.png` | 组队大厅 | |
| `experience.png` | 历练大厅 | |
| `huanqiu.png` | 寰球救援 | |
| `huanqiu-challenge.png` | 寰球救援 | |
| `huanqiu-invite.png` | 邀请 | |
| `huanqiu-post-recruitmen.png` | 发布招募 | |
| `in-huanqiu-team.png` | 寰球救援-难度 | |
| `leave-button.png` | 离开 | |
| `open-skills.png` | 已激活技能 | |
| `orange-start.png` | 开始游戏 | |
| `receive.png` | 领取 | |
| `reconnection.png` | 重新连接 | |
| `return.png` | 返回 | |
| `start-challenge.png` | 开始挑战 | |
| `start-game-button.png` | 开始游戏 | |
| `sure.png` | 确定 | |
| `think_tank.png` | 智库 | |
| `home-close-2-text.png` | 已置换/未置换的道具已通过邮件返还 | |
| `battle.png` / `battle-1.png` | 战斗 | 含图标但文字可识别 |
| `grade-level.png` | 等级提升 | |
| **`base.png` / `base-2.png`** | **基地** | **本次调整：图标→OCR** |
| **所有 `skill-*.png`（28 个）** | **见技能配置** | **本次调整：模板→OCR** |

### 图标类模板（保留模板匹配，约 15 个）
- `battling.png` / `battling-stop.png`（暂停图标）
- `close.png` / `home-close.png` / `home-close-1.png` / `home-close-2.png`（关闭X图标）
- `return-1.png`（返回箭头图标）
- `expedition-exit.png` / `expedition-personnel.png` / `expedition-vice-captain*.png` / `expedition-elite-tag.png` / `expedition-tickets.png`
- `recruitment.png` / `recruitment-1.png`（招募旗帜图标）
- `im.png`（聊天气泡图标）

---

## 目标目录结构

```
Shoot-at-the-Zombies/
├── game_bot.py              # 程序入口 + GUI + 主流程调度
├── bot_core.py              # 【新增】核心基类：窗口/截图/点击/模板匹配/OCR/通用状态判断
├── game_ocr.py              # 【新增】OCR 模块（PaddleOCR 封装 + 游戏场景优化）
├── modes/                   # 【新增】游戏模式模块
│   ├── __init__.py
│   ├── huanqiu_mode.py      # 寰球模式
│   ├── mainline_mode.py     # 主线模式
│   └── expedition_mode.py   # 远征模式（普通+超级）
├── config/                  # 【新增】配置目录
│   └── skill_config.json    # 技能 OCR 文字配置
├── templates/               # 保留图标类模板
├── requirements.txt         # 修改：新增 paddlepaddle、paddleocr
└── README.md                # 修改：更新文档
```

---

## 实现步骤

### Step 1: 创建 OCR 模块 `game_ocr.py`（含游戏场景优化）

新建 `/Users/jaychee/IdeaProjects/Shoot-at-the-Zombies/game_ocr.py`。

#### 1.1 核心类设计
```python
class GameOCR:
    def __init__(self, cache_ttl=0.3):
        # 初始化 PaddleOCR（CPU + 轻量配置，见 1.2 优化）
        # self.ocr = PaddleOCR(...)
        # self._cache = {}        # 图片hash → OCR结果
        # self._cache_ttl = cache_ttl

    def recognize(self, image, roi=None):
        """识别整张图或指定 ROI 区域的所有文字，返回 [{text, box, confidence}]"""
        # 1. 若指定 roi 则裁剪区域（见 1.3）
        # 2. 预处理（见 1.4）
        # 3. 检查缓存（基于裁剪后图片hash）
        # 4. 调用 ocr.ocr() 一次，缓存结果
        # 5. 若裁剪过 ROI，把坐标还原回原图坐标系

    def find_text(self, image, target_text, threshold=0.8, roi=None):
        """在图片中查找指定文字，返回中心坐标 (x, y) 或 None"""
        # 调用 recognize() 复用结果，再做模糊匹配

    def find_all_text(self, image, target_text, threshold=0.8, roi=None):
        """查找所有匹配位置，返回 [(x, y), ...]"""

    def find_texts_batch(self, image, target_texts, threshold=0.8, roi=None):
        """【关键优化】一次 OCR 识别，批量匹配多个目标文字
        返回 {text: [(x,y), ...]} —— 避免同一帧多次调用 OCR"""

    def read_region(self, image, x, y, w, h):
        """读取指定区域文字内容"""
```

#### 1.2 PaddleOCR 初始化优化（游戏场景）

##### 1.2.1 模型选择：PP-OCRv4 mobile vs server

PaddleOCR PP-OCRv4 提供两套模型，官方通用场景 benchmark 指标对比：

| 模型 | 检测 Hmean | 识别 Acc | 单张推理(CPU) | 模型体积 |
|------|-----------|---------|--------------|---------|
| PP-OCRv4 **mobile** | ~82.7% | ~78.2% | ~80-150ms | ~15MB |
| PP-OCRv4 **server** | ~84.9% | ~83.4% | ~300-500ms | ~140MB |
| 差距 | server +2.2% | server +5.2% | mobile 快 2-3 倍 | mobile 小 9 倍 |

**本项目采用 mobile 版**，理由：
1. 游戏场景文字是**有限固定集合**（技能名、按钮文字等约 50 个词），5% 的通用识别差距可被后处理白名单过滤弥补甚至反超（见 1.6）。
2. 游戏文字为美术字体、相对清晰，非复杂自然场景，mobile 够用。
3. CPU 单帧 80-150ms vs 300-500ms，对实时性要求高的游戏自动化至关重要。
4. mobile 版模型体积小，便于 PyInstaller 打包分发。

> 结论：mobile 对通用场景准确率损失约 **3-5%**，但本项目经白名单后处理后，**最终可用准确率不低于甚至高于 server 裸识别**。

##### 1.2.2 初始化参数（mobile 版 + 游戏场景调优）
```python
self.ocr = PaddleOCR(
    use_angle_cls=False,       # 游戏文字基本水平，关闭角度分类省 ~30% 耗时
    lang='ch',
    use_gpu=False,
    show_log=False,
    # —— mobile 模型（PaddleOCR 默认即 mobile，无需额外指定）——
    # 如需 server 版：det_model_dir/rec_model_dir 指定 server 模型路径
    # 检测参数：游戏文字较小且密集，针对性调整
    det_db_thresh=0.3,         # 降低检测阈值，避免漏检小字
    det_db_box_thresh=0.5,
    det_db_unclip_ratio=1.8,   # 放大文本框，覆盖游戏描边字
    det_limit_side_len=960,    # 限制输入尺寸，控制耗时
    det_limit_type='max',
    # 识别参数
    rec_image_shape='3,48,320', # 轻量识别输入
    drop_score=0.5,             # 丢弃低置信度结果
)
```

#### 1.3 ROI 区域裁剪优化（核心提效手段）
游戏界面布局固定，不同操作只需关注特定区域。预定义 ROI 常量：

```python
# 游戏窗口标准尺寸 542x1010，按比例定义 ROI
ROI = {
    "skill_area":     (0, 700, 542, 1010),   # 技能按钮区（底部）
    "top_buttons":    (0, 0, 542, 120),      # 顶部按钮（返回/暂停/退出）
    "center_dialog":  (80, 300, 462, 700),   # 中央弹窗（确定/领取/挑战）
    "team_list":      (0, 200, 542, 800),    # 队伍列表
    "full":           (0, 0, 542, 1010),     # 全屏兜底
}
```
- 技能识别只扫 `skill_area`：裁剪后图片面积约原图的 30%，OCR 耗时降 ~60%。
- 按钮类只扫对应区域，避免全屏 OCR。

#### 1.4 图像预处理（提升小字/描边字识别率）
```python
def _preprocess(self, image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 游戏文字带描边/发光，用 Otsu 二值化增强对比
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)  # PaddleOCR 需要 3 通道
```

#### 1.5 多级缓存策略
- **L1 截图缓存**：`bot_core` 层 TTL=0.1s（已有，保留）。
- **L2 OCR 结果缓存**：基于裁剪后 ROI 图像 hash，TTL=0.3s。同一帧内多个目标查询命中同一 `recognize()` 结果。
- **批量匹配**：`find_texts_batch()` 一次识别后内存中匹配多个文字，是技能循环的关键优化（技能需匹配 14 个文字，传统方式要 14 次 OCR）。

#### 1.6 后处理白名单过滤（弥补 mobile 准确率 + 抗误识别）

游戏内可能出现文字是有限集合，用白名单对 OCR 原始结果做纠错/过滤，可同时解决两个问题：
1. **弥补 mobile 版识别差距**：mobile 把"温压弹"误识为"温压单"，白名单可纠正回"温压弹"。
2. **抗背景干扰**：游戏画面背景复杂，OCR 可能识别出无关乱码文字，白名单直接滤除。

##### 1.6.1 白名单构建
从 `config/skill_config.json` + 文字类模板目标文字汇总，自动生成白名单集合：

```python
def _build_whitelist(self):
    """从技能配置 + 模板文字映射构建白名单"""
    whitelist = set()
    # 技能文字
    for s in self.skills:
        whitelist.add(s["text"])
    # 按钮/状态文字（从模板映射表导入）
    button_texts = [
        "基地", "历练大厅", "寰球救援", "挑战", "开始游戏", "开始挑战",
        "确定", "取消", "领取", "退出", "返回", "离开", "准备",
        "快速加入", "组队大厅", "发布招募", "邀请", "普通", "困难",
        "重新连接", "继续", "自动关闭", "选择技能", "智库",
        "点击空白处继续", "点击空白处跳过", "点击屏幕继续",
        "远征一队", "远征二队", "100%", "已激活技能", "等级提升",
    ]
    whitelist.update(button_texts)
    return whitelist
```

##### 1.6.2 纠错策略：编辑距离匹配（默认 0.8，技能场景 0.6）
OCR 原始结果不在白名单时，依次尝试：精确命中 → 模糊匹配（SequenceMatcher 相似度 ≥ 阈值）→ 包含匹配（白名单关键词为长文本子串），均失败则丢弃。

**阈值分场景**：
- **默认 0.8**：按钮/状态文字（确定、领取、退出等），严格纠错，避免误纠正。
- **技能场景 0.6**：技能名识别时放宽，覆盖 3 字技能名 1 字误识（如"温压单"→"温压弹"，相似度 0.67）。技能名是有限固定集合，放宽阈值风险可控。

```python
from difflib import SequenceMatcher

def _correct_text(self, raw_text, max_ratio=0.8):
    """对 OCR 原始文字做白名单纠错，max_ratio 由调用方按场景传入"""
    raw = raw_text.strip()
    if raw in self._whitelist:
        return raw, 1.0
    best, best_ratio = None, 0.0
    for w in self._whitelist:
        if abs(len(w) - len(raw)) > max(len(w), len(raw)) * 0.3:
            continue
        ratio = SequenceMatcher(None, raw, w).ratio()
        if ratio > best_ratio:
            best, best_ratio = w, ratio
    if best_ratio >= max_ratio:
        return best, best_ratio
    for w in self._whitelist:
        if len(raw) > len(w) and w in raw:
            return w, 0.9
    return None, best_ratio  # 纠正失败，丢弃
```

`recognize/find_text/find_all_text/find_texts_batch` 均接受 `correct_ratio` 参数透传；`bot_core.find_click_skill` 调用技能批量匹配时传 `correct_ratio=0.6`，其余按钮识别用默认 0.8。

##### 1.6.3 集成到 recognize 流程
`recognize()` 接受 `correct_ratio` 参数，**缓存原始 OCR 结果**（基于图像 hash），纠错在每次调用时按调用方阈值实时应用（纠错为纯字符串比对 <1ms，性能可忽略）。这样同一帧截图被不同阈值场景复用时不会冲突：

```python
def recognize(self, image, roi=None, correct_ratio=0.8):
    # ... ROI 裁剪、预处理、图像 hash ...
    raw_items = None
    cached = self._cache.get(key)
    if cached is not None:
        items, ts = cached
        if now - ts <= self._cache_ttl:
            raw_items = items          # 命中缓存，复用原始 OCR 结果
    if raw_items is None:
        raw_items = self._raw_ocr(preprocessed)
        self._cache[key] = (raw_items, now)   # 只缓存原始结果，不缓存纠错结果
    # 按调用方阈值实时纠错
    corrected = []
    for item in raw_items:
        text, ratio = self._correct_text(item["text"], max_ratio=correct_ratio)
        if text:
            corrected.append({**item, "text": text, "correct_ratio": ratio})
    return self._shift_items(corrected, offset_x, offset_y)
```

##### 1.6.4 效果预期
| 场景 | mobile 裸识别 | mobile + 白名单 |
|------|-------------|----------------|
| 清晰按钮文字 | ~95% | ~99%（纠错少量误识） |
| 描边/发光技能名 | ~88% | ~96%（纠正形近字） |
| 复杂背景干扰 | ~80%（乱码干扰） | ~95%（乱码被滤除） |
| 综合 | ~90% | ~97% |

> 白名单后处理使 mobile 版**最终可用准确率反超 server 裸识别**，且零额外推理耗时（纯字符串比对，<1ms）。

##### 1.6.5 白名单维护
- 白名单来源与 `skill_config.json` 联动：技能配置更新自动同步白名单。
- 按钮文字白名单集中在 `game_ocr.py` 维护，新增模板映射时同步补充。
- 建议加单元测试：对已知游戏截图跑 OCR，验证白名单纠错命中率。

### Step 2: 创建技能配置文件 `config/skill_config.json`

```json
{
    "skills": [
        {"name": "枪械",       "text": "枪械"},
        {"name": "温压弹",     "text": "温压弹"},
        {"name": "干冰弹",     "text": "干冰弹"},
        {"name": "冰雹发生器", "text": "冰雹发生器"},
        {"name": "装甲车",     "text": "装甲车"},
        {"name": "电磁穿刺",   "text": "电磁穿刺"},
        {"name": "压缩气刃",   "text": "压缩气刃"},
        {"name": "制导激光",   "text": "制导激光"},
        {"name": "旋风加农",   "text": "旋风加农"},
        {"name": "燃油弹",     "text": "燃油弹"},
        {"name": "高能射线",   "text": "高能射线"},
        {"name": "无人机冲击", "text": "无人机冲击"},
        {"name": "跃迁电子",   "text": "跃迁电子"},
        {"name": "空投轰炸",   "text": "空投轰炸"}
    ]
}
```

- `name`：GUI 下拉框显示 + 配置保存用（兼容现有 config.json 优先技能配置）。
- `text`：OCR 实际匹配的文字（可与 name 不同，便于游戏文字与内部名称解耦）。
- 配置加载：`bot_core` 启动时读取，支持热更新（文件变更自动重载）。

### Step 3: 创建核心基类 `bot_core.py`

从原 `GameBot` 抽离所有**模式无关**的公共能力：

```python
class GameBotCore:
    def __init__(self, game_title, battle_time, max_battle_count,
                 mode, priority_skills, rich_mode, wait_time, quick_exit):
        # 窗口、截图缓存、模板缓存、OCR 实例、技能配置等
        self.ocr = GameOCR(cache_ttl=0.3)
        self.skills = load_skill_config("config/skill_config.json")

    # —— 窗口管理 ——
    def find_game_window(self): ...
    def resize_game_window(self, w=542, h=1010): ...
    def find_fullscreen_window(self): ...

    # —— 截图 ——
    def take_screenshot(self, force_new=False): ...

    # —— 点击 ——
    def click(self, x, y, duration=0.2, human_like=True): ...
    def click_fast(self, x, y): ...
    def click_fast_batch(self, positions): ...

    # —— 模板匹配（仅图标类保留）——
    def find_template(self, name, threshold=0.8): ...
    def find_all_templates(self, name, threshold=0.8): ...
    def click_template(self, name, sleep_after=0.05): ...
    def click_first_template(self, names, sleep_after=0.05): ...

    # —— OCR 识别（新增，坐标自动转屏幕绝对坐标）——
    def find_text(self, text, threshold=0.8, roi=None): ...
    def find_all_text(self, text, threshold=0.8, roi=None): ...
    def click_text(self, text, sleep_after=0.05, roi=None): ...
    def click_first_text(self, texts, sleep_after=0.05, roi=None): ...

    # —— 通用状态判断（所有模式共享）——
    def find_click_receive(self): ...           # 领取
    def find_click_home_close(self): ...        # 关闭
    def find_click_reconnection(self): ...      # 重新连接
    def find_click_sure(self): ...              # 确定
    def find_click_return(self): ...            # 返回（含战斗计数）
    def find_battling(self): ...                # 是否战斗中
    def find_click_skill(self): ...             # 选技能（OCR + 配置驱动）
    def find_click_auto_close(self): ...        # 继续战斗
    def find_click_close(self): ...             # 关闭弹窗
    def find_click_continue(self): ...          # 点击屏幕继续
    def find_click_start_button(self): ...      # 战斗
    def find_click_exit(self): ...              # 退出
    def force_click_stop(self): ...             # 强制停止
    def battle_count_add(self): ...             # 战斗计数

    # —— 状态字段（供模式模块读写）——
    # self.battle_count, self.current_battle_time,
    # self.expedition_in_team_max_time, self.running 等
```

#### 技能识别改造（OCR + 配置 + 批量匹配）
```python
def find_click_skill(self):
    self.click_text("智库")  # think_tank
    if not self.find_text("选择技能", roi=ROI["center_dialog"]):
        return
    # 【关键】一次 OCR 批量匹配所有技能文字
    skill_texts = [s["text"] for s in self.skills]
    # 优先技能在前
    priority_texts = [self._skill_name_to_text(n) for n in self.priority_skills if n]
    all_texts = priority_texts + [t for t in skill_texts if t not in priority_texts]
    results = self.ocr.find_texts_batch(
        self.take_screenshot(), all_texts, roi=ROI["skill_area"]
    )
    for text in all_texts:
        for pos in results.get(text, []):
            self.click(*pos)
```

### Step 4: 创建模式模块 `modes/`

每个模式类持有 `bot`（GameBotCore 实例）引用，通过组合调用公共能力。

#### `modes/huanqiu_mode.py`
```python
class HuanqiuMode:
    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        if bot.rich_mode == 1:  # 穷B模式
            bot.find_click_recruitment()
            if bot.find_in_huanqiu_team():
                time.sleep(6)
            if not bot.find_click_start_button():
                bot.find_click_dont_battle_return()
                bot.find_click_continue()
                return
            bot.find_click_im()
        else:  # 土豪模式
            if not bot.find_in_huanqiu_team():
                bot.click_text("基地")              # base 改 OCR
                bot.click_text("历练大厅")          # experience
                bot.click_text("寰球救援")          # huanqiu-challenge
            else:
                invite = bot.find_huanqiu_invite()
                if invite:
                    bot.click(*invite)
                    time.sleep(0.2)
                    bot.click_text("发布招募")
                    bot.find_click_home_close()
                    time.sleep(1)
                else:
                    bot.click_text("开始游戏")
                    bot.click_text("开始挑战")
```

#### `modes/mainline_mode.py`
```python
class MainlineMode:
    def __init__(self, bot):
        self.bot = bot

    def run(self):
        bot = self.bot
        if not bot.find_click_start_button():
            bot.find_click_dont_battle_return()
            bot.find_click_continue()
            return
        bot.find_click_card()  # 卡关（普通/开始游戏，已转 OCR）
```

#### `modes/expedition_mode.py`
```python
class ExpeditionMode:
    def __init__(self, bot, is_super=False):
        self.bot = bot
        self.is_super = is_super  # True=超级远征(mode=3), False=普通(mode=2)

    def run(self):
        bot = self.bot
        # 误入环球队伍则退出
        if bot.find_in_huanqiu_team():
            bot.find_click_dont_battle_return()
        if not bot.find_expedition_team():
            bot.click_text("基地")
            bot.click_text("历练大厅")
            bot.click_first_text(["挑战"])  # expedition-challenge
        else:
            exit_btn = bot.find_expedition_exit()
            if exit_btn:
                if bot.quick_exit:
                    bot.force_click_stop()
                    bot.click_text("退出")
                    bot.click(*exit_btn)
                    bot.click_text("确定")
                    return
                bot.click_text("点击空白处继续")
                bot.find_click_close()
                if bot.find_expedition_vice_captain_tag():
                    bot.click(*exit_btn)
                    bot.click_text("确定")
                else:
                    elite = bot.find_expedition_elite_tag()
                    if elite:
                        bot.click(elite[0], elite[1] + 100)
                        bot.click_text("开始挑战")
                    healths = bot.find_expedition_health_100s()
                    if len(healths) == 1:
                        bot.click(healths[0][0], healths[0][1] - 100)
                        bot.click_text("开始挑战")
        # 普通/超级远征入队策略
        in_team = bot.find_expedition_difficulty() if self.is_super else (
            bot.find_expedition_normal() or not bot.find_expedition_difficulty()
        )
        bot.expedition_in_team(in_team)
        if time.time() > bot.expedition_in_team_max_time:
            bot.click_expedition_fast_join()
```

### Step 5: 重构 `game_bot.py`（入口 + 主流程 + GUI）

`game_bot.py` 瘦身为：
1. **主流程调度** `main_loop()`：公共操作 → 战斗循环 → 模式分发 → 收尾。
2. **GUI** `GameBotGUI`：保留，技能下拉框改为从 `skill_config.json` 动态加载。

```python
from bot_core import GameBotCore
from modes.huanqiu_mode import HuanqiuMode
from modes.mainline_mode import MainlineMode
from modes.expedition_mode import ExpeditionMode

class GameBotApp:
    def __init__(self, ...):
        self.core = GameBotCore(...)
        # 模式分发
        if mode == 0:
            self.mode_handler = HuanqiuMode(self.core)
        elif mode == 1:
            self.mode_handler = MainlineMode(self.core)
        elif mode in (2, 3):
            self.mode_handler = ExpeditionMode(self.core, is_super=(mode == 3))

    def main_loop(self):
        self.core.setup_hotkey()
        while self.core.running:
            if self.core.max_battle_count > 0 and self.core.battle_count >= self.core.max_battle_count:
                break
            if not self.core.game_window and not self.core.find_game_window():
                time.sleep(5); continue
            # 公共操作
            self.core.find_click_receive()
            self.core.find_click_home_close()
            self.core.find_click_reconnection()
            self.core.find_click_sure()
            self.core.find_click_return()
            # 战斗循环
            while self.core.running and self.core.find_battling():
                self.core.find_click_skill()
                self.core.find_click_auto_close()
                self.core.find_click_reconnection()
                self.core.find_click_close()
                self.core.find_click_return()
                if self.core._should_exit_battle():
                    self.core.force_click_stop()
                    self.core.find_click_exit()
            # 模式专属逻辑
            self.mode_handler.run()
            # 收尾
            self.core.find_click_continue()
```

GUI 改动：
- `SKILL_LIST` 常量删除，改为启动时读取 `config/skill_config.json`。
- `get_skill_template_by_name` → `get_skill_text_by_name`，返回文字而非模板。
- `priority_skills` 保存的仍是技能 `name`（向后兼容现有 config.json）。

### Step 6: 更新 `requirements.txt`
```
pyautogui
opencv-python
numpy
pywin32
pynput
paddlepaddle>=2.6.0
paddleocr>=2.7.0
```

### Step 7: 更新 `README.md`
- 目录结构更新（新增 `bot_core.py`、`modes/`、`config/`、`game_ocr.py`）。
- 新增「OCR 识别」功能说明与依赖安装。
- 新增「技能配置」说明（编辑 `config/skill_config.json` 调整 OCR 文字）。
- 架构说明更新（入口/核心/模式三层）。

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `game_ocr.py` | **新建** | OCR 模块 + 游戏场景优化（mobile模型/ROI/预处理/批量匹配/缓存/白名单纠错） |
| `bot_core.py` | **新建** | 核心基类，抽离公共能力 |
| `modes/__init__.py` | **新建** | 包初始化 |
| `modes/huanqiu_mode.py` | **新建** | 寰球模式 |
| `modes/mainline_mode.py` | **新建** | 主线模式 |
| `modes/expedition_mode.py` | **新建** | 远征模式（普通+超级） |
| `config/skill_config.json` | **新建** | 技能 OCR 文字配置 |
| `game_bot.py` | **重构** | 瘦身为入口 + 主流程调度 + GUI |
| `requirements.txt` | **修改** | 新增 paddlepaddle、paddleocr |
| `README.md` | **修改** | 更新文档 |

---

## 验证方式
1. 安装依赖：`pip install -r requirements.txt`
2. 运行 `python game_bot.py`，启动 GUI
3. 确认技能下拉框从 `skill_config.json` 正确加载 14 个技能
4. 启动游戏，测试各模式（环球、主线、普通远征、超级远征）
5. 重点验证：
   - 技能 OCR 识别准确率（对比原模板匹配）
   - "基地"文字识别（原 base.png）
   - OCR 单次响应速度（目标 < 150ms）
   - 模式模块分发正确性
6. 回归测试：战斗计数、秒退、土豪/穷B模式、ESC 停止

## 注意事项
- PaddleOCR 采用 **PP-OCRv4 mobile 版**（PaddleOCR 默认即 mobile），CPU 首次加载约 3-5 秒，后续单次识别经优化约 80-150ms/图。
- mobile 版通用识别准确率较 server 低约 3-5%，但本项目经白名单后处理（见 1.6）后最终可用准确率反超 server 裸识别，且推理快 2-3 倍。如需切换 server 版，指定 `det_model_dir`/`rec_model_dir`。
- 白名单与 `config/skill_config.json` 联动：技能配置或模板文字映射变更时，须同步更新白名单（`_build_whitelist`），否则纠错失效。
- ROI 坐标基于标准窗口 542×1010，若用户调整窗口大小需重新校准（`resize_game_window` 已固定该尺寸）。
- 技能 OCR 依赖 `find_texts_batch` 单次识别多目标，切勿在循环内对每个技能单独调用 OCR。
- 图标类模板（关闭X、暂停、招募旗帜等）保留模板匹配，不转 OCR。
- `config/skill_config.json` 的 `text` 字段须与游戏内实际显示文字一致，游戏更新后可能需同步。
- 架构重构需保持 GUI 的 `config.json`（优先技能）向后兼容，`priority_skills` 仍存技能 `name`。
