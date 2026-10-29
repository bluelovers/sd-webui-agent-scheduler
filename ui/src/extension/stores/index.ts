import { createHistoryTasksStore } from './history.store';
import { createPendingTasksStore } from './pending.store';
import { createSharedStore } from './shared.store';

export const sharedStore = createSharedStore({
  uiAsTab: true,
  selectedTab: 'pending',
});

export const pendingStore = createPendingTasksStore({
  current_task_id: null,
  total_pending_tasks: 0,
  pending_tasks: [],
  paused: false,
});

export const historyStore = createHistoryTasksStore({
  total: 0,
  tasks: [],
});
