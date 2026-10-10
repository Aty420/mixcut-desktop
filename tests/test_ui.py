"""Native GUI integration checks; run with a display or on Windows CI."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mixcut.app import App
from mixcut.media import Clip, Group, Control, scan
from mixcut.project import Project
from mixcut.selftest import make_video


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "Native display required")
class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.update()
        self.errors = []
        self.patch = patch("mixcut.app.messagebox.showerror", side_effect=lambda *args: self.errors.append(args))
        self.patch.start()

    def tearDown(self):
        self.app.control.stop()
        self.wait_idle()
        self.app.destroy()
        self.patch.stop()

    def wait_idle(self, timeout=30):
        limit = time.monotonic()+timeout
        while self.app.busy and time.monotonic() < limit:
            self.app.update()
            time.sleep(.02)
        self.app.update()
        self.assertFalse(self.app.busy, "Worker did not finish")

    def fixture(self, root):
        for name in ("A", "B", "C", "D"):
            (root/name).mkdir(parents=True)
            make_video(root/name/"片段.mp4", duration=.3)

    def test_scan_reorder_and_generate_through_buttons(self):
        app = self.app
        self.assertTrue(app.start_button.instate(["disabled"]))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"素材"
            self.fixture(root)
            with patch("mixcut.app.filedialog.askdirectory", return_value=str(root)):
                app.choose_root()
            self.wait_idle()
            self.assertFalse(self.errors)
            self.assertEqual([g.name for g in app.groups], list("ABCD"))
            self.assertIn("2 段", app.rule_text.get())
            app.table.rows["1"][2][0].invoke()
            self.assertEqual([g.name for g in app.groups], list("BACD"))
            app.quantity.set("1")
            app.ratio.set("竖屏 720 × 1280")
            app.mute.set(True)
            app.start_button.invoke()
            self.wait_idle()
            self.assertFalse(self.errors)
            self.assertEqual(len(list(Path(app.output_value.get()).glob("*.mp4"))), 1)
            self.assertIn("1 条", app.history.get())
            self.assertEqual(app.progress_text.get(), "1 / 1")
            self.assertTrue(app.locked_order)
            self.assertTrue(all(b.instate(["disabled"]) for _, _, buttons in app.table.rows.values() for b in buttons))
            self.assertTrue(app.resume_button.instate(["disabled"]))

    def test_existing_pending_task_resumes_from_ui(self):
        app = self.app
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"素材"
            self.fixture(root)
            groups = scan(root, Control())
            output = Path(temp)/"已有输出"
            with Project(root) as project:
                project.plan(groups, 1, output, {"width":96,"height":128,"fps":30,"mute":False}, Control())
            app.root_value.set(str(root))
            app.scan_clicked()
            self.wait_idle()
            self.assertTrue(app.resume_button.instate(["!disabled"]))
            app.resume_button.invoke()
            self.wait_idle()
            self.assertFalse(self.errors)
            self.assertEqual(len(list(output.glob("*.mp4"))), 1)
            self.assertTrue(app.resume_button.instate(["disabled"]))

    def test_pause_stop_and_compact_scrolling(self):
        app = self.app
        app.scanned_root = Path.cwd()
        app.groups = [Group(f"{i:02d} 很长的素材组文件夹名称", [Clip("unused", str(i), 1., False)]) for i in range(12)]
        app.refresh_table()
        app.geometry(f"{app.px(1120)}x{app.px(720)}")
        app.update()
        for widget in (app.start_button, app.resume_button, app.pause_button, app.stop_button):
            self.assertTrue(widget.winfo_ismapped())
            bottom = widget.winfo_rooty()+widget.winfo_height()
            parent = widget.master
            self.assertLessEqual(bottom, parent.winfo_rooty()+parent.winfo_height()+1)
        app.toggle_log()
        app.write_log("测试日志可实时查看")
        self.assertIn("测试日志", app.log_view.get("1.0", "end"))
        app.toggle_log()
        before = app.table.canvas.yview()
        app.table.selection_set("11")
        app.update()
        self.assertGreater(app.table.canvas.yview()[0], before[0])
        def worker(control):
            while True:
                control.checkpoint()
                time.sleep(.02)
        app.launch(worker)
        app.pause_button.invoke()
        self.assertFalse(app.control.gate.is_set())
        self.assertTrue(app.start_button.instate(["disabled"]))
        app.stop_button.invoke()
        self.wait_idle()
        self.assertTrue(app.control.cancelled.is_set())
        self.assertTrue(app.pause_button.instate(["disabled"]))
        self.assertEqual(app.phase.get(), "已停止")
        self.assertFalse(self.errors)


if __name__ == "__main__":
    unittest.main()
