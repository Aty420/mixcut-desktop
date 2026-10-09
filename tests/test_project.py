import json
import tempfile
import unittest
from pathlib import Path

from mixcut.combinations import assert_distance
from mixcut.media import Clip, Control, Group
from mixcut.project import Project, ProjectLock

SETTINGS = {"width": 96, "height": 128, "fps": 30, "mute": False}


def fake_groups(sizes):
    return [Group(chr(65 + i), [Clip(f"{i}-{j}.mp4", f"hash-{i}-{j}", 1, True)
                              for j in range(size)]) for i, size in enumerate(sizes)]


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "素材"
        self.root.mkdir()
        self.output = self.base / "成片"

    def tearDown(self):
        self.temp.cleanup()

    def test_history_reopen_different_output_and_capacity(self):
        groups = fake_groups([3] * 4)
        with Project(self.root) as project:
            project.plan(groups, 13, self.output, SETTINGS, Control())
        with Project(self.root) as project:
            project.plan(groups, 14, self.base / "other-output", SETTINGS, Control())
            rows = [json.loads(job["hashes"]) for job in project.jobs()]
            self.assertEqual(len(rows), 27)
            assert_distance(rows, 2)
            with self.assertRaises(ValueError):
                project.plan(groups, 1, self.output, SETTINGS, Control())
            self.assertEqual(len(project.jobs()), 27)

    def test_two_and_three_groups_use_full_product(self):
        for sizes in ([2, 3], [2, 2, 3]):
            root = self.base / str(len(sizes))
            root.mkdir()
            with Project(root) as project:
                count = 6 if len(sizes) == 2 else 12
                project.plan(fake_groups(sizes), count, self.output, SETTINGS, Control())
                assert_distance([json.loads(j["hashes"]) for j in project.jobs()], 1)

    def test_order_change_rejected(self):
        groups = fake_groups([2, 2, 2, 2])
        with Project(self.root) as project:
            project.plan(groups, 1, self.output, SETTINGS, Control())
            with self.assertRaises(ValueError):
                project.plan(groups[::-1], 1, self.output, SETTINGS, Control())

    def test_added_material_preserves_distance(self):
        with Project(self.root) as project:
            project.plan(fake_groups([2] * 4), 2, self.output, SETTINGS, Control())
            project.plan(fake_groups([3] * 4), 5, self.output, SETTINGS, Control())
            rows = [json.loads(job["hashes"]) for job in project.jobs()]
            assert_distance(rows, 2)

    def test_output_inside_input_rejected(self):
        with Project(self.root) as project:
            with self.assertRaises(ValueError):
                project.plan(fake_groups([2, 2]), 1, self.root / "output", SETTINGS, Control())

    def test_concurrent_window_lock(self):
        with ProjectLock(self.root):
            with self.assertRaises(RuntimeError):
                with ProjectLock(self.root):
                    pass


if __name__ == "__main__":
    unittest.main()
