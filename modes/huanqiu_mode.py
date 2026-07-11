import time


class HuanqiuMode:
    """环球救援模式（我是穷B = 抢别人 ticket）。

    完整主流程（循环）：
      1. 抢 ticket：进入招募频道极速抢，检测到「等待开始」或「佣兵列队」即视为成功
      2. 校验战斗：每30s查「佣兵列队」，共3次；都无则视为未真正进入战斗，回到步骤1重抢
      3. 战斗 & 结算：复用 BattleController（选技能/精英掉落/恭喜获得/掉线检测）
      4. 回到步骤1，进入下一轮抢票
    """

    # 流程参数
    GRAB_DEADLINE = 600      # 抢票单轮最长 10 分钟（避免死循环）
    CHECK_INTERVAL = 30      # 校验/轮询间隔(秒)
    CHECK_MAX_TIMES = 3      # 「佣兵列队」校验次数

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
                    # 抢票失败：招募频道没打开 / 抢票超时。
                    # 若脚本仍在运行，则 continue 进入下一轮重试（而非退出整个流程）；
                    # 若已被停止(ESC)，则 break 退出。
                    if bot.running:
                        self._log("[环球] 抢票未成功，稍后重新开始下一轮")
                        continue
                    break
                # —— 步骤2：校验是否真正进入战斗（查「佣兵队列」3次/30s）——
                self._log("[环球] ===== 步骤2/4：校验是否进入战斗 =====")
                in_battle = self._verify_battle_phase()
                if not in_battle:
                    self._log("[环球] 未检测到「佣兵队列」，可能未真正进入战斗，重新抢票")
                    continue  # 回到步骤1重抢
                # —— 步骤3+4：战斗 & 结算（复用通用战斗控制器）——
                self._log("[环球] ===== 步骤3/4：战斗 & 结算 =====")
                from modes.battle_controller import BattleController
                bc = BattleController(self.bot, tag="[环球]")
                settled = bc.run_battle()
                if not settled:
                    self._log("[环球] 结算失败/掉线，重新抢票")
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
        """抢票阶段：进入招募频道并抢，检测到「等待开始」或「佣兵列队」返回 True。
        若无法打开招募频道（识别不到「招募」标签），返回 False 让外层重新开始。
        """
        bot = self.bot
        self._log("[环球] 打开招募频道...")
        opened = self._open_recruitment_channel()
        if not opened:
            self._log("[环球] ✗ 未进入招募频道，跳过本轮抢票，稍后重试")
            bot.sleep_interruptible(5, tag="招募频道未打开等待重试")
            return False
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

    def _click_chat_icon_until_open(self):
        """点击聊天图标直到聊天框打开（检测到「招募」标签），返回是否成功。
        find_click_im 内部已做：模板匹配优先(强制新截图) + 固定坐标(514,575)兜底。
        这里循环重试 3 次，每次点完都用「招募」标签校验聊天框是否真的打开。
        """
        bot = self.bot
        for i in range(3):
            clicked = bot.find_click_im()
            self._log(f"[环球]   第{i+1}次: 点击聊天图标 clicked={clicked}")
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
        返回 True=招募频道已打开（检测到「招募」标签），False=未打开。
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
        if not opened:
            # 两次都没打开聊天框，不再继续点招募标签（点了也无效）
            self._log("[环球] ✗ 聊天框两次均未打开，放弃本轮抢票，等待重试")
            return False
        # 3. 点击招募频道标签，等待切换
        self._log("[环球] 导航3/3: 点击「招募」频道标签")
        bot.find_click_recruitment()
        time.sleep(1.0)
        self._log("[环球] 已切换到招募频道")
        return True
