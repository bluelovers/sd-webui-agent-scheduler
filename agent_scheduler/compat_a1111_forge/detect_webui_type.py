"""webui 類型偵測

依啟動參數的 description 判斷目前是否為 SD.Next，供 UI 模組切換元件型別與圖示。
"""

from modules.cmd_args import parser

__all__ = ["is_sdnext"]

is_sdnext = parser.description == "SD.Next"
