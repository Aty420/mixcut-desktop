"""Small real-video smoke test, also executed against the packaged Windows EXE."""
import tempfile
from pathlib import Path

from .combinations import assert_distance, codebook
from .engine import render_pending
from .media import Control, ffmpeg_exe, probe, run, scan
from .project import Project, ProjectLock


def make_video(path: Path, color="red", audio=True, duration=0.6, size="96x64"):
    args = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=24"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    args += ["-t", str(duration), "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac"]
    args += [str(path)]
    run(args, Control())


def self_test():
    rows = list(codebook([3, 3, 3, 3], 2))
    assert len(rows) == 27
    assert_distance(rows, 2)
    with tempfile.TemporaryDirectory(prefix="MixCut-smoke-") as temp:
        parent = Path(temp)
        root, output = parent / "素材测试", parent / "输出测试"
        (root / "A").mkdir(parents=True)
        (root / "B").mkdir()
        make_video(root / "A" / "原声.mp4", "red", True)
        make_video(root / "B" / "静音.mp4", "blue", False, size="64x96")
        control = Control()
        groups = scan(root, control)
        with ProjectLock(root), Project(root) as project:
            project.plan(groups, 1, output, {"width": 96, "height": 128, "fps": 30, "mute": False}, control)
            good, failed = render_pending(project, groups, control)
            assert (good, failed) == (1, 0), project.jobs()
            path = Path(project.jobs()[0]["output"])
            duration, audio = probe(path, control)
            assert 1.1 <= duration <= 1.5, duration
            assert audio
            assert project.counts() == {"done": 1}
    return {"ok": True, "four_groups_three_clips": 27, "min_distance": 2,
            "rendered": 1, "mixed_audio_and_aspect_ratios": True}
