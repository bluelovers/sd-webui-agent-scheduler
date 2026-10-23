# 模型切換呼叫路徑 / Model Switch Call Path

> **文件分類**：本文件只記錄 **webui 模型切換點 `manage_model_and_prompt_cache` 向上追溯至本插件的呼叫路徑與交叉點**。
> 插件自身如何取得／序列化／套用 checkpoint 屬另一領域 → [checkpoint-behavior.md](./checkpoint-behavior.md)；
> Enqueue 按鈕點擊路徑 → [enqueue-button-call-path.md](./enqueue-button-call-path.md)。

## 分析邊界 / Analysis Boundary

- 起點為維護者指名的 `manage_model_and_prompt_cache`（`D:/sd-forge/modules/processing.py`），沿**呼叫關係向上**追溯，止於本插件的呼叫點。
- 第二輪經維護者指定擴及 `D:/sd-forge/modules/sd_models.py`，只分析 `override_settings.get("sd_model_checkpoint")` 所接受的值（§2.1）。
- 只記錄與該呼叫鏈直接相關的行；不理解、不記錄依賴的其餘實作。
- 未查閱執行環境；執行期資料（如 `sd_models` 的別名快取內容）一律標記 **未驗證 (Unverified)**。
- 行號對應 `D:/sd-forge` 與本擴充目錄的實際版本。

---

## 1. 結論 / Conclusion

- 本插件**不 import `modules.processing`**（全庫僅 `from modules import …` 取 `progress` / `shared` / `sd_models` / `txt2img` / `img2img` 等），與模型切換沒有直接呼叫關係；交會只有執行端的兩個呼叫點（§4）與它寫入 `named_args` 的 override 值（§5）。
- 模型切換實際發生於 `processing.py:785` 的 `forge_model_reload()`，由 `process_images`（`processing.py:820`）呼叫。
- 插件寫入的 `sd_model_checkpoint` 在 `process_images:807-808` 經 `sd_models.checkpoint_aliases` 驗證：**未命中即靜默移除，不切模型、無任何警告**。修復後 UI 任務的 texts 雙寫 `"Model: "` 在 Forge 有消費者 → checkpoint 覆寫可抵達此關卡（dict 通道仍被簽章篩選丟，但已無害，§5.2）；API 任務則經 dict 直達。

---

## 2. 向上路徑 / Upward Path

```
manage_model_and_prompt_cache(p)                 processing.py:782   ← 維護者所述模型切換點
   │  785  p.sd_model, just_reloaded = forge_model_reload()
   ↑ 全檔唯一呼叫者（grep 全檔僅此一處）
process_images(p)                                processing.py:797
   ├─ 799-800  if p.scripts is not None: p.scripts.before_process(p)
   ├─ 802  stored_opts = {… for k in p.override_settings.keys()}     覆寫前快取原值
   ├─ 807  if sd_models.checkpoint_aliases.get(p.override_settings["sd_model_checkpoint"]) is None:
   │   808      p.override_settings.pop("sd_model_checkpoint")       ← alias 驗證關卡
   ├─ 810  _vae_override = p.override_settings.pop("sd_vae")         ← VAE 就此分流
   ├─ 813  set_config(p.override_settings, is_api=True, run_callbacks=False, save_config=False)
   ├─ 816-818  if p.txt2img_upscale: pass                            ← 該路徑跳過切換
   ├─ 820  manage_model_and_prompt_cache(p)                          ← 切模型
   ├─ 821-823  if _vae_override is not None: … forge_additional_modules
   └─ 839  if p.override_settings_restore_afterwards: …              還原覆寫前的 opts
```

webui 自身在 805-806 的註解亦說明該關卡意圖：「no checkpoint override or the override checkpoint can't be found, remove override entry and load opts checkpoint」。

### 2.1 關卡可接受的值 / Accepted Values at the Gate

`override_settings.get("sd_model_checkpoint")` 在 `processing.py` / `sd_models.py` 內的**唯一消費點**是 `processing.py:807` 的 `checkpoint_aliases.get(...)` —— 精確字典查表。同檔 `get_closet_checkpoint_match`（`sd_models.py:157-174`，含子字串與去 checksum 匹配）**未被此關卡使用**，模糊值在此一律被拒。

可接受值 = `CheckpointInfo.ids` 的全部項目（`sd_models.py:83-85` 定義，`register()` 於 87-90 逐項灌入別名表；`checkpoints_list` 只收 `title`，88）。欄位定義：`name` = 模型檔相對於 `cmd_opts.ckpt_dirs` / `model_path` 的路徑（46-58；不屬任一目錄時 fallback 為 `basename`，51）、`title` = `name [shorthash]`（無 shorthash 時即 `name`，80）。

以 `sd/a/foo.safetensors` 為例：

| # | 可接受形式 | 範例 | 來源行 |
| :--- | :--- | :--- | :--- |
| 1 | `title` | `sd/a/foo.safetensors [abc123def0]` | 80, 83, 88 |
| 2 | `name`（相對路徑） | `sd/a/foo.safetensors` | 72, 83 |
| 3 | `model_name`（分隔符→`_`、去副檔名） | `sd_a_foo` | 74, 83 |
| 4 | `name_for_extra`（basename 去副檔名） | `foo` | 73, 83 |
| 5 | `hash`（**舊 8 碼** hash，`model_hash` 177-190） | 8 位 hex | 75, 83 |
| 6 | `name [hash]` | `sd/a/foo.safetensors [1a2b3c4d]` | 83 |
| 7 | `shorthash`（sha256 前 10 碼） | 10 位 hex | 78, 85 |
| 8 | `sha256`（完整） | 64 位 hex | 77, 85 |
| 9 | `name [shorthash]`（＝#1 重複鍵） | — | 85 |
| 10 | `name_for_extra [shorthash]`（＝`short_title`，81） | `foo [abc123def0]` | 81, 85 |

**邊界特例**：檔案不存在時 `model_hash()` 回傳字面值 `"NOFILE"`（190），該值同樣成為 id（83）→ 多個缺檔 checkpoint 爭用同一鍵，選到哪個取決於字典插入順序。

**被拒**（807 → 808 `pop`，不切模型、無日誌）：`None` / 空字串 / 任意未註冊字串（含 `"System"`）、部分子字串、大小寫不符、refresh 後已不存在的模型（132 `clear()` 後須重掃才補回）。

**通過關卡後**（仍在這兩個檔案內）：813 `set_config(..., run_callbacks=False)` → 820 `manage_model_and_prompt_cache` → `forge_model_reload`（322）—— 323-326 `str(model_data.forge_loading_parameters)` 未變即回傳現有模型、不重載；349 取 `forge_loading_parameters["checkpoint_info"]` → 361 `forge_loader(...)`。

**兩檔案內的斷點**：① `set_config` 定義在 `modules/sysinfo.py`（`processing.py:34` 引入），如何寫入 opts 未看；② `opts.sd_model_checkpoint` → `forge_loading_parameters` 的賦值在這兩個檔案內不存在，且 813 傳 `run_callbacks=False` 表示不經選項回調；③ 兩檔內唯一讀 `shared.opts.sd_model_checkpoint` 的是 `select_checkpoint()`（193-208：別名未命中 → 取第一個 checkpoint ＋ stderr 警告，205-206），但 `sd_models.py` 內無它的呼叫者。

---

## 3. `process_images` 的入口 / Callers

本插件會走到的 4 個：

| 入口 | 轉交方式 | 建構 `p` | `process_images` 呼叫 |
| :--- | :--- | :--- | :--- |
| `txt2img`（`txt2img.py:164`） | 165 `main_thread.run_and_wait_result(txt2img_function, …)`；`txt2img_function` 於 132 | `txt2img_create_processing`（18）→ 19 `create_override_settings_dict(override_settings_texts)` → 24 建構 → 51 `override_settings=override_settings` | 139 |
| `img2img`（`img2img.py:302`） | 303 `main_thread.run_and_wait_result(img2img_function, …)`；`img2img_function` 於 179 | 231 `StableDiffusionProcessingImg2Img(...)` | 281 |
| `text2imgapi`（`api/api.py:432`） | — | 443-449 `populate = txt2imgreq.copy(update=…)` → 456 `args = vars(populate)` → 470 `StableDiffusionProcessingTxt2Img(sd_model=shared.sd_model, **args)` | 484 |
| `img2imgapi`（`api/api.py:495`） | — | 同構 | 558 |

同檔另有兩個 `process_images` 呼叫點**插件不會走到**：`txt2img.py:107`（`txt2img_upscale_function`）與 `img2img.py:162`（`process_batch` 批次路徑）。

---

## 4. 與本插件的交叉點 / Intersection

唯二兩處，皆在執行端：

- **UI**：`task_runner.py:704` `func = wrap_gradio_call(img2img if is_img2img else txt2img, add_stats=True)` → 712 `result = func(*args)`。
  其中 `txt2img` / `img2img` 為直接引入的入口函式（`task_runner.py:18-19`），`wrap_gradio_call` 來自 `modules.call_queue`（`task_runner.py:17`）。
  `args` 是 `__deserialize_ui_task_args` 回傳值重組後的位置參數 —— 無論插件的參數對齊以哪個簽章為準（見 [checkpoint-behavior.md](./checkpoint-behavior.md) 疑點 #3；已確認 Forge 簽章含 `override_settings_texts`、不含 `override_settings`），其最終落點是 `txt2img_create_processing` 的 `override_settings_texts`（`txt2img.py:18`）或 `img2img_function` 的同名參數（`img2img.py:179`/`302`）。修復後插件雙寫標籤，checkpoint 經 `"Model: "` 此落點正常轉入 `override_settings`（§5.1）；`"VAE: "` 則仍被清空。
- **API**：`task_runner.py:744-746` `self.__api.img2imgapi(StableDiffusionImg2ImgProcessingAPI(**kwargs))` / `text2imgapi(StableDiffusionTxt2ImgProcessingAPI(**kwargs))`，`Api` 引自 `modules.api.api`（`task_runner.py:20`）。`kwargs` 即 `__deserialize_api_task_args` 的 `named_args`。

---

## 5. 資料匯合點 / How Override Values Reach `p`

插件寫入的兩個值（`apply_checkpoint_override`，`task_helpers.py:639-671`；texts 注入，`compat_a1111_forge/infotext_labels.py:25-41` 經 `task_runner.py:186-190` 呼叫）經兩條路徑匯入同一欄位 `p.override_settings`：

```
UI :  named_args["override_settings_texts"]
        → txt2img.py:19 create_override_settings_dict(...) → 51 override_settings=
API:  named_args["override_settings"] (dict)
        → StableDiffusion*ProcessingAPI(**kwargs) → api.py:456 vars(populate) → 470 **args
        ↓
StableDiffusionProcessing.override_settings      processing.py:181（欄位定義）
        → 256 __post_init__ 正規化為 {}
        ↓
process_images:807-820 → manage_model_and_prompt_cache
```

即 §2 的驗證關卡與切換點，是兩條插件路徑**共同的最後一段** —— 但兩條路徑能否抵達該段，取決於各自接收端的實作（§5.1、§5.2）。

### 5.1 接收端實作：`create_override_settings_dict`（Forge）

texts 通道的接收端是 `infotext_utils.py:472-501`：`split(":", 1)` 拆鍵值後，依兩份映射找設定名 ——

- `data_labels[*].infotext`（489）：`sd_model_checkpoint` 宣告為 **`"Model"`**（`shared_options.py:223`，全 `modules/` 唯一 `infotext="Model"`）；`sd_vae` **無 infotext**（281），全 `modules/` 無選項宣告 `infotext="VAE"`
- `INFOTEXT_TO_SETTING`（469）：僅 `[("VAE/TE", "forge_additional_modules")]` —— `VAE/TE` 的語意是 Forge 附加模組列表，非 `sd_vae`
- `"Model hash"` 字面在 `modules/` 只有 3 處（`processing.py:731` 正向寫入 PNG info、`img2img.py:143` batch png-info 流程、`ui.py:555` checkbox 選項）—— **沒有一處是此映射的消費者**

結論：`"VAE: <值>"` 查無對應 → 492 `continue` 靜默丟棄；`"Model hash: <值>"` 同樣無對應，但插件已改為**雙寫**（`infotext_labels.py`）—— `"Model: <值>"` 命中 `data_labels` 映射、正常轉入 `override_settings`，`"Model hash: <值>"` 項被忽略且無害。

### 5.2 兩路徑實際抵達狀況 / Actual Delivery

| 通道 | 鍵名 | Forge 下的結局 |
| :--- | :--- | :--- |
| UI texts — checkpoint（`task_runner.py:186-190`，雙寫實作 `infotext_labels.py:25-41`） | `"Model: "` 前綴（＋相容 `"Model hash: "`） | §5.1：`"Model: "` 命中映射 → checkpoint 覆寫**生效** ✓（相容項被忽略、無害） |
| UI texts — VAE（`task_runner.py:194-196`） | `"VAE: "` 前綴 | §5.1：無消費者 → 靜默丟棄 ❌（維持不改，僅記錄） |
| UI dict（`task_helpers.py:639-671`） | `sd_model_checkpoint`（鍵名正確） | `map_named_args_to_ui_task_args_list` 依 `txt2img_create_processing` 簽章過濾（`task_helpers.py:422-427/437`；`txt2img.py:18` 簽章無 `override_settings`）→ 丟棄 ❌（texts 已覆蓋，無害） |
| API dict（`task_runner.py:744-746` → `api/api.py:456/470`） | `sd_model_checkpoint` | `vars(populate)` 直達 `p.override_settings` ✓，抵達 807 關卡；寫入值為 enqueue 時解析出的 title，`update_task` 改值亦已正規化（[checkpoint-behavior.md](./checkpoint-behavior.md) §7 #4/#7 已修復） |

即：**在 Forge，checkpoint 覆寫兩種任務皆可到達 §2 的驗證關卡**（UI 經 texts 雙寫、API 經 dict）；僅 **VAE 覆寫在 UI 路徑仍靜默失效**（無 `infotext="VAE"` 通道，維持不改）。

---

## 6. 對本插件的三個直接結論 / Implications

1. **值必須命中 `sd_models.checkpoint_aliases`**：否則在 `process_images:807-808` 被靜默 `pop`，模型不切換且無日誌。插件存入的值為 `title`（Current、API）或 `name`（Queue all／資料夾／下拉具名，[checkpoint-behavior.md](./checkpoint-behavior.md) §2.1）—— 兩者皆為合法精確鍵（§2.1），且執行／改值時一律先經 `resolve_checkpoint_title` 正規化（`task_helpers.py:624-637`）→ UI/API 任務皆可抵達此關卡（§5.2）；實際註冊的 alias 內容仍取決於執行期快取（§7 未驗證）。`"System"` 與 `None` 兩態在此關卡等效 —— 都沒有 `sd_model_checkpoint` 進入 820。
2. **VAE 與 checkpoint 雖同寫 override，生效路徑卻分離**：`sd_vae` 在 `process_images:810` 被 pop 出 dict，改走 821-823 的 `_overridden_modules` / `forge_additional_modules` 分支 —— 印證 [checkpoint-behavior.md](./checkpoint-behavior.md) §6 的不對稱。
3. **`p.txt2img_upscale` 為真時 820 被跳過**（`process_images:816-818`），該路徑不切模型；此旗標由 hiresfix 快速按鈕路徑設定，插件不寫入它。

補充：插件的 `SharedOptsBackup` / `set_shared_opts`（`task_runner.py:356-484`）不含 `sd_model_checkpoint`，而下游覆寫走 `set_config(..., save_config=False)`（`process_images:813`）＋ `override_settings_restore_afterwards` 還原（`process_images:839`）—— 兩套機制無重疊、互不干擾。

---

## 7. 未驗證項 / Unverified

1. `sd_models.checkpoint_aliases` 的**鍵形式**已由代碼讀出（§2.1）；仍未查閱的是**執行期實際註冊了哪些 checkpoint** —— 需執行環境。
2. `opts.sd_model_checkpoint` → `model_data.forge_loading_parameters` 的賦值（§2.1 斷點 ②）與 `forge_loader` 內部 —— 不在本次兩檔案範圍內，不展開。
3. `set_config`（`modules/sysinfo.py`）如何寫入 opts、`select_checkpoint()`（`sd_models.py:193-208`）的實際呼叫點 —— 均在範圍外。
4. Forge 與 A1111 在 `process_images:807-810`、`create_override_settings_dict` 映射、`txt2img_create_processing` 簽章是否一致 —— 依維護者指示**本次不驗證 A1111**，一律只承載 `D:/sd-forge`（Forge）一份來源的結論。
