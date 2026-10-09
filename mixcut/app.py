from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .combinations import capacity, minimum_distance
from .engine import render_pending
from .media import Cancelled, Control, scan
from .project import Project, ProjectLock

BG = "#F3F5F9"
INK = "#14243A"
ACCENT = "#246BFD"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"MixCut 素材组合工作台  ·  {__version__}")
        self.geometry("1050x820")
        self.minsize(880, 730)
        self.configure(bg=BG)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.events = queue.Queue()
        self.control = Control()
        self.busy = False
        self.closing = False
        self.groups = []
        self.scanned_root = None
        self.locked_order = False
        self.root_value = tk.StringVar()
        self.output_value = tk.StringVar()
        self.quantity = tk.StringVar(value="10")
        self.ratio = tk.StringVar(value="竖屏 1080 × 1920")
        self.mute = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="选择素材主文件夹，扫描后开始生成。")
        self.summary = tk.StringVar(value="2 / 3组：至少1段不同     ·     4组及以上：至少2段不同")
        self.history = tk.StringVar(value="所有历史成片共同参与差异检查")
        self.controls = []
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self.close_requested)
        self.after(100, self.pump)

    def _button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append(button)
        return button

    def _layout(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("TButton", padding=(13, 8), font=("Microsoft YaHei UI", 10))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#1857D8"), ("disabled", "#A9B8CD")])
        style.configure("Treeview", rowheight=34, font=("Microsoft YaHei UI", 10), background="white")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=7)
        style.configure("TProgressbar", background=ACCENT, troughcolor="#E3E9F2")
        main = ttk.Frame(self, padding=24)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="MixCut", font=("Segoe UI", 26, "bold")).pack(anchor="w")
        ttk.Label(main, text="固定顺序 · 批量拼接 · 全局组合去重", foreground="#66758B").pack(anchor="w", pady=(0, 18))
        paths = ttk.Frame(main)
        paths.pack(fill="x")
        paths.columnconfigure(1, weight=1)
        for row, (label, value, picker) in enumerate([
            ("素材主文件夹", self.root_value, self.choose_root),
            ("成片输出位置", self.output_value, self.choose_output),
        ]):
            ttk.Label(paths, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
            ttk.Entry(paths, textvariable=value, state="readonly").grid(row=row, column=1, sticky="ew", padx=(0, 10), ipady=6)
            self._button(paths, "选择文件夹", picker).grid(row=row, column=2, pady=5)
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(20, 8))
        ttk.Label(top, text="01  素材结构", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        self._button(top, "扫描 / 刷新素材", self.scan_clicked).pack(side="right")
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="x")
        self.table = ttk.Treeview(table_frame, columns=("position", "folder", "count", "duration"), show="headings", height=5)
        for key, label, width in [("position", "顺序", 60), ("folder", "子文件夹", 310),
                                  ("count", "有效素材", 120), ("duration", "片段时长范围", 180)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="center" if key != "folder" else "w")
        self.table.pack(side="left", fill="x", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="left", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        order = ttk.Frame(table_frame, padding=(10, 0, 0, 0))
        order.pack(side="right", fill="y")
        self._button(order, "上移 ↑", lambda: self.move(-1)).pack(pady=3)
        self._button(order, "下移 ↓", lambda: self.move(1)).pack(pady=3)
        ttk.Label(main, textvariable=self.summary, foreground=ACCENT).pack(anchor="w", pady=(9, 3))
        ttk.Label(main, textvariable=self.history, foreground="#66758B").pack(anchor="w")
        ttk.Label(main, text="02  生成设置", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(18, 10))
        settings = ttk.Frame(main)
        settings.pack(fill="x")
        ttk.Label(settings, text="本次新增").pack(side="left")
        spin = ttk.Spinbox(settings, from_=1, to=100000, textvariable=self.quantity, width=9)
        spin.pack(side="left", padx=(9, 5), ipady=5)
        self.controls.append(spin)
        ttk.Label(settings, text="条").pack(side="left", padx=(0, 28))
        combo = ttk.Combobox(settings, textvariable=self.ratio, state="readonly", width=23,
                             values=["竖屏 1080 × 1920", "竖屏 720 × 1280", "横屏 1920 × 1080", "方形 1080 × 1080"])
        combo.pack(side="left", ipady=5)
        self.controls.append(combo)
        mute = ttk.Checkbutton(settings, text="静音输出", variable=self.mute)
        mute.pack(side="left", padx=20)
        self.controls.append(mute)
        ttk.Label(main, text="默认：完整片段 / 硬切 / 保留原声 / 等比加边 / 30帧。暂停会在当前处理步骤结束后生效。",
                  foreground="#66758B", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(9, 14))
        actions = ttk.Frame(main)
        actions.pack(fill="x")
        self._button(actions, "新增并开始生成", self.generate_clicked, style="Accent.TButton").pack(side="left")
        self._button(actions, "继续未完成任务", self.resume_clicked).pack(side="left", padx=8)
        self.pause_button = ttk.Button(actions, text="暂停", command=self.pause_clicked, state="disabled")
        self.pause_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="停止", command=lambda: self.control.stop(), state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self._button(actions, "打开输出目录", self.open_output).pack(side="right")
        self.progress = ttk.Progressbar(main, maximum=100)
        self.progress.pack(fill="x", pady=(18, 8))
        ttk.Label(main, textvariable=self.status, wraplength=930).pack(anchor="w")
        self.log = tk.Text(main, height=6, relief="flat", background="#EAF0F7", foreground="#40516B",
                           font=("Microsoft YaHei UI", 9), padx=10, pady=8, state="disabled")
        self.log.pack(fill="both", expand=True, pady=(10, 0))

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", str(text) + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 600:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def choose_root(self):
        directory = filedialog.askdirectory(title="选择包含 A、B、C 等素材组的主文件夹")
        if directory:
            self.root_value.set(directory)
            self.output_value.set(str(Path(directory).parent / f"{Path(directory).name}_成片"))
            self.groups = []
            self.scanned_root = None
            self.table.delete(*self.table.get_children())
            self.scan_clicked()

    def choose_output(self):
        directory = filedialog.askdirectory(title="选择素材主文件夹之外的输出目录")
        if directory:
            self.output_value.set(directory)

    def launch(self, worker):
        if self.busy:
            return
        self.busy = True
        self.control = Control()
        self.progress["value"] = 0
        for widget in self.controls:
            widget.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.pause_button.configure(state="normal", text="暂停")
        self.status.set("正在处理…")

        def wrapped():
            try:
                worker(self.control)
            except Cancelled:
                self.events.put(("message", "已停止；已完成成片和待处理组合均已保留。"))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("idle",))
        threading.Thread(target=wrapped, daemon=False).start()

    def notify(self, event):
        self.events.put(event if isinstance(event, tuple) else ("log", event))

    def scan_clicked(self):
        root = Path(self.root_value.get())
        if not self.root_value.get() or not root.is_dir():
            messagebox.showinfo("选择素材", "请先选择素材主文件夹。")
            return
        self.groups = []
        self.scanned_root = None

        def worker(control):
            with ProjectLock(root), Project(root) as project:
                groups = scan(root, control, self.notify)
                order = project.get_order()
                if order is not None:
                    if set(order) != {g.name for g in groups}:
                        raise ValueError("素材组名称或数量已改变。请恢复原有组名；新结构请放入新的主文件夹。")
                    groups.sort(key=lambda g: order.index(g.name))
                self.events.put(("scanned", root.resolve(), groups, order is not None, project.counts()))
        self.launch(worker)

    def refresh_table(self):
        self.table.delete(*self.table.get_children())
        for i, group in enumerate(self.groups):
            durations = [c.duration for c in group.clips]
            self.table.insert("", "end", iid=str(i), values=(f"{i+1:02d}", group.name, len(group.clips),
                              f"{min(durations):.1f}～{max(durations):.1f} 秒"))
        if self.groups:
            d = minimum_distance(len(self.groups))
            total = capacity([len(g.clips) for g in self.groups], d)
            self.summary.set(f"{' → '.join(g.name for g in self.groups)}    |    任意两条至少 {d} 段不同    |    从零开始理论上限 {total:,} 条")

    def move(self, direction):
        if self.locked_order:
            messagebox.showinfo("顺序已锁定", "已有任务记录，保持原顺序才能检查全部历史成片。新结构请使用新的素材主文件夹。")
            return
        selected = self.table.selection()
        if not selected:
            return
        index = int(selected[0])
        target = index + direction
        if 0 <= target < len(self.groups):
            self.groups[index], self.groups[target] = self.groups[target], self.groups[index]
            self.refresh_table()
            self.table.selection_set(str(target))

    def ready(self):
        if not self.groups or self.scanned_root != Path(self.root_value.get()).resolve():
            messagebox.showinfo("需要扫描", "请先扫描素材。")
            return False
        return True

    def generate_clicked(self):
        if not self.ready():
            return
        try:
            count = int(self.quantity.get())
            if not 1 <= count <= 100000:
                raise ValueError()
        except ValueError:
            messagebox.showerror("数量错误", "请输入1～100000之间的整数。")
            return
        if not self.output_value.get():
            messagebox.showinfo("选择输出", "请先选择成片输出文件夹。")
            return
        dimensions = {"竖屏 1080 × 1920": (1080, 1920), "竖屏 720 × 1280": (720, 1280),
                      "横屏 1920 × 1080": (1920, 1080), "方形 1080 × 1080": (1080, 1080)}
        w, h = dimensions[self.ratio.get()]
        settings = {"width": w, "height": h, "fps": 30, "mute": self.mute.get()}
        root, output, groups = self.scanned_root, Path(self.output_value.get()), list(self.groups)

        def worker(control):
            with ProjectLock(root), Project(root) as project:
                if project.jobs(incomplete=True):
                    raise ValueError("存在未完成或失败任务，请先点击“继续未完成任务”，再新增组合。")
                project.plan(groups, count, output, settings, control, self.notify)
                self.events.put(("locked",))
                self.notify(f"已保存 {count} 条组合计划；停止或退出后可继续。")
                good, failed = render_pending(project, groups, control, self.notify)
                self.events.put(("counts", project.counts()))
                self.events.put(("message", f"本次完成 {good} 条，失败 {failed} 条。"))
        self.launch(worker)

    def resume_clicked(self):
        if not self.ready():
            return
        root, groups = self.scanned_root, list(self.groups)

        def worker(control):
            with ProjectLock(root), Project(root) as project:
                if project.get_order() != [g.name for g in groups]:
                    raise ValueError("请先扫描并恢复项目原有素材结构。")
                if not project.jobs(incomplete=True):
                    self.events.put(("message", "没有未完成的任务，可以新增生成。"))
                    return
                good, failed = render_pending(project, groups, control, self.notify)
                self.events.put(("counts", project.counts()))
                self.events.put(("message", f"续跑完成 {good} 条，失败 {failed} 条。"))
        self.launch(worker)

    def pause_clicked(self):
        if self.control.gate.is_set():
            self.control.gate.clear()
            self.pause_button.configure(text="继续")
            self.status.set("已请求暂停，将在当前处理步骤结束后停下。")
        else:
            self.control.gate.set()
            self.pause_button.configure(text="暂停")
            self.status.set("继续处理中…")

    def open_output(self):
        path = Path(self.output_value.get())
        if not self.output_value.get() or not path.is_dir():
            messagebox.showinfo("输出目录", "输出目录尚未创建。")
            return
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])

    def show_counts(self, counts):
        done = counts.get("done", 0)
        incomplete = sum(counts.values()) - done
        self.history.set(f"历史已完成 {done:,} 条  /  待处理或失败 {incomplete:,} 条    ·    首次创建任务后锁定素材组顺序")

    def pump(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "scanned":
                    _, self.scanned_root, self.groups, self.locked_order, counts = event
                    self.refresh_table()
                    self.show_counts(counts)
                    self.status.set("素材扫描完成。设置本次新增数量，或继续未完成任务。")
                elif kind == "locked":
                    self.locked_order = True
                elif kind == "counts":
                    self.show_counts(event[1])
                elif kind in ("message", "log", "error"):
                    self.status.set(event[1][:230])
                    self.write_log(event[1])
                    if kind == "error" and not self.closing:
                        messagebox.showerror("未能完成", event[1])
                elif kind == "progress":
                    _, done, total, good, failed = event
                    self.progress["value"] = done / total * 100 if total else 0
                    self.status.set(f"处理进度 {done}/{total}  ·  成功 {good}  ·  失败 {failed}")
                elif kind == "idle":
                    self.busy = False
                    for widget in self.controls:
                        widget.configure(state="readonly" if isinstance(widget, ttk.Combobox) else "normal")
                    self.pause_button.configure(state="disabled", text="暂停")
                    self.stop_button.configure(state="disabled")
                    if self.closing:
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def close_requested(self):
        if self.busy:
            if messagebox.askyesno("停止并退出", "停止当前处理并退出？已完成成片和任务记录会保留，下次可继续。"):
                self.closing = True
                self.control.stop()
                self.status.set("正在停止视频处理并保存记录…")
        else:
            self.destroy()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().mainloop()
