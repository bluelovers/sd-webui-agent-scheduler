# tests/ — 固定測試 / Permanent tests

本目錄是 Agent Scheduler 擴充的固定測試，取代過去的臨時腳本。
This folder holds the extension's permanent tests, replacing the earlier throw-away scripts.

## 環境與依賴 / Environment & dependencies

- **不需安裝任何東西**：只用 Python 標準庫 `unittest`，不依賴 pytest / tox / coverage。
  **Nothing to install**: only the standard-library `unittest`; no pytest / tox / coverage.
- **只需要 Python 標準庫**：`gradio`、`requests` 與 sd-webui runtime（`modules.*`）都
  **不需要**，因此任何 Python 解釋器都跑得起來（含 uv 自帶的 Python）。
  關鍵是被測模組的 logger 已從 `helpers.py`（會連帶 import gradio）抽到純標準庫的
  `agent_scheduler/log.py`，`task_output.py` 與 `shared_opts_backup.py` 因此不必為了
  取得 logger 而載入 gradio。
- 測試產物寫入 `AGENT_SCHEDULER_TEST_DIR`（未設定時用系統暫存目錄）；
  同名工作目錄每次執行前先清空，舊產物不會累積。

## 如何執行

**擴充目錄**（`…/extensions/sd-webui-agent-scheduler`）Run from the extension root:

```bat
:: 一次跑全部（建議）/ run everything (recommended)
python tests\run_tests.py
```

Example for Forge Neo:

```bat
"D:\Program Files (AI)\sd-webui-forge-classic\venv\Scripts\python.exe" tests\run_tests.py
```

Equivalent forms:

```bat
python -m unittest discover -s tests -t .       :: all
python -m unittest discover -s tests            :: all
python tests\test_task_output.py                :: one file
python tests\test_shared_opts_backup.py         :: one file
```

Exit code: `0` = all passed，`1` = at least one failure。

## 以 uv 執行

```bat
tests\run_tests_uv.bat
```

- 內部等於 `uv run --no-project --python <webui python> tests\run_tests.py`：uv 只負責
  挑 interpreter 與執行，**不安裝任何東西**，也不會在 repo 產生 `.venv` / `uv.lock`
  （git 狀態保持乾淨）。
- interpreter 順序：**不寫死任何絕對路徑**，依序為：
  1. 環境變數 `WEBUI_PYTHON`（明確指定，優先權最高）。
     The `WEBUI_PYTHON` environment variable, when set, always wins.
  2. **自動向上搜尋**：從擴充資料夾一路往上，直到發現含 `webui.bat` 的目錄
     （即收留本擴充的 webui 根目錄），再取其專案內的 venv：
     `venv\Scripts\python.exe` → `.venv\Scripts\python.exe`，
     且該 venv **必須真的提供 `gradio`**（避免誤抓只有 ruff/black 的工具環境）。
  3. 都找不到 → **退回 uv 自帶的 Python**（測試只用標準庫，任何 Python 都能跑）。
- 可 double-click、也可從任意目錄以完整路徑呼叫（批次檔自己 `pushd` 到擴充根目錄）。
- **批次檔刻意只用 ASCII 英文註解**：cmd 依 OEM 程式碼頁（cp950 / GBK）解讀 `.bat`，
  UTF-8 中文不只會亂碼，還可能讓 cmd 解析錯行、把註解當指令執行；中英對照見本檔與
  `AGENTS.md`。同理 `rem` 行內不放 `>` / `|`，因為 cmd 連註解行都會解析重導向。

## 涵蓋範圍

| 檔案 | What is tested |
|---|---|
| `test_task_output.py` | 巢狀殘留路徑的判斷／修復、根目錄守門（保證不再疊層）、空資料夾清理、當日資料夾防護、`.txt` 原因報告 |
| `test_shared_opts_backup.py` | 快照檔不覆寫、`computed` 根目錄記錄、每 key 只備份一次、備份前修復巢狀路徑、還原後路徑正確、`simplify_path` |
| `test_prompt_box_style.py` | `prompt_box_style` 支援偵測（`ui_toprow` 實作比對，而非只看選項）、Compact 判定與 `compact_prompt_box` 回退、以 `sys.modules` 替身模擬缺 API 時不拋例外、`is_compact_layout()` 純結構偵測 |
| `test_enqueue_placement.py` | classic / Compact × Near Generate / Between 的掛載點矩陣（Compact 時 Enqueue 跟著 Generate 進 `results`、Between 落在 `prompt_container`）、非掛載時機回傳 None |

**未涵蓋:** `task_runner.py` 與 `scripts/task_scheduler.py` 需要 sd-webui runtime（`modules.*`），
無法在不啟動 webui 的狀態下匯入，因此只做語法驗證：

```bat
python -m py_compile agent_scheduler\task_runner.py agent_scheduler\task_output.py agent_scheduler\shared_opts_backup.py agent_scheduler\compat_a1111_forge\prompt_box_style.py scripts\task_scheduler.py
```

## 檔案

- `_support.py` — 測試共用工具（路徑注入、暫存工作目錄、斷言輔助）/ shared helpers
- `test_task_output.py` — `agent_scheduler/task_output.py` 的測試
- `test_shared_opts_backup.py` — `agent_scheduler/shared_opts_backup.py` 的測試
- `test_prompt_box_style.py` — `agent_scheduler/compat_a1111_forge/prompt_box_style.py` 的測試
- `test_enqueue_placement.py` — `agent_scheduler/enqueue_placement.py` 的測試
- `run_tests.py` — 一次執行全部測試的入口

## 備註

- 測試輸出會帶雙語日誌（中文＋英文）；Windows 欄位若為 cp950 / GBK 可能顯示亂碼，
  但**不影響結果**（判斷一律走回傳值；檔案內容為 UTF-8）。
- 想保留失敗現場以便追查：產物在 `%TEMP%\agent_scheduler_tests\<測試類別名>\`
  （或 `AGENT_SCHEDULER_TEST_DIR\agent_scheduler_tests\...`），下次執行同名測試才會清掉。
