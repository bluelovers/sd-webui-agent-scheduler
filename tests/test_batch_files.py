"""批次檔與 PowerShell 檔的格式防護

Windows 上 cmd 讀取 .bat 的方式有三個已知陷阱，這裡用測試守住（只用標準庫）：

1. **用到標籤的 .bat 必須 CRLF**：cmd 的 ``call :label`` / ``goto :label``
   標籤搜尋在 LF-only 檔案上會隨檔案變大而失效（實測全盛期 270+ 行的
   pyrun.bat 開始報「找不到處理常式」）。**不含標籤的 .bat**（例如薄啟動器
   pyrun.bat、run_tests_uv.bat）只有順序執行，行尾隨意，**不需要任何轉換**。
2. **OEM / ANSI 程式碼頁**：cmd 依 OEM 程式碼頁（cp950 / GBK）解讀 .bat，
   PowerShell 5.1 讀取無 BOM 的 .ps1 也會用 ANSI 程式碼頁 — 兩者一旦出現
   非 ASCII 就會亂碼，甚至讓 cmd 解析錯行，所以 .bat / .ps1 一律純 ASCII。
3. **rem 行重導向**：``>`` / ``|`` 需以 ``^`` 跳脫，避免不同 Windows 版本把
   註解行當指令解析、建立多餘檔案。

"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BAT_FILES = sorted(REPO_ROOT.glob("*.bat")) + sorted((REPO_ROOT / "tests").glob("*.bat"))
PS_FILES = sorted(REPO_ROOT.glob("*.ps1"))

# 用到批次標籤的程式碼
LABEL_USE = re.compile(r"(call|goto)\s+:", re.IGNORECASE)

# rem 行上未跳脫的重導向字元
UNESCAPED_REDIRECT = re.compile(r"(?<!\^)[>|]")


class BatchLineEndingTest(unittest.TestCase):
    def test_label_using_batch_files_use_crlf(self):
        for bat in BAT_FILES:
            if not self._uses_labels(bat):
                # Label-free launcher: sequential execution only, so the line
                # endings are irrelevant and nothing ever needs converting.
                continue
            data = bat.read_bytes()
            self.assertEqual(
                data.count(b"\n"),
                data.count(b"\r\n"),
                f"{bat.name}: uses batch labels (call : / goto :) and therefore "
                "needs CRLF; cmd's label search fails on LF-only files",
            )

    @staticmethod
    def _uses_labels(path):
        # Comment lines are ignored: a rem line may merely DESCRIBE labels
        # ("cmd's call :label search is unreliable ...") without jumping to
        # one, and that must not force the file back to CRLF.
        for line in path.read_text(encoding="ascii").splitlines():
            if line.lower().startswith("rem") or line.startswith("::"):
                continue
            if LABEL_USE.search(line):
                return True
        return False


class AsciiOnlyTest(unittest.TestCase):
    def test_batch_files_are_ascii(self):
        for bat in BAT_FILES:
            self._assert_ascii(bat)

    def test_ps1_files_are_ascii(self):
        for ps1 in PS_FILES:
            self._assert_ascii(ps1)

    def _assert_ascii(self, path):
        data = path.read_bytes()
        offenders = sorted({byte for byte in data if byte > 127})
        self.assertFalse(
            offenders,
            f"{path.name}: non-ASCII bytes {offenders}; "
            "cmd uses the OEM code page, PowerShell 5.1 the ANSI code page",
        )


class RemLineRedirectTest(unittest.TestCase):
    def test_rem_lines_escape_redirect_characters(self):
        for bat in BAT_FILES:
            for number, line in enumerate(
                bat.read_text(encoding="ascii").splitlines(), start=1
            ):
                if not line.lower().startswith("rem"):
                    continue
                match = UNESCAPED_REDIRECT.search(line)
                # The message is built only when there really is a violation:
                # passing match.group() to assertIsNone would be evaluated
                # eagerly and raise AttributeError on every clean line.
                if match is not None:
                    self.fail(
                        f"{bat.name}:{number}: unescaped {match.group()!r} on a "
                        "rem line; cmd may parse it as a redirect - use ^"
                    )


if __name__ == "__main__":
    unittest.main()
