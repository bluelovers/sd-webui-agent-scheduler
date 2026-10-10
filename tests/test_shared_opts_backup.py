"""
test_shared_opts_backup.py — SharedOptsBackup 的固定測試

涵蓋:
1. save_backup_file()：寫入指定 options 快照、含 computed 根目錄資訊、
   檔案已存在時一律不覆寫、寫入失敗回傳 None 且不拋例外。
   save_backup_file(): writes the given option snapshot with computed root info,
   never overwrites an existing file, returns None (never raises) on failure.
2. set_shared_opts_core()：備份「第一次」的原始值、備份前先修復巢狀殘留路徑。
   set_shared_opts_core(): backs up the *first* original value and repairs a nested
   leftover path before backing it up.
3. restore_shared_opts()：還原時以修復後的路徑寫回。
   restore_shared_opts(): writes back the repaired path on restore.
4. simplify_path()：路徑正規化的基本行為。
   simplify_path(): basic path normalization behavior.

執行
    python tests/test_shared_opts_backup.py
    python tests/run_tests.py
"""

import json
import sys
import unittest
from pathlib import Path

# 讓 _support 可被匯入（各種呼叫方式都成立）
# Make _support importable regardless of how this module is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import posix, workspace

from agent_scheduler.shared_opts_backup import SharedOptsBackup, simplify_path


class FakeOpts:
    """最小 shared.opts 替身：只需要 get/set 語意（實際 sd-webui 的 opts 為 dict-like 物件）。

    Minimal stand-in for shared.opts: only get/set semantics are needed (the real
    sd-webui opts object is dict-like).
    """

    def __init__(self, **values):
        self.__dict__.update(values)

    def set(self, key, value):
        setattr(self, key, value)


class BackupFileTest(unittest.TestCase):
    """save_backup_file() 的行為"""

    def setUp(self):
        self.root = workspace("backup_file")

    def test_writes_snapshot_with_computed_roots(self):
        opts = FakeOpts(samples_save=False, grid_save=True)
        backup = SharedOptsBackup(opts)
        backup.set_shared_opts(samples_save=True, grid_save=False)

        path = backup.save_backup_file(
            self.root,
            "task-1",
            computed={
                "root": "D:/sd-forge/output/agent-scheduler",
                "day_dir": "D:/sd-forge/output/agent-scheduler/2026-10-10",
                "task_dir": "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)",
            },
        )

        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "shared_opts_backup.json")

        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], "task-1")
        self.assertIn("created_at", payload)
        self.assertEqual(payload["computed"]["root"], "D:/sd-forge/output/agent-scheduler")
        self.assertEqual(payload["computed"]["day_dir"], "D:/sd-forge/output/agent-scheduler/2026-10-10")
        # 快照內容必須是「變更前」的原始值
        # The snapshot must hold the *pre-change* original values.
        self.assertIs(payload["opts"]["samples_save"], False)
        self.assertIs(payload["opts"]["grid_save"], True)

    def test_existing_snapshot_is_never_overwritten(self):
        opts = FakeOpts(samples_save=False)
        backup = SharedOptsBackup(opts)
        backup.set_shared_opts(samples_save=True)

        first = backup.save_backup_file(self.root, "task-1", computed={"root": "A"})
        self.assertIsNotNone(first)
        before = first.read_text(encoding="utf-8")

        # 第二次寫入（不同 task_id／computed）必須直接放棄
        # A second write (different task_id / computed) must be skipped.
        second = backup.save_backup_file(self.root, "task-2", computed={"root": "B"})
        self.assertIsNone(second)
        self.assertEqual(first.read_text(encoding="utf-8"), before)

    def test_returns_none_when_day_dir_unwritable(self):
        """day_dir 不可寫（父層為檔案）→ 回傳 None 且不拋例外。
        When day_dir cannot be created (its parent is a file) it returns None and
        never raises."""
        blocker = self.root / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")

        backup = SharedOptsBackup(FakeOpts(samples_save=False))
        backup.set_shared_opts(samples_save=True)

        self.assertIsNone(backup.save_backup_file(blocker, "task-x"))


class BackupLifecycleTest(unittest.TestCase):
    """set_shared_opts_core() / restore_shared_opts() 的生命週期"""

    def test_backs_up_each_key_once(self):
        opts = FakeOpts(samples_save=False)
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core("samples_save", True)
        self.assertFalse(backup.get_backup_value("samples_save"))

        # 同一 key 再次變更，備份仍保留「第一次」的原始值
        # A second change on the same key keeps the *first* original value.
        backup.set_shared_opts_core("samples_save", False)
        self.assertFalse(backup.get_backup_value("samples_save"))
        self.assertTrue(backup.is_backup_exists("samples_save"))

    def test_repairs_stale_nested_path_before_backup(self):
        opts = FakeOpts()
        opts.outdir_txt2img_samples = (
            "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/samples"
        )
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core(
            "outdir_txt2img_samples",
            "D:/sd-forge/output/agent-scheduler/2026-10-10/23-04-38_task(b)/samples",
        )

        # 備份的是修復後的原始目錄，而非殘留的巢狀路徑
        # The backup holds the repaired original directory, not the nested leftover.
        self.assertEqual(
            posix(backup.get_backup_value("outdir_txt2img_samples")),
            "D:/sd-forge/output/samples",
        )

    def test_repairs_stale_grid_path_before_backup(self):
        opts = FakeOpts()
        opts.outdir_txt2img_grids = (
            "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/grids"
        )
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core(
            "outdir_txt2img_grids",
            "D:/sd-forge/output/agent-scheduler/2026-10-10/23-04-38_task(b)/grids",
        )

        self.assertEqual(
            posix(backup.get_backup_value("outdir_txt2img_grids")),
            "D:/sd-forge/output/grids",
        )

    def test_restore_writes_back_repaired_originals(self):
        opts = FakeOpts()
        opts.outdir_txt2img_samples = (
            "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/samples"
        )
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core(
            "outdir_txt2img_samples",
            "D:/sd-forge/output/agent-scheduler/2026-10-10/23-04-38_task(b)/samples",
        )
        backup.restore_shared_opts()

        # 還原後不得仍是巢狀路徑，否則下次任務會再往下疊
        # After restore the value must not still be nested, otherwise the next task
        # would stack another level.
        self.assertEqual(
            posix(opts.outdir_txt2img_samples),
            "D:/sd-forge/output/samples",
        )

    def test_real_config_value_is_kept_verbatim(self):
        """真實設定值是相對路徑（例：output\\txt2img-images），三處的型別各不相同：
        1. 備份／快照檔 → 原樣相對字串（不轉絕對路徑）
        2. 任務期間的 shared.opts → 絕對路徑（set_shared_opts_core 會 resolve）
        3. 還原後 → 回到原始相對字串
        The real config value is a relative path (e.g. output\\txt2img-images) and it
        has a different shape in each place: (1) the backup / snapshot keeps the
        relative string verbatim, (2) shared.opts holds an absolute path while the
        task runs (set_shared_opts_core resolves it), (3) restore puts the relative
        string back."""
        opts = FakeOpts()
        opts.outdir_txt2img_samples = "output\\txt2img-images"
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core(
            "outdir_txt2img_samples",
            Path("output/agent-scheduler/2026-10-10/11-16-47_task(a)/txt2img-images"),
        )

        # 1) 備份 = 原始相對設定值；原本就不是巢狀殘留，不得被「修復」
        # 1) The backup is the original relative value; it is not a leftover, so it
        #    must never be "repaired".
        self.assertEqual(backup.get_backup_value("outdir_txt2img_samples"), "output\\txt2img-images")

        # 2) 任務期間 shared.opts 存的是絕對路徑
        # 2) While the task runs, shared.opts holds an absolute path.
        live = opts.outdir_txt2img_samples
        self.assertTrue(Path(live).is_absolute(), f"執行期間應為絕對路徑: {live}")
        self.assertTrue(live.endswith("/txt2img-images"))

        # 3) 快照檔內容也是原始相對設定值
        # 3) The snapshot file holds the original relative value as well.
        path = backup.save_backup_file(workspace("real_config"), "task-1")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["opts"]["outdir_txt2img_samples"], "output\\txt2img-images")

        # 4) 還原後回到原始相對設定值，下次任務才會從正確的基準組路徑
        # 4) Restore returns the relative value, so the next task composes its paths
        #    from the correct base again.
        backup.restore_shared_opts()
        self.assertEqual(opts.outdir_txt2img_samples, "output\\txt2img-images")

    def test_non_path_values_are_untouched(self):
        opts = FakeOpts(save_mask=False)
        backup = SharedOptsBackup(opts)

        backup.set_shared_opts_core("save_mask", True)

        self.assertIs(backup.get_backup_value("save_mask"), False)
        self.assertIs(opts.save_mask, True)

        backup.restore_shared_opts()
        self.assertIs(opts.save_mask, False)


class SimplifyPathTest(unittest.TestCase):
    """simplify_path() 的基本正規化"""

    CASES = [
        ("outputs/a/samples/../b", "outputs/a/b"),
        ("../detected_maps", "../detected_maps"),  # 開頭的 '..' 必須保留
        ("a/./b", "a/b"),
        ("D:/a/b/../c", "D:/a/c"),  # 只抵銷相鄰的 '..'，不會跨層
    ]

    def test_simplify(self):
        for raw, expected in self.CASES:
            with self.subTest(raw=raw):
                self.assertEqual(simplify_path(raw).as_posix(), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
