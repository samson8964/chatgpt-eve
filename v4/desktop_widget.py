"""Small always-on-top Windows desktop widget for EVE V4 shadow task.

Local-only, read-only monitoring. Never triggers a scan, reads secrets,
imports mail modules, or makes HTTP calls. Tkinter ships with CPython.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from v4.desktop_status import elapsed_clock, human_clock, read_snapshot

COLORS = {
    "bg": "#101827",
    "panel": "#182337",
    "line": "#30425b",
    "white": "#f0f5fc",
    "muted": "#a7b4c8",
    "green": "#63d69a",
    "amber": "#f0b65c",
    "red": "#ef818c",
    "blue": "#83b9ff",
}
TASK_NAME = "EVE-V4-Shadow"
FILE_POLL_MS = 3000
TASK_POLL_SECONDS = 12


def query_windows_task(*, runner=subprocess.run) -> dict:
    """Query Task Scheduler without a visible terminal or privileged access."""
    if sys.platform != "win32":
        return {"state": "UNSUPPORTED"}
    script = (
        "$ErrorActionPreference='Stop'; "
        "$t=Get-ScheduledTask -TaskName 'EVE-V4-Shadow'; "
        "$i=Get-ScheduledTaskInfo -TaskName 'EVE-V4-Shadow'; "
        "[pscustomobject]@{"
        "state=$t.State.ToString();"
        "next_run=$i.NextRunTime.ToString('o');"
        "last_run=$i.LastRunTime.ToString('o');"
        "last_result=$i.LastTaskResult"
        "} | ConvertTo-Json -Compress"
    )
    try:
        result = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        if result.returncode:
            return {"state": "MISSING" if "ObjectNotFound" in result.stderr
                    or "No MSFT_ScheduledTask" in result.stderr else "UNKNOWN"}
        data = json.loads(result.stdout.strip())
        return data if isinstance(data, dict) else {"state": "UNKNOWN"}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"state": "UNKNOWN"}


def _status_style(s: str) -> tuple[str, str]:
    names = {
        "RUNNING": ("正在扫描", "blue"),
        "SHADOW_RECORDED": ("最近扫描成功", "green"),
        "DEGRADED_INPUT_QUARANTINE": ("数据校验告警", "amber"),
        "DEGRADED_PARTIAL_COVERAGE": ("数据覆盖不完整", "amber"),
        "PARTIAL_UNVERIFIED": ("数据尚未完整验证", "amber"),
        "CHECK_TASK_RESULT": ("需要查看任务日志", "amber"),
        "FAILED": ("上次运行失败", "red"),
        "DISABLED": ("计划任务已禁用", "red"),
        "TASK_MISSING": ("未找到计划任务", "red"),
        "NO_HISTORY": ("等待首次扫描", "muted"),
    }
    return names.get(s, ("计划任务待命", "muted"))


def _format_int(value) -> str:
    try:
        return format(int(value), ",")
    except (ValueError, TypeError):
        return "--"


class DesktopWidget:
    def __init__(self, root, data_root: Path):
        import tkinter as tk
        self.tk = tk
        self.root = root
        self.data_root = data_root
        self.log_path = data_root / "logs" / "shadow-task.log"
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v4-task-watch")
        self.pending = None
        self.last_query_at = 0.0
        self.task = {"state": "Unknown"}
        self.closed = False
        self.pinned = True
        self.drag_position = None

        root.overrideredirect(True)
        root.configure(bg=COLORS["line"])
        root.attributes("-topmost", True)
        root.resizable(False, False)
        w, h = 358, 255
        x = max(0, root.winfo_screenwidth() - w - 26)
        root.geometry(f"{w}x{h}+{x}+60")
        tkfont = ("Microsoft YaHei UI", 9)
        self.font = tkfont

        shell = tk.Frame(root, bg=COLORS["bg"], highlightbackground=COLORS["line"],
                         highlightthickness=1)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        title = tk.Frame(shell, bg=COLORS["bg"], height=34)
        title.pack(fill="x", padx=12, pady=(9, 3))
        self._label(title, "EVE V4  |  市场+合同监控", 10, "white", bold=True).pack(side="left")
        self._button(title, "×", self.close, width=2).pack(side="right")
        self.pin_button = self._button(title, "置顶", self.toggle_pin, width=4)
        self.pin_button.pack(side="right", padx=(0, 6))
        for widget in (title,):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)

        self.state_label = self._label(shell, "●  读取任务状态…", 14, "blue", bold=True)
        self.state_label.pack(anchor="w", padx=14, pady=(5, 0))
        self.phase_label = self._label(shell, "正在读取本机日志", 9, "muted")
        self.phase_label.pack(anchor="w", padx=15, pady=(0, 8))

        divider = tk.Frame(shell, height=1, bg=COLORS["line"])
        divider.pack(fill="x", padx=12)

        self.previous_label = self._label(shell, "上一轮：读取中", 9, "white")
        self.previous_label.pack(anchor="w", padx=14, pady=(9, 2))
        self.structures_label = self._label(shell, "4-H --    C-J --    O4T --", 9, "muted")
        self.structures_label.pack(anchor="w", padx=14, pady=(1, 3))
        self.metrics_label = self._label(shell, "审核记录 --  |  候选 --", 9, "muted")
        self.metrics_label.pack(anchor="w", padx=14, pady=(1, 4))
        self.next_label = self._label(shell, "下次自动：--", 9, "white")
        self.next_label.pack(anchor="w", padx=14, pady=(1, 5))

        footer = tk.Frame(shell, bg=COLORS["panel"], height=26)
        footer.pack(side="bottom", fill="x")
        self.refresh_label = self._label(footer, "只读 · 双通道审核 · 3秒刷新", 8, "muted",
                                         bg="panel")
        self.refresh_label.pack(side="left", padx=(10, 0), pady=5)
        self._button(footer, "查看日志", self.open_log, width=7, bg="panel").pack(
            side="right", padx=8, pady=1)

        self.root.after(150, self.refresh)

    def _label(self, parent, text, size, color, *, bold=False, bg="bg"):
        return self.tk.Label(parent, text=text, fg=COLORS[color], bg=COLORS[bg],
                             font=("Microsoft YaHei UI", size,
                                   "bold" if bold else "normal"),
                             anchor="w", justify="left", bd=0)

    def _button(self, parent, text, callback, *, width=5, bg="bg"):
        return self.tk.Button(parent, text=text, command=callback, width=width,
                              bg=COLORS[bg], fg=COLORS["muted"], bd=0,
                              activebackground=COLORS["line"],
                              activeforeground=COLORS["white"], cursor="hand2",
                              font=("Microsoft YaHei UI", 8))

    def start_drag(self, event):
        self.drag_position = (event.x_root - self.root.winfo_x(),
                              event.y_root - self.root.winfo_y())

    def drag(self, event):
        if self.drag_position:
            self.root.geometry("+%d+%d" % (
                event.x_root - self.drag_position[0],
                event.y_root - self.drag_position[1]))

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.root.attributes("-topmost", self.pinned)
        self.pin_button.configure(text="置顶" if self.pinned else "普通")

    def open_log(self):
        from tkinter import messagebox
        if not self.log_path.is_file():
            messagebox.showinfo("EVE V4", "尚未找到任务日志。", parent=self.root)
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self.log_path))
            else:
                messagebox.showinfo("EVE V4", str(self.log_path), parent=self.root)
        except OSError:
            messagebox.showerror("EVE V4", "无法打开日志。", parent=self.root)

    def refresh(self):
        if self.closed:
            return
        clock = time.monotonic()
        if self.pending is not None and self.pending.done():
            try:
                self.task = self.pending.result()
            except Exception:
                self.task = {"state": "UNKNOWN"}
            self.pending = None
        if self.pending is None and clock - self.last_query_at >= TASK_POLL_SECONDS:
            self.last_query_at = clock
            self.pending = self.pool.submit(query_windows_task)
        try:
            info = read_snapshot(self.data_root, self.task)
            headline, color = _status_style(info["status"])
            self.state_label.configure(text="●  " + headline, fg=COLORS[color])
            if info["status"] == "RUNNING":
                stage = info["phase"]
                elapsed = elapsed_clock(info["elapsed_start"])
                phase = f"当前阶段：{stage}   ·   运行 {elapsed}"
            else:
                gmail = "开" if info["research_gmail_enabled"] else "关"
                game = "开" if info["research_game_enabled"] else "关"
                phase = f"任务状态：{info['task_state']}  ·  Gmail {gmail} / 游戏 {game}"
            self.phase_label.configure(text=phase)
            last_name, last_color = _status_style(str(info["latest_result_status"]))
            self.previous_label.configure(
                text="上一轮结果：" + last_name, fg=COLORS[last_color])
            states = info["structures"]
            self.structures_label.configure(text="    ".join(
                f"{label} {'✓' if states[name]=='COMPLETE' else '—' if states[name]=='UNKNOWN' else '✕'}"
                for name, label in (("four_h","4-H"),("cj","C-J"),("o4t","O4T"))))
            evidence = _format_int(info["proofs"])
            models = _format_int(info["model_candidates"])
            market = _format_int(info["market_examined"])
            contracts = _format_int(info["contract_examined"])
            self.metrics_label.configure(
                text=f"市场审核 {market} · 合同审核 {contracts} · 候选 {models}")
            self.next_label.configure(text="下次自动：" + human_clock(info["next_run"]))
            channels = ("G" if info["research_gmail_enabled"] else "g") + (
                "E" if info["research_game_enabled"] else "e")
            self.refresh_label.configure(text="只读 · "+channels+" · 更新 " +
                                         time.strftime("%H:%M:%S"))
        except Exception:
            self.state_label.configure(text="●  监控数据读取异常", fg=COLORS["red"])
            self.phase_label.configure(text="扫描任务不受监控窗口影响")
        self.root.after(FILE_POLL_MS, self.refresh)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def _single_instance() -> bool:
    """Prevent accidental duplicate monitors on Windows without a dependency."""
    if sys.platform != "win32":
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW(None, 0, "Local\\EVE_V4_Desktop_Monitor")
    return kernel32.GetLastError() != 183


def main():
    parser = argparse.ArgumentParser(description="Read-only EVE V4 Windows desktop widget")
    parser.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    args = parser.parse_args()
    if not _single_instance():
        return
    import tkinter as tk
    root = tk.Tk()
    root.title("EVE V4 shadow monitor")
    DesktopWidget(root, args.data_root)
    root.mainloop()


if __name__ == "__main__":
    main()
