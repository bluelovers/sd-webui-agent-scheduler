# tests

本目錄是 Agent Scheduler 擴充的測試

## 環境與依賴

- **不需安裝任何東西**：只用 Python 標準庫 `unittest`，不依賴 pytest / tox / coverage。
  **Nothing to install**: only the standard-library `unittest`; no pytest / tox / coverage.
- **不需啟動 webui**：`gradio`、`requests` 與 sd-webui runtime（`modules.*`）都**不需要**。
- 測試產物寫入 `AGENT_SCHEDULER_TEST_DIR`（未設定時用系統暫存目錄）；

## 如何執行

在擴充目錄（`…/extensions/sd-webui-agent-scheduler`）執行 / run from the extension root:

```bat
pyrun.bat tests\run_tests.py    :: 標準命令 / the standard command
```

等價寫法 / equivalents:

```bat
python tests\run_tests.py
python -m unittest discover -s tests -t .    :: all
python tests\test_task_output.py             :: one file
```

- interpreter 的挑選、`.env` 與快取行為由 `pyrun.ps1` 定義；`pyrun.bat --which` 顯示將使用的 interpreter。
- Exit code：`0` = 全部通過 / all passed，`1` = 有至少一項失敗 / at least one failure。

## 涵蓋範圍

| 檔案 | What is tested |
|---|---|
| `test_task_output.py` | 巢狀殘留路徑的判斷／修復、根目錄守門（保證不再疊層）、空資料夾清理、當日資料夾防護、`.txt` 原因報告 |
| `test_shared_opts_backup.py` | 快照檔不覆寫、`computed` 根目錄記錄、每 key 只備份一次、備份前修復巢狀路徑、還原後路徑正確、`simplify_path` |
| `test_prompt_box_style.py` | `prompt_box_style` 支援偵測（`ui_toprow` 實作比對，而非只看選項）、Compact 判定與 `compact_prompt_box` 回退、以 `sys.modules` 替身模擬缺 API 時不拋例外、`is_compact_layout()` 純結構偵測 |
| `test_enqueue_placement.py` | classic / Compact × Near Generate / Between 的掛載點矩陣（Compact 時 Enqueue 跟著 Generate 進 `results`、Between 落在 `prompt_container`）、非掛載時機回傳 None |
| `test_batch_files.py` | `.bat` / `.ps1` 格式防護（規則見該測試檔的 docstring） |
| `test_checkpoint_override.py` | texts 標籤雙寫三態（清理／雙寫／輸入不變）、`resolve_checkpoint_title` 命中與未命中、`apply_checkpoint_override` 五案例（None 不動、System 移除、具名正規化為 title、解析失敗警告＋退回系統、非字典正規化）；以 `sys.modules` 替身滿足 `task_helpers` 的模組層匯入 |

**未涵蓋:** `task_runner.py` 與 `scripts/task_scheduler.py` 需要 sd-webui runtime（`modules.*`），
無法在不啟動 webui 的狀態下匯入，因此僅做語法驗證（`py_compile`，指令見 `AGENTS.md` 的「驗證」）。
`task_helpers.py` 的純邏輯（checkpoint 覆寫）已由 `test_checkpoint_override.py` 以 `sys.modules` 替身涵蓋。

## 檔案

- `_support.py` — 測試共用工具（路徑注入、暫存工作目錄、斷言輔助）/ shared helpers
- `run_tests.py` — 一次執行全部測試的入口
- `run_tests_uv.bat` — double-click 入口：切到擴充目錄後呼叫 `pyrun.bat`
- `test_task_output.py` — `agent_scheduler/task_output.py` 的測試
- `test_shared_opts_backup.py` — `agent_scheduler/shared_opts_backup.py` 的測試
- `test_prompt_box_style.py` — `agent_scheduler/compat_a1111_forge/prompt_box_style.py` 的測試
- `test_enqueue_placement.py` — `agent_scheduler/enqueue_placement.py` 的測試
- `test_batch_files.py` — `.bat` / `.ps1` 格式防護
- `test_checkpoint_override.py` — `agent_scheduler/compat_a1111_forge/infotext_labels.py` 與 `agent_scheduler/task_helpers.py`（checkpoint 覆寫）的測試
