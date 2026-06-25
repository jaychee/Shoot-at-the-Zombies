class MainlineMode:
    def __init__(self, bot):
        self.bot = bot

    def run(self):
        """返回 True 表示跳过主流程末尾的 find_click_continue"""
        bot = self.bot
        start_button = bot.find_click_start_button()
        if not start_button:
            bot.find_click_dont_battle_return()
            bot.find_click_continue()
            return True
        bot.find_click_card()
        return False
