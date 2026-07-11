"""通用战斗控制器：从进入战斗到结算返回的完整逻辑。

可被任何游戏模式复用（寰球/远征/主线等）。用法：
    from modes.battle_controller import BattleController
    bc = BattleController(bot, tag="[环球]")
    settled = bc.run_battle()  # 返回 True=结算成功，False=失败/掉线

流程：
  1. 战斗阶段：主动选技能/点精英掉落，检测到「恭喜获得」退出
  2. 结算阶段：点返回领奖 + 掉线检测，返回是否成功
"""
import time
import random
import pyautogui

from game_ocr import ROI
from bot_core import TEXT


class BattleController:
    """通用战斗控制器：从进入战斗到结算返回，可被任何模式复用。"""

    # —— 可配置参数（子类可覆盖或构造时传入）——
    BATTLE_SKILL_POS = [(90, 546), (270, 546), (460, 546)]  # 技能卡片坐标(窗口内)
    ELITE_DROP_POS = (260, 820)                             # 精英掉落坐标(窗口内)
    SETTLE_MAX_ROUNDS = 40                                  # 结算等待最大轮数
    CHECK_INTERVAL = 30                                     # 结算轮询间隔(秒)
    SETTLE_SCREENSHOT_PREFIX = "settle"                     # 结算截图文件名前缀

    def __init__(self, bot, tag="战斗"):
        self.bot = bot
        self.tag = tag  # 日志前缀，如 "[环球]"/"[远征]"

    def _log(self, text):
        self.bot._log(f"{self.tag} {text}")

    def _abs(self, pos):
        """窗口内坐标 → 屏幕绝对坐标。"""
        return (int(self.bot.game_window[0] + pos[0]),
                int(self.bot.game_window[1] + pos[1]))

    def run_battle(self):
        """完整战斗流程：主动打怪 → 结算 → 返回主页。
        返回 True=结算成功，False=失败/掉线/超时。
        """
        self._battle_phase()
        return self._settle_phase()

    # —— 战斗阶段：主动选技能/点精英掉落，直到「恭喜获得」——
    def _battle_phase(self):
        bot = self.bot
        # 重置本场技能选择计数
        bot.skill_select_count = 0
        self._log("===== 进入战斗，开始主动打怪 =====")
        # 进入战斗先随机点一个技能坐标
        pos = random.choice(self.BATTLE_SKILL_POS)
        pyautogui.click(*self._abs(pos))
        self._log(f"进战斗点击技能坐标 {pos}")

        check_round = 0
        while bot.running:
            check_round += 1
            # 查「选择技能」/「技能选择」(战斗中升级选技能弹窗)
            skill_pos = bot.find_text(TEXT["choose_skill"], roi=ROI["center_dialog"]) or \
                        bot.find_text("技能选择", roi=ROI["center_dialog"])
            if skill_pos:
                pick = random.choice(self.BATTLE_SKILL_POS)
                pyautogui.click(*self._abs(pick))
                bot.skill_select_count += 1
                self._log(
                    f"检测到「选择技能」(第{bot.skill_select_count}次)，"
                    f"点击技能坐标 {pick}"
                )
                time.sleep(1.5)
                continue
            # 查「精英掉落」→ 点(260,820)两次，间隔1.5s
            elite_pos = bot.find_text(TEXT["battling_elite"], roi=ROI["center_dialog"])
            if elite_pos:
                abs_pos = self._abs(self.ELITE_DROP_POS)
                pyautogui.click(*abs_pos)
                time.sleep(1.5)
                pyautogui.click(*abs_pos)
                self._log(f"检测到「精英掉落」@{elite_pos}，点击坐标 {self.ELITE_DROP_POS}×2")
                time.sleep(1.5)
                continue
            # 查「恭喜获得」(战斗结算标志) → 战斗结束
            congrats = bot.check_congrats()
            if congrats:
                self._log(
                    f"检测到「恭喜获得」@{congrats}，战斗结束！"
                    f"（本场技能选择{bot.skill_select_count}次）"
                )
                break
            # 没检测到技能选择/精英掉落/结算，短暂等待后继续
            time.sleep(2.0)
            if check_round % 15 == 0:
                self._log(f"战斗进行中(第{check_round}轮检测)，技能选择累计{bot.skill_select_count}次")

    # —— 结算阶段：点返回领奖 + 掉线检测 ——
    def _settle_phase(self):
        """结算阶段：每30s查「恭喜获得」，出现则点「返回」回主页，返回 True。
        同时做掉线检测：检测到「掉线了」→点「确定」→查「佣兵列队」判断是否还在战斗：
          - 还在战斗 → 继续等待结算
          - 不在战斗 → 返回 False
        超过 SETTLE_MAX_ROUNDS 轮仍未结算则返回 False（兜底）。
        """
        bot = self.bot
        for i in range(self.SETTLE_MAX_ROUNDS):
            if not bot.running:
                return False
            # 1. 查结算「恭喜获得」
            pos = bot.check_congrats()
            if pos:
                self._log(f"✓ 第{i+1}次检测到「恭喜获得」@{pos}，战斗结束，点返回")
                settle_file = f"screenshots/{self.SETTLE_SCREENSHOT_PREFIX}_{int(time.time())}.png"
                bot.save_screenshot(settle_file, force_new=True)
                bot.battle_count += 1
                if bot.on_battle_count_changed:
                    bot.on_battle_count_changed(bot.battle_count)
                bot.click_return_button()
                time.sleep(1.5)
                # 连点几次返回，确保退回主页
                for back in range(4):
                    if not bot.running:
                        break
                    if bot.find_in_huanqiu_team() or bot.find_text("招募", roi=None):
                        break
                    bot.click_return_button()
                    time.sleep(1.0)
                self._log("已返回主页")
                return True
            # 2. 掉线检测：查「掉线了」
            disconnect_pos = bot.check_disconnect()
            if disconnect_pos:
                self._log(f"⚠ 第{i+1}次检测到「掉线了」@{disconnect_pos}，连续点击确定按钮")
                clicked = bot.click_confirm()
                self._log(f"  共点击 {clicked} 个确定按钮")
                in_battle = bot.check_mercenary_queue()
                if in_battle:
                    self._log(f"✓ 掉线恢复后检测到「佣兵列队」@{in_battle}，仍在战斗中，继续等待结算")
                    continue
                else:
                    self._log("✗ 掉线恢复后未检测到「佣兵列队」，已不在战斗中")
                    return False
            remain = self.SETTLE_MAX_ROUNDS - i - 1
            self._log(
                f"第{i+1}次等待结算未发现「恭喜获得」/「掉线了」"
                f"{'，'+str(self.CHECK_INTERVAL)+'s后再查' if remain else ''}"
            )
            bot.sleep_interruptible(self.CHECK_INTERVAL, tag=f"等待结算({i+1})")
        return False
