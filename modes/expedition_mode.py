import time


class ExpeditionMode:
    def __init__(self, bot, is_super=False):
        self.bot = bot
        self.is_super = is_super

    def run(self):
        """返回 True 表示跳过主流程末尾的 find_click_continue"""
        bot = self.bot

        in_huanqiu_team = bot.find_in_huanqiu_team()
        if in_huanqiu_team:
            bot.find_click_dont_battle_return()

        in_expedition_team = bot.find_expedition_team()
        if not in_expedition_team:
            bot.find_click_base()
            bot.find_click_experience()
            bot.find_click_expedition_challenge()
        else:
            expedition_exit_button = bot.find_expedition_exit()
            if expedition_exit_button:
                if bot.quick_exit:
                    bot.force_click_stop()
                    bot.find_click_exit()
                    bot.click(*expedition_exit_button)
                    bot.find_click_sure()
                    return True

                bot.find_click_expedition_continue()
                bot.find_click_close()
                vice_captain_tag = bot.find_expedition_vice_captain_tag()
                if vice_captain_tag:
                    bot.click(*expedition_exit_button)
                    bot.find_click_sure()
                else:
                    elite_tag = bot.find_expedition_elite_tag()
                    if elite_tag:
                        elite_tag = (elite_tag[0], elite_tag[1] + 100)
                        bot.click(*elite_tag)
                        time.sleep(0.1)
                        bot.find_click_start_challenge()
                    expedition_healths = bot.find_expedition_health_100s()
                    if len(expedition_healths) == 1:
                        expedition_health = expedition_healths[0]
                        expedition_health = (
                            expedition_health[0],
                            expedition_health[1] - 100,
                        )
                        bot.click(*expedition_health)
                        time.sleep(0.1)
                        bot.find_click_start_challenge()

        if self.is_super:
            in_difficulty = bot.find_expedition_difficulty()
            bot.expedition_in_team(in_difficulty)
        else:
            in_normal = bot.find_expedition_normal()
            if not in_normal:
                in_normal = not bot.find_expedition_difficulty()
            bot.expedition_in_team(in_normal)

        if time.time() > bot.expedition_in_team_max_time:
            print("等待时间超过最大时间,重新点击")
            bot.click_expedition_fast_join()
        else:
            remain_time = bot.expedition_in_team_max_time - time.time()
            remain_time = int(remain_time)
            print(f"等待时间剩余{remain_time}秒")

        return False
