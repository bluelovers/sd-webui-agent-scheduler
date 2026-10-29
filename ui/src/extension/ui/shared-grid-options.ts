import {
  CellClassParams,
  ColDef,
  GridOptions,
  ValueFormatterParams,
  ValueGetterParams,
} from 'ag-grid-community';

import { Task } from '../types';

// load samplers and checkpoints
export const samplers: string[] = [];
export const checkpoints: string[] = ['System'];

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
      minWidth: 80,
      maxWidth: 80,
      editable: false,
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
        {
          field: 'params.size',
          headerName: 'Size',
          minWidth: 110,
          maxWidth: 110,
          editable: false,
          valueGetter: ({ data }: ValueGetterParams<Task, string | undefined>) => {
            const params = data?.params;
            return params != null ? `${params.width} × ${params.height}` : undefined;
          },
        },
        {
          field: 'params.batch',
          headerName: 'Batching',
          minWidth: 100,
          maxWidth: 100,
          editable: false,
          valueGetter: ({ data }: ValueGetterParams<Task, string>) => {
            const params = data?.params;
            return params != null ? `${params.batch_size} × ${params.n_iter}` : '1 × 1';
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
  paginationAutoPageSize: true,
  suppressCopyRowsToClipboard: true,
  enableBrowserTooltips: true,
  rowClass: [
    'my-ag-row-root',
  ],
};
