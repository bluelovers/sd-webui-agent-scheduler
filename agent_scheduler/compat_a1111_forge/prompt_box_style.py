"""prompt 版面選項（prompt_box_style）的版本相容工具 / Version-compatible helpers for the prompt box layout option (prompt_box_style)

Forge 提供 shared.opts.prompt_box_style（Default / Compact / Scrollable / Accordion），
A1111 則使用舊的 compact_prompt_box 布林選項，兩者介面不同。
Forge exposes shared.opts.prompt_box_style (Default / Compact / Scrollable /
Accordion) while A1111 uses the legacy compact_prompt_box boolean; the two
interfaces differ.

所有對 sd-webui API 的存取都以「該 API 可能不存在於此版本」為前提，
因此一律用 getattr / try-import 並回傳安全的預設值，確保向後相容。
Every access to a sd-webui API assumes that API may be missing in this
version, so getattr / try-import plus safe defaults are used everywhere to
keep backward compatibility.
"""

import inspect

from typing import Any, List, Optional

# Compact 版面的選項值與 ui_toprow 產生的標記 class
# The option value of the Compact layout and the marker classes emitted by ui_toprow
PROMPT_BOX_STYLE_COMPACT = "Compact"
GENERATE_BOX_COMPACT_CLASS = "generate-box-compact"
PROMPT_CONTAINER_COMPACT_CLASS = "prompt-container-compact"

# 結構偵測時最多往上追溯的父層數 / How many parents to walk up during structural detection
_MAX_PARENT_DEPTH = 4


def _get_shared() -> Any:
    """取得 modules.shared；不存在時回傳 None / Get modules.shared, or None when unavailable."""
    try:
        from modules import shared
    except Exception:
        return None
    return shared


def _get_toprow_class() -> Any:
    """取得 modules.ui_toprow.Toprow；不存在時回傳 None / Get modules.ui_toprow.Toprow, or None when unavailable."""
    try:
        from modules import ui_toprow
    except Exception:
        return None
    return getattr(ui_toprow, "Toprow", None)


def _has_prompt_box_style_option(shared: Any) -> bool:
    """shared.opts 是否定義 prompt_box_style 選項 / Whether shared.opts defines the prompt_box_style option.

    注意：此判定只代表「有這個選項」，不代表 UI 真的會套用它，
    實作有無請交給 supports_prompt_box_style() 判斷。
    Note: this only proves the option exists, not that the UI applies it;
    use supports_prompt_box_style() to check the implementation.
    """
    opts = getattr(shared, "opts", None)
    if opts is None:
        return False
    try:
        return hasattr(opts, "prompt_box_style")
    except Exception:
        return False


def _mentions_prompt_box_style(fn: Any) -> Optional[bool]:
    """讀取函式原始碼是否使用 prompt_box_style；讀不到時回傳 None。

    Read whether the given callable's source references prompt_box_style;
    returns None when the source cannot be read (frozen / compiled builds).
    """
    if not callable(fn):
        return None
    try:
        source = inspect.getsource(fn)
    except Exception:
        return None
    return "prompt_box_style" in source


def supports_prompt_box_style() -> bool:
    """webui 是否「真的」實作 prompt_box_style 版面切換 / Whether the webui really implements the prompt_box_style layout switch.

    只看到 shared.opts.prompt_box_style 並不代表支援：必須由 ui_toprow 的實作佐證，
    包括 _container_class()（把選項轉成提示詞容器 class），或 create_prompts() /
    __init__() 內直接讀取 shared.opts.prompt_box_style 的邏輯。
    Merely seeing shared.opts.prompt_box_style does not prove support: the
    ui_toprow implementation must confirm it - either _container_class() (which
    maps the option to a prompt container class), or the way create_prompts() /
    __init__() reads shared.opts.prompt_box_style directly.

    @returns True 表示此 webui 支援 prompt_box_style 版面切換 / True when this webui
        supports the prompt_box_style layout switch
    """
    shared = _get_shared()
    if shared is None or not _has_prompt_box_style_option(shared):
        # 選項不存在（如 A1111）→ 不支援 / Option absent (e.g. A1111): unsupported
        return False

    toprow = _get_toprow_class()
    if toprow is None:
        # 找不到 Toprow 無法證實實作 → 不支援 / No Toprow to verify against: unsupported
        return False

    # 1) _container_class() 是 forge 把選項套用到版面的入口 / _container_class() is forge's entry point for applying the option
    if callable(getattr(toprow, "_container_class", None)):
        return True

    # 2) 檢查會讀取選項的函式，涵蓋「直接內聯、沒有 _container_class」的實作
    # Check the functions that read the option, covering inline implementations
    # that have no _container_class()
    judged: List[bool] = []
    for name in ("create_prompts", "__init__"):
        mentioned = _mentions_prompt_box_style(getattr(toprow, name, None))
        if mentioned is not None:
            judged.append(mentioned)
    if judged:
        return any(judged)

    # 3) 原始碼讀不到、也沒有 _container_class()：無法證實亦無法證偽，
    #    退回「選項存在」的弱判定，避免凍結/編譯發行誤判為不支援。
    # Sources unreadable and no _container_class(): neither provable nor
    # falsifiable, so fall back to weak option-presence detection to avoid
    # misjudging frozen/compiled builds as unsupported.
    return True


def get_prompt_box_style() -> Optional[str]:
    """取得 prompt_box_style 選項值；不支援時回傳 None / Get the prompt_box_style value, or None when unsupported.

    @returns 選項字串（Default / Compact / Scrollable / Accordion）或 None
        the option string, or None when this webui does not support the option
    """
    if not supports_prompt_box_style():
        return None

    shared = _get_shared()
    if shared is None:
        return None
    return getattr(getattr(shared, "opts", None), "prompt_box_style", None)


def is_compact_prompt_box() -> bool:
    """目前是否為 Compact 版面 / Whether the current layout is the Compact one.

    優先使用 webui 的 prompt_box_style（需先通過支援偵測）；
    不支援時退回 A1111 的 compact_prompt_box 舊選項，維持向後相容。
    Prefers the webui's prompt_box_style (which must pass support detection
    first), then falls back to A1111's legacy compact_prompt_box option for
    backward compatibility.

    @returns 是否為 Compact 版面 / whether the layout is compact
    """
    style = get_prompt_box_style()
    if style is not None:
        return style == PROMPT_BOX_STYLE_COMPACT

    # 舊版 A1111：以 compact_prompt_box 布林選項控制 / Legacy A1111: controlled by the compact_prompt_box boolean
    shared = _get_shared()
    if shared is None:
        return False
    return bool(getattr(getattr(shared, "opts", None), "compact_prompt_box", False))


def is_compact_layout(component: Any) -> bool:
    """以「實際建立出來的元件結構」判斷是否為 Compact 版面 / Detect the Compact layout from the component tree that was actually built.

    ui_toprow 只在 Compact 時給 generate box 加上 generate-box-compact、
    給提示詞容器加上 prompt-container-compact，因此比對這些標記 class
    就是最直接的證據（元件本身或其上層任一命中即成立）。
    ui_toprow only adds generate-box-compact to the generate box and
    prompt-container-compact to the prompt container when Compact is active,
    so matching those marker classes (on the component itself or any of its
    parents) is the most direct evidence available.

    此函式不依賴任何選項 API，完全以元件結構判斷；參數可能為 None 或
    無 elem_classes / parent 的替身物件，皆以安全預設值處理。
    This function relies on no option API at all; the argument may be None or
    a stand-in without elem_classes / parent, and safe defaults are used.

    @param component - 起始元件（通常是當前觸發 after_component 的元件）
        the starting component (typically the one triggering after_component)
    @returns 是否為 Compact 版面 / whether the layout is compact
    """
    node = component
    for _ in range(_MAX_PARENT_DEPTH):
        if node is None:
            break
        classes = getattr(node, "elem_classes", None)
        if isinstance(classes, str):
            classes = [classes]
        if classes and (
            GENERATE_BOX_COMPACT_CLASS in classes
            or PROMPT_CONTAINER_COMPACT_CLASS in classes
        ):
            return True
        node = getattr(node, "parent", None)
    return False
