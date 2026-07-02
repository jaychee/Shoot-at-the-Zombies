"""后台运行环球抢 ticket（我是穷B 模式），无 GUI。"""
import sys
import time

from game_bot import GameBotApp


def main():
    print("=" * 60, flush=True)
    print("后台抢 ticket 测试  环球/我是穷B  开始", flush=True)
    print("=" * 60, flush=True)
    app = GameBotApp(
        game_title="向僵尸开炮",
        battle_time=0,
        max_battle_count=0,
        mode=0,           # 环球
        priority_skills=[],
        rich_mode=1,      # 我是穷B -> 抢 ticket
        wait_time=60,
        quick_exit=False,
    )
    # 公共模块已由 core.skip_public_ops 全局跳过
    print(f"[init] skip_public_ops={app.core.skip_public_ops}", flush=True)
    # 启动时自动调整窗口到 (0,0) 542×1010，让所有 ROI/坐标/模板稳定可复现
    if app.core.resize_game_window(542, 1010, move_to_origin=True):
        print("[init] 游戏窗口已调整至 (0,0) 542×1010", flush=True)
    else:
        print("[init] ⚠ 未找到游戏窗口，无法自动调整大小", flush=True)
    t0 = time.time()
    deadline = t0 + 1800  # 最多跑 30 分钟（含抢票+8分钟战斗等待+结算）
    try:
        while app.running and time.time() < deadline:
            app.main_loop()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("手动中断", flush=True)
    finally:
        app.running = False
        print(f"[done] 共运行 {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
