import {
  CellClassParams,
  ColDef,
  GridOptions,
  ICellRendererParams,
  ValueFormatterParams,
} from 'ag-grid-community';

import copyIcon from '../../assets/icons/copy.svg?raw';

import { Task } from '../types';
import { notify } from './notify';

// load samplers and checkpoints
export const samplers: string[] = [];
export const checkpoints: string[] = ['System'];

/**
 * 型別欄的三行內容：型別、尺寸、批次
 *
 * 三者共用同一欄顯示，故抽成單一來源，
 * 供 valueGetter（過濾／排序用的字串）與 cellRenderer（分行 DOM）共用，
 * 避免格式在兩處各寫一份。
 *
 * @param data - 任務資料；缺 `params` 時尺寸留空、批次沿用原本的 `1 × 1`
 */
function getTypeLines(data: Task | undefined): string[] {
  const params = data?.params;
  return [
    data?.type ?? '',
    params != null ? `${params.width} × ${params.height}` : '',
    params != null ? `${params.batch_size} × ${params.n_iter}` : '1 × 1',
  ];
}

/**
 * 將文字複製到剪貼簿 (Clipboard)，回傳是否複製成功
 *
 * 非安全上下文 (Secure Context)（例如以區域網路 IP 存取 WebUI）
 * 沒有 navigator.clipboard，需退回隱藏 textarea + execCommand 路徑
 *
 * @param text - 要複製的文字
 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    /** Clipboard API 不可用或權限被拒，續行備援路徑 */
  }

  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    const copied = document.execCommand('copy');
    textarea.remove();
    return copied;
  } catch {
    return false;
  }
}

/**
 * Prompt 欄的 cellRenderer：輸出提示詞文字與右上角的複製按鈕
 *
 * 提示詞為空時不輸出按鈕；按鈕攔截 mousedown / click / dblclick，
 * 避免點擊誤觸儲存格編輯與列點擊行為
 *
 * @param value - 提示詞字串
 * @returns 儲存格內容節點
 */
function promptCellRenderer({ value }: ICellRendererParams<Task, string>): HTMLElement {
  const text = value ?? '';

  const node = document.createElement('div');

  if (text !== '') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ts-btn-copy';
    button.title = 'Copy prompt';
    button.innerHTML = copyIcon;

    /**
     * 停止事件冒逸：讓按鈕點擊不進入 grid，
     * 避免 pending 頁籤由點擊啟動編輯、history 頁籤誤判列點擊
     */
    const stopEvent = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
    };
    button.addEventListener('mousedown', stopEvent);
    button.addEventListener('dblclick', stopEvent);
    button.addEventListener('click', event => {
      stopEvent(event);
      copyToClipboard(text).then(copied => {
        notify({ success: copied, message: copied ? 'Prompt copied' : 'Copy failed' });
      });
    });

    node.appendChild(button);
  }

  const content = document.createElement('span');
  content.textContent = text;
  node.appendChild(content);

  return node;
}

/**
 * 兩個頁籤共用的 Action 欄位外框
 *
 * 固定釘在右側、不允許調整寬度，欄位值即 task id；
 * 各頁籤只差 cellRenderer 與其餘少數覆寫，直接展開後補上即可。
 */
export const actionColumnBase: ColDef<Task> = {
  headerName: 'Action',
  pinned: 'right',
  minWidth: 110,
  maxWidth: 110,
  resizable: false,
  valueGetter: ({ data }) => data?.id,
};

export const sharedGridOptions: GridOptions<Task> = {
  // default col def properties get applied to all columns
  defaultColDef: {
    sortable: false,
    filter: true,
    resizable: true,
    suppressMenu: true,
  },
  // each entry here represents one column
  columnDefs: [
    {
      field: 'name',
      headerName: 'Task Id',
      cellDataType: 'text',
      minWidth: 240,
      maxWidth: 240,
      pinned: 'left',
      rowDrag: true,
      valueGetter({ data }) {
        const list = [
          data?.updated_at,
          data?.created_at,
        ]
          .filter(value => value)
          .map(value => value != null ? new Date(value).toLocaleString(document.documentElement.lang) : '');

        // @ts-ignore
        list.unshift(data?.name ?? data?.id);

        return list.join('\n');
      },
      cellClass: ({ data }: CellClassParams<Task, string>) => {
        if (data == null) return;

        return [
          'cursor-pointer',
          `task-${data.status}`,
          'cell-pre',
        ];
      },
    },
    {
      field: 'type',
      headerName: 'Type',
      minWidth: 110,
      maxWidth: 140,
      editable: false,
      // 以 valueGetter 組出三行字串，供過濾／排序使用（renderer 另行呈現）
      valueGetter: ({ data }) => getTypeLines(data).join('\n'),
      cellRenderer: ({ data }: ICellRendererParams<Task, string>) => {
        const lines = getTypeLines(data);

        const node = document.createElement('div');
        node.className = 'type-lines';

        for (const text of lines) {
          const line = document.createElement('div');
          line.className = 'type-lines__item';
          line.textContent = text;
          node.appendChild(line);
        }

        return node;
      },
    },
    {
      field: 'editing',
      editable: false,
      hide: true,
    },
    {
      headerName: 'Params',
      children: [
        {
          field: 'params.prompt',
          headerName: 'Prompt',
          cellDataType: 'text',
          minWidth: 200,
          maxWidth: 400,
          wrapText: true,
          cellClass: [
            'wrap-cell',
            'ag-selectable',
            'cell-prompts',
            'cell-pre',
          ],
          cellRenderer: promptCellRenderer,
        },
        {
          field: 'params.negative_prompt',
          headerName: 'Negative Prompt',
          cellDataType: 'text',
          minWidth: 200,
          maxWidth: 400,
          wrapText: true,
          cellClass: [
            'wrap-cell',
            'ag-selectable',
            'cell-prompts',
            'cell-pre',
          ],
        },
        {
          field: 'params.checkpoint',
          headerName: 'Checkpoint',
          cellDataType: 'text',
          minWidth: 150,
          maxWidth: 300,
          valueFormatter: ({ value }: ValueFormatterParams<Task, string | undefined>) =>
            value ?? 'System',
          cellEditor: 'agSelectCellEditor',
          cellEditorParams: () => ({ values: checkpoints }),
        },
        {
          field: 'params.sampler_name',
          headerName: 'Sampler',
          cellDataType: 'text',
          width: 150,
          minWidth: 150,
          cellEditor: 'agSelectCellEditor',
          cellEditorParams: () => ({ values: samplers }),
        },
        {
          field: 'params.steps',
          headerName: 'Steps',
          cellDataType: 'number',
          minWidth: 80,
          maxWidth: 80,
          filter: 'agNumberColumnFilter',
          cellEditor: 'agNumberCellEditor',
          cellEditorParams: {
            min: 1,
            max: 150,
            precision: 0,
            step: 1,
          },
        },
        {
          field: 'params.cfg_scale',
          headerName: 'CFG Scale',
          cellDataType: 'number',
          width: 100,
          minWidth: 100,
          filter: 'agNumberColumnFilter',
          cellEditor: 'agNumberCellEditor',
          cellEditorParams: {
            min: 1,
            max: 30,
            precision: 1,
            step: 0.5,
          },
        },
      ],
    },
  ],

  getRowId: ({ data }) => data.id,
  rowSelection: 'single', // allow rows to be selected
  animateRows: true, // have rows animate to new positions when sorted
  rowHeight: 250,
  pagination: true,
  paginationPageSize: 50,
  paginationAutoPageSize: false,
  suppressCopyRowsToClipboard: true,
  enableBrowserTooltips: true,
  rowClass: [
    'my-ag-row-root',
  ],
};
