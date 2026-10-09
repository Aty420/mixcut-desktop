import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mixcut.engine import render_pending
from mixcut.media import Cancelled, Clip, Control, normalize, probe, run, scan, ffmpeg_exe
from mixcut.project import Project
from mixcut.selftest import make_video, self_test

SETTINGS = {"width": 96, "height": 128, "fps": 30, "mute": False}


class MediaTests(unittest.TestCase):
    def test_normalization_keeps_duration_with_and_without_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for audio in (True, False):
                source = root / f"source-{audio}.mp4"
                target = root / f"normalized-{audio}.mp4"
                make_video(source, audio=audio, duration=1.7)
                duration, has_audio = probe(source, Control())
                normalize(Clip(str(source), "fixture", duration, has_audio), target, SETTINGS, Control())
                rendered_duration, rendered_audio = probe(target, Control())
                self.assertLessEqual(abs(rendered_duration - duration), 0.07)
                self.assertTrue(rendered_audio)

    def test_real_video_smoke(self):
        self.assertTrue(self_test()["ok"])

    def test_duplicates_failures_stop_resume_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "素材 with spaces '引号"
            for group in ("A", "B"):
                (root / group).mkdir(parents=True)
            make_video(root / "A" / "a.mp4", "red", True)
            shutil.copyfile(root / "A" / "a.mp4", root / "A" / "renamed.mp4")
            make_video(root / "B" / "b.mp4", "blue", False)
            make_video(root / "B" / "c.mp4", "green", True)
            groups = scan(root, Control())
            self.assertEqual([len(g.clips) for g in groups], [1, 2])
            output = base / "输出 with spaces '引号"
            with Project(root) as project:
                project.plan(groups, 2, output, SETTINGS, Control())
                stop = Control()
                stop.stop()
                with self.assertRaises(Cancelled):
                    render_pending(project, groups, stop)
                self.assertEqual(project.counts(), {"queued": 2})
                with patch("mixcut.engine.normalize", side_effect=RuntimeError("模拟失败")):
                    self.assertEqual(render_pending(project, groups, Control()), (0, 2))
                self.assertEqual(project.counts(), {"failed": 2})
                self.assertEqual(render_pending(project, groups, Control()), (2, 0))
                before = {p.name: p.stat().st_mtime_ns for p in output.glob("*.mp4")}
                self.assertEqual(render_pending(project, groups, Control()), (0, 0))
                self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in output.glob("*.mp4")})
                self.assertTrue((output / "MixCut_组合记录.csv").exists())

    def test_bad_source_blocks_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for group in ("A", "B"):
                (root / group).mkdir()
                (root / group / "bad.mp4").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                scan(root, Control())

    def test_mutation_after_scan_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "input"
            for group in ("A", "B"):
                (root / group).mkdir(parents=True)
                make_video(root / group / "video.mp4", "red")
            groups = scan(root, Control())
            with Project(root) as project:
                project.plan(groups, 1, base / "out", SETTINGS, Control())
                (root / "A" / "video.mp4").write_bytes(b"changed")
                self.assertEqual(render_pending(project, groups, Control()), (0, 1))
                self.assertIn("扫描后素材发生改变", project.jobs()[0]["error"])

    def test_visual_order_padding_and_muted_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "input"
            for name, color, size in [("A", "red", "96x64"), ("B", "blue", "64x96")]:
                (root / name).mkdir(parents=True)
                make_video(root / name / "video.mp4", color, True, size=size)
            groups = scan(root, Control())
            with Project(root) as project:
                project.plan(groups, 1, base / "out", {**SETTINGS, "mute": True}, Control())
                self.assertEqual(render_pending(project, groups, Control()), (1, 0))
                output = project.jobs()[0]["output"]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            def pixel_at(time, x, y):
                raw = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(time),
                                      "-i", output, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     capture_output=True, check=True, creationflags=flags).stdout
                offset = (y * 96 + x) * 3
                return tuple(raw[offset:offset + 3])
            red = pixel_at(0.2, 48, 64)
            blue = pixel_at(0.9, 48, 64)
            self.assertGreater(red[0], 200)
            self.assertLess(red[2], 20)
            self.assertGreater(blue[2], 200)
            self.assertLess(blue[0], 20)
            self.assertLess(max(pixel_at(0.2, 48, 1)), 8)
            _, audio_log = run([ffmpeg_exe(), "-hide_banner", "-i", output,
                                "-af", "volumedetect", "-vn", "-f", "null", "-"], Control())
            self.assertIn("max_volume: -91.0 dB", audio_log)

    def test_recover_after_final_file_published(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "input"
            for name in ("A", "B"):
                (root / name).mkdir(parents=True)
                make_video(root / name / "video.mp4")
            groups = scan(root, Control())
            with Project(root) as project:
                project.plan(groups, 1, base / "out", SETTINGS, Control())
                self.assertEqual(render_pending(project, groups, Control()), (1, 0))
                job = project.jobs()[0]
                original_time = Path(job["output"]).stat().st_mtime_ns
                project.update(job["id"], "publishing")
                self.assertEqual(render_pending(project, groups, Control()), (1, 0))
                self.assertEqual(Path(job["output"]).stat().st_mtime_ns, original_time)


if __name__ == "__main__":
    unittest.main()
