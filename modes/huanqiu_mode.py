import time


class HuanqiuMode:
    """环球救援模式（我是穷B = 抢别人 ticket）。

    完整主流程（循环）：
      1. 抢 ticket：进入招募频道极速抢，检测到「等待开始」或「已激活技能」即视为成功
      2. 校验战斗：每30s查「佣兵队列」，共3次；都无则视为未真正进入战斗，回到步骤1重抢
      3. 等待战斗：等待8分钟（让房主打完）
      4. 等待结算：每30s查「恭喜获得」，出现则点「返回」回到寰球救援主页
      5. 回到步骤1，进入下一轮抢票
    """

    # 流程参数
    GRAB_DEADLINE = 600      # 抢票单轮最长 10 分钟（避免死循环）
    CHECK_INTERVAL = 30      # 校验/轮询间隔(秒)
    CHECK_MAX_TIMES = 3      # 「佣兵队列」校验次数
    BATTLE_WAIT = 8 * 60     # 等待战斗时长(秒)
    SETTLE_MAX_ROUNDS = 40   # 等待结算最长轮数(40*30s=20分钟兜底)

    def __init__(self, bot):
        self.bot = bot

    def _log(self, text):
        """统一日志（core._log 同时打印控制台 + 触发 GUI 回调）。"""
        self.bot._log(text)

    def run(self):
        """单次完整流程：抢票→等战斗→等结算→返回。
        抢到并完成结算后回到寰球主页，由外层 main_loop 再次进入本方法开启下一轮。
        """
        bot = self.bot
        if bot.rich_mode == 1:
            # 我是穷B：抢别人 ticket 的完整循环
            while bot.running:
                # —— 步骤1：抢 ticket ——
                self._log("[环球] ===== 步骤1/4：开始抢票 =====")
                grabbed = self._grab_phase()
                if not grabbed:
                    # 抢票阶段被中断或超时
                    break
                # —— 步骤2：校验是否真正进入战斗（查「佣兵队列」3次/30s）——
                self._log("[环球] ===== 步骤2/4：校验是否进入战斗 =====")
                in_battle = self._verify_battle_phase()
                if not in_battle:
                    self._log("[环球] 未检测到「佣兵队列」，可能未真正进入战斗，重新抢票")
                    continue  # 回到步骤1重抢
                # —— 步骤3：等待战斗结束（8分钟）——
                self._log("[环球] ===== 步骤3/4：等待战斗结束 =====")
                self._wait_battle_phase()
                # —— 步骤4：等待结算并返回主页 ——
                self._log("[环球] ===== 步骤4/4：等待结算并返回 =====")
                settled = self._wait_settle_phase()
                if not settled:
                    self._log("[环球] 等待结算超时，直接重新抢票")
                # 步骤5：回到步骤1（while 循环）
            # 抢票流程被中断时，跳过 main_loop 末尾的 find_click_continue
            return True
        else:
            # 我是土豪：自己开房间
            in_huanqiu_team = bot.find_in_huanqiu_team()
            if not in_huanqiu_team:
                bot.find_click_base()
                bot.find_click_experience()
                bot.find_click_huanqiu_challenge()
            else:
                invite_button = bot.find_huanqiu_invite()
                if invite_button:
                    bot.click(*invite_button)
                    time.sleep(0.2)
                    bot.find_click_huanqiu_post_recruitment()
                    bot.find_click_home_close()
                    time.sleep(1)
                else:
                    bot.find_click_start_game_button()
                    bot.find_click_start_challenge()
            return False

    # —— 各阶段实现 ——
    def _grab_phase(self):
        """抢票阶段：进入招募频道并抢，检测到「等待开始」或「已激活技能」返回 True。"""
        bot = self.bot
        self._log("[环球] 打开招募频道...")
        self._open_recruitment_channel()
        deadline = time.time() + self.GRAB_DEADLINE
        return bot.find_click_huanqiu_ticket(deadline=deadline)

    def _verify_battle_phase(self):
        """校验战斗阶段：每30s查「佣兵队列」，共3次；任一次命中即返回 True。"""
        bot = self.bot
        for i in range(self.CHECK_MAX_TIMES):
            if not bot.running:
                return False
            pos = bot.check_mercenary_queue()
            if pos:
                self._log(f"[环球] ✓ 第{i+1}次校验检测到「佣兵队列」@{pos}，已进入战斗")
                return True
            remain = self.CHECK_MAX_TIMES - i - 1
            self._log(
                f"[环球] 第{i+1}/{self.CHECK_MAX_TIMES}次校验未发现「佣兵队列」"
                f"{'，'+str(self.CHECK_INTERVAL)+'s后再查' if remain else '，已达上限'}"
            )
            if remain:
                bot.sleep_interruptible(self.CHECK_INTERVAL, tag=f"校验间隔({i+1})")
        return False

    def _wait_battle_phase(self):
        """等待战斗结束阶段：固定等待8分钟（可被 ESC 中断）。"""
        bot = self.bot
        self._log(f"[环球] 等待战斗结束 {self.BATTLE_WAIT}s（每分钟打印进度）")
        total = self.BATTLE_WAIT
        elapsed = 0
        step = 60
        while bot.running and elapsed < total:
            bot.sleep_interruptible(min(step, total - elapsed))
            elapsed += step
            if bot.running and elapsed < total:
                self._log(f"[环球] 战斗等待进度 {elapsed}/{total}s")

    def _wait_settle_phase(self):
        """等待结算阶段：每30s查「恭喜获得」，出现则点「返回」回寰球主页，返回 True。
        超过 SETTLE_MAX_ROUNDS 轮仍未结算则返回 False（兜底）。
        """
        bot = self.bot
        for i in range(self.SETTLE_MAX_ROUNDS):
            if not bot.running:
                return False
            pos = bot.check_congrats()
            if pos:
                self._log(f"[环球] ✓ 第{i+1}次检测到「恭喜获得」@{pos}，战斗结束，点返回")
                # 保存结算截图（强制取最新帧，确保是结算奖励画面）
                settle_file = f"screenshots/huanqiu_settle_{int(time.time())}.png"
                bot.save_screenshot(settle_file, force_new=True)
                # 参与战斗次数 +1（结算成功=完成一场战斗）
                bot.battle_count += 1
                if bot.on_battle_count_changed:
                    bot.on_battle_count_changed(bot.battle_count)
                bot.click_return_button()
                time.sleep(1.5)
                # 连点几次返回，确保从结算页退回寰球救援主页
                for back in range(4):
                    if not bot.running:
                        break
                    # 已回到寰球救援主页的标志：「招募/战斗」等大厅菜单可见
                    if bot.find_in_huanqiu_team() or bot.find_text(
                        "招募", roi=None
                    ):
                        break
                    bot.click_return_button()
                    time.sleep(1.0)
                self._log("[环球] 已返回寰球救援主页，准备下一轮抢票")
                return True
            remain = self.SETTLE_MAX_ROUNDS - i - 1
            self._log(
                f"[环球] 第{i+1}次等待结算未发现「恭喜获得」"
                f"{'，'+str(self.CHECK_INTERVAL)+'s后再查' if remain else ''}"
            )
            bot.sleep_interruptible(self.CHECK_INTERVAL, tag=f"等待结算({i+1})")
        return False

    # 聊天图标(气泡)候选坐标(窗口内相对坐标，右侧由上到下排列的图标之一)。
    # 实测聊天图标在右侧 x≈485-515；与通行证/宝箱/社交等图标纵向堆叠，
    # 聊天气泡通常在 y≈540-680 之间。这些作为模板匹配失败时的兜底点击点。
    CHAT_ICON_FALLBACKS = [(500, 560), (500, 600), (500, 640), (500, 680)]

    def _click_chat_icon_until_open(self):
        """点击聊天图标直到聊天框打开（检测到「招募」标签），返回是否成功。
        优先用 im.png 模板匹配；模板失败则按固定候选坐标依次尝试，
        每次点击后都用「招募」标签 OCR 校验聊天框是否真的打开。
        """
        bot = self.bot
        for i in range(3):
            # 方式A: 模板匹配点聊天图标
            clicked = bot.find_click_im()
            if clicked:
                self._log(f"[环球]   第{i+1}次: 模板匹配点击聊天图标")
            else:
                # 方式B: 模板未命中，按候选坐标兜底点击
                cx, cy = self.CHAT_ICON_FALLBACKS[i % len(self.CHAT_ICON_FALLBACKS)]
                # 转屏幕绝对坐标
                sx = bot.game_window[0] + cx
                sy = bot.game_window[1] + cy
                import pyautogui
                pyautogui.click(int(sx), int(sy))
                self._log(f"[环球]   第{i+1}次: 模板未命中，兜底点候选坐标({cx},{cy})")
            time.sleep(0.9)
            # 校验聊天框是否打开
            if bot.find_team_up():
                self._log("[环球]   ✓ 聊天框已打开（检测到「招募」标签）")
                return True
            self._log("[环球]   未检测到「招募」标签，聊天框可能未打开")
        return False

    def _open_recruitment_channel(self):
        """打开聊天框并切换到招募频道。
        每步操作后等待界面切换，并用文字确认进入下一界面，避免导航失败。
        每步都打日志，便于在 GUI 上看到当前导航进度。
        """
        bot = self.bot
        # 1. 点击战斗按钮（确保在大厅可见底部菜单）
        self._log("[环球] 导航1/3: 点击底部「战斗」回到大厅")
        bot.find_click_start_button()
        time.sleep(0.8)
        # 2. 点击聊天图标，等待对话框打开
        self._log("[环球] 导航2/3: 点击聊天图标，确认聊天框打开")
        opened = self._click_chat_icon_until_open()
        if not opened:
            self._log("[环球] 聊天框仍未打开，回到大厅再重试一次")
            bot.find_click_start_button()
            time.sleep(0.8)
            opened = self._click_chat_icon_until_open()
        # 3. 点击招募频道标签，等待切换
        self._log("[环球] 导航3/3: 点击「招募」频道标签")
        bot.find_click_recruitment()
        time.sleep(1.0)
        self._log("[环球] 已尝试切换到招募频道" + ("（聊天框已打开）" if opened else "（⚠聊天框可能未打开，招募点击可能无效）"))
