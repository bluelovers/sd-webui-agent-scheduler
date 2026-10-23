"""override_settings_texts 的模型標籤雙寫 (Dual-write) 工具

Forge Neo 的 sd_model_checkpoint 選項宣告 infotext="Model"（modules/shared_options.py），
create_override_settings_dict 只映射宣告過 infotext 的選項與 INFOTEXT_TO_SETTING 項目；
舊環境（A1111 系）以 "Model hash" 識別模型。因此單一標籤無法在兩個環境同時生效。

兩種標籤同時寫入時，各環境只消費自己映射裡有的一項、忽略另一項；兩項攜帶的值相同，
結果一致。以 Forge Neo 為預設標籤，舊環境標籤以雙寫保留相容。
"""

from typing import List, Optional

# 模型標籤前綴：Forge Neo 消費 "Model: "、舊環境消費 "Model hash: "；
# 清除既有項目與雙寫 append 共用同一份清單
MODEL_TEXT_PREFIXES: tuple = ("Model: ", "Model hash: ")

# 與 apply_checkpoint_override 相同語意的字面值：移除 override、改用系統模型
SYSTEM_CHECKPOINT = "System"


def apply_model_texts(override_texts: List[str], checkpoint: Optional[str]) -> List[str]:
    """回傳套用 checkpoint 標籤後的 override_settings_texts（純函式，輸入不變、回傳新清單）

    三態語意與結果形狀：
    - None（Runtime Checkpoint）：原樣保留，連使用者貼上的殘留標籤一併帶走
      ["Model hash: stale", "Seed: 42"] + None
      → ["Model hash: stale", "Seed: 42"]
    - "System"：只清除既有模型標籤、不寫入 → 下游退回系統當時模型
      ["Model: old", "Seed: 42"] + "System"
      → ["Seed: 42"]
    - 具名 checkpoint：清除後雙寫新舊標籤（兩項值相同，各環境取所需）
      ["Model: old", "Seed: 42"] + "foo.safetensors"
      → ["Seed: 42", "Model: foo.safetensors", "Model hash: foo.safetensors"]
    """
    if checkpoint is None:
        # Runtime：不覆寫，連同使用者貼上的殘留標籤一併保留
        return list(override_texts)

    # 先清除新舊兩種模型標籤，避免殘留項目與即將寫入的值並存
    cleaned = [x for x in override_texts if not x.startswith(MODEL_TEXT_PREFIXES)]
    if checkpoint == SYSTEM_CHECKPOINT:
        # System：只清除不寫入 —— 下游解析不到模型 override，即退回系統當時模型
        return cleaned

    # 具名：雙寫兩種標籤，各環境只消費自己認識的一項（兩項值相同，結果一致）
    return cleaned + [label + checkpoint for label in MODEL_TEXT_PREFIXES]
