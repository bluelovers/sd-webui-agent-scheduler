"""
log.py — Agent Scheduler 的日誌設定（純標準庫，不相依 gradio）/ Logging setup for
the Agent Scheduler (standard library only, deliberately free of gradio).

為什麼獨立成檔 / Why this lives in its own module:
日誌是「檔案系統維護類」模組（task_output、shared_opts_backup）與單元測試都需要的
最基礎能力。原本放在 helpers.py，會迫使這些模組連帶 import gradio，導致單元測試必須
在已安裝 webui 的環境下才跑得起來。抽出後只需標準庫即可使用同一個 logger，單元測試
也能在任何 Python 解釋器下執行（見 tests/README.md）。
Logging is the most basic capability needed by the filesystem-maintenance modules
(task_output, shared_opts_backup) and by the unit tests. Sitting inside helpers.py it
forced them to pull in gradio, which meant the unit tests only ran inside a full webui
environment. With the logic extracted here the very same logger is available from the
standard library alone, so the unit tests run under any Python (see tests/README.md).

注意 / Note:
其他模組仍可從 helpers 匯入 log（helpers 由本檔取得同一個 logger 物件），
兩者永遠是同一個實例、行為一致。
Other modules may keep importing log from helpers: helpers obtains the same object
from this module, so both names always refer to one identical instance.
"""

import sys
import copy
import logging

# 若根 logger 已有處理器（通常由 sd-webui 啟動流程設定），直接沿用其 "sd" logger
# Reuse the existing "sd" logger if handlers are already configured on the root logger.
if logging.getLogger().hasHandlers():
    log = logging.getLogger("sd")
else:

    class ColoredFormatter(logging.Formatter):
        """
        為不同等級的日誌加上終端機顏色 / Add terminal colors to log records by level.

        為什麼需要：在 sd-webui 尚未配置日誌處理器時，提供具可讀性的彩色輸出。
        Why: when sd-webui has not configured logging, provide readable color-coded console output.
        """

        COLORS = {
            "DEBUG": "\033[0;36m",  # CYAN
            "INFO": "\033[0;32m",  # GREEN
            "WARNING": "\033[0;33m",  # YELLOW
            "ERROR": "\033[0;31m",  # RED
            "CRITICAL": "\033[0;37;41m",  # WHITE ON RED
            "RESET": "\033[0m",  # RESET COLOR
        }

        def format(self, record):
            colored_record = copy.copy(record)
            levelname = colored_record.levelname
            seq = self.COLORS.get(levelname, self.COLORS["RESET"])
            colored_record.levelname = f"{seq}{levelname}{self.COLORS['RESET']}"
            return super().format(colored_record)

    # Create a new logger
    # 建立專屬的 AgentScheduler logger，不向上層傳播以免重複輸出 / Create a dedicated logger that does not propagate to avoid duplicate output.
    logger = logging.getLogger("AgentScheduler")
    logger.propagate = False

    # Add handler if we don't have one.
    # 若尚未有處理器，則加入帶彩色格式的 stdout 處理器 / Attach a color-formatted stdout handler if none exists yet.
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)

    # Configure logger
    # 預設日誌等級設為 INFO / Default logging level is INFO.
    loglevel = logging.INFO
    logger.setLevel(loglevel)

    log = logger
