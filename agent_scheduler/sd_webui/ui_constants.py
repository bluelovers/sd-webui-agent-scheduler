"""Agent Scheduler 的 UI 與設定共用常數

入口檔（scripts/task_scheduler.py）、主畫面（main_any2img）與頁籤（tab_scheduler）
都引用這裡的字面值：擴充顯示名稱與識別 id、設定頁列出的選項、掛載邏輯比對的位置、
checkpoint 下拉的特殊值與歷史保留天數都定義在同一處。
"""

from agent_scheduler.helpers import is_macos

__all__ = [
    "agent_scheduler_id",
    "agent_scheduler_title",
    "checkpoint_current",
    "checkpoint_runtime",
    "completion_action_choices",
    "enqueue_default_hotkey",
    "enqueue_key_codes",
    "enqueue_key_modifiers",
    "placement_between_prompt_and_generate",
    "placement_under_generate",
    "queue_with_every_checkpoints",
    "task_filter_choices",
    "task_history_retenion_map",
    "ui_placement_append_to_main",
    "ui_placement_as_tab",
]

# 擴充的識別 id：頁籤 id 與設定分區 key 共用同一個字面值。
# webui 會用頁籤 id 產生 tab_agent_scheduler，前端 ui/src/extension/index.ts
# 就是用 #tab_agent_scheduler 選到本頁籤，改動前須與該處同步
agent_scheduler_id = "agent_scheduler"

# 擴充在 UI 上顯示的名稱：腳本下拉、設定分區標題、頁籤標題共用同一個字面值
agent_scheduler_title = "Agent Scheduler"

# checkpoint 下拉選單的特殊值：當前／執行時／每一顆 checkpoint 各排一個任務
checkpoint_current = "Current Checkpoint"
checkpoint_runtime = "Runtime Checkpoint"
queue_with_every_checkpoints = "$$_queue_with_all_checkpoints_$$"

# 任務佇列 UI 的擺放位置（獨立分頁 / 併入主介面）
ui_placement_as_tab = "As a tab"
ui_placement_append_to_main = "Append to main UI"

# Enqueue 按鈕擺放位置：掛載邏輯與設定頁比對同一組字串
placement_under_generate = "Near Generate button"
placement_between_prompt_and_generate = "Between Prompt and Generate button"

# 佇列完成後的動作選項
completion_action_choices = ["Do nothing", "Shut down", "Restart", "Sleep", "Hibernate", "Stop webui", "Restart webui"]

# Enqueue 鍵盤快捷鍵：修飾鍵、預設組合與按鍵名稱對照
enqueue_key_modifiers = [
    "Command" if is_macos else "Ctrl",
    "Control" if is_macos else "Alt",
    "Shift",
]
enqueue_default_hotkey = enqueue_key_modifiers[0] + "+KeyE"
enqueue_key_codes = {}
enqueue_key_codes.update({chr(i): "Key" + chr(i) for i in range(ord("A"), ord("Z") + 1)})
enqueue_key_codes.update({chr(i): "Digit" + chr(i) for i in range(ord("0"), ord("9") + 1)})
enqueue_key_codes.update({"`": "Backquote", "Enter": "Enter"})

# 歷史保留天數 → 實際天數（0 表示永久保留）
task_history_retenion_map = {
    "1 day": 1,
    "3 days": 3,
    "7 days": 7,
    "14 days": 14,
    "30 days": 30,
    "90 days": 90,
    "Keep forever": 0,
}

# Task History 頁籤的狀態篩選
task_filter_choices = ["All", "Bookmarked", "Done", "Failed", "Interrupted"]
