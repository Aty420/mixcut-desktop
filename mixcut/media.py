from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".ts", ".mts"}


class Cancelled(Exception):
    pass


class Control:
    def __init__(self):
        self.cancelled = threading.Event()
        self.gate = threading.Event()
        self.gate.set()

    def checkpoint(self):
        while not self.gate.wait(0.15):
            if self.cancelled.is_set():
                raise Cancelled()
        if self.cancelled.is_set():
            raise Cancelled()

    def stop(self):
        self.cancelled.set()
        self.gate.set()


def ffmpeg_exe() -> str:
    explicit = os.environ.get("MIXCUT_FFMPEG")
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        if found:
            return found
        raise RuntimeError("找不到视频处理引擎。请使用完整发行包，或安装 requirements.txt。")


def run(command: list[str], control: Control, check: bool = True) -> tuple[int, str]:
    control.checkpoint()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    # A temporary log avoids pipe deadlocks and unbounded RAM on long videos.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, creationflags=flags)
        try:
            while True:
                try:
                    code = process.wait(timeout=0.15)
                    break
                except subprocess.TimeoutExpired:
                    if control.cancelled.is_set():
                        raise Cancelled()
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 65536))
            output = log.read().decode("utf-8", errors="replace")
            if check and code:
                raise RuntimeError(output[-4000:])
            return code, output
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


@dataclass(frozen=True)
class Clip:
    path: str
    digest: str
    duration: float
    audio: bool

    def to_dict(self):
        return asdict(self)


@dataclass
class Group:
    name: str
    clips: list[Clip]


def digest_file(path: Path, control: Control) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            control.checkpoint()
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path, control: Control) -> tuple[float, bool]:
    _, info = run([ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path)], control, check=False)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not match or not re.search(r"Stream .*Video:", info):
        raise ValueError(f"无法读取视频或时长：{path.name}")
    h, m, s = map(float, match.groups())
    duration = h * 3600 + m * 60 + s
    if duration <= 0:
        raise ValueError(f"视频时长无效：{path.name}")
    return duration, bool(re.search(r"Stream .*Audio:", info))


def natural_key(text: str):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", text)]


def scan(root: Path, control: Control, notify=lambda _: None) -> list[Group]:
    folders = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
                     key=lambda p: natural_key(p.name))
    if len(folders) < 2:
        raise ValueError("主文件夹内至少放置2个素材子文件夹。")
    groups = []
    for folder in folders:
        files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
                       key=lambda p: natural_key(p.name))
        if not files:
            raise ValueError(f"子文件夹“{folder.name}”没有视频；请移走无关文件夹或补充素材。")
        unique = {}
        for file in files:
            control.checkpoint()
            notify(f"检查 {folder.name} / {file.name}")
            digest = digest_file(file, control)
            if digest in unique:
                notify(f"跳过同组重复文件：{file.name}")
                continue
            duration, audio = probe(file, control)
            unique[digest] = Clip(str(file.resolve()), digest, duration, audio)
        groups.append(Group(folder.name, [unique[k] for k in sorted(unique)]))
    return groups


def normalize(clip: Clip, target: Path, settings: dict, control: Control):
    width, height = settings["width"], settings["height"]
    fps = settings["fps"]
    args = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", clip.path]
    silent = settings["mute"] or not clip.audio
    if silent:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
          f"fps={fps},setpts=PTS-STARTPTS,format=yuv420p")
    args += ["-map", "0:v:0", "-map", "1:a:0" if silent else "0:a:0", "-vf", vf,
             "-af", "aresample=48000:async=1:first_pts=0,apad", "-ac", "2", "-ar", "48000",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2",
             "-c:a", "aac", "-b:a", "160k", "-shortest", "-t", str(clip.duration),
             "-map_metadata", "-1", "-movflags", "+faststart", str(target)]
    run(args, control)


def join(normalized: list[Path], target: Path, control: Control):
    # Use relative, generated-only ASCII filenames. User path quotes never enter concat syntax.
    manifest = target.parent / (target.stem + ".concat.txt")
    try:
        manifest.write_text("".join(f"file '{path.name}'\n" for path in normalized), encoding="utf-8")
        run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "concat", "-safe", "1", "-i", str(manifest), "-map", "0:v:0",
             "-map", "0:a:0", "-c", "copy", "-movflags", "+faststart", str(target)], control)
        probe(target, control)
    finally:
        manifest.unlink(missing_ok=True)
