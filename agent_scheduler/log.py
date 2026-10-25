"""
log.py — Agent Scheduler 的日誌設定（純標準庫，不相依 gradio）

為什麼獨立成檔
日誌是「檔案系統維護類」模組（task_output、shared_opts_backup）與單元測試都需要的最基礎能力。
原本放在 helpers.py，會迫使這些模組連帶 import gradio，
導致單元測試必須在已安裝 webui 的環境下才跑得起來。
抽出後只需標準庫即可使用同一個 logger，單元測試也能在任何 Python 解釋器下執行（見 tests/README.md）。

print_message — 擴充的 print / log 統一入口
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
        為不同等級的日誌加上終端機顏色

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
    # 建立專屬的 AgentScheduler logger，不向上層傳播以免重複輸出
    logger = logging.getLogger("AgentScheduler")
    logger.propagate = False

    # Add handler if we don't have one.
    # 若尚未有處理器，則加入帶彩色格式的 stdout 處理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)

    # Configure logger
    # 預設日誌等級設為 INFO
    loglevel = logging.INFO
    logger.setLevel(loglevel)

    log = logger

# 終端輸出的統一前綴：擴充的 print 都由 print_message 加上，字面值只存這一處
MESSAGE_PREFIX = "[AgentScheduler]"

# print_message 可指定的顏色名 → ANSI 序列；只包住終端輸出，寫入 log 的文字保持無色
_COLORS = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}
_RESET = "\033[0m"

# to_log 時的等級名稱 → logging 等級
_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def print_message(message, *, color=None, log_only=False, to_log=False, level="info", no_prefix=False):
    """印出一行擴充訊息，可指定終端顏色，也可只寫或同時寫入 log

    @param message - 訊息本體；prefix=True 時輸出前統一加上 [AgentScheduler]
    @param color - 終端顏色名（_COLORS 的鍵），None 表示不上色；log_only 時不使用
    @param log_only - True 時只寫入 log、不印終端，讓原本只走 log 的訊息維持舊有行為
    @param to_log - True 時把同一段文字（不帶顏色）再寫入一次 log
    @param level - 這則訊息的等級名（_LOG_LEVELS 的鍵）：to_log / log_only 寫入 log 時
        依此決定等級；未寫入 log 時仍保留呼叫端宣告的等級，方便之後開啟 log 輸出
    @param no_prefix - True 時不加前綴
    """
    write_log = log_only or to_log

    if level not in _LOG_LEVELS:
        raise ValueError(f"unknown level: {level!r}, expected one of {sorted(_LOG_LEVELS)}")
    if not log_only and color is not None and color not in _COLORS:
        raise ValueError(f"unknown color: {color!r}, expected one of {sorted(_COLORS)}")

    message_text = str(message)
    if not no_prefix and MESSAGE_PREFIX not in message_text:
        message_text = f"{MESSAGE_PREFIX} {message_text}"
    text = message_text

    if not log_only:
        if color is None:
            print(text)
        else:
            print(f"{_COLORS[color]}{text}{_RESET}")

    if write_log:
        log.log(_LOG_LEVELS[level], text)
