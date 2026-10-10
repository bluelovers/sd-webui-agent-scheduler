"""
test_enqueue_placement.py — Enqueue 掛載點解析的固定測試

涵蓋:
1. classic 版面（有 {tab}_toprow / {tab}_actions_column）：
   - Near Generate → generate 按鈕建立時掛 `{tab}_actions_column`。
   - Between → 負向提示詞建立時掛 `{tab}_toprow`。
   classic layout (has {tab}_toprow / {tab}_actions_column):
   - Near Generate → mount `{tab}_actions_column` when the Generate button is built.
   - Between → mount `{tab}_toprow` when the negative prompt is built.
2. Compact 版面（無 toprow，Generate 稍後渲染進 `{tab}_results`）：
   - Near Generate → 掛 `{tab}_results`，Enqueue 列落在 Generate 前方同步移動。
   - Between → 掛 `{tab}_prompt_container`（提示詞下方、Generate 之前）。
   Compact layout (no toprow; Generate is rendered into `{tab}_results` later):
   - Near Generate → mount `{tab}_results` so the row sits in front of Generate
     and moves with it.
   - Between → mount `{tab}_prompt_container` (below the prompts, before Generate).
3. 非掛載時機（其他元件、elem_id 為 None）一律回傳 None，不誤掛。
   Non-mounting moments (other components, elem_id None) always return None.

執行
    python tests/test_enqueue_placement.py
    python tests/run_tests.py
"""

import sys
import unittest
from pathlib import Path

# 讓 _support 與 agent_scheduler 可被匯入（各種呼叫方式都成立）
# Make _support and agent_scheduler importable regardless of invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_scheduler.enqueue_placement import resolve_enqueue_mount_point  # noqa: E402


def resolve(id_part, component_elem_id, compact, between):
    """測試用的關鍵字參數包裝"""
    return resolve_enqueue_mount_point(
        id_part=id_part,
        component_elem_id=component_elem_id,
        compact=compact,
        between=between,
    )


class ClassicLayoutTest(unittest.TestCase):
    """classic 版面（A1111 預設、Forge 的 Default / Scrollable / Accordion）。

    The classic layout (A1111 default; Forge's Default / Scrollable / Accordion).
    """

    def test_near_generate_mounts_into_actions_column(self):
        self.assertEqual(
            resolve("txt2img", "txt2img_generate", compact=False, between=False),
            "txt2img_actions_column",
        )
        self.assertEqual(
            resolve("img2img", "img2img_generate", compact=False, between=False),
            "img2img_actions_column",
        )

    def test_between_mounts_into_toprow_at_negative_prompt(self):
        self.assertEqual(
            resolve("txt2img", "txt2img_neg_prompt", compact=False, between=True),
            "txt2img_toprow",
        )

    def test_results_container_is_not_a_mount_point(self):
        # classic 版面沒有把 Generate 渲染進 results，不能在這裡掛
        # The classic layout does not render Generate into results: no mounting here
        self.assertIsNone(
            resolve("txt2img", "txt2img_results", compact=False, between=False)
        )

    def test_wrong_moment_for_selected_placement_is_none(self):
        # 選 Near Generate 時不掛在提示詞；選 Between 時不掛在 generate
        # With Near Generate, do not mount at the prompt; with Between, not at Generate
        self.assertIsNone(
            resolve("txt2img", "txt2img_neg_prompt", compact=False, between=False)
        )
        self.assertIsNone(
            resolve("txt2img", "txt2img_generate", compact=False, between=True)
        )


class CompactLayoutTest(unittest.TestCase):
    """Compact 版面（Forge 的 prompt_box_style=Compact、A1111 的 compact_prompt_box）。

    The Compact layout (Forge prompt_box_style=Compact, A1111 compact_prompt_box).
    """

    def test_near_generate_mounts_into_results_with_generate(self):
        # Generate box 由 create_inline_toprow_image() 渲染進 results，
        # 因此 Enqueue 列掛在 results 內即與 Generate 同排同側
        # The Generate box is rendered into results by create_inline_toprow_image,
        # so mounting the Enqueue row there keeps it beside Generate
        self.assertEqual(
            resolve("txt2img", "txt2img_results", compact=True, between=False),
            "txt2img_results",
        )

    def test_generate_button_is_not_the_mount_point_in_compact(self):
        # Compact 沒有 {id_part}_actions_column，掛在 generate 時機會找不到容器
        # Compact has no {id_part}_actions_column, so the Generate moment has no container
        self.assertIsNone(
            resolve("txt2img", "txt2img_generate", compact=True, between=False)
        )

    def test_between_mounts_into_prompt_container(self):
        # Compact 沒有 {id_part}_toprow，提示詞容器才是「提示詞與 Generate 之間」
        # Compact has no {id_part}_toprow; the prompt container is the spot
        # between the prompt and Generate
        self.assertEqual(
            resolve("img2img", "img2img_neg_prompt", compact=True, between=True),
            "img2img_prompt_container",
        )

    def test_toprow_moment_is_skipped_in_compact(self):
        # 負向提示詞在 Between 時機不可掛 toprow（該容器不存在）
        # The negative-prompt moment must not mount into toprow (it does not exist)
        self.assertIsNone(
            resolve("txt2img", "txt2img_neg_prompt", compact=True, between=False)
        )

    def test_results_moment_is_skipped_when_between_selected(self):
        # 選 Between 時不在 results 掛載（已在提示詞時機掛好）
        # With Between selected, do not mount at results (already mounted at the prompt)
        self.assertIsNone(
            resolve("txt2img", "txt2img_results", compact=True, between=True)
        )


class NonMountingMomentTest(unittest.TestCase):
    """不是掛載時機的元件"""

    def test_unrelated_component_returns_none(self):
        for elem_id in (
            "txt2img_prompt",
            "txt2img_prompt_container",
            "txt2img_enqueue_wrapper",
            "txt2img_width",
        ):
            self.assertIsNone(
                resolve("txt2img", elem_id, compact=False, between=False), elem_id
            )
            self.assertIsNone(
                resolve("txt2img", elem_id, compact=True, between=True), elem_id
            )

    def test_missing_elem_id_returns_none(self):
        self.assertIsNone(resolve("txt2img", None, compact=False, between=False))
        self.assertIsNone(resolve("txt2img", "", compact=True, between=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
