"""Per-user cache ownership and Windows install/uninstall coordination."""
from __future__ import annotations

import ctypes
import os
import re
import sqlite3
import stat
from contextlib import closing, ExitStack
from pathlib import Path

RUNNING_MUTEX = "Local\\MixCut.Desktop.Running"
CLEANUP_MUTEX = "Local\\MixCut.Desktop.Cleanup"
_tracking = False
_directory = None
WORK_FILE = re.compile(r"(?:clip_[0-9a-f]{64}(?:\.part)?\.mp4|result_[0-9a-f]{32}\.(?:mp4|concat\.txt))\Z")
STATE_FILES = ("usage.sqlite3", "usage.sqlite3-journal", "usage.sqlite3-wal", "usage.sqlite3-shm")


def state_directory():
    if _directory is not None:
        return Path(_directory)
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData"/"Local")))
    return base / "MixCut"


def plain_path(path):
    """Never traverse symbolic links, junctions or other reparse points."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError(f"为保护链接指向的文件，未清理此路径：{item}")
    return path


def remember(kind, path):
    if not _tracking:
        return
    directory = plain_path(state_directory())
    directory.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(directory/"usage.sqlite3", timeout=10)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS paths (kind TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(kind,path))")
        db.execute("INSERT OR IGNORE INTO paths VALUES (?,?)", (kind, os.path.abspath(path)))


def remember_project(root, outputs=()):
    remember("project", root)
    for output in outputs:
        remember("output", output)


def cleanup(directory=None):
    """Delete only recognized caches. Keep source clips, outputs and history.

    No directory-wide recursive deletion. Failed cleanup keeps the registry for
    retry; unknown files are never treated as caches just because of location.
    """
    directory = plain_path(directory or state_directory())
    db_path = directory/"usage.sqlite3"
    if not db_path.exists():
        if any((directory/name).exists() for name in STATE_FILES[1:]):
            raise OSError("缓存目录记录不完整，请恢复 usage.sqlite3 后重试。")
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()
        return {"removed": 0, "preserved": [], "errors": []}
    plain_path(db_path)
    with closing(sqlite3.connect(db_path.as_uri()+"?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT kind,path FROM paths").fetchall()
    from .project import ProjectLock
    with ExitStack() as locks:
        for kind, value in rows:
            if kind == "project":
                root = plain_path(value)
                if not Path(root.anchor).exists():
                    raise OSError(f"请连接项目所在磁盘后重试：{root}")
                if plain_path(root/".mixcut"/"project.sqlite3").exists():
                    locks.enter_context(ProjectLock(root))
        return _cleanup_tracked(directory, rows)


def _cleanup_tracked(directory, rows):
    outputs = set()
    errors, preserved = [], []
    removed = 0
    for kind, value in rows:
        if kind == "output":
            outputs.add(value)
        elif kind == "project":
            # Recover earlier-version output locations from projects visited in
            # this version, even if there are no new render jobs.
            try:
                history = plain_path(Path(value)/".mixcut"/"project.sqlite3")
                if history.is_file():
                    with closing(sqlite3.connect(history.as_uri()+"?mode=ro", uri=True)) as db:
                        outputs.update(str(Path(row[0]).parent) for row in db.execute("SELECT output FROM jobs"))
            except (OSError, sqlite3.Error) as exc:
                errors.append(str(exc))
    if errors:
        return {"removed": 0, "preserved": [], "errors": errors}
    for output in sorted(outputs):
        try:
            parent = plain_path(output)
            if not Path(parent.anchor).exists():
                raise OSError(f"请连接输出所在磁盘后重试：{parent}")
            if not parent.exists():
                continue
            for item in parent.iterdir():
                if item.name == ".mixcut-manifest.tmp":
                    plain_path(item)
                    if item.is_file():
                        with item.open("r", encoding="utf-8-sig") as stream:
                            header = stream.readline(128)
                        if header.startswith("成片文件,状态,依次使用的素材,"):
                            item.unlink()
                            removed += 1
                        else:
                            preserved.append(str(item))
                elif item.name.startswith(".mixcut-work-"):
                    plain_path(item)
                    if not item.is_dir():
                        preserved.append(str(item))
                        continue
                    for entry in item.iterdir():
                        plain_path(entry)
                        if entry.is_file() and WORK_FILE.fullmatch(entry.name):
                            entry.unlink()
                            removed += 1
                        else:
                            preserved.append(str(entry))
                    if not any(item.iterdir()):
                        item.rmdir()
        except (OSError, UnicodeError) as exc:
            errors.append(f"{output}: {exc}")
    if not errors:
        # Exact known files only: never delete another product's data or user
        # files even if someone placed them inside the MixCut data directory.
        for name in STATE_FILES:
            path = plain_path(directory/name)
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(str(exc))
        if not errors and directory.exists() and not any(directory.iterdir()):
            directory.rmdir()
    return {"removed": removed, "preserved": preserved, "errors": errors}


class RuntimeSession:
    """Keep app mutex alive without limiting multiple MixCut windows."""
    def __enter__(self):
        global _tracking
        self.handle = None
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.OpenMutexW.restype = wintypes.HANDLE
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            self.kernel = kernel
            def cleaning():
                handle = kernel.OpenMutexW(0x100000, False, CLEANUP_MUTEX)
                if handle:
                    kernel.CloseHandle(handle)
                    return True
                return False
            if cleaning():
                raise RuntimeError("MixCut 正在卸载或清理，请等待完成。")
            self.handle = kernel.CreateMutexW(None, False, RUNNING_MUTEX)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            if cleaning():
                kernel.CloseHandle(self.handle)
                self.handle = None
                raise RuntimeError("MixCut 正在卸载或清理，请等待完成。")
        _tracking = True
        return self

    def __exit__(self, *args):
        global _tracking
        _tracking = False
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def cleanup_main():
    """Installer-only entry; reports failures instead of claiming full cleanup."""
    try:
        import sys
        directory = None
        if "--state-directory" in sys.argv:
            directory = Path(sys.argv[sys.argv.index("--state-directory")+1])
            if directory.name != "MixCut" and not directory.name.startswith("MixCut-uninstall-test-"):
                raise ValueError("不接受此缓存目录名称。")
        result = cleanup(directory)
        if result["errors"]:
            raise RuntimeError("\n".join(result["errors"])[:2000])
        return 0
    except Exception as exc:
        if "--silent-cleanup" not in __import__("sys").argv:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror("缓存未清理完成", f"请关闭占用文件的程序或连接原磁盘后重试。\n\n{exc}")
            root.destroy()
        return 1
