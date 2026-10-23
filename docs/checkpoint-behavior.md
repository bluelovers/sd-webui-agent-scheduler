# Checkpoint 使用狀況 / Checkpoint Behavior

> **文件分類**：本文件只記錄 **checkpoint 資料的來源、儲存、序列化與執行時套用邏輯**。
> 按鈕點擊後的呼叫路徑屬另一領域，另見 [enqueue-button-call-path.md](./enqueue-button-call-path.md)。
> 下游模型切換點與插件的交叉點屬另一領域，另見 [model-switch-call-path.md](./model-switch-call-path.md)。

## 分析邊界 / Analysis Boundary

- 分析範圍**僅限本倉庫代碼**；未查閱任何依賴實作（`modules.*`、webui 內建 JS）與執行環境。
- 因此凡「底層如何解釋 override 值」的行為一律標記為 **未驗證 (Unverified)**，不做臆測。
- **例外（後續授權）**：維護者指名後，限 `modules/processing.py` / `modules/sd_models.py` 兩檔的下游分析已另立 [model-switch-call-path.md](./model-switch-call-path.md)；本文件仍只承載倉庫內代碼的結論。
- 代碼位置以 `檔案:行號` 表示，行號對應本次分析時的版本。

---

## 1. 結論 / Conclusion

**有使用 checkpoint 設定**，但執行時**不會直接載入模型**：checkpoint 在 `parse_task_args()` 階段就被「烘焙 (bake)」進 `named_args` 的 override 欄位，再交由底層 `txt2img / img2img / API` 生效。

> **重要限定（Forge，checkpoint 缺陷已修復）**：UI 任務的 texts 通道已改為**雙寫標籤**（`"Model: "` Forge 可消費＋ `"Model hash: "` 舊環境相容，§7 #1 已修復）→ checkpoint 覆寫可正常到達 `p.override_settings`；dict 通道仍被簽章篩選丟棄（§7 #3，已被 texts 覆蓋、無害）。**VAE 覆寫仍兩通道皆無效**（§7 #6，無接收通道，本次不改）。`update_task` 的條件缺陷與 raw 值問題亦已修復（§7 #4/#7）。A1111 未查（依維護者指示本次不驗證）。

- `execute_task()` 本身與 `ParsedTaskArgs.checkpoint` 欄位，在執行路徑上**從未被讀取**（該欄位僅供 `api.py:187` 回傳給前端）。
- 全倉庫沒有任何直接載入模型的呼叫；`execute_task()` 內 `SharedOptsBackup` 改寫的 20+ 個選項（`task_runner.py:356-484`）**不含 `sd_model_checkpoint`**。

---

## 2. 存值來源 / Value Sources

### 2.1 UI 任務

`scripts/task_scheduler.py:298-338`，配合前端 `ui/src/extension/index.ts:360-375`：

| 使用者選項 | 實際存進 task 的值 |
| :--- | :--- |
| Current Checkpoint | JS 端先替換成 `#setting_sd_model_checkpoint` 的設定值；Python 端 fallback 為 `shared.sd_model.sd_checkpoint_info.title` |
| Runtime Checkpoint | `None` |
| 具名 checkpoint / 整個資料夾 / Queue with all checkpoints | `list_checkpoint_tiles()` 的每一項（**`name`，即模型檔相對路徑** —— `sd_models.py:127` 回傳 `x.name` 非 title），每一項各自開一個 task |

存值形式有兩種：Current 為 **`title`**，其餘（資料夾過濾、Queue all、下拉具名）為 **`name`**。兩者皆為 `checkpoint_aliases` 的**合法精確鍵**（[model-switch-call-path.md](./model-switch-call-path.md) §2.1 列出 ids 全集），下游 807 關卡皆可通過。倉庫內沒有任何路徑會產生 model hash。

> 另註：API 的 `/agent-scheduler/v1/sd-models` 回傳 **`title`**（`api.py:131`），與 UI 下拉顯示的 `name` 形式不同 —— 展示不一致，但兩端值皆合法，不影響正確性。

### 2.2 API 任務

`api.py:139` / `api.py:164` pop 出 checkpoint → `register_api_task()` → `task_helpers.py:736-742`（與執行時共用 `resolve_checkpoint_title`）：

```python
title = resolve_checkpoint_title(checkpoint)   # 經 get_closet_checkpoint_match 解析 title / name / hash
if not title:
    log.warning(...)      # 解析失敗：只警告，退回系統模型，不寫 override
else:
    args.override_settings["sd_model_checkpoint"] = title
```

隨後 `task_runner.py:152` 再從 `override_settings.sd_model_checkpoint` 讀回頂層 `checkpoint`。因此 **API 任務是雙寫**（`args` 內一份＋頂層一份）；解析失敗時頂層會是 `None`。

> 此段是 **enqueue 時**的解析（`get_closet_checkpoint_match` ＋找不到只警告），與 §4 的**執行時**三態覆寫語意不同，刻意不合併：這段寫入 pydantic `args` 模型且不處理 `"System"`，執行時則寫 `named_args` dict。
> 執行時 `apply_checkpoint_override` 寫入的 `task.checkpoint` **已是此處解析後的 title**（`task_runner.py:152` 讀回 `override_settings.sd_model_checkpoint` 作為頂層存值；解析失敗時為 `None`）→ 執行時的覆蓋屬冪等、無害。
> `update_task` 改值路徑（`api.py:346-353`）**已修復**：可解析的先正規化為 title、`"System"` 原樣保留、解析不了保留原值交由執行時警告並退回系統模型 → §7 #4/#7 已結案。

---

## 3. 序列化 / Serialization

| 路徑 | 函式 | checkpoint 落點 |
| :--- | :--- | :--- |
| UI | `__serialize_ui_task_args`（`task_runner.py:114-142`） | **只寫到 params JSON 頂層 `checkpoint`**；`args`（named_args）一個字都沒動 |
| API | `__serialize_api_task_args`（`task_runner.py:144-164`） | `args.override_settings` 內 + 頂層 `checkpoint` |

UI 路徑的關鍵後果：enqueues 時 `args.override_settings_texts` 保持 UI 原樣 —— 可能含使用者貼上的 `Model hash: ...`，以及 `task_helpers.py:390-398` 補上的 Clip skip。

---

## 4. 執行時套用 / Apply at Execution

`execute_task()`（`task_runner.py:378`）→ `parse_task_args(task)`（`task_runner.py:389`，`deserialization=True`）→ 依 `is_ui` 分派：

> **執行時日誌**：每次執行 `parse_task_args` 都會以 `print` 輸出一份（`task_runner.py:271-272`，實作 `__log_override_targets`，`task_runner.py:282-331`）—— 記錄 task 存值與**實際送往 webui 的 checkpoint / VAE**（含 Runtime／System 三態顯示，格式 `[AgentScheduler] Task <id> execute (ui|api): checkpoint stored=..., sent=...; vae stored=..., sent=...`），供直接比對模型切換行為；**實送值與存值不同**（如 name 正規化為 title、VAE 存值與送出值不一致）時整行以綠色 ANSI（`\33[32m`）標示，慣例同 `shared_opts_backup.py` 的 `[change]`；前端顯示路徑（`api.py`，`deserialization=False`）不輸出。用 `print` 而非 `logging`：webui 環境下 logging 不保證掛在使用者可見的終端（`shared_opts_backup.py` 亦以 `print` 輸出），`print` 才保證直接可見。
> **texts 差異日誌**：UI 任務執行且 `apply_model_texts` 的輸出與輸入不同時，另輸出一行 `[AgentScheduler] [texts] removed=[...]; added=[...]`（`task_runner.py:188-196`）—— 顯示被清除的舊模型標籤與雙寫寫入的新標籤，可直接確認雙寫是否生效；輸入輸出相同（Runtime 原樣保留、System 且無殘留標籤）則不輸出。

### 4.1 UI 路徑（雙寫 / Dual-write）

`__deserialize_ui_task_args`（`task_runner.py:179-190`）**同時**寫入兩處，checkpoint 一旦為 `None`（Runtime）則兩處都不動：

```python
# (A) override_settings 字典：交由共用函式寫入，欄位名 sd_model_checkpoint
apply_checkpoint_override(named_args, checkpoint)

# (B) override_settings_texts 字串注入：交由相容層雙寫新舊標籤
named_args["override_settings_texts"] = apply_model_texts(
    named_args.get("override_settings_texts", []), checkpoint
)
```

- **(A)**：三態判斷的唯一實現在 `task_helpers.py:639-671` 的 `apply_checkpoint_override`，API 路徑（§4.2）呼叫同一份，兩路徑不會各自漂移；具名值先經 `resolve_checkpoint_title`（`task_helpers.py:624-637`）正規化為 title，解析失敗警告並 `pop` 退回系統模型（§7 #2 已修復）。**在 Forge 仍被簽章篩選丟棄**：`map_named_args_to_ui_task_args_list` 依 `txt2img_create_processing` 簽章重建位置參數（`task_helpers.py:422-427/437`），簽章只有 `override_settings_texts`、**沒有 `override_settings`**（`txt2img.py:18`，img2img 同構 `img2img.py:179`）→ §7 #3；因 (B) 已可生效，無害。
- **(B)**：`apply_model_texts`（`compat_a1111_forge/infotext_labels.py`）先清除新舊兩種模型標籤，再**雙寫** `"Model: "`（Forge 消費 —— `sd_model_checkpoint` 宣告 `infotext="Model"`）與 `"Model hash: "`（舊環境相容）—— 兩項值相同，任何環境只消費自己映射裡有的一項、忽略另一項 → §7 #1 已修復。VAE 的 `"VAE: "` 維持單寫且在 Forge 無消費者 → §7 #6。
- 綜合 (A)(B)：**在 Forge 環境，UI 任務的 checkpoint 覆寫經 texts 通道生效**（dict 被篩選但 (B) 已覆蓋）；VAE 覆寫仍無可達通道（§7 #6，本次不改）。

### 4.2 API 路徑

`__deserialize_api_task_args`（`task_runner.py:219-220`）呼叫同一個共用函式：

```python
apply_checkpoint_override(named_args, checkpoint)
```

三態判斷（具名 → 指派、`"System"` → `pop` 掉 `sd_model_checkpoint`、`None` → 不動作）與具名值的解析正規化（`resolve_checkpoint_title`，解析失敗警告並退回系統模型）皆實作於 `task_helpers.py:639-671`。

### 4.3 後續執行 / Subsequent Execution

`__execute_task`（`task_runner.py:686-746`）只取 `named_args` + `script_args`：

- UI → `map_named_args_to_ui_task_args_list`（依 `inspect.getfullargspec(txt2img_create_processing)` 簽章重組位置參數 —— `task_helpers.py:422-427`，舊版環境回退 `txt2img.txt2img`）→ `wrap_gradio_call(txt2img/img2img)`
- API → `StableDiffusionTxt2ImgProcessingAPI(**named_args)` → `self.__api.text2imgapi`

---

## 5. 三態語意 / Three-State Semantics

UI 欄位依 4.1 的雙寫分成 (A) `override_settings` dict 與 (B) `override_settings_texts` 字串：

| 存值 | UI 執行 (A) dict | UI 執行 (B) texts | API 執行 |
| :--- | :--- | :--- | :--- |
| `None`（Runtime Checkpoint） | 不動 → 保留 `args` 內既有 override | 不動 → 連 enqueues 時殘留的模型標籤一併帶去執行 | 不動 → 保留 `args.override_settings` |
| `"System"` | `pop` 掉 `sd_model_checkpoint` | 清除所有 `"Model: "` / `"Model hash: "` 標籤 | `pop` 掉 `sd_model_checkpoint` |
| 具名（name/title） | `sd_model_checkpoint = resolve_checkpoint_title(存值)` | 清除舊標籤後雙寫 `"Model: "` 與 `"Model hash: "`（值＝存值原樣，name/title 皆為合法鍵） | `sd_model_checkpoint = resolve_checkpoint_title(存值)` |

> 上表描述的是插件端「寫了什麼」與 webui 端「收到什麼」：(B) texts 的 `"Model: "` 標籤在 Forge 有消費者 → **checkpoint 覆寫生效**（§7 #1 已修復）；(A) dict 在 UI 路徑被簽章篩選丟棄（§7 #3，無害，(B) 已覆蓋），僅 API 欄到達 `p.override_settings`。VAE 在 Forge 兩通道皆無消費者（§7 #6）。

> `"System"` 字面值**只可能來自前端編輯**：`ui/src/extension/index.ts:85` 的 `checkpoints[0] = 'System'` 經 `PUT /agent-scheduler/v1/task/{id}`（`pending.store.ts:103-120`）寫入。Enqueue 下拉本身只會產生 `Current Checkpoint` / `Runtime Checkpoint` / title。
> Python 端的 `checkpoint_current` / `checkpoint_runtime` 字面值（`task_scheduler.py:51-52`）與 deserialize 端的 `"System"` 是**兩套不同的比對字面值**。

---

## 6. VAE 的不對稱行為 / VAE Asymmetry

`register_ui_task`（`task_runner.py:329`）：

```python
vae = getattr(shared.opts, "sd_vae", "Automatic")
```

該值**永非 `None`**，因此 `__deserialize_ui_task_args` 的 `if vae is not None` 恆真 → **每個 UI 任務執行時都會強制注入 enqueues 時的 VAE 快照**（`"VAE: " + vae`），即便 checkpoint 選的是 Runtime Checkpoint。惟該注入在 Forge 無消費者（§7 #6）—— 寫了但收不到。

checkpoint 可為 `None`（即時模型），VAE 則沒有對等的 Runtime 語意 —— 兩者行為不對稱。

---

## 7. 疑點清單 / Findings

| # | 疑點 | 位置 | 影響 |
| :--- | :--- | :--- | :--- |
| 1 | UI 路徑 (B) 的 `"Model hash: "` 標籤在 Forge 映射查無對應 → 項目被靜默丟棄 | `compat_a1111_forge/infotext_labels.py`（修復前為 `task_runner.py:188`） | **已修復**：改為雙寫 `"Model: "`（Forge 可消費 —— `sd_model_checkpoint` 宣告 `infotext="Model"`，`shared_options.py:223`）＋ `"Model hash: "`（舊環境相容）；兩項值相同，各環境只取所需。映射規則見 §8.3。A1111 未查 |
| 2 | 兩路徑驗證強度不一致：enqueue 時解析為 title，執行時原值直寫（非精確值無救援、靜默不切換） | `task_helpers.py:624-637`（修復前為 `714` vs `task_runner.py:183/188`） | **已修復**：`resolve_checkpoint_title` 收斂為單一判定，enqueue（`serialize_api_task_args`）、執行（`apply_checkpoint_override`）、`update_task` 三處共用 —— 具名值一律正規化為 title，解析失敗警告並退回系統模型（與 [model-switch-call-path.md](./model-switch-call-path.md) §2.1 807 關卡同判定） |
| 3 | `map_named_args_to_ui_task_args_list` 以 `named_args.get(name, None)` 依簽章取值 | `task_helpers.py:437` | **已確認（Forge）**：簽章含 `override_settings_texts`、不含 `override_settings`（`txt2img.py:18`；img2img 同構 `img2img.py:179`）→ **(A) dict 分支必被丟棄**。`task_helpers.py:390` 的 `or []` 顯示作者本就預期它可能不存在 → **版本相依**。**已被 #1 修復緩解**：dict 失效無害，texts 雙寫已可獨立生效。A1111 未查 |
| 4 | `update_task` 的判斷重複兩次，第二個原應為 `body.params is not None` | `api.py:338-355`（修復前為 `338-343`） | **已修復**：第二個條件改為 `body.params is not None`（`api.py:355`）→ (a) 只改 prompt／steps 而 checkpoint 為 `null` 時 params 正常合併；(b) 只送 checkpoint 不送 params 不再 `dict.update(None)` → TypeError |
| 5 | `ParsedTaskArgs.checkpoint` 在執行路徑上未被使用 | `task_runner.py:64-69` | checkpoint 的套用完全發生在 parse 階段；追蹤執行行為時不應去讀該欄位 |
| 6 | UI 路徑 (B) 的 VAE 前綴同樣無消費者：Forge 無選項宣告 `infotext="VAE"`（`sd_vae` 無 infotext，`shared_options.py:281`），`INFOTEXT_TO_SETTING` 的 `VAE/TE` 語意是 `forge_additional_modules` 模組列表、非 `sd_vae` | `task_runner.py:192-197` | UI 任務的 VAE 覆寫在 Forge 亦靜默失效；`sd_vae` 鍵只在 dict 通道有意義，而 UI 的 dict 通道見 #3 → **UI VAE 覆寫在 Forge 無任何可達通道**。維持不改（見 §6），僅記錄 |
| 7 | `update_task` 改值路徑把 client 原始 checkpoint 字串未經解析直接寫入頂層存值 | `api.py:346-353`（修復前為 `340-341`） | **已修復**：可解析的先經 `resolve_checkpoint_title` 正規化為 title（與 enqueue 同判定）、`"System"` 原樣保留、解析不了保留原值 —— 後者執行時由 `apply_checkpoint_override` 再解析，失敗即警告並 `pop` 退回系統模型（雙保險，消除「靜默不切換」）。新建 API 任務本就安全（enqueue 時已解析、`task_runner.py:152` 讀回 title） |

---

## 8. 驗證狀態 / Verification Status

**已由 [model-switch-call-path.md](./model-switch-call-path.md) 補答**（維護者授權後限兩檔閱讀）：

1. 底層 `txt2img / img2img / API` 對 `override_settings` 的生效方式與模型載入時機 → 該文件 §2 讀出 `processing.py:807-839` 完整鏈（alias 驗證 → `set_config` → 切模型 → 還原），§2.1 列出 `sd_model_checkpoint` 可接受的值形式。
2. `get_closet_checkpoint_match` 的匹配優先順序（`sd_models.py:157-174`）：① `checkpoint_aliases` 精確命中 → ② `checkpoints_list` 中含該字串的最短 `title` → ③ 去除 checksum 後再比子字串 → ④ `None`（`search_string` 為 falsy 時 158 直接回 `None`）。
3. `create_override_settings_dict` 的解析規則（`infotext_utils.py:472-501`）：先 `split(":", 1)` 拆成鍵值，鍵依 `data_labels[*].infotext` 與 `INFOTEXT_TO_SETTING`（469）映射到設定名，值經 `cast_value` 轉型。**結果：`"Model hash: <title>"` 與 `"VAE: <x>"` 在 Forge 查無對應 → 靜默丟棄**（§7 #1、#6；修復後插件雙寫 `"Model: "`，此鍵有對應 → checkpoint 生效）。

**修復實作與測試**（本檔 §7 #1/#2/#4/#7）：改動落在 `compat_a1111_forge/infotext_labels.py`（新建）、`task_helpers.py`、`task_runner.py`、`api.py`；單元測試 `tests/test_checkpoint_override.py`（11 例，涵蓋雙寫三態、解析正規化與失敗退回），`tests/run_tests.py` 通過（既有 `test_compat_ui.py` 4 失敗為先前既有，與本次無關）。

**仍未查閱**：

4. `opts.sd_model_checkpoint` → `model_data.forge_loading_parameters` 橋接、`sysinfo.set_config`、`forge_loader` 內部 —— 依賴內部實作，見 companion 文件 §7 斷點。
5. A1111 的對應實作（其 infotext→設定映射是否消費 `"Model hash"`、簽章是否含 `override_settings`）—— 依維護者指示**本次不驗證**。
