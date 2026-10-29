import { ColumnMovedEvent, ColumnResizedEvent, GridApi, GridOptions, SortChangedEvent } from 'ag-grid-community';

import { Task } from '../types';

/** 將當前欄位順序、寬度與排序寫入 localStorage */
function saveColumnState(api: GridApi<Task>, storageKey: string): void {
  const colState = api.getColumnState();
  const colStateStr = JSON.stringify(colState);
  localStorage.setItem(storageKey, colStateStr);
}

/** 從 localStorage 還原欄位順序、寬度與排序；無紀錄時不做任何事 */
function restoreColumnState(api: GridApi<Task>, storageKey: string): void {
  const colStateStr = localStorage.getItem(storageKey);
  if (colStateStr == null) return;

  const colState = JSON.parse(colStateStr);
  api.applyColumnState({ state: colState, applyOrder: true });
}

/**
 * 依 storageKey 產生「欄位狀態持久化」的 grid 事件組與還原函式
 *
 * 兩個頁籤的行為完全相同，差別只在 localStorage 的鍵名；
 * handlers 直接展開到 gridOptions 上即可取得三個存檔 handler，
 * onGridReady 末尾呼叫 restore 則負責還原。
 *
 * @param storageKey - localStorage 鍵名，例如 `agent_scheduler:queue_col_state`
 */
export function createColumnStatePersistence(storageKey: string): {
  handlers: Pick<GridOptions<Task>, 'onColumnMoved' | 'onSortChanged' | 'onColumnResized'>;
  restore: (api: GridApi<Task>) => void;
} {
  return {
    handlers: {
      onColumnMoved: ({ api }: ColumnMovedEvent<Task>) => saveColumnState(api, storageKey),
      onSortChanged: ({ api }: SortChangedEvent<Task>) => saveColumnState(api, storageKey),
      onColumnResized: ({ api }: ColumnResizedEvent<Task>) => saveColumnState(api, storageKey),
    },
    restore: (api: GridApi<Task>) => restoreColumnState(api, storageKey),
  };
}
