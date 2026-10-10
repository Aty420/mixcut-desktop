import ctypes
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mixcut import lifecycle
from mixcut.project import Project, ProjectLock


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root/'MixCut'
        self.output = self.root/'output'
        self.output.mkdir()
        self.project = self.root/'source'
        self.project.mkdir()
        with patch.object(lifecycle, '_tracking', True), patch.object(lifecycle, '_directory', self.state):
            lifecycle.remember_project(self.project)
            lifecycle.remember('output', self.output)
        with Project(self.project):
            pass
        self.work = self.output/'.mixcut-work-crashed'
        self.work.mkdir()
        self.cached = self.work/('clip_'+'a'*64+'.mp4')
        self.cached.write_bytes(b'cache')

    def tearDown(self):
        self.temp.cleanup()

    def test_cleans_caches_but_preserves_media_history_and_unknown_files(self):
        (self.work/('clip_'+'b'*64+'.part.mp4')).write_bytes(b'partial')
        (self.work/('result_'+'c'*32+'.concat.txt')).write_text('concat')
        (self.output/'.mixcut-manifest.tmp').write_text('成片文件,状态,依次使用的素材,素材SHA256,错误信息\n',encoding='utf-8-sig')
        (self.output/'finished.mp4').write_bytes(b'finished')
        (self.project/'source.mp4').write_bytes(b'source')
        unknown = self.work/'my-video.mp4'
        unknown.write_bytes(b'user file')
        (self.state/'my-notes.txt').write_text('mine')
        result = lifecycle.cleanup(self.state)
        self.assertFalse(result['errors'])
        self.assertEqual(result['removed'],4)
        self.assertFalse(self.cached.exists())
        self.assertTrue(unknown.exists())
        self.assertTrue((self.output/'finished.mp4').exists())
        self.assertTrue((self.project/'source.mp4').exists())
        self.assertTrue((self.project/'.mixcut/project.sqlite3').exists())
        self.assertTrue((self.state/'my-notes.txt').exists())
        self.assertFalse((self.state/'usage.sqlite3').exists())

    def test_empty_app_cache_directories_are_removed(self):
        result = lifecycle.cleanup(self.state)
        self.assertFalse(result['errors'])
        self.assertFalse(self.work.exists())
        self.assertFalse(self.state.exists())
        self.assertTrue(self.output.exists())
        self.assertFalse(lifecycle.cleanup(self.state)['errors'])

    def test_active_project_stops_cleanup_before_deleting_any_cache(self):
        with ProjectLock(self.project):
            with self.assertRaises(RuntimeError):
                lifecycle.cleanup(self.state)
        self.assertTrue(self.cached.exists())
        self.assertTrue((self.state/'usage.sqlite3').exists())

    def test_failed_deletion_keeps_registry_for_retry(self):
        real_unlink = Path.unlink
        def denied(path, *args, **kwargs):
            if path == self.cached:
                raise PermissionError('cache is busy')
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', denied):
            result = lifecycle.cleanup(self.state)
        self.assertTrue(result['errors'])
        self.assertTrue((self.state/'usage.sqlite3').exists())
        self.assertTrue(self.cached.exists())
        self.assertFalse(lifecycle.cleanup(self.state)['errors'])
        self.assertFalse(self.state.exists())

    def test_never_follows_link_to_user_files(self):
        elsewhere = self.root/'personal'
        elsewhere.mkdir()
        protected = elsewhere/self.cached.name
        protected.write_bytes(b'important')
        link = self.output/'.mixcut-work-linked'
        try:
            link.symlink_to(elsewhere, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symbolic links is unavailable')
        result = lifecycle.cleanup(self.state)
        self.assertTrue(result['errors'])
        self.assertEqual(protected.read_bytes(), b'important')
        self.assertTrue((self.state/'usage.sqlite3').exists())

    def test_legacy_history_recovers_prior_output_locations(self):
        old_output = self.root/'old-output'
        old_work = old_output/'.mixcut-work-old'
        old_work.mkdir(parents=True)
        old_cache = old_work/('result_'+'e'*32+'.mp4')
        old_cache.write_bytes(b'old temporary output')
        with Project(self.project) as project:
            project.db.execute("INSERT INTO jobs (id,created,clips,hashes,settings,output) VALUES ('old',0,'[]','[]','{}',?)", (str(old_output/'finished.mp4'),))
            project.db.commit()
        self.assertFalse(lifecycle.cleanup(self.state)['errors'])
        self.assertFalse(old_work.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows named mutex integration')
    def test_uninstall_mutex_blocks_new_app_launch(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        from ctypes import wintypes
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.CreateMutexW(None, False, lifecycle.CLEANUP_MUTEX)
        self.assertTrue(handle)
        try:
            with self.assertRaises(RuntimeError):
                with lifecycle.RuntimeSession():
                    self.fail('App started during uninstall')
        finally:
            kernel.CloseHandle(handle)
