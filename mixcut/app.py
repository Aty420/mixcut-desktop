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
from .workbench import Workbench, BG

class App(Workbench, tk.Tk):
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
        self.summary = tk.StringVar(value="2 / 3组至少1段不同；4组及以上至少2段不同")
        self.history = tk.StringVar(value="历史已完成 0 条")
        self.controls = []
        self.app_version = __version__
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self.close_requested)
        self._pump_after = self.after(100, self.pump)

    def _button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append(button)
        return button

    def write_log(self, text):
        targets = [self.log]
        if self.log_visible:
            targets.append(self.log_view)
        for target in targets:
            target.configure(state="normal")
            target.insert("end", str(text) + "\n")
            if int(target.index("end-1c").split(".")[0]) > 600:
                target.delete("1.0", "100.0")
            target.see("end")
            target.configure(state="disabled")

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
        self.phase.set("处理中")
        self.last_error = False
        self.control = Control()
        self.progress["value"] = 0
        for widget in self.controls:
            widget.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.pause_button.configure(state="normal", text="暂停")
        self.sync_controls()
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
        self.locked_order = False
        self.incomplete_count = 0
        self.refresh_table()
        self.history.set("正在读取项目记录…")

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
        self.phase.set("扫描中")
        self.operation = "scan"
        self.progress_text.set("0 / 0")

    def refresh_table(self):
        self.table.delete(*self.table.get_children())
        for i, group in enumerate(self.groups):
            durations = [c.duration for c in group.clips]
            self.table.insert("", "end", iid=str(i), values=(f"{i+1:02d}", group.name, len(group.clips),
                              f"{min(durations):.1f} – {max(durations):.1f} 秒"))
        if self.groups:
            d = minimum_distance(len(self.groups))
            total = capacity([len(g.clips) for g in self.groups], d)
            self.rule_text.set(f"任意两条成片至少 {d} 段不同")
            self.summary.set(f"{len(self.groups)} 个分组 · {sum(len(g.clips) for g in self.groups)} 条素材 · 从零开始理论最多 {total:,} 条")
            self.capacity_hint.set(f"从零开始最多 {total:,} 条")
        else:
            self.rule_text.set("组合不重复，差异规则自动匹配")
            self.summary.set("2 / 3组至少1段不同；4组及以上至少2段不同")
            self.capacity_hint.set("扫描后计算可生成数量")
        self.refresh_flow()
        self.sync_controls()

    def move(self, direction):
        if self.busy:
            return
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
                try:
                    good, failed = render_pending(project, groups, control, self.notify)
                finally:
                    self.events.put(("counts", project.counts()))
                self.events.put(("message", f"本次完成 {good} 条，失败 {failed} 条。"))
        self.task_total = count
        self.progress_text.set(f"0 / {count:,}")
        self.launch(worker)
        self.phase.set("生成中")
        self.operation = "generate"

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
                try:
                    good, failed = render_pending(project, groups, control, self.notify)
                finally:
                    self.events.put(("counts", project.counts()))
                self.events.put(("message", f"续跑完成 {good} 条，失败 {failed} 条。"))
        self.task_total = self.incomplete_count
        self.progress_text.set(f"0 / {self.task_total:,}")
        self.launch(worker)
        self.phase.set("续跑中")
        self.operation = "resume"

    def pause_clicked(self):
        if self.control.gate.is_set():
            self.control.gate.clear()
            self.phase.set("等待暂停")
            self.pause_button.configure(text="继续")
            self.status.set("已请求暂停，将在当前处理步骤结束后停下。")
        else:
            self.control.gate.set()
            self.phase.set("处理中")
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
        self.incomplete_count = incomplete
        self.history.set(f"历史已完成 {done:,} 条" + (f" · 待处理 {incomplete:,} 条" if incomplete else ""))
        self.sync_controls()

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
                    self.refresh_flow()
                    self.sync_controls()
                elif kind == "counts":
                    self.show_counts(event[1])
                elif kind in ("message", "log", "error"):
                    self.status.set(event[1][:230])
                    self.write_log(event[1])
                    if kind == "error":
                        self.last_error = True
                    if kind == "error" and not self.closing:
                        messagebox.showerror("未能完成", event[1])
                elif kind == "progress":
                    _, done, total, good, failed = event
                    self.progress["value"] = done / total * 100 if total else 0
                    self.progress_text.set(f"{done:,} / {total:,}")
                    self.status.set(f"处理进度 {done}/{total}  ·  成功 {good}  ·  失败 {failed}")
                elif kind == "idle":
                    self.busy = False
                    for widget in self.controls:
                        widget.configure(state="readonly" if isinstance(widget, ttk.Combobox) else "normal")
                    self.pause_button.configure(state="disabled", text="暂停")
                    self.stop_button.configure(state="disabled")
                    if self.last_error:
                        self.phase.set("处理失败")
                    elif self.control.cancelled.is_set():
                        self.phase.set("已停止")
                    elif getattr(self, "operation", "scan") != "scan":
                        self.phase.set("已结束")
                    else:
                        self.phase.set("等待开始" if self.groups else "等待素材")
                    self.sync_controls()
                    if self.closing:
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self._pump_after = self.after(100, self.pump)

    def destroy(self):
        if getattr(self, "_pump_after", None):
            self.after_cancel(self._pump_after)
            self._pump_after = None
        super().destroy()

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
