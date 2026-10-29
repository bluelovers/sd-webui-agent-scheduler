import {
  CellClickedEvent,
  CellClassParams,
  GridOptions,
  ICellRendererParams,
  ITooltipParams,
} from 'ag-grid-community';

import bookmark from '../../assets/icons/bookmark.svg?raw';
import bookmarked from '../../assets/icons/bookmark-filled.svg?raw';
import deleteIcon from '../../assets/icons/delete.svg?raw';
import rotateIcon from '../../assets/icons/rotate.svg?raw';

import { historyStore, pendingStore } from '../stores';
import { Task, TaskStatus } from '../types';
import { createColumnStatePersistence } from './column-state';
import { notify } from './notify';
import { actionColumnBase, sharedGridOptions } from './shared-grid-options';
import { bindQuickSearch, bindRowData, createTaskGrid } from './task-grid';

export function initHistoryTab() {
  const store = historyStore;

  // init actions
  const refreshButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_refresh_history'
  )!;
  refreshButton.addEventListener('click', () => store.refresh());
  const clearButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_clear_history'
  )!;
  clearButton.addEventListener('click', () => {
    if (!confirm('Are you sure you want to clear the history?')) return;
    store.clearHistory().then(notify);
  });
  const requeueButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_requeue'
  )!;
  requeueButton.addEventListener('click', () => {
    store.requeueFailedTasks().then(notify);
  });

  const resultTaskId = gradioApp().querySelector<HTMLTextAreaElement>(
    '#agent_scheduler_history_selected_task textarea'
  )!;
  const resultImageId = gradioApp().querySelector<HTMLTextAreaElement>(
    '#agent_scheduler_history_selected_image textarea'
  )!;
  const resultGallery = gradioApp().querySelector<HTMLDivElement>(
    '#agent_scheduler_history_gallery'
  )!;
  resultGallery.addEventListener('click', e => {
    const target = e.target as Element | null;
    if (target?.tagName === 'IMG') {
      const imageIdx = Array.prototype.indexOf.call(
        target.parentElement!.parentElement!.children,
        target.parentElement!
      );
      resultImageId.value = imageIdx.toString();
      resultImageId.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });

  window.agent_scheduler_status_filter_changed = value => {
    store.onFilterStatus(value?.toLowerCase() as TaskStatus | undefined);
  };

  // init grid
  const persistence = createColumnStatePersistence('agent_scheduler:history_col_state');

  // 未讀追蹤：以初次渲染（首次非空 tasks）的 id 集合為基準，
  // 之後 refresh 才新增出現的列標記 task-row-unread，點擊該列後移除
  const knownTaskIds = new Set<string>();
  const unreadTaskIds = new Set<string>();
  let baselineReady = false;
  const clearUnreadStyle = (data: Task | undefined, row: Element | null | undefined) => {
    // 先從集合移除，避免後續重繪時 rowClassRules 再次套用
    if (data == null || !unreadTaskIds.delete(data.id)) return;
    row?.classList.remove('task-row-unread');
  };

  const gridOptions: GridOptions<Task> = {
    ...sharedGridOptions,
    readOnlyEdit: true,
    // 初次渲染後才新增的列追加醒目 class；樣式定義於 index.scss 的 .task-row-unread
    rowClassRules: {
      'task-row-unread': ({ data }) => data != null && unreadTaskIds.has(data.id),
    },
    defaultColDef: {
      ...sharedGridOptions.defaultColDef,
      sortable: true,
      editable: ({ colDef }) => colDef?.field === 'name',
    },
    // each entry here represents one column
    columnDefs: [
      {
        headerName: '',
        field: 'bookmarked',
        minWidth: 55,
        maxWidth: 55,
        pinned: 'left',
        sort: 'desc',
        tooltipValueGetter: ({ value }: ITooltipParams<Task, boolean | undefined, any>) =>
          value === true ? 'Unbookmark' : 'Bookmark',
        cellClass: ({ value }: CellClassParams<Task, boolean | undefined>) => [
          'cursor-pointer',
          'pt-3',
          value === true ? 'ts-bookmarked' : 'ts-bookmark',
        ],
        cellRenderer: ({ data, value }: ICellRendererParams<Task, boolean | undefined>) => {
          const node = document.createElement('div');
          node.className = 'ts-bookmark-cell';
          node.innerHTML = `
            <span class="ts-bookmark-icon">${value === true ? bookmarked : bookmark}</span>
            <span class="ts-history-index"></span>
          `;

          // 序號 newest-first：tasks[0] 即最後一筆，故以 total 遞減編號
          const { tasks, total } = store.getState();
          const index = data != null ? tasks.findIndex(task => task.id === data.id) : -1;
          if (index >= 0) {
            node.querySelector<HTMLElement>('.ts-history-index')!.textContent = `#${total - index}`;
          }

          return node;
        },
        onCellClicked: ({
          api,
          data,
          value,
          event,
        }: CellClickedEvent<Task, boolean | undefined>) => {
          if (data == null) return;

          if (event != null) {
            event.stopPropagation();
            event.preventDefault();
          }

          // bookmark 欄會攔截事件，未讀樣式的移除須在此一併處理
          clearUnreadStyle(data, (event?.target as Element | null)?.closest('.ag-row'));

          const bookmarked = value === true;
          store.bookmarkTask(data.id, !bookmarked).then(res => {
            notify(res);
            api.applyTransaction({
              update: [{ ...data, bookmarked: !bookmarked }],
            });
          });
        },
      },
      {
        field: 'priority',
        hide: true,
        sort: 'desc',
      },
      {
        ...sharedGridOptions.columnDefs![0],
        rowDrag: false,
      },
      ...sharedGridOptions.columnDefs!.slice(1),
      {
        ...actionColumnBase,
        cellRenderer: ({ api, data, value }: ICellRendererParams<Task, string | undefined>) => {
          if (data == null || value == null) return;

          const node = document.createElement('div');
          node.innerHTML = `
          <div class="inline-flex mt-1" role="group">
            <button type="button" title="Requeue" class="ts-btn-action primary ts-btn-run">
              ${rotateIcon}
            </button>
            <button type="button" title="Delete" class="ts-btn-action stop ts-btn-delete">
              ${deleteIcon}
            </button>
          </div>
          `;

          const btnRun = node.querySelector<HTMLButtonElement>('button.ts-btn-run')!;
          btnRun.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            // 按鈕會 stopPropagation，requeue 代表已看過該列，一併清除未讀樣式
            clearUnreadStyle(data, (e.currentTarget as Element).closest('.ag-row'));
            store.requeueTask(value).then(notify);
          });
          const btnDelete = node.querySelector<HTMLButtonElement>('button.ts-btn-delete')!;
          btnDelete.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            api.showLoadingOverlay();
            pendingStore.deleteTask(value).then(res => {
              notify(res);
              api.applyTransaction({ remove: [data] });
              api.hideOverlay();
            });
          });

          return node;
        },
      },
    ],
    rowSelection: 'single',
    suppressRowDeselection: true,
    ...persistence.handlers,
    onGridReady: ({ api }) => {
      // init quick search input
      bindQuickSearch(api, '#agent_scheduler_action_search_history');

      // 未讀追蹤須先於 bindRowData 訂閱：zustand 依訂閱順序同步呼叫 listener，
      // 讓 unreadTaskIds 在 rowData 套用（列建立、rowClassRules 評估）前就緒
      store.subscribe(state => {
        if (!baselineReady) {
          // 首次非空資料即為基準（通常是第一次 refresh），整批不算未讀
          if (state.tasks.length === 0) return;
          baselineReady = true;
          state.tasks.forEach(task => knownTaskIds.add(task.id));
          return;
        }

        // 之後才新增出現的 id 標記為未讀
        state.tasks.forEach(task => {
          if (!knownTaskIds.has(task.id)) {
            knownTaskIds.add(task.id);
            unreadTaskIds.add(task.id);
          }
        });
      });

      bindRowData(api, store, state => state.tasks);

      // restore col state
      persistence.restore(api);
    },
    onRowClicked: ({ data, event }) => {
      // bookmark 欄已 stopPropagation，其餘欄位點擊列任意處即標記已讀
      clearUnreadStyle(data, (event?.target as Element | null)?.closest('.ag-row'));
    },
    onSelectionChanged: ({ api }) => {
      const [selected] = api.getSelectedRows();
      resultTaskId.value = selected.id;
      resultTaskId.dispatchEvent(new Event('input', { bubbles: true }));
    },
    onCellEditRequest: ({ api, data, colDef, newValue }) => {
      if (colDef.field !== 'name') return;

      const name = newValue as string | undefined;
      if (name == null) return;

      api.showLoadingOverlay();
      historyStore.renameTask(data.id, name).then(res => {
        notify(res);
        const newData = { ...data, name };
        api.applyTransaction({ update: [newData] });
        api.hideOverlay();
      });
    },
  };

  createTaskGrid('#agent_scheduler_history_tasks_grid', gridOptions);
}
