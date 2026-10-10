"""
test_prompt_box_style.py — prompt_box_style 相容偵測的固定測試 / Permanent tests for prompt_box_style compatibility detection.

涵蓋:
1. supports_prompt_box_style()：以 ui_toprow 的實作（_container_class /
   create_prompts 內的讀取邏輯）判斷支援與否，而非只看選項存不存在。
   supports_prompt_box_style(): support is decided by the ui_toprow
   implementation (_container_class / how create_prompts reads the option),
   not merely by the option's existence.
   - A1111（只有 compact_prompt_box、沒有 prompt_box_style）→ 不支援。
   - 選項存在但 Toprow 沒有任何套用邏輯 → 不支援（關鍵回歸案例）。
   - 選項存在且 Toprow 有 _container_class 或 create_prompts 內聯讀取 → 支援。
2. get_prompt_box_style()：不支援時回傳 None；支援時回傳選項值。
   get_prompt_box_style(): None when unsupported, the option value otherwise.
3. is_compact_prompt_box()：Compact 才為 True，並在不支援時退回 A1111
   的 compact_prompt_box 舊選項。
   is_compact_prompt_box(): True only for Compact, falling back to A1111's
   legacy compact_prompt_box option when the new API is unsupported.
4. is_compact_layout()：純以元件結構（generate-box-compact /
   prompt-container-compact 標記 class）判斷，不依賴任何選項 API。
   is_compact_layout(): pure structural detection from marker classes,
   depending on no option API at all.

執行 / Run:
    python tests/test_prompt_box_style.py
    python tests/run_tests.py
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

# 讓 _support 與 agent_scheduler 可被匯入（各種呼叫方式都成立）
# Make _support and agent_scheduler importable regardless of invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_scheduler.compat_a1111_forge.prompt_box_style import (  # noqa: E402
    get_prompt_box_style,
    is_compact_layout,
    is_compact_prompt_box,
    supports_prompt_box_style,
)


class FakeOpts:
    """最小 shared.opts 替身：以屬性反映設定值 / Minimal shared.opts stand-in exposing options as attributes."""

    def __init__(self, **values):
        self.__dict__.update(values)


# ---------------------------------------------------------------------------
# Toprow 替身：原始碼內容決定偵測結果，因此刻意寫成不同實作。
# Toprow stand-ins: their source text decides the detection result, so they
# are deliberately written as different implementations.
# ---------------------------------------------------------------------------


class ToprowWithContainerClass:
    """forge 形式：以 _container_class() 把選項套用到版面 / forge-style: applies the option via _container_class()."""

    @staticmethod
    def _container_class():
        return "prompt-container-compact"

    def create_prompts(self):
        return None


class ToprowInlineOptionReader:
    """內聯形式：沒有 _container_class()，但在 create_prompts 直接讀取選項。

    Inline style: no _container_class(), but create_prompts reads the option.
    """

    def create_prompts(self):
        # 模擬「shared.opts.prompt_box_style 直接寫在 create_prompts 裡」的實作
        # Simulates an implementation that reads shared.opts.prompt_box_style inline
        option_name = "prompt_box_style"
        return option_name


class ToprowWithoutOption:
    """選項存在但 Toprow 完全不套用（模擬「有選項、無實作」的分支）。

    The option exists but Toprow never applies it (simulates a fork shipping
    the option without the implementation).
    """

    def create_prompts(self):
        return "prompt-container-compact"


# ---------------------------------------------------------------------------
# 元件樹替身 / Component tree stand-ins
# ---------------------------------------------------------------------------


class FakeBlock:
    """最小 gradio Block 替身：只需要 elem_id / elem_classes / parent。

    Minimal gradio Block stand-in: only elem_id / elem_classes / parent matter.
    """

    def __init__(self, elem_id=None, elem_classes=None, parent=None):
        self.elem_id = elem_id
        self.elem_classes = elem_classes
        self.parent = parent
        self.children = []

    def add(self, child):
        child.parent = self
        self.children.append(child)


class WebuiStubTestBase(unittest.TestCase):
    """共用的 modules.* 替身安裝 / Shared installation of the modules.* stand-ins."""

    def install_webui(self, opts=None, toprow=None, with_ui_toprow=True):
        """把假的 modules / modules.shared / modules.ui_toprow 放進 sys.modules。

        Put fake modules / modules.shared / modules.ui_toprow into sys.modules.
        """
        modules = types.ModuleType("modules")
        # 標示為套件，讓「子模組不存在」有明確的失敗點
        # Mark as a package so a missing submodule fails at a well-defined point
        modules.__path__ = []

        shared_mod = types.ModuleType("modules.shared")
        shared_mod.opts = opts if opts is not None else FakeOpts()
        modules.shared = shared_mod

        sys_modules = {"modules": modules, "modules.shared": shared_mod}

        if with_ui_toprow:
            ui_toprow_mod = types.ModuleType("modules.ui_toprow")
            ui_toprow_mod.Toprow = toprow
            modules.ui_toprow = ui_toprow_mod
            sys_modules["modules.ui_toprow"] = ui_toprow_mod

        patcher = mock.patch.dict(sys.modules, sys_modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        return modules


class SupportsPromptBoxStyleTest(WebuiStubTestBase):
    """supports_prompt_box_style() / get_prompt_box_style() 的判定 / Decisions of supports_prompt_box_style() and get_prompt_box_style()."""

    def test_a1111_without_option_is_unsupported(self):
        # 只有 compact_prompt_box、沒有 prompt_box_style → 不支援
        # Only compact_prompt_box, no prompt_box_style → unsupported
        self.install_webui(
            opts=FakeOpts(compact_prompt_box=True),
            toprow=ToprowWithContainerClass,
        )

        self.assertFalse(supports_prompt_box_style())
        self.assertIsNone(get_prompt_box_style())
        # 舊選項仍然有效 / The legacy option still works
        self.assertTrue(is_compact_prompt_box())

    def test_option_without_implementation_is_unsupported(self):
        # 關鍵案例：選項存在但 ui_toprow 沒有套用邏輯 → 不能視為支援
        # Key case: option exists but ui_toprow never applies it → not supported
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Compact"),
            toprow=ToprowWithoutOption,
        )

        self.assertFalse(supports_prompt_box_style())
        self.assertIsNone(get_prompt_box_style())
        # 不支援時不得把 Compact 當真 / Compact must not be trusted when unsupported
        self.assertFalse(is_compact_prompt_box())

    def test_container_class_implementation_is_supported(self):
        # forge 形式：有 _container_class() 即代表選項真的會套用到版面
        # forge-style: a _container_class() means the option really drives the layout
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Compact"),
            toprow=ToprowWithContainerClass,
        )

        self.assertTrue(supports_prompt_box_style())
        self.assertEqual(get_prompt_box_style(), "Compact")
        self.assertTrue(is_compact_prompt_box())

    def test_non_compact_style_is_not_compact(self):
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Scrollable"),
            toprow=ToprowWithContainerClass,
        )

        self.assertTrue(supports_prompt_box_style())
        self.assertEqual(get_prompt_box_style(), "Scrollable")
        self.assertFalse(is_compact_prompt_box())

    def test_inline_reader_in_create_prompts_is_supported(self):
        # 沒有 _container_class()，但 create_prompts 內聯讀取選項 → 支援
        # No _container_class(), but create_prompts reads the option inline → supported
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Compact"),
            toprow=ToprowInlineOptionReader,
        )

        self.assertTrue(supports_prompt_box_style())
        self.assertTrue(is_compact_prompt_box())

    def test_missing_toprow_class_is_unsupported(self):
        # ui_toprow 模組存在但沒有 Toprow → 無法證實實作 → 不支援
        # ui_toprow exists but has no Toprow → implementation unprovable → unsupported
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Compact"),
            toprow=None,
        )

        self.assertFalse(supports_prompt_box_style())
        self.assertFalse(is_compact_prompt_box())

    def test_missing_ui_toprow_module_is_unsupported(self):
        # ui_toprow 模組不存在 → 不支援，且不得拋例外
        # ui_toprow module missing → unsupported, and must not raise
        self.install_webui(
            opts=FakeOpts(prompt_box_style="Compact"),
            with_ui_toprow=False,
        )

        self.assertFalse(supports_prompt_box_style())
        self.assertFalse(is_compact_prompt_box())

    def test_missing_modules_package_is_unsupported(self):
        # 完全沒有 modules.*（脫離 webui 執行）→ 安全回傳 False，不拋例外
        # No modules.* at all (running outside the webui) → safe False, no exception
        with mock.patch.dict(sys.modules, {"modules": None}):
            self.assertFalse(supports_prompt_box_style())
            self.assertFalse(is_compact_prompt_box())


class IsCompactLayoutTest(unittest.TestCase):
    """is_compact_layout() 的純結構偵測 / Pure structural detection in is_compact_layout()."""

    def test_detects_generate_box_compact_marker(self):
        generate_box = FakeBlock(
            elem_id="txt2img_generate_box",
            elem_classes=["gradio-row", "generate-box", "generate-box-compact"],
        )
        generate = FakeBlock(elem_id="txt2img_generate", parent=generate_box)

        self.assertTrue(is_compact_layout(generate))

    def test_detects_prompt_container_marker_on_grandparent(self):
        prompt_container = FakeBlock(
            elem_id="txt2img_prompt_container",
            elem_classes=["gradio-column", "prompt-container-compact"],
        )
        prompt_row = FakeBlock(elem_id="txt2img_neg_prompt_row", parent=prompt_container)
        neg_prompt = FakeBlock(elem_id="txt2img_neg_prompt", parent=prompt_row)

        self.assertTrue(is_compact_layout(neg_prompt))

    def test_rejects_non_compact_markers(self):
        # Scrollable 版面有 prompt-container-scroll，但不是 Compact
        # The Scrollable layout has prompt-container-scroll, which is not Compact
        prompt_container = FakeBlock(
            elem_classes=["gradio-column", "prompt-container-scroll"],
        )
        prompt_row = FakeBlock(elem_classes=["gradio-row"], parent=prompt_container)
        prompt = FakeBlock(elem_classes=["gradio-textbox"], parent=prompt_row)

        self.assertFalse(is_compact_layout(prompt))

    def test_handles_elem_classes_as_plain_string(self):
        generate_box = FakeBlock(elem_classes="generate-box-compact")
        generate = FakeBlock(parent=generate_box)

        self.assertTrue(is_compact_layout(generate))

    def test_handles_missing_or_none_component(self):
        self.assertFalse(is_compact_layout(None))
        self.assertFalse(is_compact_layout(FakeBlock()))
        self.assertFalse(is_compact_layout(object()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
