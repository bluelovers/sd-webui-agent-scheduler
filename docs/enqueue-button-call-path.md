# Enqueue 按鈕觸發路徑 / Enqueue Button Call Path

> **文件分類**：本文件只記錄 **Enqueue 按鈕被點擊後的呼叫路徑 (Call Path)**。
> checkpoint 值的來源、序列化與執行時套用邏輯屬另一領域，另見 [checkpoint-behavior.md](./checkpoint-behavior.md)。

## 分析邊界 / Analysis Boundary

- 分析範圍**僅限本倉庫代碼**；未查閱任何依賴實作（`modules.*`、webui 內建 JS）與執行環境。
- 凡「webui 本體提供的全域函式」一律標記為 **外部 (External)**，不推論其實作。

---

## 0. DOM 說明 / DOM Clarification

`#txt2img_enqueue_wrapper` / `#img2img_enqueue_wrapper` 是 `gr.Row`（`task_scheduler.py:214`），**本身沒有 click handler**。真正可點的是列內的 `#{id_part}_enqueue` 按鈕（`task_scheduler.py:233`）。

下文「按下按鈕」即指該按鈕。

---

## 1. 階段 0：按鈕如何存在並被綁定 / Mount & Binding

```
Script.__init__ (task_scheduler.py:101)
   └─ script_callbacks.on_app_started(self.on_app_started)

Script.after_component (task_scheduler.py:123-204)
   └─ resolve_enqueue_mount_point()      [agent_scheduler/enqueue_placement.py:26-77]
        classic + Near Generate   → {tab}_actions_column
        classic + Between prompt  → {tab}_toprow
        Compact + Near Generate   → {tab}_results
        Compact + Between prompt  → {tab}_prompt_container
   └─ add_enqueue_row() → add_enqueue_button()   (174-190 → 211-233)
        ├─ gr.Row(elem_id=f"{id_part}_enqueue_wrapper")
        ├─ checkpoint 下拉選單（217-223）＋重新整理按鈕（226-231）
        └─ gr.Button("Enqueue", elem_id=f"{id_part}_enqueue")

Script.on_app_started (206-209) → bind_enqueue_button(block) (235-289)
   ├─ 從 get_ui_dependencies(root) 找 generate 按鈕的 click 依賴 (239-256)
   │     outputs >= 4            → 主生成依賴 dependency
   │     單一輸出且為 UiControlNetUnit → cnet_dependency
   ├─ fn_block = inputs 相同的 BlockFunction (264)
   ├─ inputs = fn_block.inputs.copy()，並 insert(0, checkpoint_dropdown) (266-267)
   ├─ submit_button.click(fn=…, _js="submit_enqueue"|"_img2img", …) (268-277)
   └─ 若有 ControlNet：第二個 click → UiControlNetUnit, queue=False (280-289)
```

### 輸入序號對齊表 / Input Index Alignment

這是後續 JS 與 Python 索引的關鍵：

| index | 0 | 1 | 2 | 3… |
| :--- | :--- | :--- | :--- | :--- |
| Python `inputs` | `checkpoint_dropdown` | `id_task`（`gr.State`） | img2img `mode` | 其餘 generate 輸入 |

---

## 2. 階段 1：點擊 → 瀏覽器端 `_js` / Browser Hook

gradio 會先執行 `_js` 指定的全域函式，其**回傳值即為送回 server 的 payload**。

```
#txt2img_enqueue click
  └─ window.submit_enqueue(...args)          ui/src/extension/index.ts:378-397
       ├─ res = create_submit_args(args)     ← 外部全域（index.ts:43/46 僅型別宣告，本倉庫無實作）
       ├─ res[0] = getUiCheckpoint(false)    index.ts:360-375
       │     讀 `#{tab}_enqueue_wrapper input`：
       │       'Runtime Checkpoint' / 其他具名 → 原樣回傳
       │       'Current Checkpoint'            → 改讀 `#setting_sd_model_checkpoint input`
       ├─ res[1] = randomId()                index.ts:381   ← 預設亂數 task id，可被預先 patch
       ├─ 按鈕文字 'Queued' → 1 秒後還原，pending tab 則 pendingStore.refresh() (384-394)
       └─ return res  →  gradio POST 回 server

#img2img_enqueue click
  └─ window.submit_enqueue_img2img(...)      index.ts:400-420
       同上，另加 res[2] = get_tab_index('mode_img2img')  (404)  ← 覆寫 img2img 模式
```

### `window.randomId` 的預先覆寫來源 / Monkey-patch Sources

三者都是「先 patch randomId，再程式化 `btn.click()`」：

| 來源 | randomId 回傳 | Python 端解讀為 |
| :--- | :--- | :--- |
| `index.ts:477-485` Queue with task name | 使用者輸入的名字 | `task_name`（非 `task(` 開頭 → 另開 uuid） |
| `index.ts:486-493` Queue with all checkpoints | `$$_queue_with_all_checkpoints_$$` | 每個 checkpoint 各開一個 task |
| `index.ts:436-452` 鍵盤快捷鍵 (Hotkey) | 不 patch，走預設 | 一般 uuid |

> `index.ts:311-357` 的 `showTaskProgress` 也會 patch `randomId` 後呼叫 `submit()`，但那是**排程器自身的進度輪詢路徑**（走 Generate），不屬於 Enqueue 路徑，勿混淆。

---

## 3. 階段 2：Python 端註冊函式 / Registration Function

```
gradio 呼叫 f(request, *args)                scripts/task_scheduler.py:291-343
   │  request: gr.Request 由 gradio 依型別注入
   │  args[0] = checkpoint（已由 JS 解析後的最終值）
   │  args[1] = task_id（即 id_task state，來自 randomId()）
   │  args    = args[1:]     ← 丟棄 checkpoint，其餘即「原本 generate 的輸入」(300)
   ├─ if task_id == "$$_queue_with_all_checkpoints_$$" → checkpoint = list_checkpoint_tiles() (304-306)
   ├─ elif not task_id.startswith("task(") → task_name = task_id; task_id = uuid4() (309-311)
   ├─ checkpoint 解析 (313-322)
   └─ for i, c in enumerate(checkpoint):    (325-338)  ← 多 checkpoint 會產生 N 個 task
         task_runner.register_ui_task(t_id, is_img2img, *args,
                                      checkpoint=c, task_name=task_name, request=request)
```

---

## 4. 階段 3：註冊 / Enqueue into DB

```
register_ui_task                             agent_scheduler/task_runner.py:272-303
   ├─ progress.add_task_to_queue(task_id)
   ├─ __serialize_ui_task_args (114-142)
   ├─ task_manager.add_task(Task(...))       ← 寫入 DB
   ├─ __run_callbacks("task_registered", …)  (299)
   └─ __total_pending_tasks += 1
```

---

## 5. 階段 4：觸發執行緒 / Kick off Runner

`task_scheduler.py:341` 呼叫：

```
execute_pending_tasks_threading()            agent_scheduler/task_runner.py:614-636
   ├─ paused / is_executing_task 檢查
   ├─ pending_task = __get_pending_task()    (713-745)
   └─ threading.Thread(target=execute_task,
                       args=(pending_task, self.__get_pending_task))
        └─ execute_task (332) → parse_task_args → __execute_task
```

多 checkpoint 情境下 `register_ui_task` 會被呼叫 N 次，但 `execute_pending_tasks_threading()` **只呼叫一次**；其餘 task 由 `execute_task` 迴圈內的 `get_next_task()` 拉取（`task_runner.py:607`）。

---

## 6. 併行的第二個 click handler / Parallel ControlNet Handler

`task_scheduler.py:280-289`：若偵測到 ControlNet，同一次點擊會額外觸發

```python
self.submit_button.click(fn=UiControlNetUnit,
                         inputs=cnet_fn_block.inputs,
                         outputs=cnet_fn_block.outputs,
                         queue=False)
```

用途是把 ControlNet 的 UI 狀態寫進對應的 `gr.State`，讓主註冊函式抓到的 ControlNet 參數是「按下當下」的值。

---

## 7. `task_runner` 全域的初始化時序 / Initialization Ordering

`task_scheduler.py:899-906` 的模組級 `on_app_started` 執行 `task_runner = get_instance(block)`（`TaskRunner.get_instance` 定義於 `task_runner.py:867-892`）。

而 `f()` 閉包在**呼叫時**才讀取模組全域 `task_runner`（`task_scheduler.py:331`、`341`），因此安全性取決於兩個 `on_app_started` 回呼的執行先後 —— `Script.__init__` 註冊的（`task_scheduler.py:101`）與模組級註冊的（`task_scheduler.py:925`）順序在本倉庫內**沒有保證程式碼**。屬潛在時序風險。

---

## 8. 未驗證項 / Unverified

1. **`create_submit_args` / `randomId`**：`index.ts:43`、`index.ts:46` 只有 ambient 型別宣告，實作來自 webui 本體 JS → 對 `args` 長度與結尾 request 欄位的處理無法在此確認。
2. **`_js=` 參數**：綁定使用 gradio 3 風格的 `_js`（`task_scheduler.py:270`），而 `compat_a1111_forge/ui.py` 的相容層只正規化了 `get_ui_dependencies` / `get_ui_fns`，**沒有**處理 `_js` → 在 gradio 4 環境下該 JS hook 是否仍被採用，屬環境行為，未驗證。
