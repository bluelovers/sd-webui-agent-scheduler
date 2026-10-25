"""webui 提示訊息（toast）的共用入口

呼叫端不直接呼叫 gradio 的提示函式，一律走 notify_message：之後若要換成別的
提示 API（例如 gr.toast），只需改這個模組。
Callers never call gradio's notification functions directly; they go through
notify_message, so switching to a different notification API later (gr.toast,
for example) only means editing this module.

api 風格與 print_message 對齊：同樣用 level 決定等級，to_print 可順便印到終端。
"""

import gradio as gr

from agent_scheduler.log import print_message, with_prefix

__all__ = ["notify_message"]

# 等級名 → gradio 的提示函式名；呼叫時才取用，
# 避免載入本檔時就要求 gradio 一定提供該符號
_NOTIFY_FNS = {"info": "Info", "warning": "Warning", "error": "Error"}


def notify_message(message, *, level="info", to_print=False, no_prefix=False):
    """顯示一則 webui 提示訊息，可順便印到終端

    @param message - 訊息本體；輸出前統一加上 [AgentScheduler]
    @param level - 等級名（_NOTIFY_FNS 的鍵）：info / warning / error
    @param to_print - True 時同一段文字再以 print_message 印到終端（預設不印）
    @param no_prefix - True 時不加前綴
    """
    if level not in _NOTIFY_FNS:
        raise ValueError(f"unknown level: {level!r}, expected one of {sorted(_NOTIFY_FNS)}")

    getattr(gr, _NOTIFY_FNS[level])(with_prefix(message, no_prefix=no_prefix))

    if to_print:
        print_message(message, level=level, no_prefix=no_prefix)
