"""Enqueue 按鈕擺放解析

依「webui 版面（classic / Compact）＋ 使用者設定的擺放位置」解析 Enqueue 列
應該掛進哪個容器，讓按鈕在版面切換時能跟著 Generate 一起移動。

此模組刻意只用標準庫、不接觸任何 sd-webui API：純函式便於單元測試，
版本差異（哪些容器存在）則集中表現在下表：

| 版面 | Near Generate | Between Prompt and Generate |
|---|---|---|
| classic（有 `{tab}_toprow` / `{tab}_actions_column`） | `{tab}_actions_column`（Generate 下方） | `{tab}_toprow`（提示詞與 actions 之間） |
| Compact（無 toprow / actions_column，Generate 由 `Toprow.create_inline_toprow_image()` 渲染進 `{tab}_results`） | `{tab}_results`（Generate 上方，跟著 Generate 移動） | `{tab}_prompt_container`（提示詞下方） |
"""

from typing import Optional

__all__ = ["resolve_enqueue_mount_point"]


def resolve_enqueue_mount_point(
    id_part: str,
    component_elem_id: Optional[str],
    compact: bool,
    between: bool,
) -> Optional[str]:
    """解析 Enqueue 列的掛載容器

    由 after_component 依序對每個元件呼叫：只有當「目前這個元件」正是
    對應版面的掛載時機時才回傳容器 id，其餘回傳 None（不掛載）。

    @param id_part - 版面前綴（txt2img / img2img）
    @param component_elem_id - 目前元件的 elem_id，可能為 None
    @param compact - 是否為 Compact 版面
    @param between - 是否選用「提示詞與 Generate 之間」擺放
    @returns 應掛載的容器 elem_id；此元件不是掛載時機時回傳 None
    """
    if not component_elem_id:
        return None

    generate_id = f"{id_part}_generate"
    neg_id = f"{id_part}_neg_prompt"
    results_id = f"{id_part}_results"
    actions_column_id = f"{id_part}_actions_column"
    toprow_id = f"{id_part}_toprow"
    prompt_container_id = f"{id_part}_prompt_container"

    # Generate 按鈕建立時：classic 版面的 actions column 就在它下方
    if component_elem_id == generate_id:
        if not compact and not between:
            return actions_column_id

    # 負向提示詞建立時：「介於提示詞與 Generate 之間」的落點
    elif component_elem_id == neg_id:
        if between:
            return prompt_container_id if compact else toprow_id

    # results 容器建立時：Compact 的 Generate 稍後才渲染進來，先放好即與它同步
    elif component_elem_id == results_id:
        if compact and not between:
            return results_id

    return None
