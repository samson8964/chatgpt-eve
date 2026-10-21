"""Small Windows V4 monitor with explicit manual full-scan action.

Read-only status monitoring plus one user-click action that requests the
ALREADY INSTALLED Task Scheduler job. Never runs a parallel scanner,
touches secrets, imports mail modules, or makes HTTP calls itself.
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
from v4.manual_scan import request_full_scan

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
        "WAITING_NEW_SCOPE": ("等待四站首次完整扫描", "amber"),
        "SKIPPED_UPSTREAM_STALE": ("上游数据尚未更新", "amber"),
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


def _station_symbol(status: str) -> str:
    if status == "COMPLETE":
        return "✓"
    if status in ("UNKNOWN", "PENDING_FIRST_RUN"):
        return "…" if status == "PENDING_FIRST_RUN" else "—"
    return "✕"


def _channel_label(status: str) -> str:
    if status in ("GAME_MAIL_SENT", "GMAIL_SENT"):
        return "已发送"
    if status in ("GAME_MAIL_ALREADY_SENT", "GMAIL_ALREADY_SENT"):
        return "已处理"
    if status == "NO_NEW_QUALIFIED_LEADS":
        return "无新机会"
    if status == "OPPORTUNITY_CHANNEL_FAILED":
        return "发送失败"
    return "未确认"


def _opportunity_text(opportunity: dict, banestar_enabled: bool) -> tuple[str, str, str]:
    """Pure text conversion; does not infer live opportunity availability."""
    status = opportunity.get("status")
    if status == "WAITING_FIRST_CYCLE":
        header = "最近捡漏：等待新扫描报告"
    elif status == "INCOMPLETE_COVERAGE":
        header = "最近捡漏：采集不完整，未确认结果"
    elif status == "COMPLETE":
        n = _format_int(opportunity.get("qualified_model_leads"))
        stamp = human_clock(opportunity.get("reported_at"))
        header = f"最近捡漏：完成 · 合格 {n} · {stamp}"
    elif status == "STALE_REPORT":
        header = ("最近捡漏：报告已过期 · " +
                  human_clock(opportunity.get("reported_at")))
    else:
        header = "最近捡漏：结果未知"
    station = opportunity.get("station") or {}
    if not banestar_enabled:
        detail = "74L2-U：未启用"
    elif status == "STALE_REPORT":
        detail = "74L2-U：仅有过期历史结果，需新一轮"
    elif status != "COMPLETE":
        detail = "74L2-U：等待四站机会扫描通过"
    elif not isinstance(station, dict):
        detail = "74L2-U：品种数据待确认"
    else:
        sell = _format_int(station.get("sell_types", 0))
        pre = _format_int(station.get("PREFILTER_PASSED", 0))
        passed = _format_int(station.get("MODEL_PASS_RESEARCH_ONLY", 0))
        detail = f"74L2-U：卖盘品种 {sell} · 初筛 {pre} · 合格 {passed}"
    if status == "COMPLETE":
        mail = ("通知：游戏 " + _channel_label(opportunity.get("game_mail")) +
                " · Gmail " + _channel_label(opportunity.get("gmail")))
    else:
        mail = "通知：等待有效扫描结果（并非零机会）"
    return header, detail, mail


class DesktopWidget:
    def __init__(self, root, data_root: Path):
        import tkinter as tk
        self.tk = tk
        self.root = root
        self.data_root = data_root
        self.log_path = data_root / "logs" / "shadow-task.log"
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v4-task-watch")
        self.manual_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v4-click-scan")
        self.pending = None
        self.manual_future = None
        self.manual_started_request_at = None
        self.manual_prior_last_run = None
        self.manual_message = "与自动扫描共用任务，避免重复运行"
        self.manual_message_color = "muted"
        self.last_query_at = 0.0
        self.task = {"state": "Unknown"}
        self.closed = False
        self.pinned = True
        self.drag_position = None

        root.overrideredirect(True)
        root.configure(bg=COLORS["line"])
        root.attributes("-topmost", True)
        root.resizable(False, False)
        w, h = 392, 424
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
        self.structures_label = self._label(shell, "4-H —    C-J —    O4T —", 9, "muted")
        self.structures_label.pack(anchor="w", padx=14, pady=(1, 1))
        self.fourth_label = self._label(shell, "74L2-U：读取配置中", 9, "muted")
        self.fourth_label.pack(anchor="w", padx=14, pady=(1, 3))
        self.metrics_label = self._label(shell, "审核记录 --  |  候选 --", 9, "muted")
        self.metrics_label.pack(anchor="w", padx=14, pady=(1, 4))
        self.next_label = self._label(shell, "下次自动：--", 9, "white")
        self.next_label.pack(anchor="w", padx=14, pady=(1, 5))

        tk.Frame(shell, height=1, bg=COLORS["line"]).pack(fill="x", padx=12, pady=(1, 5))
        self.opportunity_label = self._label(shell, "最近捡漏：读取中", 9, "white")
        self.opportunity_label.pack(anchor="w", padx=14, pady=(1, 3))
        self.opportunity_station_label = self._label(shell, "74L2-U：读取中", 9, "muted")
        self.opportunity_station_label.pack(anchor="w", padx=14, pady=(1, 3))
        self.opportunity_mail_label = self._label(shell, "通知：读取中", 9, "muted")
        self.opportunity_mail_label.pack(anchor="w", padx=14, pady=(1, 6))

        # Manual start is user-initiated only. Task Scheduler's IgnoreNew
        # setting serializes it with the normal hourly trigger.
        self.manual_button = self._button(
            shell, "立即全面扫描", self.start_full_scan, width=16, bg="panel")
        self.manual_button.pack(anchor="w", padx=14, pady=(2, 2))
        self.manual_button.configure(state="disabled")
        self.manual_label = self._label(
            shell, self.manual_message, 8, "muted")
        self.manual_label.pack(anchor="w", padx=14, pady=(1, 2))

        footer = tk.Frame(shell, bg=COLORS["panel"], height=26)
        footer.pack(side="bottom", fill="x")
        self.refresh_label = self._label(footer, "只读 · 四站/机会监控 · 3秒刷新", 8, "muted",
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

    def start_full_scan(self):
        """Tk-thread callback; launch only the already installed job.

        Never run a second V4 Python process or block Tk on PowerShell.
        A task accepted by Windows may later safely SKIP if sources are stale.
        """
        if self.closed or self.manual_future is not None:
            return
        if self.manual_started_request_at is not None:
            return  # Wait for the previous request to be observed or time out.
        if str(self.task.get("state") or "").lower() != "ready":
            self.manual_message = "计划任务未就绪，无法立即启动"
            self.manual_message_color = "amber"
            return
        self.manual_prior_last_run = self.task.get("last_run")
        self.manual_message = "正在向计划任务提交启动请求…"
        self.manual_message_color = "blue"
        self.manual_button.configure(state="disabled")
        self.manual_future = self.manual_pool.submit(request_full_scan)

    def _refresh_manual_action(self, clock):
        """Only this UI thread may touch Tk widgets or the task snapshot."""
        if self.manual_future is not None and self.manual_future.done():
            try:
                status = self.manual_future.result().get("status")
            except Exception:
                status = "TASK_START_FAILED"
            self.manual_future = None
            if status == "START_REQUESTED":
                self.manual_started_request_at = clock
                self.manual_message = "启动请求已提交，等待任务状态确认"
                self.manual_message_color = "blue"
                # Do not wait the normal polling period after a manual click.
                self.last_query_at = 0.0
            elif status == "ALREADY_RUNNING":
                self.manual_message = "自动扫描正在运行，未重复启动"
                self.manual_message_color = "amber"
            elif status == "NOT_READY":
                self.manual_message = "计划任务不在待命状态，未启动"
                self.manual_message_color = "amber"
            elif status == "UNSAFE_MULTIPLE_INSTANCES":
                self.manual_message = "任务缺少防重叠保护，拒绝启动"
                self.manual_message_color = "red"
            elif status == "TASK_ACTION_MISMATCH":
                self.manual_message = "计划任务执行程序不符，拒绝启动"
                self.manual_message_color = "red"
            elif status == "WINDOWS_REQUIRED":
                self.manual_message = "此功能仅在 Windows 上可用"
                self.manual_message_color = "amber"
            else:
                self.manual_message = "未能提交启动请求，请查看计划任务"
                self.manual_message_color = "red"

        if self.manual_started_request_at is not None:
            current_state = str(self.task.get("state") or "").lower()
            new_last_run = self.task.get("last_run")
            if current_state == "running":
                self.manual_message = "任务正在运行，已进入完整扫描流程"
                self.manual_message_color = "blue"
                self.manual_started_request_at = None
            elif (new_last_run and self.manual_prior_last_run and
                  new_last_run != self.manual_prior_last_run):
                self.manual_message = "任务已触发；请查看扫描状态及邮件结果"
                self.manual_message_color = "green"
                self.manual_started_request_at = None
            elif clock - self.manual_started_request_at > 30:
                self.manual_message = "启动请求已提交；未能确认运行，请查看日志"
                self.manual_message_color = "amber"
                self.manual_started_request_at = None

        if self.closed:
            return
        state = str(self.task.get("state") or "").lower()
        can_start = (state == "ready" and self.manual_future is None
                     and self.manual_started_request_at is None)
        self.manual_button.configure(state="normal" if can_start else "disabled")
        self.manual_label.configure(
            text=self.manual_message,fg=COLORS[self.manual_message_color])

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
                if info["status"] == "SKIPPED_UPSTREAM_STALE":
                    phase = "待上游快照发布 · 本轮不扫描、不发邮件"
                else:
                    phase = f"任务状态：{info['task_state']}  ·  Gmail {gmail} / 游戏 {game}"
            self.phase_label.configure(text=phase)
            last_name, last_color = _status_style(str(info["latest_result_status"]))
            self.previous_label.configure(
                text="上一轮结果：" + last_name, fg=COLORS[last_color])
            states = info["structures"]
            self.structures_label.configure(text="    ".join(
                f"{label} {_station_symbol(states.get(name, 'UNKNOWN'))}"
                for name, label in (("four_h", "4-H"), ("cj", "C-J"), ("o4t", "O4T"))))
            if info["banestar_enabled"]:
                fourth = states.get("banestar", "UNKNOWN")
                tail = (" · 等待首次四站扫描" if fourth == "PENDING_FIRST_RUN"
                        else " · 采集完整" if fourth == "COMPLETE"
                        else " · 采集异常/缺失")
                self.fourth_label.configure(
                    text="74L2-U " + _station_symbol(fourth) + tail,
                    fg=COLORS["green" if fourth == "COMPLETE" else "amber"])
            else:
                self.fourth_label.configure(text="74L2-U — 未启用", fg=COLORS["muted"])
            evidence = _format_int(info["proofs"])
            models = _format_int(info["model_candidates"])
            market = _format_int(info["market_examined"])
            contracts = _format_int(info["contract_examined"])
            self.metrics_label.configure(
                text=f"市场审核 {market} · 合同审核 {contracts} · 候选 {models}")
            self.next_label.configure(text="下次自动：" + human_clock(info["next_run"]))
            o_header, o_station, o_mail = _opportunity_text(
                info["opportunity"], info["banestar_enabled"])
            self.opportunity_label.configure(
                text=o_header, fg=COLORS["amber" if info["opportunity"]["status"]
                                        != "COMPLETE" else "white"])
            self.opportunity_station_label.configure(text=o_station)
            self.opportunity_mail_label.configure(text=o_mail)
            channels = ("G" if info["research_gmail_enabled"] else "g") + (
                "E" if info["research_game_enabled"] else "e")
            self.refresh_label.configure(text="状态只读 · "+channels+" · 更新 " +
                                         time.strftime("%H:%M:%S"))
        except Exception:
            self.state_label.configure(text="●  监控数据读取异常", fg=COLORS["red"])
            self.phase_label.configure(text="扫描任务不受监控窗口影响")
        self._refresh_manual_action(clock)
        self.root.after(FILE_POLL_MS, self.refresh)

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.manual_pool.shutdown(wait=False, cancel_futures=True)
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
