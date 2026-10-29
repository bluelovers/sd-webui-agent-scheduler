import { GridApi, GridOptions, ICellRendererParams, RowHighlightPosition, RowNode } from 'ag-grid-community';

import cancelIcon from '../../assets/icons/cancel.svg?raw';
import deleteIcon from '../../assets/icons/delete.svg?raw';
import playIcon from '../../assets/icons/play.svg?raw';
import saveIcon from '../../assets/icons/save.svg?raw';
import { getHighlightPosition, getPixelOnRow, getRowNodeAtPixel } from '../../utils/ag-grid';

import { pendingStore, sharedStore } from '../stores';
import { Task } from '../types';
import { createColumnStatePersistence } from './column-state';
import { notify } from './notify';
import { actionColumnBase, checkpoints, samplers, sharedGridOptions } from './shared-grid-options';
import { bindQuickSearch, bindRowData, createTaskGrid } from './task-grid';

export function initPendingTab() {
  const store = pendingStore;

  // load data for edit
  sharedStore.getSamplers().then(res => samplers.push(...res));
  sharedStore.getCheckpoints().then(res => checkpoints.push(...res));

  // init actions
  const refreshButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_reload'
  )!;
  refreshButton.addEventListener('click', () => store.refresh());

  const clearButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_clear_queue'
  )!;
  clearButton.addEventListener('click', () => {
    if (confirm('Are you sure you want to clear the queue?')) {
      store.clearQueue().then(notify);
    }
  });

  const importButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_import'
  )!;
  const importInput = gradioApp().querySelector<HTMLInputElement>('#agent_scheduler_import_file')!;

  importButton.addEventListener('click', () => {
    importInput.click();
  });
  importInput.addEventListener('change', e => {
    if (e.target === null) return;

    const files = importInput.files;
    if (files == null || files.length === 0) return;

    const file = files[0];
    const reader = new FileReader();
    reader.onload = () => {
      const data = reader.result as string;
      store
        .importQueue(data)
        .then(notify)
        .then(() => {
          importInput.value = '';
          store.refresh();
        });
    };
    reader.readAsText(file);
  });

  const exportButton = gradioApp().querySelector<HTMLButtonElement>(
    '#agent_scheduler_action_export'
  )!;
  exportButton.addEventListener('click', () => {
    store.exportQueue().then(data => {
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data));
      const dlAnchorElem = document.createElement('a');
      dlAnchorElem.setAttribute('href', dataStr);
      dlAnchorElem.setAttribute('download', `agent-scheduler-${Date.now()}.json`);
      dlAnchorElem.click();
    });
  });

  let lastHighlightedRow: RowNode<Task> | null;

  let pageMoveTimeout: ReturnType<typeof setTimeout> | null;

  const PAGE_MOVE_TIMEOUT_MS = 1.5 * 1000;
  const PAGE_MOVE_Y_MARGIN = 45 / 2; // half of default (min) rowHeight

  const clearPageMoveTimeout = () => {
    if (pageMoveTimeout != null) {
      clearTimeout(pageMoveTimeout);
      pageMoveTimeout = null;
    }
  };
  const updatePageMoveTimeout = (api: GridApi<Task>, pixel: number) => {
    if (lastHighlightedRow == null) {
      clearPageMoveTimeout();
      return;
    }

    const firstRowIndexOfPage = api.paginationGetPageSize() * api.paginationGetCurrentPage();
    const lastRowIndexOfPage = Math.min(
      api.paginationGetPageSize() * (api.paginationGetCurrentPage() + 1) - 1,
      api.getDisplayedRowCount() - 1
    );

    const rowIndex = lastHighlightedRow.rowIndex!;
    if (rowIndex === firstRowIndexOfPage) {
      if (getPixelOnRow(api, lastHighlightedRow, pixel) > PAGE_MOVE_Y_MARGIN) {
        clearPageMoveTimeout();
        return;
      }
      if (pageMoveTimeout == null) {
        pageMoveTimeout = setTimeout(() => {
          if (api.paginationGetCurrentPage() > 0) {
            api.paginationGoToPreviousPage();
            highlightRow(api);
          }
          pageMoveTimeout = null;
        }, PAGE_MOVE_TIMEOUT_MS);
      }
    } else if (rowIndex === lastRowIndexOfPage) {
      if (
        getPixelOnRow(api, lastHighlightedRow, pixel) <
        lastHighlightedRow.rowHeight! - PAGE_MOVE_Y_MARGIN
      ) {
        clearPageMoveTimeout();
        return;
      }
      if (pageMoveTimeout == null) {
        pageMoveTimeout = setTimeout(() => {
          if (api.paginationGetCurrentPage() < api.paginationGetTotalPages() - 1) {
            api.paginationGoToNextPage();
            highlightRow(api);
          }
          pageMoveTimeout = null;
        }, PAGE_MOVE_TIMEOUT_MS);
      }
    }
  };

  let lastPixel: number | null;

  const clearHighlightedRow = () => {
    clearPageMoveTimeout();
    lastPixel = null;
    if (lastHighlightedRow != null) {
      lastHighlightedRow.setHighlighted(null);
      lastHighlightedRow = null;
    }
  };
  const highlightRow = (api: GridApi<Task>, pixel?: number) => {
    if (pixel == null) {
      if (lastPixel == null) return;
      pixel = lastPixel;
    } else {
      lastPixel = pixel;
    }

    const rowNode = getRowNodeAtPixel(api, pixel) as RowNode<Task> | undefined;
    if (rowNode == null) return;

    const highlight = getHighlightPosition(api, rowNode, pixel);
    if (lastHighlightedRow != null && rowNode.id !== lastHighlightedRow.id) {
      clearHighlightedRow();
    }
    rowNode.setHighlighted(highlight);
    lastHighlightedRow = rowNode;
    updatePageMoveTimeout(api, pixel);
  };

  // init grid
  const persistence = createColumnStatePersistence('agent_scheduler:queue_col_state');
  const gridOptions: GridOptions<Task> = {
    ...sharedGridOptions,
    editType: 'fullRow',
    defaultColDef: {
      ...sharedGridOptions.defaultColDef,
      editable: ({ data }) => data?.status === 'pending',
      cellDataType: false,
    },
    // each entry here represents one column
    columnDefs: [
      {
        field: 'priority',
        hide: true,
        sort: 'asc',
      },
      ...sharedGridOptions.columnDefs!,
      {
        ...actionColumnBase,
        editable: false,
        cellClass: 'pending-actions',
        cellRenderer: ({ api, value, data }: ICellRendererParams<Task, string>) => {
          if (data == null || value == null) return;

          const node = document.createElement('div');
          node.innerHTML = `
          <div class="inline-flex mt-1 edit-actions" role="group">
            <button type="button" title="Save" class="ts-btn-action primary ts-btn-save">
              ${saveIcon}
            </button>
            <button type="button" title="Cancel" class="ts-btn-action secondary ts-btn-cancel">
              ${cancelIcon}
            </button>
          </div>
          <div class="inline-flex mt-1 control-actions" role="group">
            <button type="button" title="Run" class="ts-btn-action primary ts-btn-run"
              ${data.status === 'running' ? 'disabled' : ''}>
              ${playIcon}
            </button>
            <button type="button" title="${data.status === 'pending' ? 'Delete' : 'Interrupt'}"
              class="ts-btn-action stop ts-btn-delete">
              ${data.status === 'pending' ? deleteIcon : cancelIcon}
            </button>
            <span class="ml-auto"></span>
          </div>
          `;

          const btnSave = node.querySelector<HTMLButtonElement>('button.ts-btn-save')!;
          btnSave.addEventListener('click', () => {
            api.showLoadingOverlay();
            pendingStore.updateTask(data.id, data).then(res => {
              notify(res);
              api.hideOverlay();
              api.stopEditing(false);
            });
          });

          const btnCancel = node.querySelector<HTMLButtonElement>('button.ts-btn-cancel')!;
          btnCancel.addEventListener('click', () => api.stopEditing(true));

          const btnRun = node.querySelector<HTMLButtonElement>('button.ts-btn-run')!;
          btnRun.addEventListener('click', () => {
            api.showLoadingOverlay();
            store.runTask(value).then(() => api.hideOverlay());
          });
          const btnDelete = node.querySelector<HTMLButtonElement>('button.ts-btn-delete')!;
          btnDelete.addEventListener('click', () => {
            api.showLoadingOverlay();
            store.deleteTask(value).then(res => {
              notify(res);
              api.applyTransaction({ remove: [data] });
              api.hideOverlay();
            });
          });

          return node;
        },
      },
    ],
    ...persistence.handlers,
    onGridReady: ({ api }) => {
      // init quick search input
      bindQuickSearch(api, '#agent_scheduler_action_search');

      bindRowData(
        api,
        store,
        state => state.pending_tasks,
        (state, api) => {
          if (state.current_task_id == null) return;

          const node = api.getRowNode(state.current_task_id);
          if (node != null) {
            api.refreshCells({ rowNodes: [node], force: true });
          }
        }
      );

      // restore col state
      persistence.restore(api);
    },
    onRowDragEnter: ({ api, y }) => highlightRow(api, y),
    onRowDragMove: ({ api, y }) => highlightRow(api, y),
    onRowDragLeave: () => clearHighlightedRow(),
    onRowDragEnd: ({ api, node }) => {
      const highlightedRow = lastHighlightedRow;
      if (highlightedRow == null) {
        clearHighlightedRow();
        return;
      }

      const id = node.data?.id;
      const highlightedId = highlightedRow.data?.id;
      if (id == null || highlightedId == null || id === highlightedId) {
        clearHighlightedRow();
        return;
      }

      let index = -1,
        overIndex = -1;
      const tasks = [...store.getState().pending_tasks].sort((a, b) => a.priority - b.priority);
      for (let i = 0; i < tasks.length; i++) {
        if (tasks[i].id === id) {
          index = i;
        }
        if (tasks[i].id === highlightedId) {
          overIndex = i;
        }
        if (index !== -1 && overIndex !== -1) {
          break;
        }
      }
      if (index === -1 || overIndex === -1) {
        clearHighlightedRow();
        return;
      }
      if (highlightedRow.highlighted === RowHighlightPosition.Below) {
        overIndex += 1;
      }
      if (overIndex === index || overIndex === index + 1) {
        clearHighlightedRow();
        return;
      }

      const overId = tasks[overIndex]?.id ?? 'bottom';

      api.showLoadingOverlay();
      store.moveTask(id, overId).then(() => {
        clearHighlightedRow();
        api.hideOverlay();
      });
    },
    onRowEditingStarted: ({ api, data, node }) => {
      if (data == null) return;

      node.setDataValue('editing', true);
      api.refreshCells({ rowNodes: [node], force: true });
    },
    onRowEditingStopped: ({ api, data, node }) => {
      if (data == null) return;

      node.setDataValue('editing', false);
      api.refreshCells({ rowNodes: [node], force: true });
    },
    onRowValueChanged: ({ api, data }) => {
      if (data == null) return;

      api.showLoadingOverlay();
      pendingStore.updateTask(data.id, data).then(res => {
        notify(res);
        api.hideOverlay();
      });
    },
  };

  createTaskGrid('#agent_scheduler_pending_tasks_grid', gridOptions);
}
