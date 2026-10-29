import { createGrid, GridApi, GridOptions } from 'ag-grid-community';

import { debounce } from '../../utils/debounce';

import { Task } from '../types';
import { initSearchInput } from './search-input';

/**
 * 綁定快速搜尋輸入框，輸入時以 debounced quickFilterText 篩選表格
 *
 * @param api - 目標 grid 的 GridApi
 * @param selector - 搜尋框容器的 selector
 */
export function bindQuickSearch(api: GridApi<Task>, selector: string): void {
  const searchInput = initSearchInput(selector);
  searchInput.addEventListener(
    'keyup',
    debounce(function () {
      api.updateGridOptions({ quickFilterText: this.value });
    }, 200)
  );
}

/**
 * 以 store 內容驅動表格 rowData，並在更新後整理焦點與欄寬
 *
 * 兩個頁籤的同步流程相同，差別在 rowData 取自哪個欄位，
 * 以及更新後是否需要額外刷新特定儲存格（如執行中任務的那一列）。
 *
 * @param store - 具備 subscribe / getState 的 zustand store
 * @param getRowData - 從 store state 取出 rowData 的函式
 * @param onAfterUpdate - rowData 套用後、整理焦點前呼叫的額外更新鉤子
 */
export function bindRowData<TState>(
  api: GridApi<Task>,
  store: {
    subscribe: (listener: (state: TState) => void) => void;
    getState: () => TState;
  },
  getRowData: (state: TState) => Task[],
  onAfterUpdate?: (state: TState, api: GridApi<Task>) => void
): void {
  const updateRowData = (state: TState) => {
    api.updateGridOptions({ rowData: getRowData(state) });

    onAfterUpdate?.(state, api);

    api.clearFocusedCell();
    api.autoSizeAllColumns();
  };
  store.subscribe(updateRowData);
  updateRowData(store.getState());
}

/**
 * 依容器 selector 建立表格，套用 data-page-size 後呼叫 createGrid
 *
 * 容器若以 data-page-size 指定每頁列數（大於 0），
 * 則改用固定頁大小並關閉自動頁大小。
 *
 * @param containerSelector - 表格容器的 selector
 * @param gridOptions - 已組裝完成的 grid options
 */
export function createTaskGrid(containerSelector: string, gridOptions: GridOptions<Task>): void {
  const eGridDiv = gradioApp().querySelector<HTMLDivElement>(containerSelector)!;

  if (typeof eGridDiv.dataset.pageSize === 'string') {
    const pageSize = parseInt(eGridDiv.dataset.pageSize, 10);

    if (pageSize > 0) {
      gridOptions.paginationAutoPageSize = false;
      gridOptions.paginationPageSize = pageSize;
    }
  }

  createGrid(eGridDiv, gridOptions);
}
