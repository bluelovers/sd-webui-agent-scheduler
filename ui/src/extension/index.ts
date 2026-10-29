import { extractArgs } from '../utils/extract-args';

import { historyStore, pendingStore, sharedStore } from './stores';
import { ProgressResponse, ResponseStatus } from './types';
import { initHistoryTab } from './ui/history-tab';
import { notify } from './ui/notify';
import { initPendingTab } from './ui/pending-tab';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import 'notyf/notyf.min.css';
import './index.scss';

declare global {
  let opts: object;
  function gradioApp(): HTMLElement;
  function randomId(): string;
  function origRandomId(): string;
  function get_tab_index(name: string): number;
  function create_submit_args(args: any[]): any[];
  function requestProgress(
    id: string,
    progressContainer: HTMLElement,
    imagesContainer: HTMLElement,
    onDone?: () => void,
    onProgress?: (res: ProgressResponse) => void
  ): void;
  function onUiLoaded(callback: () => void): void;
  function notify(response: ResponseStatus): void;
  function submit(...args: any[]): any[];
  function submit_txt2img(...args: any[]): any[];
  function submit_img2img(...args: any[]): any[];
  function submit_enqueue(...args: any[]): any[];
  function submit_enqueue_img2img(...args: any[]): any[];
  function agent_scheduler_status_filter_changed(value: string): void;
  function appendContextMenuOption(selector: string, label: string, callback: () => void): void;
  function modalSaveImage(event: Event): void;
}

/**
 * 佇列狀態提示文字：初始值由 agent_scheduler/sd_webui/main_any2img.py 的
 * QUEUE_STATUS_RUNNING / QUEUE_STATUS_PAUSED 渲染，此處字串須與其一致，
 * 供 updateUiState 在 paused 切換時改寫狀態標籤
 */
const QUEUE_STATUS_RUNNING = 'Queue running';
const QUEUE_STATUS_PAUSED = 'Queue paused';

/**
 * 切換便捷 Pause/Resume 與佇列狀態提示的顯示狀態
 *
 * gradio 的 `visible` 可能以 class、`hidden` 屬性或 `style.display` 實作，
 * 三者一起切換，兩種 sd-webui 環境才會得到一致結果。
 * 此外 gradio 對部分元件（例如 Textbox）會把 visible 標在包住 id 的容器上，
 * 只清元素本身不會真的顯示，所以顯示時會由元素往上清到快速列為止；
 * 遇到 .agent_scheduler_quick_row 就停，不跨越快速列，避免動到頁籤層級的顯示狀態。
 */
function setElementHidden(element: HTMLElement, hidden: boolean): void {
  if (hidden) {
    element.classList.add('hide', 'hidden');
    element.toggleAttribute('hidden', true);
    element.style.display = 'none';
    return;
  }

  // 不隱藏：移除元素本身的 hide、hidden 兩個 class
  element.classList.remove('hide', 'hidden');
  element.toggleAttribute('hidden', false);
  element.style.display = '';

  let node: HTMLElement | null = element.parentElement;
  for (let depth = 0; node && depth < 4; depth += 1) {
    if (node.id === 'agent_scheduler_pending_tasks_actions' || node.classList.contains('agent_scheduler_quick_row')) {
      break;
    }
    node.classList.remove('hide', 'hidden');
    node.removeAttribute('hidden');
    if (node.style.display === 'none') {
      node.style.display = '';
    }
    if (node.getClientRects().length > 0) {
      break;
    }
    node = node.parentElement;
  }
}

/**
 * 取得成對便捷列元素的反向 id
 *
 * pause/resume 按鈕與狀態 Textbox 的 id 以 _enqueue_pause / _enqueue_resume 結尾，
 * 兩者由同一個 paused 狀態驅動，可互相推得對方 id。
 *
 * @param id - 原元素 id
 * @returns 反向元素的 id；不屬於成對 id 時回傳 null
 */
function getCounterEnqueueId(id: string): string | null {
  if (id.endsWith('_pause')) {
    return `${id.slice(0, -'_pause'.length)}_resume`;
  }
  if (id.endsWith('_resume')) {
    return `${id.slice(0, -'_resume'.length)}_pause`;
  }
  return null;
}

/**
 * 切換狀態標籤的「處理中」紅綠邊框動畫 class
 *
 * 按下 pause/resume 時開啟，notify 收到回應時關閉；
 * 每次都重新查詢：gradio 重建 DOM 之後，init 時快取的節點會失效。
 *
 * @param switching - 是否顯示處理中動畫
 */
function setStatusSwitching(switching: boolean): void {
  gradioApp()
    .querySelectorAll<HTMLElement>('.agent_scheduler_status_label')
    .forEach(el => el.classList.toggle('agent_scheduler_status_label--switching', switching));
}

window.notify = notify;
window.origRandomId = window.randomId;

function showTaskProgress(task_id: string, type: string | undefined, callback: () => void) {
  // delay progress request until the options loaded
  if (Object.keys(opts).length === 0) {
    setTimeout(() => showTaskProgress(task_id, type, callback), 500);
    return;
  }

  const args = extractArgs(requestProgress);

  const gallery = gradioApp().querySelector<HTMLDivElement>(
    '#agent_scheduler_current_task_images'
  )!;

  // A1111 version
  if (args.includes('progressbarContainer')) {
    requestProgress(task_id, gallery, gallery, callback);
  } else {
    // Vlad version
    const progressDiv = document.createElement('div');
    progressDiv.className = 'progressDiv';
    gallery.parentElement!.insertBefore(progressDiv, gallery);
    requestProgress(
      task_id,
      gallery,
      gallery,
      () => {
        progressDiv.remove();
        callback();
      },
      res => {
        const perc = `${Math.round(res.progress * 100.0)}%`;
        const eta = res.paused ? 'Paused' : `ETA: ${Math.round(res.eta)}s`;
        progressDiv.innerText = `${perc} ${eta}`;
        progressDiv.style.background = `linear-gradient(to right, var(--primary-500) 0%, var(--primary-800) ${perc}, var(--neutral-700) ${perc})`;
      }
    );
  }

  // monkey patch randomId to return task_id, then call submit to trigger progress
  window.randomId = () => task_id;
  if (type === 'txt2img') {
    submit();
  } else if (type === 'img2img') {
    submit_img2img();
  }
  window.randomId = window.origRandomId;
}

function initQueueHandler() {
  const getUiCheckpoint = (is_img2img: boolean) => {
    const enqueue_wrapper_model = gradioApp().querySelector<HTMLInputElement>(
      `#${is_img2img ? 'img2img_enqueue_wrapper' : 'txt2img_enqueue_wrapper'} input`
    );
    if (enqueue_wrapper_model != null) {
      const checkpoint = enqueue_wrapper_model.value;
      if (checkpoint === 'Runtime Checkpoint' || checkpoint !== 'Current Checkpoint') {
        return checkpoint;
      }
    }

    const setting_sd_model = gradioApp().querySelector<HTMLInputElement>(
      '#setting_sd_model_checkpoint input'
    );
    return setting_sd_model?.value ?? 'Current Checkpoint';
  };

  const btnEnqueue = gradioApp().querySelector<HTMLButtonElement>('#txt2img_enqueue')!;
  window.submit_enqueue = (...args) => {
    const res = create_submit_args(args);
    res[0] = getUiCheckpoint(false);
    res[1] = randomId();
    window.randomId = window.origRandomId;

    if (btnEnqueue != null) {
      btnEnqueue.innerText = 'Queued';
      setTimeout(() => {
        btnEnqueue.innerText = 'Enqueue';
        if (!sharedStore.getState().uiAsTab) {
          if (sharedStore.getState().selectedTab === 'pending') {
            pendingStore.refresh();
          }
        }
      }, 1000);
    }

    return res;
  };

  const btnImg2ImgEnqueue = gradioApp().querySelector<HTMLButtonElement>('#img2img_enqueue')!;
  window.submit_enqueue_img2img = (...args) => {
    const res = create_submit_args(args);
    res[0] = getUiCheckpoint(true);
    res[1] = randomId();
    res[2] = get_tab_index('mode_img2img');
    window.randomId = window.origRandomId;

    if (btnImg2ImgEnqueue != null) {
      btnImg2ImgEnqueue.innerText = 'Queued';
      setTimeout(() => {
        btnImg2ImgEnqueue.innerText = 'Enqueue';
        if (!sharedStore.getState().uiAsTab) {
          if (sharedStore.getState().selectedTab === 'pending') {
            pendingStore.refresh();
          }
        }
      }, 1000);
    }

    return res;
  };

  // detect queue button placement
  const interrogateCol = gradioApp().querySelector<HTMLDivElement>('.interrogate-col');
  if (interrogateCol != null && interrogateCol.childElementCount > 2) {
    interrogateCol.classList.add('has-queue-button');
  }

  // setup keyboard shortcut
  const setting = gradioApp().querySelector<HTMLTextAreaElement>(
    '#setting_queue_keyboard_shortcut textarea'
  )!;
  if (!setting.value.includes('Disabled')) {
    const parts = setting.value.split('+');
    const code = parts.pop();

    const handleShortcut = (e: KeyboardEvent) => {
      if (e.code !== code) return;
      if (parts.includes('Shift') && !e.shiftKey) return;
      if (parts.includes('Alt') && !e.altKey) return;
      if (parts.includes('Command') && !e.metaKey) return;
      if ((parts.includes('Control') || parts.includes('Ctrl')) && !e.ctrlKey) return;

      e.preventDefault();
      e.stopPropagation();

      const activeTab = get_tab_index('tabs');
      if (activeTab === 0) {
        btnEnqueue.click();
      } else if (activeTab === 1) {
        btnImg2ImgEnqueue.click();
      }
    };

    window.addEventListener('keydown', handleShortcut);

    const txt2imgPrompt = gradioApp().querySelector<HTMLTextAreaElement>(
      '#txt2img_prompt textarea'
    )!;
    txt2imgPrompt.addEventListener('keydown', handleShortcut);

    const img2imgPrompt = gradioApp().querySelector<HTMLTextAreaElement>(
      '#img2img_prompt textarea'
    )!;
    img2imgPrompt.addEventListener('keydown', handleShortcut);
  }

  // watch for current task id change
  pendingStore.subscribe((curr, prev) => {
    const id = curr.current_task_id;
    if (id !== prev.current_task_id && id != null) {
      const task = curr.pending_tasks.find(t => t.id === id);
      showTaskProgress(id, task?.type, pendingStore.refresh);
    }
  });

  // context menu
  const queueWithTaskName = (img2img = false) => {
    const name = prompt('Enter task name');
    window.randomId = () => name ?? window.origRandomId();
    if (img2img) {
      btnImg2ImgEnqueue.click();
    } else {
      btnEnqueue.click();
    }
  };
  const queueWithEveryCheckpoint = (img2img = false) => {
    window.randomId = () => '$$_queue_with_all_checkpoints_$$';
    if (img2img) {
      btnImg2ImgEnqueue.click();
    } else {
      btnEnqueue.click();
    }
  };

  appendContextMenuOption('#txt2img_enqueue', 'Queue with task name', () => queueWithTaskName());
  appendContextMenuOption('#txt2img_enqueue', 'Queue with all checkpoints', () =>
    queueWithEveryCheckpoint()
  );
  appendContextMenuOption('#img2img_enqueue', 'Queue with task name', () =>
    queueWithTaskName(true)
  );
  appendContextMenuOption('#img2img_enqueue', 'Queue with all checkpoints', () =>
    queueWithEveryCheckpoint(true)
  );

  // preview modal save button
  const origModalSaveImage = window.modalSaveImage;
  window.modalSaveImage = (event: Event) => {
    const tab = gradioApp().querySelector<HTMLDivElement>('#tab_agent_scheduler')!;
    if (tab.style.display !== 'none') {
      gradioApp().querySelector<HTMLButtonElement>('#agent_scheduler_save')!.click();
      event.preventDefault();
    } else {
      origModalSaveImage(event);
    }
  };
}

function initTabChangeHandler() {
  sharedStore.subscribe((curr, prev) => {
    if (!curr.uiAsTab || curr.selectedTab !== prev.selectedTab) {
      if (curr.selectedTab === 'pending') {
        pendingStore.refresh();
      } else {
        historyStore.refresh();
      }
    }
  });

  // watch for tab activation
  const observer = new MutationObserver(mutationsList => {
    mutationsList.forEach(styleChange => {
      const tab = styleChange.target as HTMLElement;
      const visible = tab.style.display !== 'none';
      if (!visible) return;

      switch (tab.id) {
        case 'tab_agent_scheduler':
          if (sharedStore.getState().selectedTab === 'pending') {
            pendingStore.refresh();
          } else {
            historyStore.refresh();
          }
          break;
        case 'agent_scheduler_pending_tasks_tab':
          sharedStore.setSelectedTab('pending');
          break;
        case 'agent_scheduler_history_tab':
          sharedStore.setSelectedTab('history');
          break;
      }
    });
  });
  const tab = gradioApp().querySelector('#tab_agent_scheduler');
  if (tab != null) {
    observer.observe(tab, { attributeFilter: ['style'] });
  } else {
    sharedStore.setState({ uiAsTab: false });
  }
  observer.observe(gradioApp().querySelector('#agent_scheduler_pending_tasks_tab')!, {
    attributeFilter: ['style'],
  });
  observer.observe(gradioApp().querySelector('#agent_scheduler_history_tab')!, {
    attributeFilter: ['style'],
  });
}

function _queryTogglesElement() {
  const pauseToggleButtons = gradioApp().querySelectorAll<HTMLElement>(
    '#agent_scheduler_action_pause, [id$="_enqueue_pause"]'
  );
  const resumeToggleButtons = gradioApp().querySelectorAll<HTMLElement>(
    '#agent_scheduler_action_resume, [id$="_enqueue_resume"]'
  );

  const statusTextElement = gradioApp().querySelectorAll<HTMLElement>(
    '.agent_scheduler_status_label h2'
  );

  return {
    pauseToggleButtons,
    resumeToggleButtons,
    statusTextElement,
  };
}

let { pauseToggleButtons, resumeToggleButtons, statusTextElement } = _queryTogglesElement();

function _createHookToggleSwitching(action: () => Promise<ResponseStatus>) {
  return () => {
    setStatusSwitching(true);
    return action().then(notify);
  }
}

const hookTogglePauseQueue = _createHookToggleSwitching(() => pendingStore.pauseQueue());
const hookToggleResumeQueue = _createHookToggleSwitching(() => pendingStore.resumeQueue());

/**
 * Pause/Resume 切換邏輯組：家族按鈕綁定與佇列狀態監聽
 *
 * 頁籤按鈕與 Enqueue 列便捷按鈕（元件由 scripts/task_scheduler.py 建立）
 * 作用相同，各以一個家族 selector 合併成一次查詢、共用同一段點擊邏輯；
 * 點擊先開啟狀態標籤動畫再執行 queue 動作，回應回來交給 notify 收尾。
 * 訂閱 store 之後，paused 變動會同步切換按鈕顯示、改寫狀態標籤文字，
 * 並結束狀態標籤的處理中動畫。
 */
function initQueueToggles(): void {

  ({ pauseToggleButtons, resumeToggleButtons, statusTextElement } = _queryTogglesElement());

  /** 開啟狀態標籤動畫後執行對應 queue 動作，回應回來交給 notify 收尾 */
  const bindToggleButtons = (buttons: NodeListOf<HTMLElement>, fn: ReturnType<typeof _createHookToggleSwitching>) => {
    buttons?.forEach(button => {
      button.removeEventListener('click', fn);
      button.addEventListener('click', fn);
    });
  };
  bindToggleButtons(pauseToggleButtons, hookTogglePauseQueue);
  bindToggleButtons(resumeToggleButtons, hookToggleResumeQueue);

  statusTextElement?.forEach(el => el.classList.add('agent_scheduler_status_label--initializing'));
}

function initQueueSubscribe(): void {
  // watch for queue status change
  const updateUiState = (state: ReturnType<typeof pendingStore.getState>) => {
    /**
     * 便捷列跟著同一個 paused 狀態切換，與頁籤那對同步顯示。
     * processed 只存在於本次呼叫：兩條掃描路徑共用，先掃到的路徑連同
     * 反向 id 的成對元素一起入集合，後一條路徑碰到已處理元素就跳過，
     * 同一輪更新內每個元素只會被 setElementHidden 一次。
     * 每次都重新查詢：gradio 重建 DOM 之後，init 時快取的節點會失效。
     */
    const processed = new WeakSet<HTMLElement>();

    /**
     * 處理單一元素：入集合後套用隱藏狀態，
     * 再依反向 id 查出成對元素，存在時一併入集合並套用相反狀態
     */
    const applyHidden = (element: HTMLElement, hidden: boolean): void => {
      if (processed.has(element)) return;
      processed.add(element);
      setElementHidden(element, hidden);

      const counterId = getCounterEnqueueId(element.id);
      if (counterId == null) return;

      const counter = gradioApp().querySelector<HTMLElement>(`#${counterId}`);
      if (counter == null || processed.has(counter)) return;
      processed.add(counter);
      setElementHidden(counter, !hidden);
    };

    pauseToggleButtons.forEach(el => applyHidden(el, state.paused));
    resumeToggleButtons.forEach(el => applyHidden(el, !state.paused));

    /**
     * 狀態標籤文字跟著 paused 切換；文字在 server 端以 gr.Label 建立，
     * 這裡直接改寫 h2 內容，不另發送更新請求。
     * 每次都重新查詢：gradio 重建 DOM 之後，init 時快取的節點會失效。
     */
    const statusText = state.paused ? QUEUE_STATUS_PAUSED : QUEUE_STATUS_RUNNING;
    statusTextElement
      .forEach(el => {
        el.textContent = statusText;
      });

    setStatusSwitching(false);
  };
  pendingStore.subscribe(updateUiState);
  updateUiState(pendingStore.getState());

  statusTextElement.forEach(el => el.classList.remove('agent_scheduler_status_label--initializing'));
}

let agentSchedulerInitialized = false;
onUiLoaded(function initAgentScheduler() {

  if (pauseToggleButtons?.length || resumeToggleButtons?.length || statusTextElement?.length) {
    initQueueToggles();
  }

  // delay ui init until dom is available
  if (gradioApp().querySelector('#agent_scheduler_tabs') == null) {
    setTimeout(initAgentScheduler, 1000);
    return;
  }

  if (agentSchedulerInitialized) return;
  initQueueHandler();
  initTabChangeHandler();
  initQueueToggles();
  initQueueSubscribe();
  initPendingTab();
  initHistoryTab();
  agentSchedulerInitialized = true;
});
