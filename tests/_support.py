"""
_support.py — 測試共用基礎設施 / Shared infrastructure for the test suite.

設計原則:
1. 只使用 Python 標準庫（unittest / pathlib / tempfile / shutil / json），
   不引入 pytest 等任何額外測試框架。
2. 被測模組（task_output、shared_opts_backup）刻意不依賴 sd-webui 的 modules.*，
   連 logger 都取自純標準庫的 agent_scheduler/log.py（而非會 import gradio 的
   helpers.py），因此**任何 Python 解釋器都能跑**，不需要 webui、也不需要 gradio。
3. 測試產物寫入可由環境變數 AGENT_SCHEDULER_TEST_DIR 指定的目錄
   （預設系統暫存目錄），同名工作目錄每次執行前會先清空。
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Union

# 本檔所在 = tests/；其上一層即擴充根目錄（agent_scheduler 套件所在）
TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

# 匯入本模組時即把擴充根目錄加入 sys.path，讓 `import agent_scheduler.*` 可用

# for every test module that imports this support file.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def ensure_self_on_path() -> None:
    """確保 tests/ 在 sys.path 上（供以 `python -m unittest tests.test_x` 執行時使用）。
    Make sure tests/ is on sys.path (for `python -m unittest tests.test_x`)."""
    path = str(TESTS_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


def workspace(name: str) -> Path:
    """
    建立一個「乾淨」的測試工作目錄（同名者先整個刪除）。
    Create a clean workspace for a test (an existing one is removed first).

    參數 / Parameters
    ----------
    name : str
        工作目錄名稱，建議使用測試類別名稱以便對照。
        Workspace name; using the test class name keeps it recognizable.
    """
    base_env = os.environ.get("AGENT_SCHEDULER_TEST_DIR", "").strip()
    base = Path(base_env).expanduser() if base_env else Path(tempfile.gettempdir())
    target = base.joinpath("agent_scheduler_tests", name)
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    return target


def posix(path: Optional[Union[Path, str]]) -> Optional[str]:
    """把路徑轉成 posix 字串；None 仍為 None（供斷言用）。
    Convert a path to a posix string; None stays None (for assertions)."""
    if path is None:
        return None
    return Path(path).as_posix()


def make_task_tree(task_dir: Path, *relative_dirs: str) -> Path:
    """建立任務資料夾與其下的子目錄（模擬 change_output_dir 建出的結構）。
    Create the task folder plus its sub-directories (mirrors what change_output_dir builds)."""
    task_dir.mkdir(parents=True, exist_ok=True)
    for rel in relative_dirs:
        task_dir.joinpath(rel).mkdir(parents=True, exist_ok=True)
    return task_dir


def read_text(path: Path) -> str:
    """讀取文字檔；不存在時回傳空字串，方便斷言。
    Read a text file; return an empty string when missing so assertions stay simple."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def sub_dirs(path: Path) -> List[str]:
    """列出目錄下所有子目錄名稱。
    List the names of all sub-directories under the given path."""
    return sorted(p.name for p in path.iterdir() if p.is_dir())
