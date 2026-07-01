import time
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from bot_core import GameBotCore
from modes.huanqiu_mode import HuanqiuMode
from modes.mainline_mode import MainlineMode
from modes.expedition_mode import ExpeditionMode
from game_ocr import load_skill_config

SKILL_LIST = load_skill_config()

MODE_MAP = {"环球": 0, "主线": 1, "普通远征": 2, "超级远征": 3}


class GameBotApp:
    def __init__(
        self,
        game_title="游戏窗口标题",
        battle_time=0,
        max_battle_count=0,
        mode=0,
        priority_skills=None,
        rich_mode=0,
        wait_time=60,
        quick_exit=False,
    ):
        self.core = GameBotCore(
            game_title,
            battle_time,
            max_battle_count,
            mode,
            priority_skills,
            rich_mode,
            wait_time,
            quick_exit,
        )
        self.mode = mode
        if mode == 0:
            self.mode_handler = HuanqiuMode(self.core)
        elif mode == 1:
            self.mode_handler = MainlineMode(self.core)
        else:
            self.mode_handler = ExpeditionMode(self.core, is_super=(mode == 3))

    @property
    def running(self):
        return self.core.running

    @running.setter
    def running(self, value):
        self.core.running = value

    def main_loop(self):
        core = self.core
        core.setup_hotkey()

        print("开始自动刷图脚本...")
        print("提示: 按下ESC键可以随时停止脚本")

        while core.running:
            if core.max_battle_count > 0 and core.battle_count >= core.max_battle_count:
                print(f"已完成 {core.battle_count} 次刷图，脚本停止")
                core.running = False
                break

            if not core.game_window and not core.find_game_window():
                time.sleep(5)
                continue

            # 公共模块：领取/关闭/重连/确定/返回 等通用处理。
            # 当前 skip_public_ops=True，主流程暂不执行这些公共操作，
            # 直接进入模式分发。方法定义均保留在 bot_core，需要时关闭开关即可恢复。
            if not getattr(core, "skip_public_ops", False):
                core.find_click_receive()
                core.find_click_home_close()
                core.find_click_reconnection()
                core.find_click_sure()
                core.find_click_return()

            # 战斗中循环：技能/自动关闭/重连/关闭/返回/超时退出。
            # 同样受 skip_public_ops 控制，暂不执行。
            while True and core.running and not getattr(core, "skip_public_ops", False):
                battling = core.find_battling()
                if not battling:
                    break
                core.find_click_skill()
                core.find_click_auto_close()
                core.find_click_reconnection()
                core.find_click_close()
                core.find_click_return()

                if core.should_exit_battle():
                    print(f"战斗时间超过{core.battle_time}秒,退出")
                    core.force_click_stop()
                    core.find_click_exit()
                print("战斗时间:", time.time() - core.current_battle_time)

            skip_final = self.mode_handler.run()
            if not skip_final:
                core.find_click_continue()


class GameBotGUI:
    CONFIG_FILE = "config.json"

    def __init__(self, root):
        self.root = root
        self.root.title("游戏机器人操作界面")
        self.root.geometry("600x800")
        self.root.resizable(False, False)

        self.bot = None
        self.is_running = False

        self.create_widgets()
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    priority_skills = config.get("priority_skills", [])
                    for i, skill_name in enumerate(priority_skills):
                        if i < len(self.priority_skill_vars):
                            self.priority_skill_vars[i].set(skill_name)
        except Exception as e:
            print(f"加载配置失败: {e}")

    def save_config(self):
        try:
            config = {
                "priority_skills": [var.get() for var in self.priority_skill_vars]
            }
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def create_widgets(self):
        for i in range(16):
            self.root.grid_rowconfigure(i, minsize=40)

        ttk.Label(self.root, text="游戏窗口标题:").grid(
            row=0, column=0, padx=10, pady=5, sticky=tk.W
        )
        self.game_title_var = tk.StringVar(value="向僵尸开炮")
        self.game_title_entry = ttk.Entry(
            self.root, textvariable=self.game_title_var, width=30
        )
        self.game_title_entry.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)

        ttk.Label(self.root, text="模式:").grid(
            row=1, column=0, padx=10, pady=5, sticky=tk.W
        )
        self.mode_var = tk.StringVar(value="环球")
        self.mode_combo = ttk.Combobox(
            self.root,
            textvariable=self.mode_var,
            values=["环球", "主线", "普通远征", "超级远征"],
            width=15,
            state="readonly",
        )
        self.mode_combo.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_changed)

        self.rich_mode_label = ttk.Label(self.root, text="消费模式:")
        self.rich_mode_label.grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        self.rich_mode_frame = ttk.Frame(self.root)
        self.rich_mode_var = tk.IntVar(value=1)
        ttk.Radiobutton(
            self.rich_mode_frame, text="我是土豪", variable=self.rich_mode_var, value=0
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            self.rich_mode_frame, text="我是穷B", variable=self.rich_mode_var, value=1
        ).pack(side=tk.LEFT, padx=5)
        self.rich_mode_frame.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)

        self.quick_exit_label = ttk.Label(self.root, text="秒退模式:")
        self.quick_exit_label.grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        self.quick_exit_var = tk.BooleanVar(value=False)
        self.quick_exit_check = ttk.Checkbutton(
            self.root, text="开启秒退", variable=self.quick_exit_var
        )
        self.quick_exit_check.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)

        self.on_mode_changed(None)

        ttk.Label(self.root, text="战斗次数:").grid(
            row=4, column=0, padx=10, pady=5, sticky=tk.W
        )
        self.max_battle_count_var = tk.IntVar(value=0)
        self.max_battle_count_spinbox = ttk.Spinbox(
            self.root, from_=0, to=999, textvariable=self.max_battle_count_var, width=10
        )
        self.max_battle_count_spinbox.grid(
            row=4, column=1, padx=10, pady=5, sticky=tk.W
        )
        ttk.Label(self.root, text="(0表示无限循环)").grid(
            row=4, column=2, padx=5, pady=5, sticky=tk.W
        )

        ttk.Label(self.root, text="战斗时间(秒):").grid(
            row=5, column=0, padx=10, pady=5, sticky=tk.W
        )
        self.battle_time_var = tk.IntVar(value=0)
        self.battle_time_spinbox = ttk.Spinbox(
            self.root, from_=0, to=999, textvariable=self.battle_time_var, width=10
        )
        self.battle_time_spinbox.grid(row=5, column=1, padx=10, pady=5, sticky=tk.W)
        ttk.Label(self.root, text="(0表示无限制)").grid(
            row=5, column=2, padx=5, pady=5, sticky=tk.W
        )

        ttk.Label(self.root, text="优先技能(从上到下):").grid(
            row=7, column=0, padx=10, pady=5, sticky=tk.W
        )

        skill_names = [skill["name"] for skill in SKILL_LIST]

        self.priority_skill_vars = []
        self.priority_skill_combos = []
        for i in range(5):
            var = tk.StringVar(value="")
            self.priority_skill_vars.append(var)
            combo = ttk.Combobox(
                self.root,
                textvariable=var,
                values=[""] + skill_names,
                width=15,
                state="readonly",
            )
            combo.grid(row=6 + i, column=1, padx=10, pady=3, sticky=tk.W)
            combo.bind("<<ComboboxSelected>>", self.on_skill_selected)
            self.priority_skill_combos.append(combo)
            ttk.Label(self.root, text=f"优先级{i+1}").grid(
                row=6 + i, column=2, padx=5, pady=3, sticky=tk.W
            )

        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=11, column=0, columnspan=3, padx=10, pady=20)

        self.start_btn = ttk.Button(
            button_frame, text="开始", command=self.start_bot, width=15
        )
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = ttk.Button(
            button_frame,
            text="停止",
            command=self.stop_bot,
            width=15,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        self.resize_btn = ttk.Button(
            button_frame, text="调整窗口大小", command=self.resize_window, width=15
        )
        self.resize_btn.pack(side=tk.LEFT, padx=10)

        self.quit_btn = ttk.Button(
            button_frame, text="退出", command=self.quit_app, width=15
        )
        self.quit_btn.pack(side=tk.LEFT, padx=10)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, foreground="green").grid(
            row=12, column=0, columnspan=3, padx=10, pady=10, sticky=tk.W
        )

        self.battle_count_var = tk.StringVar(value="战斗次数: 0")
        ttk.Label(
            self.root, textvariable=self.battle_count_var, foreground="blue"
        ).grid(row=13, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W)

        ttk.Label(self.root, text="提示: 按ESC键暂停脚本", foreground="blue").grid(
            row=14, column=0, columnspan=3, padx=10, pady=5, sticky=tk.W
        )

    def on_skill_selected(self, event):
        selected_skills = [var.get() for var in self.priority_skill_vars if var.get()]
        all_skills = [skill["name"] for skill in SKILL_LIST]
        for i, combo in enumerate(self.priority_skill_combos):
            current_value = self.priority_skill_vars[i].get()
            available = [""] + [
                s for s in all_skills if s not in selected_skills or s == current_value
            ]
            combo["values"] = available

    def _update_battle_count(self, count):
        self.root.after(0, lambda: self.battle_count_var.set(f"战斗次数: {count}"))

    def on_mode_changed(self, event):
        mode = self.mode_var.get()
        if mode in ["环球", "普通远征", "超级远征"]:
            self.rich_mode_label.grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
            self.rich_mode_frame.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
        else:
            self.rich_mode_label.grid_remove()
            self.rich_mode_frame.grid_remove()

        if mode in ["普通远征", "超级远征", "主线"]:
            self.quick_exit_label.grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
            self.quick_exit_check.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)
        else:
            self.quick_exit_label.grid_remove()
            self.quick_exit_check.grid_remove()

    def start_bot(self):
        try:
            game_title = self.game_title_var.get()
            mode_text = self.mode_var.get()
            mode = MODE_MAP.get(mode_text, 0)
            max_battle_count = self.max_battle_count_var.get()
            battle_time = self.battle_time_var.get()
            rich_mode = self.rich_mode_var.get()
            quick_exit = self.quick_exit_var.get()

            priority_skills = []
            for var in self.priority_skill_vars:
                skill_name = var.get()
                if skill_name:
                    priority_skills.append(skill_name)

            self.save_config()

            if not game_title:
                messagebox.showerror("错误", "请输入游戏窗口标题")
                return

            try:
                temp_core = GameBotCore(game_title=game_title, init_ocr=False)
                if temp_core.resize_game_window(move_to_origin=True):
                    self.status_var.set("游戏窗口已调整至(0,0) 542x1010")
                else:
                    messagebox.showwarning("提示", "未找到游戏窗口，无法自动调整大小，请确认游戏已打开")
            except Exception as e:
                print(f"调整游戏窗口失败: {e}")

            self.bot = GameBotApp(
                game_title,
                battle_time,
                max_battle_count,
                mode,
                priority_skills,
                rich_mode,
                60,
                quick_exit,
            )
            self.bot.core.on_battle_count_changed = self._update_battle_count

            self.status_var.set("运行中...")
            self.battle_count_var.set("战斗次数: 0")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)

            self.game_title_entry.config(state=tk.DISABLED)
            self.mode_combo.config(state=tk.DISABLED)
            for child in self.rich_mode_frame.winfo_children():
                child.config(state=tk.DISABLED)
            self.quick_exit_check.config(state=tk.DISABLED)
            self.max_battle_count_spinbox.config(state=tk.DISABLED)
            self.battle_time_spinbox.config(state=tk.DISABLED)
            for combo in self.priority_skill_combos:
                combo.config(state=tk.DISABLED)
            self.resize_btn.config(state=tk.DISABLED)

            self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
            self.bot_thread.start()

        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
            self.status_var.set("就绪")

    def run_bot(self):
        try:
            while self.bot and self.bot.running:
                self.bot.main_loop()
                time.sleep(0.1)
        except Exception as e:
            print(f"运行出错: {str(e)}")
        finally:
            self.root.after(0, self.stop_bot)

    def stop_bot(self):
        if self.bot:
            self.bot.running = False
            self.bot = None

        self.status_var.set("已停止")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        self.game_title_entry.config(state=tk.NORMAL)
        self.mode_combo.config(state=tk.NORMAL)
        for child in self.rich_mode_frame.winfo_children():
            child.config(state=tk.NORMAL)
        self.quick_exit_check.config(state=tk.NORMAL)
        self.max_battle_count_spinbox.config(state=tk.NORMAL)
        self.battle_time_spinbox.config(state=tk.NORMAL)
        for combo in self.priority_skill_combos:
            combo.config(state=tk.NORMAL)
        self.resize_btn.config(state=tk.NORMAL)

    def resize_window(self):
        try:
            game_title = self.game_title_var.get()
            temp_core = GameBotCore(game_title=game_title, init_ocr=False)
            if temp_core.resize_game_window():
                self.status_var.set("窗口大小已调整为542*1010")
            else:
                self.status_var.set("未找到游戏窗口，无法调整大小")
        except Exception as e:
            self.status_var.set(f"调整窗口大小失败: {e}")

    def quit_app(self):
        if self.bot:
            self.bot.running = False
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(default=None)
    except:
        pass
    app = GameBotGUI(root)
    root.mainloop()
