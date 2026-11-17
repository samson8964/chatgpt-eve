"""Simple masked Windows popup for saving the existing EVE bridge credential.

Local-only. No HTTP or GitHub calls and no password value in stdout/logs.
"""
from __future__ import annotations

from v4.local_bridge_auth import valid_bridge_key


def launch_dialog(store=None) -> bool:
    import tkinter as tk
    from tkinter import ttk, messagebox

    if store is None:
        from v4.local_bridge_auth import save_bridge_key
        store = save_bridge_key

    root = tk.Tk()
    root.title("EVE V4 - 保存 API 密钥")
    root.geometry("530x285")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))

    container = ttk.Frame(root, padding=20)
    container.pack(fill="both", expand=True)
    ttk.Label(container, text="从 Bitwarden 复制原密钥，粘贴到下方。", font=("Segoe UI", 11)).pack(anchor="w")
    ttk.Label(container, text="密钥不会通过此窗口发送到 GitHub 或 Cloudflare。").pack(anchor="w", pady=(2, 12))

    ttk.Label(container, text="API 密钥").pack(anchor="w")
    value = tk.StringVar()
    entry = ttk.Entry(container, textvariable=value, show="*", width=65)
    entry.pack(fill="x", pady=(3, 9))

    ttk.Label(container, text="再次粘贴以确认").pack(anchor="w")
    confirmation = tk.StringVar()
    check = ttk.Entry(container, textvariable=confirmation, show="*", width=65)
    check.pack(fill="x", pady=(3, 9))

    length = tk.StringVar(value="字符数：0（要求 32–256 位英文字母、数字或可打印 ASCII 字符）")
    ttk.Label(container, textvariable=length, foreground="#555555").pack(anchor="w")
    result = {"saved": False}

    def update_length(*unused):
        length.set(f"字符数：{len(value.get())}；格式：{'符合要求' if valid_bridge_key(value.get()) else '不符合要求'}")

    value.trace_add("write", update_length)

    buttons = ttk.Frame(container)
    buttons.pack(fill="x", pady=(14, 0))

    def save():
        first, second = value.get(), confirmation.get()
        if first != second:
            messagebox.showwarning("两次输入不一致", "请重新核对粘贴的密钥。", parent=root)
            return
        if not valid_bridge_key(first):
            messagebox.showwarning("密钥格式不符合要求",
                                   "请检查长度（32–256 位）、首尾空格、换行或不可打印字符。\n"
                                   "当前凭据未被覆盖。", parent=root)
            return
        try:
            store(first)
        except Exception:
            messagebox.showerror("保存失败",
                                 "无法写入 Windows 凭据库，原有内容未确认更改。",
                                 parent=root)
            return
        result["saved"] = True
        value.set("")
        confirmation.set("")
        messagebox.showinfo("保存成功", "密钥已保存到 Windows 当前用户凭据库。", parent=root)
        root.destroy()

    ttk.Button(buttons, text="取消（不修改）", command=root.destroy).pack(side="right")
    ttk.Button(buttons, text="保存到 Windows 凭据库", command=save).pack(side="right", padx=(0, 10))
    root.bind("<Escape>", lambda event: root.destroy())
    entry.focus_set()
    root.mainloop()
    return result["saved"]
