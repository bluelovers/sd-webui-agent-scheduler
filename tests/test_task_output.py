"""
test_task_output.py — task_output 模組的固定測試

涵蓋:
1. 巢狀殘留路徑的判斷與修復（上次任務在還原設定前中斷）。
2. 輸出根目錄的推導（含「根目錄守門」，保證不會往下再疊一層）。
3. 任務結束後的空資料夾清理、當日資料夾防護、.txt 原因報告。

執行
    pyrun-test.bat tests/test_task_output.py
"""

import sys
import unittest
from pathlib import Path

# 讓 _support 可被匯入（各種呼叫方式都成立）
# Make _support importable regardless of how this module is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _support import make_task_tree, posix, read_text, workspace

from agent_scheduler.shared_opts_backup import simplify_path
from agent_scheduler.task_output import (
    OUTPUT_ROOT_NAME,
    cleanup_task_output_dir,
    compose_output_root,
    find_scheduler_prefix,
    repair_stale_outdir,
    resolve_samples_base,
)

# 巢狀殘留案例表：(輸入路徑, 期望修復結果, 期望樹前綴)
# Nested-leftover cases: (input, expected repaired path, expected tree prefix).
STALE_CASES = [
    # 現行版：root/日期/任務標籤/samples
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/samples",
     "D:/sd-forge/output/samples", "D:/sd-forge/output"),
    # 真實設定形狀：設定值為 output\txt2img-images，殘留值的葉節即原始目錄名
    # Real config shape: the option holds output\txt2img-images, so the leftover
    # leaf is the original directory name itself.
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/txt2img-images",
     "D:/sd-forge/output/txt2img-images", "D:/sd-forge/output"),
    # 中斷兩次造成的雙重巢狀
    ("D:/out/agent-scheduler/2026-10-10/11-16-47_task(a)/agent-scheduler/2026-10-10/23-04-38_task(b)/samples",
     "D:/out/samples", "D:/out"),
    # 舊版：無 agent-scheduler 層（日期 + 任務標籤）
    ("D:/out/2026-10-10/11-16-47_task(a)/samples",
     "D:/out/samples", "D:/out"),
    # 舊版：YYYY-MM-DD_HH-MM-SS_task(...) 合一標籤
    ("D:/out/2026-10-10_11-16-47_task(a)/samples",
     "D:/out/samples", "D:/out"),
    # 相對路徑型殘留（control_net_detectedmap_dir 舊版寫法）
    ("../outputs/agent-scheduler/2026-10-10/11-16-47_task(a)/detected_maps",
     "../outputs/detected_maps", "../outputs"),
    # 原始目錄名不可考（只剩標籤層）→ 不猜，但前綴仍可取得
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/23-04-38_task(b)",
     None, "D:/sd-forge/output"),
    # 使用者自己的資料夾剛好叫 2026-10-10：以 agent-scheduler 為錨點
    ("D:/photos/2026-10-10/agent-scheduler/2026-10-10/11-16-47_task(a)/samples",
     "D:/photos/2026-10-10/samples", "D:/photos/2026-10-10"),
    # 以下為「一般使用者路徑」，一律不得誤判
    ("outputs/txt2img-images/samples", None, None),
    # 真實設定值本身（相對路徑，正／反斜線）不得被當成殘留
    # The real config value (relative, forward/backslash) is never a leftover.
    ("output/txt2img-images", None, None),
    ("output\\txt2img-images", None, None),
    ("D:/photos/2026-10-10/samples", None, None),   # 有日期但無任務標籤
    ("D:/x/agent-scheduler/samples", None, None),   # 有 root 層但無任務標籤
    ("../detected_maps", None, None),
    ("", None, None),
    (None, None, None),
    (123, None, None),
]

# 根目錄推導案例表：(輸入基準, 期望根目錄)
# Root derivation cases: (input base, expected root).
ROOT_CASES = [
    # 正常情況：基準往上一層 + agent-scheduler
    ("outputs/txt2img-images/samples", "outputs/txt2img-images/agent-scheduler"),
    ("D:/sd-forge/output/samples", "D:/sd-forge/output/agent-scheduler"),
    # 真實設定值（相對路徑）：與 change_output_dir 的組法一致
    # Real config value (relative): composed exactly the way change_output_dir does.
    ("output/txt2img-images", "output/agent-scheduler"),
    ("output/img2img-images", "output/agent-scheduler"),
    # 殘留情況：一律收回同一個根目錄，不再往下疊
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/samples",
     "D:/sd-forge/output/agent-scheduler"),
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/agent-scheduler/2026-10-10/23-04-38_task(b)/samples",
     "D:/sd-forge/output/agent-scheduler"),
    ("D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/23-04-38_task(b)",
     "D:/sd-forge/output/agent-scheduler"),
    ("D:/out/2026-10-10/11-16-47_task(a)/samples",
     "D:/out/agent-scheduler"),
]


class RepairStaleOutdirTest(unittest.TestCase):
    """巢狀殘留路徑的判斷與修復"""

    def test_repair_and_prefix(self):
        for raw, expected_repair, expected_prefix in STALE_CASES:
            with self.subTest(raw=raw):
                self.assertEqual(posix(repair_stale_outdir(raw)), expected_repair)
                self.assertEqual(posix(find_scheduler_prefix(raw)), expected_prefix)

    def test_repair_result_is_idempotent(self):
        """修復結果再次套用必須是無操作：不得再被改動，也不得留在輸出樹內。
        Applying the repair to an already-repaired path must be a no-op: nothing is
        modified again and the result no longer sits inside the output tree."""
        for raw, expected_repair, _ in STALE_CASES:
            if expected_repair is None:
                continue
            with self.subTest(raw=raw):
                once = repair_stale_outdir(raw)
                self.assertEqual(posix(once), expected_repair)
                # 再修一次 → 回傳 None（已不是巢狀殘留，什麼都不做）
                # Repairing again → None (no longer a leftover, so nothing happens).
                self.assertIsNone(repair_stale_outdir(once))
                self.assertIsNone(find_scheduler_prefix(once))


class ComposeOutputRootTest(unittest.TestCase):
    """輸出根目錄推導（含根目錄守門）"""

    def test_root_matches_expected(self):
        for base, expected_root in ROOT_CASES:
            with self.subTest(base=base):
                root = simplify_path(compose_output_root(base))
                self.assertEqual(root.as_posix(), expected_root)

    def test_root_is_never_nested(self):
        """不論輸入多深，根目錄都只能含一層 agent-scheduler，且本身不在輸出樹內。
        However deep the input is, the root must hold exactly one agent-scheduler
        segment and must not itself sit inside the output tree."""
        for base, _ in ROOT_CASES:
            with self.subTest(base=base):
                root = simplify_path(compose_output_root(base))
                self.assertEqual(root.as_posix().count(OUTPUT_ROOT_NAME), 1)
                self.assertIsNone(find_scheduler_prefix(root))

    def test_resolve_samples_base_repairs_recoverable_path(self):
        raw = "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/samples"
        resolved = resolve_samples_base(raw)
        self.assertEqual(posix(resolved), "D:/sd-forge/output/samples")
        self.assertEqual(
            simplify_path(compose_output_root(resolved)).as_posix(),
            "D:/sd-forge/output/agent-scheduler",
        )

    def test_resolve_samples_base_keeps_clean_base(self):
        raw = "outputs/txt2img-images/samples"
        self.assertEqual(posix(resolve_samples_base(raw)), raw)

    def test_resolve_samples_base_keeps_unrecoverable_path(self):
        """原始目錄名不可考時原樣回傳，交由根目錄守門處理。
        When the original name is unknown the path is passed through unchanged and
        the root guard takes over."""
        raw = "D:/sd-forge/output/agent-scheduler/2026-10-10/11-16-47_task(a)/23-04-38_task(b)"
        self.assertEqual(posix(resolve_samples_base(raw)), raw)
        self.assertEqual(
            simplify_path(compose_output_root(resolve_samples_base(raw))).as_posix(),
            "D:/sd-forge/output/agent-scheduler",
        )


class CleanupTaskOutputDirTest(unittest.TestCase):
    """任務結束後的空資料夾清理與原因報告"""

    def setUp(self):
        self.root = workspace("cleanup")

    def test_keeps_folder_with_output_but_removes_empty_subdirs(self):
        task = make_task_tree(self.root / "14-01-00_taskB", "samples", "grids")
        (task / "samples" / "img.png").write_bytes(b"png")

        cleanup_task_output_dir(task, task_id="taskB", status="done")

        self.assertTrue(task.exists())
        self.assertTrue((task / "samples").exists())     # 有產出 → 保留
        self.assertFalse((task / "grids").exists())      # 空子目錄 → 刪除
        self.assertFalse((self.root / "14-01-00_taskB.txt").exists())  # 有產出 → 不報告

    def test_removes_fully_empty_task_folder_and_writes_report(self):
        # 含多層空子目錄，確認由內往外整個清掉
        task = make_task_tree(self.root / "14-00-00_taskA", "samples/a/b", "grids")

        cleanup_task_output_dir(task, task_id="taskA", status="interrupted", interrupted=True)

        self.assertFalse(task.exists())
        report = self.root / "14-00-00_taskA.txt"
        self.assertTrue(report.exists(), "空任務資料夾必須留下同名 .txt 報告")

        text = read_text(report)
        self.assertIn("任務資料夾清理報告", text)
        self.assertIn("taskA", text)
        self.assertIn("判定原因", text)
        self.assertIn("取消任務", text)
        self.assertIn("是，空資料夾已刪除", text)

    def test_report_reasons(self):
        cases = [
            ("14-02-00_taskF", dict(status="failed", failed=True, error=RuntimeError("boom")), "任務出錯"),
            ("14-03-00_taskU", dict(status="done"), "其他／未知原因"),
            ("14-04-00_taskP", dict(status="pending", queue_purged=True), "佇列被傾空"),
            ("14-05-00_taskI", dict(status="interrupted", interrupted=True), "取消任務"),
        ]
        for name, kwargs, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                task = make_task_tree(self.root / name, "samples")
                cleanup_task_output_dir(task, task_id=name, **kwargs)

                self.assertFalse(task.exists())
                text = read_text(self.root / f"{name}.txt")
                self.assertIn("判定原因", text)
                self.assertIn(expected_reason, text)
                self.assertIn(name, text)

    def test_day_folder_is_never_cleaned(self):
        """當日資料夾是 .txt 報告的容器，永遠不得刪除。
        The day folder holds the .txt reports and must never be removed."""
        day = self.root / "2026-10-11"
        inner_task = make_task_tree(day / "15-00-00_taskX", "samples")

        cleanup_task_output_dir(day, task_id="x")

        self.assertTrue(day.exists())
        self.assertTrue(inner_task.exists())
        self.assertFalse((self.root / "2026-10-11.txt").exists())

    def test_output_root_is_never_cleaned(self):
        out_root = self.root / OUTPUT_ROOT_NAME
        nested_task = make_task_tree(out_root / "2026-10-12" / "16-00-00_taskY", "samples")

        cleanup_task_output_dir(out_root, task_id="x")

        self.assertTrue(out_root.exists())
        self.assertTrue(nested_task.exists())

        # 但真正的任務資料夾仍會被正常清理
        cleanup_task_output_dir(
            nested_task, task_id="taskY", status="failed", failed=True, error=RuntimeError("boom")
        )
        self.assertFalse(nested_task.exists())
        self.assertTrue((nested_task.parent / "16-00-00_taskY.txt").exists())

    def test_ignores_invalid_inputs(self):
        """None／空字串／不存在／非目錄／非路徑型別 一律靜默略過，不得拋例外。
        None, empty, missing, non-directory and non-path inputs are skipped silently
        and must never raise."""
        sentinel = make_task_tree(self.root / "17-00-00_taskZ", "samples")
        plain_file = self.root / "plain.txt"
        plain_file.write_text("not a directory", encoding="utf-8")

        for value in (None, "", self.root / "does-not-exist", 123, plain_file):
            with self.subTest(value=value):
                cleanup_task_output_dir(value, task_id="x")

        # 不屬於任務資料夾者一律不動其內容
        # Anything that is not a task folder is left untouched.
        self.assertTrue(sentinel.exists())
        self.assertTrue((sentinel / "samples").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
