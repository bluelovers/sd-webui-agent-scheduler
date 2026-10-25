"""
test_compat_ui.py — get_ui_task_error_message 的固定測試

wrap_gradio_call 例外時不重拋，改回傳 [None, '', "<div class='error'>...</div>"]，
錯誤訊息經過 html.escape 轉義。此測試鎖定「抽出純文字錯誤訊息」的行為，
確保任務失敗時真正原因能帶到日誌與清理報告。

執行
    pyrun-test.bat tests/test_compat_ui.py
"""

import sys
import unittest
from pathlib import Path

# 讓 _support 與 agent_scheduler 可被匯入（各種呼叫方式都成立）
# Make _support and agent_scheduler importable regardless of how this module is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 匯入 _support 會把擴充根目錄加入 sys.path（與其他測試檔相同機制）
# Importing _support puts the extension root on sys.path (same mechanism as the other test modules).
from _support import REPO_ROOT  # noqa: E402,F401

from agent_scheduler.compat_a1111_forge.ui import get_ui_task_error_text  # noqa: E402


class GetUiTaskErrorMessageTest(unittest.TestCase):
    """從 error div 抽出純文字錯誤訊息."""

    def test_extracts_and_unescapes_forge_error_div(self):
        """Forge 例外回傳：錯誤訊息經 html.escape 轉義，且同元素尾端接有 performance div。"""
        result = (
            None,
            "",
            "<div class='error'>RuntimeError: Prompt S/R did not find &quot;:0&gt;&quot; "
            "in either prompt or negative prompt...</div>"
            "<div class='performance'><p class='time'>Time taken: 1.2 sec.</p></div>",
        )
        message = get_ui_task_error_text(result)
        self.assertIn('Prompt S/R did not find ":0>"', message)
        self.assertNotIn("<div", message)
        self.assertNotIn("performance", message)

    def test_handles_double_quoted_error_div(self):
        """屬性引號可能為雙引號（相容不同版本的 HTML 寫法）。"""
        result = (None, "", """<div class="error">ValueError: bad input</div>""")
        self.assertEqual(get_ui_task_error_text(result), "ValueError: bad input")

    def test_handles_multi_line_message(self):
        """A1111 的錯誤訊息可能是「例外型別\\n訊息」多行格式，保留內部換行。"""
        result = (None, "", "<div class='error'>RuntimeError\nPrompt S/R not found</div>")
        self.assertEqual(
            get_ui_task_error_text(result),
            "RuntimeError\nPrompt S/R not found",
        )

    def test_returns_empty_without_error_div(self):
        """成功路徑沒有 error div → 回傳空字串，呼叫端據此判定無錯誤訊息。"""
        result = (["img"], '{"prompt": "cat"}', "<p>info</p>")
        self.assertEqual(get_ui_task_error_text(result), "")

    def test_ignores_non_string_items(self):
        """回傳元組中的非字串元素（如圖片陣列）一律略過。"""
        result = (None, "", None)
        self.assertEqual(get_ui_task_error_text(result), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
