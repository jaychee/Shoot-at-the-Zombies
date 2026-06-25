import time


class HuanqiuMode:
    def __init__(self, bot):
        self.bot = bot

    def run(self):
        """返回 True 表示跳过主流程末尾的 find_click_continue"""
        bot = self.bot
        if bot.rich_mode == 1:
            bot.find_click_recruitment()
            in_huanqiu_team = bot.find_in_huanqiu_team()
            if in_huanqiu_team:
                time.sleep(6)
            start_button = bot.find_click_start_button()
            if not start_button:
                bot.find_click_dont_battle_return()
                bot.find_click_continue()
                return True
            bot.find_click_im()
            return False
        else:
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
