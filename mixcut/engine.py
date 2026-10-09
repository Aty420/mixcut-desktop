from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .media import Cancelled, Clip, Control, Group, digest_file, join, normalize, probe
from .project import Project


def render_pending(project: Project, groups: list[Group], control: Control, notify=lambda _: None):
    """Caller holds ProjectLock. Reservations survive failures, stops and restarts."""
    jobs = project.jobs(incomplete=True)
    current = [{c.digest: c for c in group.clips} for group in groups]
    verified: set[str] = set()
    caches = {}
    good = failed = 0
    try:
        for number, job in enumerate(jobs, start=1):
            control.checkpoint()
            output = Path(job["output"])
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                # Recovery window: a valid final file was atomically published before DB update.
                if output.exists():
                    if job["status"] != "publishing":
                        raise RuntimeError(f"目标文件已存在，未覆盖：{output.name}")
                    probe(output, control)
                    project.update(job["id"], "done")
                    good += 1
                    notify(("progress", number, len(jobs), good, failed))
                    continue
                settings = json.loads(job["settings"])
                hashes = json.loads(job["hashes"])
                if len(hashes) != len(groups):
                    raise ValueError("素材组数量已变化，不能续跑此任务。")
                selected = []
                for group, digest in zip(current, hashes):
                    clip = group.get(digest)
                    if clip is None:
                        raise ValueError("有素材被修改或移除。请恢复原文件后继续未完成任务。")
                    if clip.path not in verified:
                        if digest_file(Path(clip.path), control) != clip.digest:
                            raise ValueError(f"扫描后素材发生改变，请重新扫描：{clip.path}")
                        verified.add(clip.path)
                    selected.append(clip)
                key = str(output.parent)
                if key not in caches:
                    caches[key] = tempfile.TemporaryDirectory(prefix=".mixcut-work-", dir=output.parent)
                work = Path(caches[key].name)
                normalized = []
                project.update(job["id"], "rendering")
                for position, clip in enumerate(selected, start=1):
                    notify(f"成片 {number}/{len(jobs)} · 第 {position}/{len(selected)} 段 · {Path(clip.path).name}")
                    cache_key = hashlib.sha256((clip.digest + json.dumps(settings, sort_keys=True)).encode()).hexdigest()
                    cached = work / f"clip_{cache_key}.mp4"
                    if not cached.exists():
                        pending = work / f"clip_{cache_key}.part.mp4"
                        normalize(clip, pending, settings, control)
                        os.replace(pending, cached)
                    normalized.append(cached)
                temporary = work / f"result_{job['id']}.mp4"
                join(normalized, temporary, control)
                if output.exists():
                    raise RuntimeError(f"目标文件在处理期间被占用，未覆盖：{output.name}")
                project.update(job["id"], "publishing")
                # Windows rename refuses existing files. Linux link likewise avoids clobber.
                if os.name == "nt":
                    os.rename(temporary, output)
                else:
                    os.link(temporary, output)
                    temporary.unlink()
                project.update(job["id"], "done")
                good += 1
            except Cancelled:
                # A publishing reservation must remain recoverable if its final file exists.
                if not output.exists():
                    project.update(job["id"], "queued")
                raise
            except Exception as exc:
                project.update(job["id"], "failed", str(exc))
                failed += 1
                notify(f"失败：{output.name} — {exc}")
            notify(("progress", number, len(jobs), good, failed))
    finally:
        for directory in caches.values():
            directory.cleanup()
        try:
            project.export_csv()
        except OSError as exc:
            notify(f"组合记录CSV未能更新（数据库记录已保留）：{exc}")
    return good, failed
