# Checkpoint 使用狀況 / Checkpoint Behavior

> **文件分類**：本文件只記錄 **checkpoint 資料的來源、儲存、序列化與執行時套用邏輯**。
> 按鈕點擊後的呼叫路徑屬另一領域，另見 [enqueue-button-call-path.md](./enqueue-button-call-path.md)。

## 分析邊界 / Analysis Boundary

- 分析範圍**僅限本倉庫代碼**；未查閱任何依賴實作（`modules.*`、webui 內建 JS）與執行環境。
- 因此凡「底層如何解釋 override 值」的行為一律標記為 **未驗證 (Unverified)**，不做臆測。
- 代碼位置以 `檔案:行號` 表示，行號對應本次分析時的版本。

---

## 1. 結論 / Conclusion

**有使用 checkpoint 設定**，但執行時**不會直接載入模型**：checkpoint 在 `parse_task_args()` 階段就被「烘焙 (bake)」進 `named_args` 的 override 欄位，再交由底層 `txt2img / img2img / API` 生效。

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
| 具名 checkpoint / 整個資料夾 / Queue with all checkpoints | `list_checkpoint_tiles()` 的每一項（**title**），每一項各自開一個 task |

所有來源皆為 **title**，倉庫內沒有任何路徑會產生 model hash。

### 2.2 API 任務

`api.py:139` / `api.py:164` pop 出 checkpoint → `register_api_task()` → `task_helpers.py:712-718`：

```python
checkpoint_info = get_closet_checkpoint_match(checkpoint)   # 解析 title / hash / name
if not checkpoint_info:
    log.warning(...)      # 解析失敗：只警告，退回系統模型，不寫 override
else:
    args.override_settings["sd_model_checkpoint"] = checkpoint_info.title
```

隨後 `task_runner.py:152` 再從 `override_settings.sd_model_checkpoint` 讀回頂層 `checkpoint`。因此 **API 任務是雙寫**（`args` 內一份＋頂層一份）；解析失敗時頂層會是 `None`。

> 此段是 **enqueue 時**的解析（`get_closet_checkpoint_match` ＋找不到只警告），與 §4 的**執行時**三態覆寫語意不同，刻意不合併：這段寫入 pydantic `args` 模型且不處理 `"System"`，執行時則寫 `named_args` dict。

---

## 3. 序列化 / Serialization

| 路徑 | 函式 | checkpoint 落點 |
| :--- | :--- | :--- |
| UI | `__serialize_ui_task_args`（`task_runner.py:114-142`） | **只寫到 params JSON 頂層 `checkpoint`**；`args`（named_args）一個字都沒動 |
| API | `__serialize_api_task_args`（`task_runner.py:144-164`） | `args.override_settings` 內 + 頂層 `checkpoint` |

UI 路徑的關鍵後果：enqueues 時 `args.override_settings_texts` 保持 UI 原樣 —— 可能含使用者貼上的 `Model hash: ...`，以及 `task_helpers.py:390-398` 補上的 Clip skip。

---

## 4. 執行時套用 / Apply at Execution

`execute_task()`（`task_runner.py:332`）→ `parse_task_args(task)`（`task_runner.py:343`，`deserialization=True`）→ 依 `is_ui` 分派：

### 4.1 UI 路徑（雙寫 / Dual-write）

`__deserialize_ui_task_args`（`task_runner.py:179-189`）**同時**寫入兩處，checkpoint 一旦為 `None`（Runtime）則兩處都不動：

```python
# (A) override_settings 字典：交由共用函式寫入，欄位名 sd_model_checkpoint
apply_checkpoint_override(named_args, checkpoint)

# (B) override_settings_texts 字串注入：既有行為，保留不回歸
override = [x for x in override if not x.startswith("Model hash: ")]    # 先清掉舊的
if checkpoint != "System":
    override.append("Model hash: " + checkpoint)
named_args["override_settings_texts"] = override
```

- **(A) 為本次補寫**：讓 UI 任務也帶 `override_settings` dict；三態判斷的唯一實作在 `task_helpers.py:623-646` 的 `apply_checkpoint_override`，API 路徑（§4.2）呼叫同一份，兩路徑不會各自漂移。
- **(B) 為原本行為**：雙寫策略下不移除，避免既有環境回歸。
- 兩者皆須通過 `map_named_args_to_ui_task_args_list` 的簽章篩選（見疑點 #3），缺任一 key 該分支即被靜默丟棄。

### 4.2 API 路徑

`__deserialize_api_task_args`（`task_runner.py:219-220`）呼叫同一個共用函式：

```python
apply_checkpoint_override(named_args, checkpoint)
```

具名 → 指派、`"System"` → `pop` 掉 `sd_model_checkpoint`、`None` → 不動作的三態判斷實作於 `task_helpers.py:623-646`。

### 4.3 後續執行 / Subsequent Execution

`__execute_task`（`task_runner.py:638-650`）只取 `named_args` + `script_args`：

- UI → `map_named_args_to_ui_task_args_list`（依 `inspect.getfullargspec(txt2img/img2img)` 簽章重組位置參數）→ `wrap_gradio_call(txt2img/img2img)`
- API → `StableDiffusionTxt2ImgProcessingAPI(**named_args)` → `self.__api.text2imgapi`

---

## 5. 三態語意 / Three-State Semantics

UI 欄位依 4.1 的雙寫分成 (A) `override_settings` dict 與 (B) `override_settings_texts` 字串：

| 存值 | UI 執行 (A) dict | UI 執行 (B) texts | API 執行 |
| :--- | :--- | :--- | :--- |
| `None`（Runtime Checkpoint） | 不動 → 保留 `args` 內既有 override | 不動 → 連 enqueues 時殘留的 `Model hash:` 一併帶去執行 | 不動 → 保留 `args.override_settings` |
| `"System"` | `pop` 掉 `sd_model_checkpoint` | 清除所有 `Model hash: ` | `pop` 掉 `sd_model_checkpoint` |
| 具名 title | `sd_model_checkpoint = title` | 替換為 `"Model hash: " + title` | `sd_model_checkpoint = title` |

> `"System"` 字面值**只可能來自前端編輯**：`ui/src/extension/index.ts:85` 的 `checkpoints[0] = 'System'` 經 `PUT /agent-scheduler/v1/task/{id}`（`pending.store.ts:103-120`）寫入。Enqueue 下拉本身只會產生 `Current Checkpoint` / `Runtime Checkpoint` / title。
> Python 端的 `checkpoint_current` / `checkpoint_runtime` 字面值（`task_scheduler.py:51-52`）與 deserialize 端的 `"System"` 是**兩套不同的比對字面值**。

---

## 6. VAE 的不對稱行為 / VAE Asymmetry

`register_ui_task`（`task_runner.py:283`）：

```python
vae = getattr(shared.opts, "sd_vae", "Automatic")
```

該值**永非 `None`**，因此 `__deserialize_ui_task_args` 的 `if vae is not None` 恆真 → **每個 UI 任務執行時都會強制注入 enqueues 時的 VAE 快照**（`"VAE: " + vae`），即便 checkpoint 選的是 Runtime Checkpoint。

checkpoint 可為 `None`（即時模型），VAE 則沒有對等的 Runtime 語意 —— 兩者行為不對稱。

---

## 7. 疑點清單 / Findings

| # | 疑點 | 位置 | 影響 |
| :--- | :--- | :--- | :--- |
| 1 | UI 路徑 (B) 寫入 `"Model hash: " + checkpoint`，但存入值全是 **title** | `task_runner.py:188` | 前綴宣稱 hash、實值為 title，是否正確解析**未驗證**（需查依賴）。(A) 的共用函式分支直接存 title，不受此前綴影響 |
| 2 | API 路徑在 enqueue 時經 `get_closet_checkpoint_match` 統一解析為 title，UI 路徑在**執行時不做任何解析**，直接字串／原值寫入 | `task_helpers.py:714` vs `task_runner.py:183` / `task_runner.py:188` | 兩路徑驗證強度不一致 |
| 3 | `map_named_args_to_ui_task_args_list` 以 `named_args.get(name, None)` 依簽章取值 | `task_helpers.py:437` | 若目標函式簽章**不含** `override_settings_texts` 或 `override_settings`，該 key 會被靜默丟棄 → checkpoint / VAE / Clip skip override 失效（雙寫下兩者同時存在於簽章時才有冗餘效果）。`task_helpers.py:390` 的 `or []` 顯示作者本就預期它可能不存在 → **版本相依** |
| 4 | `update_task` 的判斷重複兩次，第二個應為 `body.params is not None` | `api.py:338-343` | (a) 只改 prompt／steps 而 `checkpoint` 為 `null` 時，`params` 整包不會被合併（編輯靜默失效）；(b) 只送 checkpoint 不送 params 會 `dict.update(None)` → TypeError。前端目前剛好兩者都送，尚未爆開 |
| 5 | `ParsedTaskArgs.checkpoint` 在執行路徑上未被使用 | `task_runner.py:64-69` | checkpoint 的套用完全發生在 parse 階段；追蹤執行行為時不應去讀該欄位 |

---

## 8. 未驗證項 / Unverified

依「分析邊界」約束，以下事項**未查閱依賴實作，不作結論**：

1. `create_override_settings_dict`（`compat_a1111_forge/paste_params.py:18` re-export）如何解析 `"Model hash: <title>"`。
2. 底層 `txt2img / img2img / API` 對 `override_settings` 的實際生效方式與模型載入時機。
3. `get_closet_checkpoint_match` 對 title / hash / name 的匹配優先順序。
