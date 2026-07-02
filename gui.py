"""寰球救援 - 抢票&战斗 简易 GUI。

功能：
- 点击「开始」按钮或按 F9 启动；按 ESC 停止。
- 实时显示抢到票次数 / 参与战斗次数。
- 实时日志区显示当前脚本执行步骤。
- 每场战斗结算后自动截图保存到 screenshots/。

入口：python gui.py
"""
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from game_bot import GameBotApp

MAX_LOG_LINES = 500  # 日志区最多保留行数（超出自动裁剪旧日志）


class HuanqiuGUI:
    """抢票&战斗简易控制面板。"""

    def __init__(self, root):
        self.root = root
        self.root.title("寰球救援 - 抢票&战斗")
        self.root.geometry("460x560")
        self.root.resizable(False, False)
        # 置顶方便观察（不抢游戏焦点）
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.bot = None
        self.bot_thread = None
        self.f9_listener = None

        self._build_ui()
        # 启动定时刷新战绩
        self._refresh_stats()

    # —— UI 构建 ——
    def _build_ui(self):
        # 顶部：标题 + 状态
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=(10, 4))
        ttk.Label(top, text="寰球救援 · 抢票 & 战斗", font=("Microsoft YaHei", 13, "bold")).pack()
        self.status_var = tk.StringVar(value="就绪")
        self.status_lbl = ttk.Label(
            top, textvariable=self.status_var, font=("Microsoft YaHei", 10), foreground="green"
        )
        self.status_lbl.pack()

        # 战绩区
        stat_frame = ttk.Frame(self.root)
        stat_frame.pack(pady=6)
        self.grab_var = tk.StringVar(value="抢到票: 0")
        self.battle_var = tk.StringVar(value="参与战斗: 0")
        ttk.Label(
            stat_frame, textvariable=self.grab_var, font=("Microsoft YaHei", 15, "bold"),
            foreground="#cc6600",
        ).grid(row=0, column=0, padx=18)
        ttk.Label(
            stat_frame, textvariable=self.battle_var, font=("Microsoft YaHei", 15, "bold"),
            foreground="#0066cc",
        ).grid(row=0, column=1, padx=18)

        # 按钮区
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=4)
        self.start_btn = ttk.Button(btn_frame, text="开始", width=12, command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=8)
        self.stop_btn = ttk.Button(btn_frame, text="停止", width=12, command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=8)
        # 清空日志按钮
        self.clear_btn = ttk.Button(btn_frame, text="清空日志", width=10, command=self._clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=8)

        # 日志区标题
        log_header = ttk.Frame(self.root)
        log_header.pack(fill=tk.X, padx=10)
        ttk.Label(log_header, text="执行日志：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        # 日志文本框（滚动）
        self.log_text = scrolledtext.ScrolledText(
            self.root, height=14, font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 4))

        # 底部提示
        ttk.Label(
            self.root,
            text="F9 启动 / ESC 停止 · 结算截图保存到 screenshots/",
            font=("Microsoft YaHei", 8),
            foreground="gray",
        ).pack(side=tk.BOTTOM, pady=4)

    # —— 日志显示 ——
    def _append_log(self, text):
        """向日志区追加一行（线程安全：通过 after 切回主线程）。"""
        def _do():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, str(text) + "\n")
            # 超出行数限制则裁剪旧日志
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > MAX_LOG_LINES:
                self.log_text.delete(1.0, f"{line_count - MAX_LOG_LINES}.0")
            self.log_text.see(tk.END)  # 自动滚到底部
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, _do)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    # —— 启停逻辑 ——
    def start(self):
        if self.bot is not None:
            return
        self._append_log("===== 启动脚本 =====")
        try:
            self.bot = GameBotApp(
                game_title="向僵尸开炮",
                mode=0,           # 环球
                rich_mode=1,      # 我是穷B（抢票）
                max_battle_count=0,
                battle_time=0,
                priority_skills=[],
                wait_time=60,
                quick_exit=False,
            )
            # 绑定回调
            self.bot.core.on_grab_count_changed = self._on_grab_changed
            self.bot.core.on_battle_count_changed = self._on_battle_changed
            self.bot.core.on_log = self._append_log  # 关键：实时日志
            # 启动时自动调整窗口到 (0,0) 542×1010，让所有 ROI/坐标/模板稳定可复现
            try:
                if self.bot.core.resize_game_window(542, 1010, move_to_origin=True):
                    self._append_log("游戏窗口已调整至 (0,0) 542×1010")
                else:
                    self._append_log("⚠ 未找到游戏窗口，无法自动调整大小（请确认游戏已打开）")
            except Exception as e:
                # MoveWindow「拒绝访问」= 当前非管理员权限。
                # 游戏是微信小程序(WeChatAppEx.exe)，窗口受保护，必须管理员才能调整。
                # 此时窗口位置/尺寸可能不对，后续坐标会偏，抢票大概率失败。
                self._append_log(
                    f"调整窗口失败: {e}\n"
                    "  → 根因：未以管理员身份运行。微信小程序窗口需管理员权限才能调整。\n"
                    "  → 解决：请用「启动.bat」启动（会自动请求管理员权限），"
                    "或右键以管理员身份运行。窗口未调整时抢票坐标会偏移。"
                )
            # 初始化战绩显示
            self.grab_var.set(f"抢到票: {self.bot.core.grab_count}")
            self.battle_var.set(f"参与战斗: {self.bot.core.battle_count}")
        except Exception as e:
            self._append_log(f"启动失败: {e}")
            return

        self.status_var.set("运行中...")
        self.status_lbl.config(foreground="green")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # 后台线程跑主循环（mode_handler.run 内含 抢票→战斗→结算→重抢 循环）
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _run_bot(self):
        try:
            bot = self.bot
            if bot is None:
                return
            while bot and bot.running:
                bot.main_loop()
        except Exception as e:
            self._append_log(f"运行出错: {e}")
        finally:
            self.root.after(0, self._on_stopped)

    def stop(self):
        if self.bot is not None:
            self.bot.running = False
            self._append_log("正在停止脚本...")

    def _on_stopped(self):
        self.bot = None
        self.status_var.set("已停止")
        self.status_lbl.config(foreground="gray")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self._append_log("===== 脚本已停止 =====")

    # —— 战绩回调（在工作线程触发，通过 after 切回主线程）——
    def _on_grab_changed(self, count):
        self.root.after(0, lambda: self.grab_var.set(f"抢到票: {count}"))

    def _on_battle_changed(self, count):
        self.root.after(0, lambda: self.battle_var.set(f"参与战斗: {count}"))

    def _refresh_stats(self):
        """定时轮询战绩（回调兜底，确保数值同步）。"""
        if self.bot and self.bot.core:
            self.grab_var.set(f"抢到票: {self.bot.core.grab_count}")
            self.battle_var.set(f"参与战斗: {self.bot.core.battle_count}")
            if not self.bot.running:
                self._on_stopped()
        self.root.after(1000, self._refresh_stats)

    # —— F9 启动快捷键（后台 pynput 监听，无需窗口焦点）——
    def setup_f9_hotkey(self):
        from pynput import keyboard

        def on_activate():
            # 切回主线程触发 start
            self.root.after(0, self.start)

        try:
            self.f9_listener = keyboard.GlobalHotKeys({"<f9>": on_activate})
            self.f9_listener.start()
            self._append_log("快捷键已就绪: F9 启动 / ESC 停止")
        except Exception as e:
            self._append_log(f"F9 快捷键设置失败: {e}")

    def on_close(self):
        if self.bot is not None:
            self.bot.running = False
        if self.f9_listener is not None:
            self.f9_listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = HuanqiuGUI(root)
    app.setup_f9_hotkey()
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
