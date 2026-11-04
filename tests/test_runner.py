import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'plugin'
        (self.root/'native').mkdir(parents=True)
        (self.root/'scripts').mkdir()
        (self.root/'native/pointer-observer.cpp').write_text('observer')
        (self.root/'scripts/build-observer.sh').write_text('build')
        self.cache=Path(self.tmp.name)/'cache'
        self.version={'abiHash':'test-abi','commit':'abc'}

    def tearDown(self): self.tmp.cleanup()

    def fake_process(self,args,**kwargs):
        Path(args[-1]).write_bytes(b'compiled test fixture')
        class Process:
            def wait(self,timeout=None): return 0
        return Process()

    def test_build_cache_reuse_and_abi_and_source_changes(self):
        with patch.object(runner.subprocess,'check_output',side_effect=lambda *a,**kw:json.dumps(self.version)), \
             patch.object(runner.subprocess,'Popen',side_effect=self.fake_process) as build, \
             patch.object(runner,'status'):
            first=runner.ensure_observer(self.root,self.cache)
            self.assertTrue(first.is_relative_to(self.cache))
            self.assertEqual(runner.ensure_observer(self.root,self.cache),first)
            self.assertEqual(build.call_count,1)
            self.version['abiHash']='next-abi'
            second=runner.ensure_observer(self.root,self.cache)
            self.assertNotEqual(first,second)
            (self.root/'native/pointer-observer.cpp').write_text('updated observer')
            self.assertNotEqual(runner.ensure_observer(self.root,self.cache),second)
            self.assertEqual(build.call_count,3)

    def test_forced_retry_replaces_cache_and_then_reuses_result(self):
        with patch.object(runner.subprocess,'check_output',return_value=json.dumps(self.version)), \
             patch.object(runner.subprocess,'Popen',side_effect=self.fake_process) as build, \
             patch.object(runner,'status'):
            library=runner.ensure_observer(self.root,self.cache)
            library.write_bytes(b'broken cached helper')
            rebuilt=runner.ensure_observer(self.root,self.cache,force_rebuild=True)
            self.assertEqual(rebuilt,library)
            self.assertEqual(library.read_bytes(),b'compiled test fixture')
            self.assertEqual(build.call_count,2)
            self.assertEqual(runner.ensure_observer(self.root,self.cache),library)
            self.assertEqual(build.call_count,2)

    def test_failed_forced_retry_removes_stale_binary_and_can_recover(self):
        class Failed:
            def wait(self,timeout=None):return 1
        with patch.object(runner.subprocess,'check_output',return_value=json.dumps(self.version)), \
             patch.object(runner.subprocess,'Popen',side_effect=self.fake_process) as build, \
             patch.object(runner,'status'):
            library=runner.ensure_observer(self.root,self.cache)
            build.side_effect=None
            build.return_value=Failed()
            with self.assertRaises(RuntimeError):
                runner.ensure_observer(self.root,self.cache,force_rebuild=True)
            self.assertFalse(library.exists())
            build.side_effect=self.fake_process
            self.assertEqual(runner.ensure_observer(self.root,self.cache),library)
            self.assertTrue(library.is_file())

    def test_cli_rebuild_flag_is_forwarded_before_backend_start(self):
        with patch.object(runner.sys,'argv',['runner.py','--rebuild-observer','--','--dry-run']), \
             patch.object(runner.signal,'signal'), patch.object(runner,'status'), \
             patch.object(runner,'ensure_observer',return_value=Path('/test/observer.so')) as build, \
             patch.object(runner.os,'execv') as start:
            runner.main()
            build.assert_called_once_with(force_rebuild=True)
            self.assertIn('--dry-run',start.call_args.args[1])
            self.assertIn('/test/observer.so',start.call_args.args[1])

    def test_missing_abi_fails_without_compiling(self):
        with patch.object(runner.subprocess,'check_output',return_value='{}'), \
             patch.object(runner.subprocess,'Popen') as build:
            with self.assertRaises(RuntimeError):runner.ensure_observer(self.root,self.cache)
            build.assert_not_called()

    def test_failed_build_keeps_log_and_no_library(self):
        class Failed:
            def wait(self,timeout=None):return 1
        with patch.object(runner.subprocess,'check_output',return_value=json.dumps(self.version)), \
             patch.object(runner.subprocess,'Popen',return_value=Failed()), \
             patch.object(runner,'status'):
            with self.assertRaisesRegex(RuntimeError,'base-devel'):
                runner.ensure_observer(self.root,self.cache)
            self.assertFalse(list(self.cache.rglob('observer.so')))
            self.assertEqual(len(list(self.cache.rglob('build.log'))),1)

if __name__=='__main__':unittest.main()
