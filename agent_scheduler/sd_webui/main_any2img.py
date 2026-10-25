"""txt2img / img2img 主畫面的 Enqueue 列

sd-webui 逐一把元件建構出來時會呼叫 Script.after_component；本模組承接該
回呼的核心邏輯：捕捉 Generate 按鈕、判定版面（classic / Compact），並依使用者
設定把 Enqueue 列插進正確的容器。Enqueue 列本身的建立（add_enqueue_button）
與它用到的 checkpoint 選項（get_checkpoint_choices）也在這裡。

狀態都透過宿主 Script 物件（script 參數）存取，本模組不反向 import
scripts/task_scheduler.py，入口檔與功能模組因此互不牽連。
"""

import os
from collections import defaultdict
from typing import List

import gradio as gr

from modules import shared
from modules.shared import list_checkpoint_tiles, refresh_checkpoints
from modules.ui import create_refresh_button

from agent_scheduler.compat_a1111_forge.prompt_box_style import (
    is_compact_layout,
    is_compact_prompt_box,
)
from agent_scheduler.compat_a1111_forge.ui_components import ToolButton
from agent_scheduler.sd_webui.enqueue_placement import resolve_enqueue_mount_point
from agent_scheduler.sd_webui.ui_constants import (
    checkpoint_current,
    checkpoint_runtime,
    placement_between_prompt_and_generate,
    placement_under_generate,
)

__all__ = [
    "add_enqueue_button",
    "after_component",
    "get_checkpoint_choices",
]


def after_component(script, component, **_kwargs):
    """在每個 UI 元件建立後掛載 Enqueue 按鈕

    sd-webui 會在建構每個元件時呼叫此函式，我們藉此定位 generate 按鈕所在的容器，
    並依使用者設定的擺放位置把 Enqueue 列插入正確的位置。

    @param script - 宿主 Script 實例：讀取 is_img2img / enqueue_row /
        compact_layout，並呼叫其 add_enqueue_button()
    @param component - 剛建構完成的 UI 元件
    """
    # 依模式選擇對應的 elem_id 前綴
    id_part = "img2img" if script.is_img2img else "txt2img"

    enqueue_wrapper = f"{id_part}_enqueue_wrapper"
    generate_id = f"{id_part}_generate"

    # 目前元件的 elem_id
    component_elem_id = _kwargs.get('elem_id')

    # 先捕捉 generate 按鈕以備後續綁定
    if component_elem_id == generate_id:
        script.generate_button = component

    # 若 Enqueue 列已建立，或遇到不需處理的容器則提早結束
    if script.enqueue_row is not None:
        return
    elif component_elem_id is None or component_elem_id == enqueue_wrapper:
        return

    # Compact 版面偵測：先比對 webui 對 prompt_box_style 的實作與選項值，
    # 再以實際長出來的元件結構（generate-box-compact / prompt-container-compact）
    # 佐證；兩者皆以「API 可能不存在」為前提設計，缺 API 時自然退回舊版行為。
    compact_prompt_box = is_compact_prompt_box() or is_compact_layout(component)
    # 標記 class 只出現在前段元件（generate box / 提示詞容器），後段的 results
    # 容器本身沒有標記，因此一旦確認是 Compact 就沿用，避免掛載時機錯過
    if compact_prompt_box:
        script.compact_layout = True
    else:
        compact_prompt_box = script.compact_layout

    # 讀取影響按鈕擺放的使用者設定
    queue_button_placement = getattr(shared.opts, "queue_button_placement", placement_under_generate)

    # 是否選擇放在提示詞與生成按鈕之間
    bool_placement_between_prompt_and_generate = queue_button_placement == placement_between_prompt_and_generate

    def add_enqueue_row(elem_id):
        # 找到目標容器後插入 Enqueue 列；若元件已被放在錯誶的父層，則搬移到正確位置
        parent = component if elem_id is None or component.elem_id == elem_id else component.parent
        while parent is not None:
            if parent.elem_id is None or elem_id is None or parent.elem_id == elem_id:
                script.add_enqueue_button()
                if component.parent != parent:
                    # 目前的 render context 不是目標容器時才搬移；
                    # parent 可能尚未掛上父層（部分版本的元件建立順序不同），須防呆
                    if component.parent is not None:
                        component.parent.children.pop()
                    parent.add(script.enqueue_row)
                break
            parent = parent.parent

    # 依版面（classic / Compact）與設定解析掛載點，非掛載時機則不動作
    mount_point = resolve_enqueue_mount_point(
        id_part=id_part,
        component_elem_id=component_elem_id,
        compact=compact_prompt_box,
        between=bool_placement_between_prompt_and_generate,
    )
    if mount_point is not None:
        # 掛載到解析出的容器；classic 與 Compact 的落點不同，細節見 enqueue_placement
        add_enqueue_row(mount_point)


def add_enqueue_button(script):
    """建立 Enqueue 列（checkpoint 下拉、選項與便捷按鈕列、Enqueue 主按鈕）

    建立的元件都寫進宿主 Script 的欄位，事件綁定仍由入口檔的
    bind_enqueue_button 處理。

    @param script - 宿主 Script 實例：寫入 enqueue_row / checkpoint_dropdown /
        skip_change_output_dir_checkbox / pause_button / resume_button /
        unload_models_button / submit_button
    """
    id_part = "img2img" if script.is_img2img else "txt2img"
    with gr.Row(elem_id=f"{id_part}_enqueue_wrapper") as row:
        script.enqueue_row = row
        hide_checkpoint = getattr(shared.opts, "queue_button_hide_checkpoint", True)
        script.checkpoint_dropdown = gr.Dropdown(
            choices=get_checkpoint_choices(),
            value=checkpoint_current,
            show_label=False,
            interactive=True,
            visible=not hide_checkpoint,
        )
        # 當顯示 checkpoint 下拉時，提供重新整理按鈕以同步模型清單
        if not hide_checkpoint:
            create_refresh_button(
                script.checkpoint_dropdown,
                refresh_checkpoints,
                lambda: {"choices": get_checkpoint_choices()},
                f"refresh_{id_part}_checkpoint",
            )

        # 選項與便捷按鈕列放在主按鈕上方：外層 wrapper 是直向堆疊（column），
        # 自成一列才會並排，也才不會與 Enqueue 主按鈕等寬
        with gr.Row(elem_classes="agent_scheduler_quick_row"):
            # 「Disable output to agent-scheduler directory」(skip_change_output_dir)：
            # 勾選時該次任務不啟動 change_output_dir 機制。
            # 刻意不做記憶功能：不進設定、不進 localStorage，重載後一律回到未勾選；
            # 生效範圍只綁在勾選狀態下按下的那次 Enqueue 所產生的任務上。
            script.skip_change_output_dir_checkbox = gr.Checkbox(
                label="Disable output to agent-scheduler directory",
                value=False,
                elem_id=f"{id_part}_enqueue_skip_change_output_dir",
            )

            # 便捷按鈕沿用 ToolButton 的圖示按鈕（與 send to 同款、尺寸不搶主按鈕視覺）；
            # 顏色交由 variant 決定（stop、primary），不另寫樣式，說明放 tooltip；
            # 顯示狀態由 ui/src/extension/index.ts 與 Task Queue 頁籤那對一併處理
            paused = getattr(shared.opts, "queue_paused", False)
            script.pause_button = ToolButton(
                "⏸",
                elem_id=f"{id_part}_enqueue_pause",
                variant="stop",
                tooltip="Pause queue: queued tasks wait, the running one finishes",
                visible=not paused,
            )
            script.resume_button = ToolButton(
                "▶",
                elem_id=f"{id_part}_enqueue_resume",
                variant="primary",
                tooltip="Resume queue: start the next queued task",
                visible=paused,
            )

            # 一鍵卸載所有模型以釋放 VRAM 讓按鈕在列內自動靠右
            script.unload_models_button = ToolButton(
                "🧼",
                elem_id=f"{id_part}_enqueue_unload_models",
                elem_classes="ml-auto",
                tooltip="Unload all models and free VRAM",
            )

        # 實際的 Enqueue 主按鈕（列內最後一個、也是最大的一個）
        script.submit_button = gr.Button("Enqueue", elem_id=f"{id_part}_enqueue", variant="primary")


def get_checkpoint_choices():
    """建構 Enqueue 下拉選單的 checkpoint 選項

    除了個別 checkpoint 外，也依目錄分組提供「整個資料夾」選項，方便一次排程多個模型。
    """
    checkpoints: List[str] = list_checkpoint_tiles()

    # 統計各目錄下的 checkpoint 數量，用於分組選項
    checkpoint_dirs = defaultdict(lambda: 0)
    for checkpoint in checkpoints:
        checkpoint_dir = os.path.dirname(checkpoint)
        while checkpoint_dir != "" and checkpoint_dir != "/":
            checkpoint_dirs[checkpoint_dir] += 1
            checkpoint_dir = os.path.dirname(checkpoint_dir)

    choices = checkpoints
    choices.extend([f"{d} ({checkpoint_dirs[d]} checkpoints)" for d in checkpoint_dirs.keys()])
    choices = sorted(choices)

    # 固定將「當前 / 執行時」選項放在首位
    choices.insert(0, checkpoint_runtime)
    choices.insert(0, checkpoint_current)

    return choices
