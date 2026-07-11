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

    # 战斗中技能选择的3个固定坐标（技能卡片位置）
    BATTLE_SKILL_POS = [(90, 546), (270, 546), (460, 546)]
    # 精英掉落坐标
    ELITE_DROP_POS = (260, 820)

    def _wait_battle_phase(self):
        """战斗阶段：不再固定等待8分钟，改为主动参与战斗。
        流程：
        1. 进入战斗页后随机点击3个技能坐标之一
        2. 循环识别页面：
           - 出现「选择技能」/「技能选择」→ 点3个技能坐标之一，技能选择计数+1
           - 出现「精英掉落」→ 点精英掉落坐标(260,820)
        本场战斗技能选择次数保存在 bot.skill_select_count（每次进入战斗重置为0）。
        循环直到 _wait_settle_phase 阶段接管（由外层 run() 调用顺序保证）。
        """
        import random
        bot = self.bot
        # 重置本场技能选择计数
        bot.skill_select_count = 0
        self._log("[环球] ===== 进入战斗，开始主动打怪 =====")
        # 进入战斗先随机点一个技能坐标
        pos = random.choice(self.BATTLE_SKILL_POS)
        sx = bot.game_window[0] + pos[0]
        sy = bot.game_window[1] + pos[1]
        import pyautogui
        pyautogui.click(int(sx), int(sy))
        self._log(f"[环球] 进战斗点击技能坐标 {pos}")

        # 循环识别技能选择/精英掉落
        check_round = 0
        while bot.running:
            check_round += 1
            # 查「选择技能」/「技能选择」(战斗中升级选技能弹窗)
            skill_pos = bot.find_text("选择技能", roi=ROI["center_dialog"]) or \
                        bot.find_text("技能选择", roi=ROI["center_dialog"])
            if skill_pos:
                # 出现技能选择，点3个坐标之一
                pick = random.choice(self.BATTLE_SKILL_POS)
                sx = bot.game_window[0] + pick[0]
                sy = bot.game_window[1] + pick[1]
                pyautogui.click(int(sx), int(sy))
                bot.skill_select_count += 1
                self._log(
                    f"[环球] 检测到「选择技能」(第{bot.skill_select_count}次)，"
                    f"点击技能坐标 {pick}"
                )
                time.sleep(1.5)  # 等待技能选择动画
                continue
            # 查「精英掉落」
            elite_pos = bot.find_text("精英掉落", roi=ROI["center_dialog"])
            if elite_pos:
                ex = bot.game_window[0] + self.ELITE_DROP_POS[0]
                ey = bot.game_window[1] + self.ELITE_DROP_POS[1]
                pyautogui.click(int(ex), int(ey))
                self._log(f"[环球] 检测到「精英掉落」@{elite_pos}，点击坐标 {self.ELITE_DROP_POS}")
                time.sleep(1.5)
                continue
            # 查「恭喜获得」(战斗结算标志) → 战斗结束，退出循环交给步骤4
            congrats = bot.check_congrats()
            if congrats:
                self._log(
                    f"[环球] 检测到「恭喜获得」@{congrats}，战斗结束！"
                    f"（本场技能选择{bot.skill_select_count}次）"
                )
                break
            # 没检测到技能选择/精英掉落/结算，短暂等待后继续
            time.sleep(2.0)
            if check_round % 15 == 0:
                self._log(f"[环球] 战斗进行中(第{check_round}轮检测)，技能选择累计{bot.skill_select_count}次")

    def _wait_settle_phase(self):
        """等待结算阶段：每30s查「恭喜获得」，出现则点「返回」回寰球主页，返回 True。
        每轮同时做掉线检测：检测到「掉线了」→点「确认」→查「佣兵列队」判断是否还在战斗：
          - 还在战斗(有佣兵列队) → 继续结算等待循环
          - 不在战斗(无佣兵列队) → 返回 False，由外层回主流程重新抢票
        超过 SETTLE_MAX_ROUNDS 轮仍未结算则返回 False（兜底）。
        """
        bot = self.bot
        for i in range(self.SETTLE_MAX_ROUNDS):
            if not bot.running:
                return False
            # 1. 查结算「恭喜获得」
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
            # 2. 掉线检测：查「掉线了」
            disconnect_pos = bot.check_disconnect()
            if disconnect_pos:
                self._log(f"[环球] ⚠ 第{i+1}次检测到「掉线了」@{disconnect_pos}，连续点击确定按钮")
                # click_confirm 会循环点击所有「确定」按钮（处理连续弹窗，如掉线后弹战斗结束）
                clicked = bot.click_confirm()
                self._log(f"[环球]   共点击 {clicked} 个确定按钮")
                # 点完所有确定后查「佣兵列队」判断是否还在战斗中
                in_battle = bot.check_mercenary_queue()
                if in_battle:
                    self._log(f"[环球] ✓ 掉线恢复后检测到「佣兵列队」@{in_battle}，仍在战斗中，继续等待结算")
                    # 继续结算等待循环（不 sleep，立即进入下一轮检查）
                    continue
                else:
                    self._log("[环球] ✗ 掉线恢复后未检测到「佣兵列队」，已不在战斗中，回主流程重新抢票")
                    return False
            remain = self.SETTLE_MAX_ROUNDS - i - 1
            self._log(
                f"[环球] 第{i+1}次等待结算未发现「恭喜获得」/「掉线了」"
                f"{'，'+str(self.CHECK_INTERVAL)+'s后再查' if remain else ''}"
            )
            bot.sleep_interruptible(self.CHECK_INTERVAL, tag=f"等待结算({i+1})")
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
