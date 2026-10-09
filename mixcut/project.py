from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
import uuid
from contextlib import AbstractContextManager
from pathlib import Path

from .combinations import DistanceIndex, capacity, codebook, minimum_distance
from .media import Control, Group


class ProjectLock(AbstractContextManager):
    """OS-owned lock is released even after a crash; no stale PID deletion needed."""
    def __init__(self, root: Path):
        self.directory = root / ".mixcut"
        self.handle = None

    def __enter__(self):
        self.directory.mkdir(exist_ok=True)
        try:
            # Windows byte-range locks also deny reads of the locked byte.
            # Locking beyond EOF is supported, so no read/write is needed.
            self.handle = (self.directory / "lock").open("a+b")
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            raise RuntimeError("此素材项目正在被另一个程序窗口处理。") from exc
        return self

    def __exit__(self, *args):
        if self.handle:
            self.handle.close()


class Project(AbstractContextManager):
    def __init__(self, root: Path):
        self.root = root.resolve()
        directory = self.root / ".mixcut"
        directory.mkdir(exist_ok=True)
        self.db = sqlite3.connect(directory / "project.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, created REAL NOT NULL, clips TEXT NOT NULL,
              hashes TEXT NOT NULL, settings TEXT NOT NULL, output TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL DEFAULT 'queued', error TEXT NOT NULL DEFAULT ''
            );
        """)

    def __exit__(self, *args):
        self.db.close()

    def get_order(self):
        row = self.db.execute("SELECT value FROM metadata WHERE key='group_order'").fetchone()
        return json.loads(row[0]) if row else None

    def counts(self):
        return dict(self.db.execute("SELECT status, count(*) FROM jobs GROUP BY status").fetchall())

    def jobs(self, incomplete=False):
        where = "WHERE status != 'done'" if incomplete else ""
        return [dict(row) for row in self.db.execute(f"SELECT * FROM jobs {where} ORDER BY created, rowid")]

    def update(self, job_id: str, status: str, error: str = ""):
        with self.db:
            self.db.execute("UPDATE jobs SET status=?, error=? WHERE id=?", (status, error, job_id))

    def plan(self, groups: list[Group], count: int, output: Path, settings: dict,
             control: Control, notify=lambda _: None) -> int:
        output = output.resolve()
        if output == self.root or self.root in output.parents:
            raise ValueError("输出文件夹必须放在素材主文件夹之外，以免成片被再次识别为素材。")
        if not 1 <= count <= 100000:
            raise ValueError("单次新增数量需在1～100000之间，可分批继续生成。")
        names = [g.name for g in groups]
        locked = self.get_order()
        if locked is not None and names != locked:
            raise ValueError("此项目已锁定素材组顺序。请恢复原有组名和顺序；新结构请使用新的主文件夹。")
        sizes = [len(g.clips) for g in groups]
        distance = minimum_distance(len(groups))
        total = capacity(sizes, distance)
        if count > total:
            raise ValueError(f"超过当前素材从零开始的理论上限 {total:,} 条（历史记录还会占用组合）。")
        history = [json.loads(row[0]) for row in self.db.execute("SELECT hashes FROM jobs")]
        index = DistanceIndex(len(groups), distance, history)
        chosen = []
        limit = min(total, max(200000, count * 100))
        for tried, positions in enumerate(codebook(sizes, distance), start=1):
            control.checkpoint()
            clips = [group.clips[pos] for group, pos in zip(groups, positions)]
            hashes = tuple(clip.digest for clip in clips)
            if index.allows(hashes):
                index.add(hashes)
                chosen.append(clips)
                if len(chosen) == count:
                    break
            if tried % 2000 == 0:
                notify(f"筛选组合：已找到 {len(chosen):,} / {count:,}")
            if tried >= limit:
                break
        if len(chosen) < count:
            note = "本轮达到搜索上限" if limit < total else "已检查当前组合方案"
            raise ValueError(f"{note}，可新增 {len(chosen):,} 条，少于申请的 {count:,} 条。"
                             "请降低数量。素材增删后为兼容历史，可能无法达到从零开始的理论上限。")
        output.mkdir(parents=True, exist_ok=True)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('group_order', ?)",
                            (json.dumps(names, ensure_ascii=False),))
            first = self.db.execute("SELECT count(*) FROM jobs").fetchone()[0] + 1
            for offset, clips in enumerate(chosen):
                job_id = uuid.uuid4().hex
                target = output / f"MixCut_{first + offset:06d}_{job_id[:8]}.mp4"
                self.db.execute("INSERT INTO jobs (id,created,clips,hashes,settings,output) VALUES (?,?,?,?,?,?)",
                                (job_id, time.time(), json.dumps([c.to_dict() for c in clips], ensure_ascii=False),
                                 json.dumps([c.digest for c in clips]), json.dumps(settings), str(target)))
        return len(chosen)

    def export_csv(self):
        rows = self.jobs()
        outputs = {Path(row["output"]).parent for row in rows}
        for directory in outputs:
            if not directory.is_dir():
                continue
            temporary = directory / ".mixcut-manifest.tmp"
            with temporary.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(["成片文件", "状态", "依次使用的素材", "素材SHA256", "错误信息"])
                for row in rows:
                    if Path(row["output"]).parent != directory:
                        continue
                    clips = json.loads(row["clips"])
                    writer.writerow([Path(row["output"]).name, row["status"],
                                     " → ".join(c["path"] for c in clips),
                                     " | ".join(json.loads(row["hashes"])), row["error"]])
            os.replace(temporary, directory / "MixCut_组合记录.csv")
