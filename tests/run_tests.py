#!/usr/bin/env python3
"""
run_tests.py — 執行 tests/ 底下的測試：全部、指定檔案或 glob

用法
    pyrun.bat tests/run_tests.py                          # 全部 test_*.py（預設）
    pyrun.bat tests/run_tests.py tests/test_compat_ui.py  # 指定檔案（相對目前工作目錄）
    pyrun.bat tests/run_tests.py test_compat_ui.py        # 只給檔名 → 相對 tests/ 尋找
    pyrun.bat tests/run_tests.py "tests/test_compat*.py"  # glob（* ? [...] 與 **）
    pyrun.bat tests/run_tests.py tests/                   # 目錄 → 掃描其下 test_*.py
    pyrun.bat tests/run_tests.py -v                       # 詳細輸出（預設已為 verbosity=2）

    可同時給多個引數；同一檔案被匹配多次時只執行一次（依輸入順序去重）。

依賴
    僅 Python 標準庫（unittest），不需 pytest；被測模組只用到 sd-webui 環境
    本就存在的 gradio / requests，因此請以「sd-webui 自己的 Python」執行。

環境變數
    AGENT_SCHEDULER_TEST_DIR
        指定測試產物的根目錄（預設系統暫存目錄）。

回傳值
    0 = 全部通過；1 = 有失敗；2 = 引數錯誤，或指定的檔案 / glob 沒對應到任何測試
"""

import glob
import importlib.util
import sys
import traceback
import unittest
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

TESTS_DIR = Path(__file__).resolve().parent


def expand_patterns(patterns: Sequence[str]) -> Tuple[List[Path], List[str]]:
    """把路徑 / glob 引數展開成測試檔（或目錄）清單

    每個引數先相對「目前工作目錄」展開、再相對 tests/ 展開，
    因此 `tests/test_x.py`、`test_x.py`、`test_x*.py` 三種寫法都成立。

    @param patterns - 使用者輸入的路徑或 glob 字串
    @returns (展開後的檔案/目錄絕對路徑, 沒匹配到任何東西的引數)
    """
    files: List[Path] = []
    seen = set()
    unmatched: List[str] = []

    for raw in patterns:
        hits: List[Path] = []
        for base in (Path.cwd(), TESTS_DIR):
            for hit in glob.glob(str(base / raw), recursive=True):
                path = Path(hit)
                # 只接受測試檔與目錄；README 等非 .py 檔視為未匹配
                if path.is_dir() or path.suffix == ".py":
                    hits.append(path)
        if not hits:
            unmatched.append(raw)
            continue
        for path in hits:
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            files.append(key)
    return files, unmatched


def import_failure_test(path: Path, detail: str) -> unittest.TestCase:
    """把「測試檔載入失敗」轉成一個失敗測試，讓錯誤出現在報告裡而非直接中斷

    @param path - 載入失敗的測試檔
    @param detail - 失敗原因（含 traceback 文字）
    @returns 表示載入失敗的 TestCase
    """

    class ImportFailure(unittest.TestCase):
        def runTest(self) -> None:
            self.fail(f"failed to load test module {path}:\n{detail}")

    return ImportFailure()


def load_test_module(path: Path, loader: unittest.TestLoader) -> unittest.TestSuite:
    """以檔案路徑載入測試模組並收集測試

    @param path - 測試檔路徑
    @param loader - unittest 測試載入器
    @returns 測試 suite；載入失敗時內含一個失敗測試
    """
    name = path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    suite = unittest.TestSuite()
    if spec is None or spec.loader is None:
        suite.addTest(import_failure_test(path, f"cannot build module spec: {path}"))
        return suite

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # 移除半成品模組，避免後續 import 續用到它
        # Drop the half-initialized module so later imports do not reuse it.
        sys.modules.pop(name, None)
        suite.addTest(import_failure_test(path, traceback.format_exc()))
        return suite
    suite.addTests(loader.loadTestsFromModule(module))
    return suite


def discover_dir(directory: Path) -> unittest.TestSuite:
    """掃描目錄底下的 test_*.py

    每次呼叫都用新 loader：unittest.TestLoader.discover 會沿用前一次的
    top_level_dir，共用同一個 loader 會讓不同目錄互相干擾。

    @param directory - 要掃描的目錄
    @returns 測試 suite
    """
    return unittest.TestLoader().discover(start_dir=str(directory), pattern="test_*.py")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    verbosity = 2
    patterns: List[str] = []

    for arg in args:
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        if arg in ("-v", "--verbose"):
            verbosity = 2
        elif arg in ("-q", "--quiet"):
            verbosity = 1
        elif arg.startswith("-") and arg != "-":
            print(f"unknown option: {arg}", file=sys.stderr)
            print(__doc__, file=sys.stderr)
            return 2
        else:
            patterns.append(arg)

    # 讓 discover 與 test_* 模組都能找到 _support
    # Let discover and the test_* modules resolve _support.
    if str(TESTS_DIR) not in sys.path:
        sys.path.insert(0, str(TESTS_DIR))

    if patterns:
        files, unmatched = expand_patterns(patterns)
        if unmatched:
            for raw in unmatched:
                print(f"no tests matched: {raw}", file=sys.stderr)
            return 2

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for path in files:
            suite.addTests(discover_dir(path) if path.is_dir() else load_test_module(path, loader))

        if suite.countTestCases() == 0:
            print("no tests loaded from the given sources", file=sys.stderr)
            return 2
    else:
        suite = discover_dir(TESTS_DIR)

    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
