#!/usr/bin/env python3
"""
run_tests.py — 一次執行 tests/ 底下所有測試

用法
    python tests/run_tests.py
    python tests/run_tests.py -v          # 詳細輸出（預設已為 verbosity=2）

依賴
    僅 Python 標準庫（unittest），不需 pytest；被測模組只用到 sd-webui 環境
    本就存在的 gradio / requests，因此請以「sd-webui 自己的 Python」執行。
    Standard library only (unittest); no pytest. The modules under test only
    need gradio / requests, which the sd-webui environment already ships, so run
    this with "sd-webui's own Python".

環境變數
    AGENT_SCHEDULER_TEST_DIR
        指定測試產物的根目錄（預設系統暫存目錄）。
        Root directory for test artifacts (defaults to the system temp dir).

回傳值
    0 = 全部通過；1 = 有失敗
"""

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


def main() -> int:
    # 讓 discover 與 test_* 模組都能找到 _support
    # Let discover and the test_* modules resolve _support.
    if str(TESTS_DIR) not in sys.path:
        sys.path.insert(0, str(TESTS_DIR))

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
