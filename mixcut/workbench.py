"""Light desktop workbench. Presentation only; rendering lives in engine.py."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

from .ui_icons import ICONS

BG = "#F8FAFD"
WHITE = "#FFFFFF"
INK = "#14243A"
MUTED = "#748096"
LINE = "#E2E7EF"
ACCENT = "#3263FF"
FONT_SCALE = 0.85

PALETTE = [("#E3EFFF", "#1461C5"), ("#ECE6FF", "#6A4FD7"),
           ("#E3F5E9", "#168653"), ("#FFF0E3", "#C55D20")]


def label(parent, text="", size=14, bold=False, color=INK, **kw):
    kw.setdefault("anchor", "w")
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=parent.winfo_toplevel().font(size, bold),
                    bd=0, **kw)


class GroupList(tk.Frame):
    """Scrollable, keyboard-accessible rows with an explicit selection model."""
    def __init__(self, parent, app):
        super().__init__(parent, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        self.app = app
        self.selected = None
        self.rows = {}
        self.values = {}
        self.enabled = True
        self.header = tk.Frame(self, bg="#F7F9FC", height=44)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self._columns(self.header)
        for col, text in [(0, "顺序"), (1, "素材分组"), (2, "视频数量"), (3, "时长范围")]:
            label(self.header, text, 12, color=MUTED).grid(row=0, column=col, sticky="w", padx=12, pady=12)
        tk.Frame(self, bg=LINE, height=1).pack(fill="x")
        body = tk.Frame(self, bg=WHITE)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=WHITE, highlightthickness=0, takefocus=True, height=290)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._scrollbar)
        self.inner = tk.Frame(self.canvas, bg=WHITE)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind("<Up>", lambda e: self._key(-1))
        self.canvas.bind("<Down>", lambda e: self._key(1))
        self.canvas.bind("<Alt-Up>", lambda e: self._move_selected(-1))
        self.canvas.bind("<Alt-Down>", lambda e: self._move_selected(1))
        self.canvas.bind("<FocusIn>", lambda e: self.configure(highlightbackground=ACCENT))
        self.canvas.bind("<FocusOut>", lambda e: self.configure(highlightbackground=LINE))
        self.empty = tk.Frame(self.canvas, bg=WHITE)
        label(self.empty, "添加你的素材", 17, True).pack(anchor="center")
        label(self.empty, "选择包含 A、B、C 等子文件夹的主目录", 11, color=MUTED).pack(pady=(9, 18))
        app._button(self.empty, " 选择素材文件夹", app.choose_root, image=app.icon("folder", "blue"),
                    compound="left").pack()
        self.empty.place(relx=.5, rely=.5, anchor="center")
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _columns(self, frame):
        widths = [(0, 64), (2, 102), (3, 140), (4, 88)] if self.app.compact else [(0, 118), (2, 140), (3, 175), (4, 108)]
        for col, width in widths:
            frame.columnconfigure(col, minsize=self.app.px(width))
        frame.columnconfigure(1, weight=1, minsize=self.app.px(140))

    def _scrollbar(self, first, last):
        self.scroll.set(first, last)
        if float(first) > 0 or float(last) < 1:
            self.scroll.pack(side="right", fill="y")
        else:
            self.scroll.pack_forget()

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _key(self, delta):
        if self.values:
            index = int(self.selected or 0)
            self.selection_set(str(max(0, min(len(self.values)-1, index+delta))))
        return "break"

    def _move_selected(self, delta):
        if self.enabled:
            self.app.move(delta)
        return "break"

    def selection(self):
        return (self.selected,) if self.selected in self.values else ()

    def selection_set(self, iid):
        self.selected = str(iid)
        for key, (row, widgets, _) in self.rows.items():
            color = "#EEF1FF" if key == self.selected else WHITE
            row.configure(bg=color)
            for widget in widgets:
                widget.configure(bg=color)
        if self.selected in self.rows:
            row = self.rows[self.selected][0]
            self.update_idletasks()
            top = self.canvas.canvasy(0)
            bottom = top+self.canvas.winfo_height()
            if row.winfo_y() < top or row.winfo_y()+row.winfo_height() > bottom:
                height = max(1, self.inner.winfo_height())
                self.canvas.yview_moveto(row.winfo_y()/height)

    def get_children(self):
        return tuple(self.values)

    def delete(self, *items):
        for iid in items:
            self.rows.pop(iid)[0].destroy()
            self.values.pop(iid)
        self.selected = None
        if not self.values:
            self.empty.place(relx=.5, rely=.5, anchor="center")

    def insert(self, parent, where, iid, values):
        self.empty.place_forget()
        self.values[iid] = values
        row = tk.Frame(self.inner, bg=WHITE, height=self.app.px(72))
        row.pack(fill="x")
        row.pack_propagate(False)
        # A fixed-height inner frame allows the name column to shrink safely.
        content = tk.Frame(row, bg=WHITE)
        content.pack(fill="both", expand=True)
        self._columns(content)
        content.rowconfigure(0, weight=1)
        widgets = [content]
        num = label(content, values[0], 14)
        num.grid(row=0, column=0, padx=12, sticky="w")
        name = tk.Frame(content, bg=WHITE)
        name.grid(row=0, column=1, sticky="ew", padx=(8, 4))
        folder = label(name, image=self.app.icon("folder", size=28))
        folder.pack(side="left", padx=(0, 10))
        bg, fg = PALETTE[int(iid) % len(PALETTE)]
        badge = label(name, self.app.group_letter(int(iid)), 15, True, fg, padx=10, pady=3)
        badge.configure(bg=bg)
        badge.pack(side="left", padx=(0, 10))
        title = label(name, values[1], 14)
        title.pack(side="left", fill="x", expand=True)
        count = label(content, f"{values[2]} 条", 14)
        count.grid(row=0, column=2, padx=12, sticky="w")
        duration = label(content, values[3], 13)
        duration.grid(row=0, column=3, padx=8, sticky="w")
        actions = tk.Frame(content, bg=WHITE)
        actions.grid(row=0, column=4, sticky="e", padx=(0, 9))
        buttons = []
        for step, icon in [(-1, "chevron-up"), (1, "chevron-down")]:
            button = ttk.Button(actions, image=self.app.button_icon(icon, size=18), style="Icon.TButton",
                                command=lambda i=iid, d=step: self._move_row(i, d), takefocus=True)
            button.pack(side="left", padx=2)
            buttons.append(button)
        widgets += [num, name, folder, title, count, duration, actions]
        for widget in [row, *widgets, badge]:
            widget.bind("<Button-1>", lambda e, i=iid: (self.canvas.focus_set(), self.selection_set(i)))
            widget.bind("<MouseWheel>", self._wheel)
            widget.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        tk.Frame(row, height=1, bg=LINE).pack(fill="x", side="bottom")
        self.rows[iid] = (row, widgets, buttons)

    def _move_row(self, iid, delta):
        if self.enabled:
            self.selection_set(iid)
            self.app.move(delta)

    def set_enabled(self, enabled):
        self.enabled = enabled
        for iid, (_, _, buttons) in self.rows.items():
            for index, button in enumerate(buttons):
                boundary = int(iid) == (0 if index == 0 else len(self.rows)-1)
                button.configure(state="normal" if enabled and not boundary and not self.app.locked_order else "disabled")


class Workbench:
    """Mixin exposing the existing controller's widgets and UI state."""
    def px(self, value):
        return round(value*self.ui_scale)

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            actual = max(9, round(size * FONT_SCALE * (.87 if self.compact else 1)))
            self._fonts[key] = tkfont.Font(self, family=self.ui_font, size=actual,
                                           weight="bold" if bold else "normal")
        return self._fonts[key]

    def responsive(self, event):
        if event.widget != self:
            return
        compact = event.height < self.px(900) or event.width < self.px(1280)
        if compact == self.compact:
            return
        self.compact = compact
        for (size, _), font in self._fonts.items():
            font.configure(size=max(9, round(size * FONT_SCALE * (.87 if compact else 1))))
        style = ttk.Style(self)
        for name in ("TButton", "Segment.TRadiobutton"):
            style.configure(name, font=(self.ui_font, 10 if compact else 11))
        style.configure("TButton", padding=(12, 6 if compact else 9))
        style.configure("Accent.TButton", font=(self.ui_font, 12 if compact else 17, "bold"),
                        padding=(16, 9 if compact else 12))
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(name, padding=(8, 6 if compact else 9))
        self.export_panel.grid_configure(pady=self.px(10 if compact else 22))
        self.material_panel.grid_configure(pady=self.px(10 if compact else 22))
        self.start_button.grid_configure(pady=(10 if compact else 20, 8 if compact else 12))
        self.task_panel.configure(pady=10 if compact else 16)
        self.main_frame.pack_configure(pady=(self.px(10 if compact else 18), 0))
        self.header_frame.grid_configure(pady=(0, self.px(12 if compact else 20)))
        self.flow.configure(height=self.px(50 if compact else 65))
        for widget in self.export_panel.grid_slaves():
            row = int(widget.grid_info()["row"])
            if row == 0:
                widget.grid_configure(pady=(0, 12 if compact else 24))
            elif row == 2:
                widget.grid_configure(pady=(4 if compact else 5, 8 if compact else 25))
            elif row in (3, 4):
                widget.grid_configure(pady=(0, 8 if compact else 26))
            elif row == 6:
                widget.grid_configure(pady=(6 if compact else 20, 0))
        self.resume_button.grid_configure(pady=(0, 0 if compact else 35))
        self.table._columns(self.table.header)
        for _, widgets, _ in self.table.rows.values():
            self.table._columns(widgets[0])

    def group_letter(self, index):
        first = self.groups[index].name[:1].upper() if index < len(self.groups) else ""
        return first if first.isascii() and first.isalpha() else str(index+1)

    def icon(self, name, color="ink", size=22):
        key = (name, color, size)
        if key not in self._icons:
            self._icons[key] = tk.PhotoImage(master=self, data=ICONS[f"{name}:{color}:{size}"])
        return self._icons[key]

    def button_icon(self, name, color="ink", size=22):
        return (self.icon(name, color, size), "disabled", self.icon(name, "disabled", size))

    def _layout(self):
        self._icons = {}
        self._fonts = {}
        self.compact = False
        native_scale = float(self.tk.call("tk", "scaling"))/(96/72)
        # Keep the initial window usable on laptop screens and at Windows 150% DPI.
        self.ui_scale = max(.75, min(native_scale, (self.winfo_screenwidth()-40)/1120,
                                      (self.winfo_screenheight()-90)/720))
        self.tk.call("tk", "scaling", self.ui_scale*(96/72))
        families = tkfont.families(self)
        self.ui_font = next((f for f in ("Microsoft YaHei UI", "Noto Sans CJK SC", "Microsoft YaHei", "Segoe UI") if f in families), "TkDefaultFont")
        width = min(self.px(1440), self.winfo_screenwidth()-40)
        height = min(self.px(960), self.winfo_screenheight()-90)
        self.geometry(f"{width}x{height}")
        self.minsize(self.px(1120), self.px(720))
        self.configure(bg=BG)
        self.option_add("*Font", (self.ui_font, 11))
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=(self.ui_font, 11), foreground=INK, background=WHITE,
                        bordercolor=LINE, lightcolor=WHITE, darkcolor=WHITE, padding=(12, 9), relief="solid", borderwidth=1)
        style.map("TButton", background=[("disabled", "#F1F3F7"), ("pressed", "#E3E9FC"), ("active", "#F1F5FF")],
                  foreground=[("disabled", "#A2AABB")], bordercolor=[("focus", ACCENT)])
        style.configure("Footer.TButton", font=(self.ui_font, 9), padding=(8, 2), background=BG)
        style.configure("Icon.TButton", padding=(5, 7), width=0)
        style.configure("Accent.TButton", font=(self.ui_font, 17, "bold"), padding=(16, 12), background=ACCENT,
                        foreground=WHITE, bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT)
        style.map("Accent.TButton", background=[("disabled", "#DDE5FA"), ("pressed", "#2148D1"), ("active", "#2855E7")],
                  foreground=[("disabled", "#8396BA")], bordercolor=[("focus", "#14243A")])
        style.configure("Segment.TRadiobutton", indicatoron=False, padding=(10, 9), font=(self.ui_font, 11),
                        background=WHITE, foreground=INK, bordercolor=LINE, relief="solid", anchor="center")
        style.layout("Segment.TRadiobutton", [("Radiobutton.border", {"sticky": "nswe", "children": [
            ("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})]})])
        style.map("Segment.TRadiobutton", background=[("disabled", "#F1F3F7"), ("selected", ACCENT), ("active", "#F0F4FF")],
                  foreground=[("disabled", "#A2AABB"), ("selected", WHITE)], bordercolor=[("focus", INK)])
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(name, padding=(10, 9), fieldbackground=WHITE, bordercolor=LINE, lightcolor=WHITE,
                            darkcolor=WHITE, foreground=INK, arrowsize=16)
            style.map(name, fieldbackground=[("readonly", WHITE), ("disabled", "#F5F6F9")], bordercolor=[("focus", ACCENT)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#E9EDF4", borderwidth=0,
                        bordercolor="#E9EDF4", lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
        style.configure("Vertical.TScrollbar", background="#DCE2ED", troughcolor=WHITE, borderwidth=0, arrowsize=12)
        self.capacity_hint = tk.StringVar(value="扫描后计算可生成数量")
        self.rule_text = tk.StringVar(value="组合不重复，差异规则自动匹配")
        self.phase = tk.StringVar(value="等待素材")
        self.progress_text = tk.StringVar(value="0 / 0")
        self.incomplete_count = 0
        self.task_total = 0
        self.title(f"MixCut  ·  批量混剪  ·  {self.app_version}")
        main = tk.Frame(self, bg=BG)
        self.main_frame = main
        main.pack(fill="both", expand=True, padx=self.px(20), pady=(self.px(18), 0))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        header = tk.Frame(main, bg=BG)
        self.header_frame = header
        header.grid(row=0, column=0, sticky="ew", pady=(0, self.px(20)))
        label(header, "批量混剪", 34, True).pack(side="left")
        label(header, "按固定结构，生成不同组合", 15, color=MUTED).pack(side="left", padx=24, pady=(12, 0))
        panel = tk.Frame(main, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=2, uniform="columns")
        panel.columnconfigure(2, weight=1, uniform="columns", minsize=self.px(365))
        panel.rowconfigure(0, weight=1)
        left = tk.Frame(panel, bg=WHITE)
        self.material_panel = left
        left.grid(row=0, column=0, sticky="nsew", padx=self.px(24), pady=self.px(22))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        label(left, "素材结构", 21, True).grid(row=0, column=0, sticky="w", pady=(0, 15))
        paths = tk.Frame(left, bg=WHITE)
        paths.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        paths.columnconfigure(1, weight=1)
        label(paths, image=self.icon("folder", size=28)).grid(row=0, column=0, padx=(0, 8))
        path = ttk.Entry(paths, textvariable=self.root_value, state="readonly", width=12)
        path.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self._button(paths, "更换目录", self.choose_root).grid(row=0, column=2, padx=(0, 8))
        self._button(paths, " 重新扫描", self.scan_clicked, image=self.icon("refresh", size=18), compound="left").grid(row=0, column=3)
        self.table = GroupList(left, self)
        self.table.grid(row=2, column=0, sticky="nsew")
        self.flow = tk.Frame(left, bg=WHITE, height=self.px(65))
        self.flow.grid(row=3, column=0, sticky="ew", pady=(12, 10))
        self.flow.pack_propagate(False)
        info = tk.Frame(left, bg="#EDF5FF", padx=15, pady=13)
        info.grid(row=4, column=0, sticky="ew")
        label(info, image=self.icon("info-circle", "blue")).pack(side="left", anchor="n", padx=(0, 10), pady=3)
        details = tk.Frame(info, bg="#EDF5FF")
        details.pack(side="left", fill="x", expand=True)
        label(details, textvariable=self.rule_text, size=13, bold=True, color="#1859DA").pack(anchor="w")
        summary_label = label(details, textvariable=self.summary, size=11, color=MUTED, justify="left")
        summary_label.pack(anchor="w", fill="x", pady=(5, 0))
        details.bind("<Configure>", lambda e: summary_label.configure(wraplength=e.width))
        tk.Frame(panel, bg=LINE, width=1).grid(row=0, column=1, sticky="ns", pady=10)
        right = tk.Frame(panel, bg=WHITE)
        self.export_panel = right
        right.grid(row=0, column=2, sticky="nsew", padx=self.px(24), pady=self.px(22))
        right.columnconfigure(1, weight=1)
        right.rowconfigure(9, weight=1)
        label(right, "导出设置", 21, True).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 24))
        label(right, "本次生成").grid(row=1, column=0, sticky="w", padx=(0, 18))
        amount = tk.Frame(right, bg=WHITE)
        amount.grid(row=1, column=1, sticky="ew")
        spin = ttk.Spinbox(amount, from_=1, to=100000, textvariable=self.quantity, width=7, font=self.font(13))
        spin.pack(side="left")
        self.controls.append(spin)
        label(amount, "条").pack(side="left", padx=12)
        label(right, textvariable=self.capacity_hint, size=11, color=MUTED).grid(row=2, column=1, sticky="w", pady=(5, 25))
        label(right, "画面尺寸").grid(row=3, column=0, sticky="w")
        combo = ttk.Combobox(right, textvariable=self.ratio, state="readonly", width=16,
                             font=self.font(13),
                             values=["竖屏 1080 × 1920", "竖屏 720 × 1280", "横屏 1920 × 1080", "方形 1080 × 1080"])
        combo.grid(row=3, column=1, sticky="ew", pady=(0, 26))
        self.controls.append(combo)
        label(right, "声音").grid(row=4, column=0, sticky="w")
        sound = tk.Frame(right, bg=WHITE)
        sound.grid(row=4, column=1, sticky="ew", pady=(0, 26))
        sound.columnconfigure((0, 1), weight=1, uniform="sound")
        for index, (text, value) in enumerate([("保留原声", False), ("静音", True)]):
            radio = ttk.Radiobutton(sound, text=text, variable=self.mute, value=value, style="Segment.TRadiobutton")
            radio.grid(row=0, column=index, sticky="ew")
            self.controls.append(radio)
        label(right, "输出位置").grid(row=5, column=0, sticky="w")
        output = tk.Frame(right, bg=WHITE)
        output.grid(row=5, column=1, sticky="ew")
        output.columnconfigure(0, weight=1)
        ttk.Entry(output, textvariable=self.output_value, state="readonly", width=12).grid(row=0, column=0, sticky="ew")
        self._button(output, "", self.choose_output, image=self.icon("folder"), style="Icon.TButton").grid(row=0, column=1, padx=(4, 0))
        label(right, "完整片段 · 硬切拼接 · 30 帧", 10, color=MUTED).grid(row=6, column=0, columnspan=2, sticky="e", pady=(20, 0))
        self.start_button = self._button(right, " 开始生成", self.generate_clicked, style="Accent.TButton",
                                        image=self.button_icon("player-play", "white"), compound="left")
        self.start_button.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(20, 12))
        self.resume_button = self._button(right, " 继续未完成任务", self.resume_clicked,
                                         image=self.icon("player-play", "disabled"), compound="left")
        self.resume_button.grid(row=11, column=0, columnspan=2, sticky="ew", ipady=3, pady=(0, 35))
        tasks = tk.Frame(main, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=20, pady=16)
        tasks.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        tasks.columnconfigure(2, weight=1)
        self.task_panel = tasks
        label(tasks, "生成任务", 17, True).grid(row=0, column=0, sticky="w", padx=(0, 22))
        label(tasks, textvariable=self.phase, size=11, color=MUTED, width=10).grid(row=0, column=1, sticky="w")
        self.progress = ttk.Progressbar(tasks, maximum=100)
        self.progress.grid(row=0, column=2, sticky="ew", padx=16, ipady=0)
        label(tasks, textvariable=self.progress_text, size=11, color=MUTED, width=12, anchor="center").grid(row=0, column=3)
        self.pause_button = ttk.Button(tasks, text=" 暂停", image=self.button_icon("player-pause", size=18),
                                       compound="left", command=self.pause_clicked, state="disabled")
        self.pause_button.grid(row=0, column=4, padx=(6, 8))
        self.stop_button = ttk.Button(tasks, text=" 停止", image=self.button_icon("player-stop", size=18),
                                      compound="left", command=self.stop_clicked, state="disabled")
        self.stop_button.grid(row=0, column=5)
        status_row = tk.Frame(tasks, bg=WHITE)
        status_row.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(12, 0))
        status_row.columnconfigure(1, weight=1)
        label(status_row, image=self.icon("file-text", size=22)).grid(row=0, column=0, padx=(0, 10))
        status_label = label(status_row, textvariable=self.status, size=11, justify="left")
        status_label.grid(row=0, column=1, sticky="ew")
        status_label.bind("<Configure>", lambda e: status_label.configure(wraplength=max(100, e.width)))
        self._button(status_row, " 打开输出目录", self.open_output, image=self.icon("folder", "blue", 18), compound="left").grid(row=0, column=2, padx=(12, 0))
        self.log = tk.Text(tasks, height=2, relief="flat", bg="#F8FAFD", fg=MUTED, font=(self.ui_font, 9),
                           padx=10, pady=6, state="disabled", wrap="word")
        self.log_visible = False
        self.log_toggle = ttk.Button(status_row, text="查看日志", command=self.toggle_log)
        self.log_toggle.grid(row=0, column=3, padx=(8, 0))
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=3, column=0, sticky="ew", pady=10)
        label(footer, "本地运行", 9, color="#218555", image=self.icon("circle-check", "blue", 18), compound="left", padx=4).pack(side="left")
        ttk.Button(footer, text="卸载软件", style="Footer.TButton", command=self.uninstall_clicked).pack(side="right", padx=(18, 0))
        label(footer, textvariable=self.history, size=9, color=MUTED).pack(side="right")
        self.quantity.trace_add("write", lambda *_: self.update_quantity())
        self.update_quantity()
        self.refresh_flow()
        self.sync_controls()
        self.bind("<Configure>", self.responsive, add=True)

    def toggle_log(self):
        if self.log_visible:
            self.log_window.destroy()
            self.log_visible = False
            self.log_toggle.configure(text="查看日志")
            return
        window = self.log_window = tk.Toplevel(self)
        window.title("MixCut · 运行日志")
        window.geometry(f"{min(self.px(900), self.winfo_screenwidth()-60)}x{min(self.px(360), self.winfo_screenheight()-120)}")
        window.configure(bg=WHITE)
        window.transient(self)
        self.log_view = tk.Text(window, relief="flat", bg=WHITE, fg=INK,
                                font=self.font(11), padx=16, pady=16, wrap="word")
        self.log_view.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(window, orient="vertical", command=self.log_view.yview)
        scroll.pack(side="right", fill="y")
        self.log_view.configure(yscrollcommand=scroll.set)
        self.log_view.insert("1.0", self.log.get("1.0", "end-1c"))
        self.log_view.configure(state="disabled")
        self.log_view.see("end")
        self.log_visible = True
        self.log_toggle.configure(text="关闭日志")
        window.protocol("WM_DELETE_WINDOW", self.toggle_log)

    def update_quantity(self):
        value = self.quantity.get()
        text = f" 开始生成 {int(value):,} 条" if len(value) <= 6 and value.isdecimal() and 0 < int(value) <= 100000 else " 开始生成"
        self.start_button.configure(text=text)

    def refresh_flow(self):
        for child in self.flow.winfo_children():
            child.destroy()
        if not self.groups:
            label(self.flow, "每组取 1 条，按文件夹顺序拼接", 11, color=MUTED).pack(side="left", padx=12)
            return
        for i in range(min(4, len(self.groups))):
            if i:
                label(self.flow, image=self.icon("arrow-right", size=18)).pack(side="left", padx=10)
            bg, fg = PALETTE[i % 4]
            badge = label(self.flow, self.group_letter(i), 14, True, fg, padx=14, pady=7)
            badge.configure(bg=bg)
            badge.pack(side="left", padx=(10 if i == 0 else 0, 0))
        suffix = f" … 共 {len(self.groups)} 组" if len(self.groups) > 4 else "每组取 1 条，按顺序拼接"
        if self.locked_order:
            suffix = "顺序已锁定 · 历史参与去重"
        label(self.flow, suffix, 12, color=MUTED).pack(side="left", padx=18)

    def sync_controls(self):
        self.table.set_enabled(not self.busy)
        ready = bool(self.groups and self.scanned_root)
        self.start_button.configure(state="normal" if ready and not self.busy else "disabled")
        can_resume = ready and self.incomplete_count and not self.busy
        self.resume_button.configure(state="normal" if can_resume else "disabled",
                                     image=self.button_icon("player-play"))

    def stop_clicked(self):
        self.control.stop()
        self.phase.set("正在停止")
        self.status.set("正在结束当前处理，任务记录会保留。")
        self.stop_button.configure(state="disabled")
        self.pause_button.configure(state="disabled")
