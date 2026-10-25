"""sd-webui 圖示按鈕的型別分流

不同 webui 對 ToolButton 的提供方式不同：有的版本從 modules.ui_components
匯出 ToolButton，有的版本該符號為 None。這裡只做一次分流，讓各 UI 模組一律
引用 ToolButton 這個符號，不必各自判斷環境。
"""

import gradio as gr

from modules import ui_components

__all__ = ["ToolButton"]

# webui 有提供 ToolButton 時沿用其樣式，否則退回 gr.Button 維持可用
ToolButton = gr.Button if ui_components.ToolButton is None else ui_components.ToolButton
