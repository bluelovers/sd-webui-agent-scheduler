"""任務排程器腳本（入口）

排程器的入口點：宣告 sd-webui 的 Script（事件綁定與任務註冊）、註冊設定項目與 app 啟動鉤子。
"""

import gradio as gr
from uuid import uuid4
from typing import List
from datetime import datetime, timedelta

from modules import shared, script_callbacks, scripts
from modules.shared import list_checkpoint_tiles
from modules.sd_models import model_path
from agent_scheduler.compat_a1111_forge.paste_params import (
    connect_paste_params_buttons,
    registered_param_bindings,
)
from agent_scheduler.compat_a1111_forge.ui import get_ui_dependencies, get_ui_fns

from agent_scheduler.task_runner import TaskRunner, get_instance
from agent_scheduler.helpers import compare_components_with_ids, get_components_by_ids
from agent_scheduler.log import print_message
from agent_scheduler.db import init as init_db, task_manager
from agent_scheduler.api import regsiter_apis
# 畫面模組與共用常數：畫面只做自己的 UI，不反向 import 本檔
from agent_scheduler.sd_webui import main_any2img, tab_scheduler
from agent_scheduler.sd_webui.notify import notify_message
from agent_scheduler.sd_webui.ui_constants import (
    agent_scheduler_id,
    agent_scheduler_title,
    checkpoint_current,
    checkpoint_runtime,
    completion_action_choices,
    enqueue_default_hotkey,
    enqueue_key_codes,
    enqueue_key_modifiers,
    placement_between_prompt_and_generate,
    placement_under_generate,
    queue_with_every_checkpoints,
    task_history_retenion_map,
    ui_placement_append_to_main,
    ui_placement_as_tab,
)
from agent_scheduler.utils.torch_helpers import (
    UNLOADED_ALL_MODELS,
    UNLOADING_ALL_MODELS,
    unload_all_models,
)

# 全域任務執行器實例，於 on_app_started 時初始化
task_runner: TaskRunner = None

init_db()


class Script(scripts.Script):
    """sd-webui 擴充主腳本

    負責在 txt2img / img2img 介面上注入 Enqueue 按鈕與 checkpoint 下拉選單，
    並將其點擊事件綁定到排程器的任務註冊邏輯。
    """

    def __init__(self):
        super().__init__()
        # 註冊 app 啟動回呼，等待 UI 元件就緒後綁定事件
        script_callbacks.on_app_started(lambda block, _: self.on_app_started(block))
        self.checkpoint_override = checkpoint_current
        self.generate_button = None
        self.enqueue_row = None
        self.checkpoint_dropdown = None
        self.submit_button = None
        # skip_change_output_dir 核取方塊
        self.skip_change_output_dir_checkbox = None
        # 便捷按鈕（見 add_enqueue_button）
        self.pause_button = None
        self.resume_button = None
        self.unload_models_button = None
        # 是否已確認為 Compact 版面（確認後沿用，見 after_component）/
        self.compact_layout = False

    def title(self):
        # 擴充在 UI 上顯示的名稱
        return agent_scheduler_title

    def show(self, is_img2img):
        # 此擴充在兩種模式皆常駐顯示
        return scripts.AlwaysVisible

    def on_checkpoint_changed(self, checkpoint):
        # 記錄使用者於下拉選單選取的 checkpoint，供後續任務使用
        self.checkpoint_override = checkpoint

    def after_component(self, component, **_kwargs):
        """在每個 UI 元件建立後掛載 Enqueue 按鈕（委派給 main_any2img）

        掛載的核心邏輯（版面偵測、掛載點解析、Enqueue 列插入）。
        """
        main_any2img.after_component(self, component, **_kwargs)

    def on_app_started(self, block):
        # UI 元件就緒後才綁定 Enqueue 按鈕事件
        if self.generate_button is not None:
            self.bind_enqueue_button(block)

    def add_enqueue_button(self):
        """建立 Enqueue 列（委派給 main_any2img）

        建立出來的元件都寫回本實例的欄位，事件綁定仍由 bind_enqueue_button 處理。
        """
        main_any2img.add_enqueue_button(self)

    def bind_enqueue_button(self, root: gr.Blocks):
        # 找出 generate 按鈕背後的 gradio 依賴，用來複製其輸入元件並掛載 Enqueue 行為
        generate = self.generate_button
        is_img2img = self.is_img2img
        dependencies: List[dict] = [
            x for x in get_ui_dependencies(root) if x["trigger"] == "click" and generate._id in x["targets"]
        ]

        dependency: dict = None
        cnet_dependency: dict = None
        UiControlNetUnit = None
        # 從依賴中識別主生成函式與 ControlNet 單元，分別綁定
        for d in dependencies:
            if len(d["outputs"]) == 1:
                outputs = get_components_by_ids(root, d["outputs"])
                output = outputs[0]
                if isinstance(output, gr.State) and type(output.value).__name__ == "UiControlNetUnit":
                    cnet_dependency = d
                    UiControlNetUnit = type(output.value)

            elif len(d["outputs"]) >= 4:
                dependency = d

        with root:
            # 同步 checkpoint 下拉選單的變更
            if self.checkpoint_dropdown is not None:
                self.checkpoint_dropdown.change(fn=self.on_checkpoint_changed, inputs=[self.checkpoint_dropdown])

            # 找到與主生成函式相同輸入的 BlockFunction，作為 Enqueue 的輸入來源
            fn_block = next(fn for fn in get_ui_fns(root) if compare_components_with_ids(fn.inputs, dependency["inputs"]))
            inputs = fn_block.inputs.copy()
            inputs.insert(0, self.checkpoint_dropdown)

            # skip_change_output_dir 核取方塊的插入位置有兩個約束，缺一不可：
            # 1) 必須排在 _js 覆寫的索引之後（res[0]=checkpoint、res[1]=task id、
            #    img2img 另有 res[2]=mode），否則值會被 JS 蓋掉；
            # 2) 不可接在輸入清單尾端：create_submit_args 的尾端檢查以清單結尾為基準，
            #    多一個元素會讓檢查位移到最後一個 generate 輸入上。
            skip_change_output_dir_index = None
            if self.skip_change_output_dir_checkbox is not None:
                skip_change_output_dir_index = 3 if is_img2img else 2
                inputs.insert(skip_change_output_dir_index, self.skip_change_output_dir_checkbox)

            fn = self.wrap_register_ui_task(skip_change_output_dir_index)
            args = dict(
                fn=fn,
                _js="submit_enqueue_img2img" if is_img2img else "submit_enqueue",
                inputs=inputs,
                outputs=None,
                show_progress=False,
            )

            # 將 Enqueue 點擊事件綁定到包裝後的註冊函式
            self.submit_button.click(**args)

            def unload_all_models_with_notification():
                # 一鍵卸載按鈕的入口：卸載前後各提示一次，toast 顯示在瀏覽器；
                # 終端輸出仍由 unload_all_models 內的 print_message 負責，故不加 to_print
                notify_message(UNLOADING_ALL_MODELS, level="info")
                unload_all_models()
                notify_message(UNLOADED_ALL_MODELS, level="info")

            # 一鍵卸載模型：純後端動作、無輸入輸出；queue=False 讓它即時執行，
            # 不排在生成佇列後面才輪到
            if self.unload_models_button is not None:
                self.unload_models_button.click(
                    fn=unload_all_models_with_notification,
                    inputs=None,
                    outputs=None,
                    queue=False,
                )

            # 若存在 ControlNet 單元，額外綁定以確保其設定一併送出
            if cnet_dependency is not None:
                cnet_fn_block = next(
                    fn for fn in get_ui_fns(root) if compare_components_with_ids(fn.inputs, cnet_dependency["inputs"])
                )
                self.submit_button.click(
                    fn=UiControlNetUnit,
                    inputs=cnet_fn_block.inputs,
                    outputs=cnet_fn_block.outputs,
                    queue=False,
                )

    def wrap_register_ui_task(self, skip_change_output_dir_index: int = None):
        # 包裝 Enqueue 行為：解析 checkbox、checkpoint、task 名稱後註冊任務
        def f(request: gr.Request, *args):
            # 至少需要一個參數，否則視為非法呼叫
            if len(args) == 0:
                raise Exception("Invalid call")

            checkpoint: str = args[0]
            task_id = args[1]

            # 讀出 skip_change_output_dir 並連同 checkpoint 一起移出參數清單；
            # 其餘參數須維持原本 generate 輸入的順序，序列化才對得齊處理函式的簽章。
            skip_change_output_dir = False
            if skip_change_output_dir_index is not None and len(args) > skip_change_output_dir_index:
                skip_change_output_dir = bool(args[skip_change_output_dir_index])
                args = list(args[1:skip_change_output_dir_index]) + list(args[skip_change_output_dir_index + 1 :])
            else:
                args = args[1:]
            task_name = None

            # 特別關鍵字：對每一個 checkpoint 各產生一個任務
            if task_id == queue_with_every_checkpoints:
                task_id = str(uuid4())
                checkpoint = list_checkpoint_tiles()
            else:
                # 非 task(...) 開頭表示這是任務名稱，需產生新 id
                if not task_id.startswith("task("):
                    task_name = task_id
                    task_id = str(uuid4())

                # 依下拉選項決定實際要使用的 checkpoint 清單
                if checkpoint is None or checkpoint == "" or checkpoint == checkpoint_current:
                    checkpoint = [shared.sd_model.sd_checkpoint_info.title]
                elif checkpoint == checkpoint_runtime:
                    checkpoint = [None]
                elif checkpoint.endswith(" checkpoints)"):
                    checkpoint_dir = " ".join(checkpoint.split(" ")[0:-2])
                    checkpoint = list(filter(lambda c: c.startswith(checkpoint_dir), list_checkpoint_tiles()))
                else:
                    checkpoint = [checkpoint]

            # 多個 checkpoint 時為每個產生獨立 task id
            for i, c in enumerate(checkpoint):
                t_id = task_id if i == 0 else f"{task_id}.{i}"

                # gr.Info(f"[AgentScheduler] Add new Task {t_id} {task_name or ''}")

                # 註冊單一 UI 任務，帶入 checkpoint、任務名稱與 skip_change_output_dir 選擇
                task_runner.register_ui_task(
                    t_id,
                    self.is_img2img,
                    *args,
                    checkpoint=c,
                    task_name=task_name,
                    request=request,
                    skip_change_output_dir=skip_change_output_dir,
                )

            # 註冊後立即觸發背景執行緒處理佇列
            task_runner.execute_pending_tasks_threading()

        return f


def remove_old_tasks():
    # delete task that are too old
    # 依設定刪除過舊的歷史任務，避免資料庫無限增長
    retention_days = 30
    # 若使用者在設定中指定了保留天數則採用該值
    if (
        getattr(shared.opts, "queue_history_retention_days", None)
        and shared.opts.queue_history_retention_days in task_history_retenion_map
    ):
        retention_days = task_history_retenion_map[shared.opts.queue_history_retention_days]

    # 僅在保留天數大於 0 時執行刪除（"Keep forever" 對應 0） / Only delete when retention > 0 ("Keep forever" maps to 0)
    if retention_days > 0:
        deleted_rows = task_manager.delete_tasks(before=datetime.now() - timedelta(days=retention_days))
        if deleted_rows > 0:
            print_message(f"Deleted {deleted_rows} tasks older than {retention_days} days", log_only=True, level="debug")


def on_ui_settings():
    # 註冊所有 Agent Scheduler 的設定項目
    section = (agent_scheduler_id, agent_scheduler_title)
    shared.opts.add_option(
        "queue_paused",
        shared.OptionInfo(
            False,
            "Disable queue auto-processing",
            gr.Checkbox,
            {"interactive": True},
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_button_hide_checkpoint",
        shared.OptionInfo(
            True,
            "Hide the custom checkpoint dropdown",
            gr.Checkbox,
            {},
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_button_placement",
        shared.OptionInfo(
            placement_under_generate,
            "Queue button placement",
            gr.Radio,
            lambda: {
                "choices": [
                    placement_under_generate,
                    placement_between_prompt_and_generate,
                ]
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_ui_placement",
        shared.OptionInfo(
            ui_placement_as_tab,
            "Task queue UI placement",
            gr.Radio,
            lambda: {
                "choices": [
                    ui_placement_as_tab,
                    ui_placement_append_to_main,
                ]
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_history_retention_days",
        shared.OptionInfo(
            "30 days",
            "Auto delete queue history (bookmarked tasks excluded)",
            gr.Radio,
            lambda: {
                "choices": list(task_history_retenion_map.keys()),
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_automatic_requeue_failed_task",
        shared.OptionInfo(
            False,
            "Auto requeue failed tasks",
            gr.Checkbox,
            {},
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_grid_page_size",
        shared.OptionInfo(
            0,
            "Task list page size (0 for auto)",
            gr.Slider,
            {"minimum": 0, "maximum": 200, "step": 1},
            section=section,
        ),
    )

    def enqueue_keyboard_shortcut(disabled: bool, modifiers, key_code: str):
        # 根據勾選的修飾鍵與按鍵計算出快捷鍵字串
        if disabled:
            modifiers.insert(0, "Disabled")

        shortcut = "+".join(sorted(modifiers) + [enqueue_key_codes[key_code]])

        # 停用時連帶停用修飾鍵與按鍵的編輯
        return (
            shortcut,
            gr.CheckboxGroup.update(interactive=not disabled),
            gr.Dropdown.update(interactive=not disabled),
        )

    def enqueue_keyboard_shortcut_ui(**_kwargs):
        # Enqueue 快捷鍵的設定 UI 元件
        value = _kwargs.get("value", enqueue_default_hotkey)
        parts = value.split("+")
        key = parts.pop()
        key_code_value = [k for k, v in enqueue_key_codes.items() if v == key]
        modifiers = [m for m in parts if m in enqueue_key_modifiers]
        disabled = "Disabled" in value

        with gr.Group(elem_id="enqueue_keyboard_shortcut_wrapper"):
            modifiers = gr.CheckboxGroup(
                enqueue_key_modifiers,
                value=modifiers,
                label="Enqueue keyboard shortcut",
                elem_id="enqueue_keyboard_shortcut_modifiers",
                interactive=not disabled,
            )
            key_code = gr.Dropdown(
                choices=list(enqueue_key_codes.keys()),
                value="E" if len(key_code_value) == 0 else key_code_value[0],
                elem_id="enqueue_keyboard_shortcut_key",
                label="Key",
                interactive=not disabled,
            )
            shortcut = gr.Textbox(**_kwargs)
            disable = gr.Checkbox(
                value=disabled,
                elem_id="enqueue_keyboard_shortcut_disable",
                label="Disable keyboard shortcut",
            )

        modifiers.change(
            fn=enqueue_keyboard_shortcut,
            inputs=[disable, modifiers, key_code],
            outputs=[shortcut, modifiers, key_code],
        )
        key_code.change(
            fn=enqueue_keyboard_shortcut,
            inputs=[disable, modifiers, key_code],
            outputs=[shortcut, modifiers, key_code],
        )
        disable.change(
            fn=enqueue_keyboard_shortcut,
            inputs=[disable, modifiers, key_code],
            outputs=[shortcut, modifiers, key_code],
        )

        return shortcut

    shared.opts.add_option(
        "queue_keyboard_shortcut",
        shared.OptionInfo(
            enqueue_default_hotkey,
            "Enqueue keyboard shortcut",
            enqueue_keyboard_shortcut_ui,
            {
                "interactive": False,
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        "queue_completion_action",
        shared.OptionInfo(
            "Do nothing",
            "Action after queue completion",
            gr.Radio,
            lambda: {
                "choices": completion_action_choices,
            },
            section=section,
        ),
    )


def on_app_started(block: gr.Blocks, app):
    # app 啟動時初始化任務執行器、註冊 API 與清理回呼
    global task_runner
    task_runner = get_instance(block)
    task_runner.execute_pending_tasks_threading()
    regsiter_apis(app, task_runner)
    # 任務清空後自動刪除過舊的歷史
    task_runner.on_task_cleared(lambda: remove_old_tasks())

    # 當設定為併入主 UI 時，把分頁內容掛到主介面上
    if getattr(shared.opts, "queue_ui_placement", "") == ui_placement_append_to_main and block:
        with block:
            with block.children[1]:
                # 暫存已註冊的貼上綁定，避免掛載流程複製時重複
                bindings = registered_param_bindings.copy()
                registered_param_bindings.clear()
                tab_scheduler.on_ui_tab()
                connect_paste_params_buttons()
                registered_param_bindings.extend(bindings)


# 若採用獨立分頁（預設），以 on_ui_tabs 註冊（頁籤畫面在 tab_scheduler）
if getattr(shared.opts, "queue_ui_placement", "") != ui_placement_append_to_main:
    script_callbacks.on_ui_tabs(tab_scheduler.on_ui_tab)

script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_app_started(on_app_started)
