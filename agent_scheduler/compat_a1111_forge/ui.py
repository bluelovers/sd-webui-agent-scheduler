"""gradio UI 相依結構的版本相容工具"""

import html
import json
import re

from typing import Any, Dict, List, Optional

"""
統一取得 gradio Blocks 的 click 相依列表

舊版 gradio (A1111 classic) 以 root.dependencies 儲存，其元素為 dict，
包含 trigger / targets / inputs / outputs 等以元件 id 表示的欄位。
新版 gradio (Forge Neo, 4.x) 改以 root.fns 儲存 BlockFunction 物件，
targets 為 (id, event_name) 元組、inputs / outputs 為元件物件列表。
此函式將兩種結構正規化為舊版 dict 格式，供既有程式碼直接使用。
"""


def get_ui_dependencies(root: Any) -> List[Dict[str, Any]]:
    """取得正規化的 UI 相依列表

    @param root - gradio Blocks 實例
    @returns 正規化相依列表，元素格式為
        {"trigger": str, "targets": [int], "inputs": [int], "outputs": [int]}
    """
    if hasattr(root, "dependencies"):
        return root.dependencies

    dependencies: List[Dict[str, Any]] = []
    for fn in getattr(root, "fns", {}).values():
        trigger = fn.targets[0][1] if fn.targets else None
        dependencies.append(
            {
                "trigger": trigger,
                "targets": [block_id for block_id, _ in fn.targets],
                "inputs": [c._id for c in fn.inputs],
                "outputs": [c._id for c in fn.outputs],
            }
        )
    return dependencies


def get_ui_fns(root: Any) -> List[Any]:
    """取得 BlockFunction 物件列表

    新版 gradio 的 root.fns 為 dict，迭代時會得到 id 鍵而非函式物件；
    此 helper 統一回傳可迭代的 BlockFunction 列表。

    @param root - gradio Blocks 實例
    @returns BlockFunction 物件列表
    """
    fns = getattr(root, "fns", None)
    if isinstance(fns, dict):
        return list(fns.values())
    return list(fns) if fns else []


def get_ui_task_geninfo(result: Any) -> Any:
    """從 txt2img / img2img 的 UI 回傳元組中取出 generation info JSON 字串

    A1111 回傳 (images, geninfo, html_info, comments)，geninfo 位於索引 1。
    Forge 回傳 (gallery, video_arg, geninfo, html_info, comments)，geninfo 位於索引 2。
    以「字串且可解析為 JSON」定位 geninfo，因此兩種結構皆相容。

    @param result - wrap_gradio_call 的回傳元組
    @returns geninfo JSON 字串；找不到時回傳 None
    """
    # 從第 2 個元素開始掃描：geninfo 是「可解析為 JSON 的字串」。
    # 用 json.loads 探測而非寫死索引，因此 A1111 (idx 1) 與 Forge (idx 2) 皆相容。
    # Scan from the 2nd element onward: geninfo is "a string parseable as JSON".
    # Probing with json.loads (instead of hard-coding indices) keeps A1111 (idx 1)
    # and Forge (idx 2) both compatible.
    for item in result[1:]:
        if isinstance(item, str):
            try:
                json.loads(item)
                return item
            except (TypeError, ValueError):
                continue
    return None


# error div 的起始標籤：<div ... class="error" ...>；擷取 class 屬性值供後續判斷
# Opening tag of an error div: <div ... class="error" ...>; capture the class value for the check.
_ERROR_DIV_START_RE = re.compile(
    r"<div\b[^>]*?\bclass\s*=\s*(?P<q>['\"])(?P<cls>[^'\"]*)(?P=q)[^>]*>",
    re.IGNORECASE,
)

# 任何 <div> 開頭或 </div> 結尾標籤，供深度配對使用
# Any <div> start or </div> end tag, used for depth matching.
_DIV_TAG_RE = re.compile(r"<div\b|</div\s*>", re.IGNORECASE)


def _div_body_end(text: str, start: int) -> Optional[int]:
    """從 start 起掃描，回傳包住該 <div> 的 </div> 起始索引

    以深度配對（而非非貪婪抓第一個 </div>）處理巢狀 div，
    避免錯誤區塊後方的 performance 等同級 div 被誤併入訊息。

    @param text - 含有 error div 的 HTML 字串
    @param start - 開始標籤結束處的索引
    @returns 配對 </div> 的起始索引；標籤未閉合時回傳 None（取用字串其餘部分）
    """
    depth = 1
    for match in _DIV_TAG_RE.finditer(text, start):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return match.start()
        else:
            depth += 1
    return None


def get_ui_task_error_text(result: Any) -> str:
    """抽出 UI 回傳元組中 error div 的純文字錯誤訊息 / Extract the plain-text error

    A1111 與 Forge 在 wrap_gradio_call 捕獲例外後不重拋，改回傳
    [None, '', "<div class='error'>...</div><div class='performance'>...</div>"]；
    內文先經 html.escape 轉義，同一筆回傳還可能夾帶 performance 等非錯誤 div。
    此函式只取出 class 含 error 的 div 內文並還原轉義，讓呼叫端拿到可直接寫入
    日誌、掃描 "CUDA out of memory" 等關鍵字的純文字，而不必理會索引差異。

    @param result - wrap_gradio_call 的回傳元組
    @returns error div 的純文字訊息（多個以換行連接）；沒有 error div 時回傳 ""
    """
    messages: List[str] = []
    for item in result:
        if not isinstance(item, str):
            continue
        for match in _ERROR_DIV_START_RE.finditer(item):
            if "error" not in match.group("cls").split():
                continue
            end = _div_body_end(item, match.end())
            body = item[match.end():] if end is None else item[match.end():end]
            text = html.unescape(body).strip()
            if text:
                messages.append(text)
    return "\n".join(messages)