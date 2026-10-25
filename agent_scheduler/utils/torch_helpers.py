"""torch / webui 記憶體相關的輔助函式

目前收錄 Enqueue 列上「一鍵卸載所有模型」按鈕的處理函式，由入口檔
scripts/task_scheduler.py 匯入後綁定到該按鈕。
"""

from ..log import print_message


def unload_all_models():
    # 匯入放在函式內：handler 只在按鈕點擊時執行，
    # 避免載入本檔時就要求 backend 等模組存在（A1111 無 backend 套件）
    from backend import memory_management
    from modules import devices, errors
    import gc

    try:
        memory_management.unload_all_models()
    except Exception:
        errors.report("Error releasing memory", exc_info=True)
    finally:
        devices.torch_gc()
        gc.collect()
    print_message("All models unloaded")
