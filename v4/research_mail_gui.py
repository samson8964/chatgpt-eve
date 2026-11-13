"""Local Windows Gmail App Password dialog for V4 contract review email.

This is only a Tkinter front-end for v4.research_mail.configure. The password
stays in memory until it is written to Windows Credential Manager. No SMTP
request, scan run, GitHub operation, stdout secret, or password file.
"""
from __future__ import annotations

import json
from pathlib import Path

from v4.research_mail import CONFIG, configure


def saved_addresses(data_root: Path) -> tuple[str, str]:
    """Prefill only nonsecret addresses from the existing local config."""
    try:
        config = json.loads((Path(data_root) / CONFIG).read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return "", ""
        sender = str(config.get("sender") or "").strip()
        recipient = str(config.get("recipient") or "").strip()
        # Do not prefill addresses from an unexpected config format.
        if config.get("schema") != 1 or config.get("mode") != "V4_CONTRACT_RESEARCH_ONLY":
            return "", ""
        return sender, recipient
    except (OSError, ValueError, UnicodeError):
        return "", ""


def normalized_length(value: str) -> int:
    """Google shows a 16-letter application password, sometimes grouped by spaces."""
    return len("".join(str(value).split()))


def launch_dialog(data_root: Path | None = None, *, save_func=None) -> bool:
    import tkinter as tk
    from tkinter import messagebox, ttk

    data_root = Path(data_root) if data_root is not None else Path.home() / "EVE-V4-Data"
    save_func = save_func or configure
    existing_sender, existing_recipient = saved_addresses(data_root)

    root = tk.Tk()
    root.title("EVE V4 - Gmail 应用专用密码")
    root.geometry("550x360")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(450, lambda: root.attributes("-topmost", False))

    form = ttk.Frame(root, padding=18)
    form.pack(fill="both", expand=True)

    ttk.Label(form, text="EVE V4 合同审核邮件 · Gmail 设置",
              font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
    ttk.Label(form, text="只在这台电脑保存应用专用密码，不会发往 ChatGPT 或 GitHub。",
              wraplength=490).pack(anchor="w", pady=(3, 12))

    ttk.Label(form, text="Gmail 发件邮箱").pack(anchor="w")
    sender_var = tk.StringVar(value=existing_sender)
    sender_entry = ttk.Entry(form, textvariable=sender_var, width=66)
    sender_entry.pack(fill="x", pady=(3, 8))

    ttk.Label(form, text="收件邮箱（留空则发送给自己）").pack(anchor="w")
    recipient_var = tk.StringVar(value=existing_recipient or existing_sender)
    ttk.Entry(form, textvariable=recipient_var, width=66).pack(fill="x", pady=(3, 8))

    ttk.Label(form, text="Google 16 位应用专用密码（可直接 Ctrl+V 粘贴）").pack(anchor="w")
    password_var = tk.StringVar()
    password_row = ttk.Frame(form)
    password_row.pack(fill="x", pady=(3, 4))
    password_entry = ttk.Entry(password_row, textvariable=password_var,
                               show="*", width=52)
    password_entry.pack(side="left", fill="x", expand=True)
    show_var = tk.BooleanVar(value=False)

    def toggle_visible():
        password_entry.configure(show="" if show_var.get() else "*")

    ttk.Checkbutton(password_row, text="显示密码", variable=show_var,
                    command=toggle_visible).pack(side="left", padx=(9, 0))

    length_var = tk.StringVar(value="已输入 0 / 16 位（自动忽略空格与换行）")
    ttk.Label(form, textvariable=length_var, foreground="#555555").pack(anchor="w")
    password_var.trace_add("write", lambda *_: length_var.set(
        f"已输入 {normalized_length(password_var.get())} / 16 位（自动忽略空格与换行）"))

    state = {"saved": False}

    def save():
        sender = sender_var.get().strip()
        recipient = recipient_var.get().strip() or sender
        secret = password_var.get()
        if normalized_length(secret) != 16:
            messagebox.showwarning("密码长度不正确",
                "Google 应用专用密码通常为 16 位字母。请完整复制 Google 生成的密码。\n"
                "粘贴时可以包含空格，保存程序会自动忽略空格。", parent=root)
            password_entry.focus_set()
            return
        try:
            save_func(data_root, sender, recipient, secret)
        except ValueError as exc:
            codes = {
                "INVALID_GMAIL_ADDRESS": "请检查 Gmail 发件邮箱和收件邮箱。",
                "SENDER_MUST_BE_GMAIL": "发件地址必须是 Gmail 邮箱。",
                "INVALID_GMAIL_APP_PASSWORD": "密码格式不符合要求。请使用 Google 生成的 16 位应用专用密码。",
            }
            messagebox.showwarning("信息需要修改",
                codes.get(str(exc), "邮箱或密码格式不正确，请核对后重试。"), parent=root)
            return
        except Exception:
            # Do not display raw exception messages from credential providers:
            # they might include user-provided secret content.
            password_var.set("")
            messagebox.showerror("无法保存",
                "无法完成 Windows 凭据管理器保存。请确认已安装 keyring、"
                "当前 Windows 用户可使用凭据管理器，然后重试。", parent=root)
            return

        password_var.set("")
        show_var.set(False)
        state["saved"] = True
        messagebox.showinfo("保存成功",
            "Gmail 应用专用密码已保存到当前 Windows 用户的凭据管理器。\n"
            "V4 合同审核邮件配置已启用。\n"
            "保存配置本身不会立即发送邮件；新版扫描后才会生成邮件。", parent=root)
        root.destroy()

    buttons = ttk.Frame(form)
    buttons.pack(fill="x", pady=(16, 0))
    ttk.Button(buttons, text="取消", command=root.destroy).pack(side="right")
    ttk.Button(buttons, text="保存到 Windows 凭据管理器",
               command=save).pack(side="right", padx=(0, 10))

    root.bind("<Escape>", lambda _event: root.destroy())
    (password_entry if existing_sender else sender_entry).focus_set()
    root.mainloop()
    return state["saved"]


if __name__ == "__main__":
    launch_dialog()
