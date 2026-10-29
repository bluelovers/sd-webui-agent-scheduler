import {
  CellClickedEvent,
  CellClassParams,
  createGrid,
  GridOptions,
  ICellRendererParams,
  ITooltipParams,
} from 'ag-grid-community';

import bookmark from '../../assets/icons/bookmark.svg?raw';
import bookmarked from '../../assets/icons/bookmark-filled.svg?raw';
import deleteIcon from '../../assets/icons/delete.svg?raw';
import rotateIcon from '../../assets/icons/rotate.svg?raw';
import { debounce } from '../../utils/debounce';

import { historyStore, pendingStore } from '../stores';
import { Task, TaskStatus } from '../types';
import { notify } from './notify';
import { initSearchInput } from './search-input';
import { sharedGridOptions } from './shared-grid-options';

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
  const gridOptions: GridOptions<Task> = {
    ...sharedGridOptions,
    readOnlyEdit: true,
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
        cellRenderer: ({ value }: ICellRendererParams<Task, boolean | undefined>) =>
          value === true ? bookmarked : bookmark,
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
        headerName: 'Action',
        pinned: 'right',
        minWidth: 110,
        maxWidth: 110,
        resizable: false,
        valueGetter: ({ data }) => data?.id,
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
    onColumnMoved: ({ api }) => {
      const colState = api.getColumnState();
      const colStateStr = JSON.stringify(colState);
      localStorage.setItem('agent_scheduler:history_col_state', colStateStr);
    },
    onSortChanged: ({ api }) => {
      const colState = api.getColumnState();
      const colStateStr = JSON.stringify(colState);
      localStorage.setItem('agent_scheduler:history_col_state', colStateStr);
    },
    onColumnResized: ({ api }) => {
      const colState = api.getColumnState();
      const colStateStr = JSON.stringify(colState);
      localStorage.setItem('agent_scheduler:history_col_state', colStateStr);
    },
    onGridReady: ({ api }) => {
      // init quick search input
      const searchInput = initSearchInput('#agent_scheduler_action_search_history');
      searchInput.addEventListener(
        'keyup',
        debounce(function () {
          api.updateGridOptions({ quickFilterText: this.value });
        }, 200)
      );

      const updateRowData = (state: ReturnType<typeof store.getState>) => {
        api.updateGridOptions({ rowData: state.tasks });
        api.clearFocusedCell();
        api.autoSizeAllColumns();
      };
      store.subscribe(updateRowData);
      updateRowData(store.getState());

      // restore col state
      const colStateStr = localStorage.getItem('agent_scheduler:history_col_state');
      if (colStateStr != null) {
        const colState = JSON.parse(colStateStr);
        api.applyColumnState({ state: colState, applyOrder: true });
      }
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
  const eGridDiv = gradioApp().querySelector<HTMLDivElement>(
    '#agent_scheduler_history_tasks_grid'
  )!;

  if (typeof eGridDiv.dataset.pageSize === 'string') {
    const pageSize = parseInt(eGridDiv.dataset.pageSize, 10);

    if (pageSize > 0) {
      gridOptions.paginationAutoPageSize = false;
      gridOptions.paginationPageSize = pageSize;
    }
  }

  createGrid(eGridDiv, gridOptions);
}
