"""Agent Scheduler 頁籤 UI（Task Queue / Task History）

本模組負責建立獨立分頁的介面、註冊分頁內的事件處理器，並提供把結果送往其他
分頁的按鈕；排程器入口（scripts/task_scheduler.py）只負責註冊這個頁籤。
"""

import os
import json
from typing import List

import gradio as gr
from PIL import Image

from modules import call_queue, shared
from modules.ui_common import save_files

from agent_scheduler.compat_a1111_forge.detect_webui_type import is_sdnext
from agent_scheduler.compat_a1111_forge.infotext import parse_generation_parameters
from agent_scheduler.compat_a1111_forge.paste_params import (
    ParamBinding,
    register_paste_params_button,
)
from agent_scheduler.compat_a1111_forge.ui_components import ToolButton
from agent_scheduler.db import task_manager, TaskStatus
from agent_scheduler.helpers import log
from agent_scheduler.sd_webui.ui_constants import (
    agent_scheduler_id,
    agent_scheduler_title,
    task_filter_choices,
)


def create_send_to_buttons():
    # 建立把結果送到其他分頁（txt2img/img2img/...）的按鈕組
    return {
        "txt2img": ToolButton(
            "➠ text" if is_sdnext else "📝",
            elem_id="agent_scheduler_send_to_txt2img",
            tooltip="Send generation parameters to txt2img tab.",
        ),
        "img2img": ToolButton(
            "➠ image" if is_sdnext else "🖼️",
            elem_id="agent_scheduler_send_to_img2img",
            tooltip="Send image and generation parameters to img2img tab.",
        ),
        "inpaint": ToolButton(
            "➠ inpaint" if is_sdnext else "🎨️",
            elem_id="agent_scheduler_send_to_inpaint",
            tooltip="Send image and generation parameters to img2img inpaint tab.",
        ),
        "extras": ToolButton(
            "➠ process" if is_sdnext else "📐",
            elem_id="agent_scheduler_send_to_extras",
            tooltip="Send image and generation parameters to extras tab.",
        ),
    }


def infotexts_to_geninfo(infotexts: List[str]):
    # 將多筆 infotext 彙整成 geninfo 結構，供前端展示
    all_promts = []
    all_seeds = []

    geninfo = {"infotexts": infotexts, "all_prompts": all_promts, "all_seeds": all_seeds, "index_of_first_image": 0}

    for infotext in infotexts:
        # Dynamic prompt 會破壞 infotext 排版，故移除 Template 行
        if "Template: " in infotext:
            lines = infotext.split("\n")
            lines = [l for l in lines if not (l.startswith("Template: ") or l.startswith("Negative Template: "))]
            infotext = "\n".join(lines)

        # 解析單筆 infotext 的產圖參數
        params = parse_generation_parameters(infotext)

        # 僅以第一筆作為整體 geninfo 的主要欄位
        if "prompt" not in geninfo:
            geninfo["prompt"] = params.get("Prompt", "")
            geninfo["negative_prompt"] = params.get("Negative prompt", "")
            geninfo["seed"] = params.get("Seed", "-1")
            geninfo["sampler_name"] = params.get("Sampler", "")
            geninfo["cfg_scale"] = params.get("CFG scale", "")
            geninfo["steps"] = params.get("Steps", "0")
            geninfo["width"] = params.get("Size-1", "512")
            geninfo["height"] = params.get("Size-2", "512")

        all_promts.append(params.get("Prompt", ""))
        all_seeds.append(params.get("Seed", "-1"))

    return geninfo


def get_task_results(task_id: str, image_idx: int = None):
    # 依 task id 讀取結果並整理成前端要顯示的元件更新
    task = task_manager.get_task(task_id)

    galerry = None
    geninfo = None
    infotext = None
    # 任務不存在時不顯示內容
    if task is None:
        pass
    # 未完成的任務僅顯示狀態（失敗時附錯誤）
    elif task.status != TaskStatus.DONE:
        infotext = f"Status: {task.status}"
        if task.status == TaskStatus.FAILED and task.result:
            infotext += f"\nError: {task.result}"
    # 已完成的任務解析 result，準備圖片與 geninfo
    elif task.status == TaskStatus.DONE:
        try:
            result: dict = json.loads(task.result)
            images = result.get("images", [])
            geninfo = result.get("geninfo", None)
            if isinstance(geninfo, dict):
                infotexts = geninfo.get("infotexts", [])
            else:
                infotexts = result.get("infotexts", [])
                geninfo = infotexts_to_geninfo(infotexts)

            # 依 image_idx 決定顯示全部圖片或單張，並取對應的 infotext
            galerry = [Image.open(i) for i in images if os.path.exists(i)] if image_idx is None else gr.update()
            idx = image_idx if image_idx is not None else 0
            if idx < len(infotexts):
                infotext = infotexts[idx]
        # 解析失敗時回報錯誤而不中斷整個 UI
        except Exception as e:
            log.error(f"[AgentScheduler] Failed to load task result")
            log.error(e)
            infotext = f"Failed to load task result: {str(e)}"

    res = (
        gr.Textbox.update(infotext, visible=infotext is not None),
        gr.Row.update(visible=galerry is not None),
    )

    if image_idx is None:
        geninfo = json.dumps(geninfo) if geninfo else None
        res += (
            galerry,
            gr.Textbox.update(geninfo),
            gr.File.update(None, visible=False),
            gr.HTML.update(None),
        )

    return res


def on_ui_tab(**_kwargs):
    # Build the Agent Scheduler tab UI (queue + history)
    grid_page_size = getattr(shared.opts, "queue_grid_page_size", 0)

    with gr.Blocks(analytics_enabled=False) as scheduler_tab:
        with gr.Tabs(elem_id="agent_scheduler_tabs"):
            with gr.Tab("Task Queue", id=0, elem_id="agent_scheduler_pending_tasks_tab"):
                with gr.Row(elem_id="agent_scheduler_pending_tasks_wrapper"):
                    with gr.Column(scale=1):
                        with gr.Row(elem_id="agent_scheduler_pending_tasks_actions", elem_classes="flex-row"):
                            paused = getattr(shared.opts, "queue_paused", False)

                            gr.Button(
                                "Pause",
                                elem_id="agent_scheduler_action_pause",
                                variant="stop",
                                visible=not paused,
                            )
                            gr.Button(
                                "Resume",
                                elem_id="agent_scheduler_action_resume",
                                variant="primary",
                                visible=paused,
                            )
                            gr.Button(
                                "Refresh",
                                elem_id="agent_scheduler_action_reload",
                                variant="secondary",
                            )
                            gr.Button(
                                "Clear",
                                elem_id="agent_scheduler_action_clear_queue",
                                variant="stop",
                            )
                            gr.Button(
                                "Export",
                                elem_id="agent_scheduler_action_export",
                                variant="secondary",
                            )
                            gr.Button(
                                "Import",
                                elem_id="agent_scheduler_action_import",
                                variant="secondary",
                            )
                            gr.HTML(f'<input type="file" id="agent_scheduler_import_file" style="display: none" accept="application/json" />')

                            with gr.Row(elem_classes=["agent_scheduler_filter_container", "flex-row", "ml-auto"]):
                                gr.Textbox(
                                    max_lines=1,
                                    placeholder="Search",
                                    label="Search",
                                    show_label=False,
                                    min_width=0,
                                    elem_id="agent_scheduler_action_search",
                                )
                        gr.HTML(
                            f'<div id="agent_scheduler_pending_tasks_grid" class="ag-theme-gradio" data-page-size="{grid_page_size}"></div>'
                        )
                    with gr.Column(scale=1):
                        gr.Gallery(
                            elem_id="agent_scheduler_current_task_images",
                            label="Output",
                            show_label=False,
                            columns=2,
                            object_fit="contain",
                        )
            with gr.Tab("Task History", id=1, elem_id="agent_scheduler_history_tab"):
                with gr.Row(elem_id="agent_scheduler_history_wrapper"):
                    with gr.Column(scale=1):
                        with gr.Row(elem_id="agent_scheduler_history_actions", elem_classes="flex-row"):
                            gr.Button(
                                "Requeue Failed",
                                elem_id="agent_scheduler_action_requeue",
                                variant="primary",
                            )
                            gr.Button(
                                "Refresh",
                                elem_id="agent_scheduler_action_refresh_history",
                                elem_classes="agent_scheduler_action_refresh",
                                variant="secondary",
                            )
                            gr.Button(
                                "Clear",
                                elem_id="agent_scheduler_action_clear_history",
                                variant="stop",
                            )

                            with gr.Row(elem_classes=["agent_scheduler_filter_container", "flex-row", "ml-auto"]):
                                status = gr.Dropdown(
                                    elem_id="agent_scheduler_status_filter",
                                    choices=task_filter_choices,
                                    value="All",
                                    show_label=False,
                                    min_width=0,
                                )
                                gr.Textbox(
                                    max_lines=1,
                                    placeholder="Search",
                                    label="Search",
                                    show_label=False,
                                    min_width=0,
                                    elem_id="agent_scheduler_action_search_history",
                                )
                        gr.HTML(
                            f'<div id="agent_scheduler_history_tasks_grid" class="ag-theme-gradio" data-page-size="{grid_page_size}"></div>'
                        )
                    with gr.Column(scale=1, elem_id="agent_scheduler_history_results"):
                        galerry = gr.Gallery(
                            elem_id="agent_scheduler_history_gallery",
                            label="Output",
                            show_label=False,
                            columns=2,
                            preview=True,
                            object_fit="contain",
                        )
                        with gr.Row(
                            elem_id="agent_scheduler_history_result_actions",
                            visible=False,
                        ) as result_actions:
                            if is_sdnext:
                                with gr.Group():
                                    save = ToolButton(
                                        "💾",
                                        elem_id="agent_scheduler_save",
                                        tooltip=f"Save the image to a dedicated directory ({shared.opts.outdir_save}).",
                                    )
                                    save_zip = None
                            else:
                                save = ToolButton(
                                    "💾",
                                    elem_id="agent_scheduler_save",
                                    tooltip=f"Save the image to a dedicated directory ({shared.opts.outdir_save}).",
                                )
                                save_zip = ToolButton(
                                    "🗃️",
                                    elem_id="agent_scheduler_save_zip",
                                    tooltip=f"Save zip archive with images to a dedicated directory ({shared.opts.outdir_save})",
                                )
                            send_to_buttons = create_send_to_buttons()
                        with gr.Group():
                            generation_info = gr.Textbox(visible=False, elem_id=f"agent_scheduler_generation_info")
                            infotext = gr.TextArea(
                                label="Generation Info",
                                elem_id=f"agent_scheduler_history_infotext",
                                interactive=False,
                                visible=True,
                                lines=3,
                            )
                            download_files = gr.File(
                                None,
                                file_count="multiple",
                                interactive=False,
                                show_label=False,
                                visible=False,
                                elem_id=f"agent_scheduler_download_files",
                            )
                            html_log = gr.HTML(elem_id=f"agent_scheduler_html_log", elem_classes="html-log")
                            selected_task = gr.Textbox(
                                elem_id="agent_scheduler_history_selected_task",
                                visible=False,
                                show_label=False,
                            )
                            selected_image_id = gr.Textbox(
                                elem_id="agent_scheduler_history_selected_image",
                                visible=False,
                                show_label=False,
                            )

        # 註冊前端互動的事件處理器
        status.change(
            fn=lambda x: None,
            _js="agent_scheduler_status_filter_changed",
            inputs=[status],
        )
        save.click(
            fn=lambda x, y, z: call_queue.wrap_gradio_call(save_files)(x, y, False, int(z)),
            _js="(x, y, z) => [x, y, selected_gallery_index()]",
            inputs=[generation_info, galerry, infotext],
            outputs=[download_files, html_log],
            show_progress=False,
        )
        if save_zip:
            save_zip.click(
                fn=lambda x, y, z: call_queue.wrap_gradio_call(save_files)(x, y, True, int(z)),
                _js="(x, y, z) => [x, y, selected_gallery_index()]",
                inputs=[generation_info, galerry, infotext],
                outputs=[download_files, html_log],
            )
        selected_task.change(
            fn=lambda x: get_task_results(x, None),
            inputs=[selected_task],
            outputs=[infotext, result_actions, galerry, generation_info, download_files, html_log],
        )
        selected_image_id.change(
            fn=lambda x, y: get_task_results(x, image_idx=int(y)),
            inputs=[selected_task, selected_image_id],
            outputs=[infotext, result_actions],
        )
        # 註冊「送往其他分頁」的貼上參數按鈕
        try:
            for paste_tabname, paste_button in send_to_buttons.items():
                register_paste_params_button(
                    ParamBinding(
                        paste_button=paste_button,
                        tabname=paste_tabname,
                        source_text_component=infotext,
                        source_image_component=galerry,
                    )
                )
        # 貼上按鈕註冊失敗時靜默忽略，不影響主 UI
        except:
            pass

    return [(scheduler_tab, agent_scheduler_title, agent_scheduler_id)]
