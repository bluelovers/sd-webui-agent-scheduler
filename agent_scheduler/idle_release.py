from __future__ import annotations

import gc
import threading
import traceback
from typing import Optional

from modules import devices
from modules.shared import state

from agent_scheduler.log import print_message
from agent_scheduler.utils.torch_helpers import unload_all_models

# region Idle release: free memory once no task reached processing for IDLE_RELEASE_TIMEOUT seconds

IDLE_RELEASE_TIMEOUT = 5 * 60

_idle_lock = threading.Lock()
_idle_timer: Optional[threading.Timer] = None
_idle_tasks_running = 0


def _arm_idle_timer():
    """(Re)starts the idle countdown. Caller must hold _idle_lock."""
    global _idle_timer

    if _idle_timer is not None:
        _idle_timer.cancel()

    _idle_timer = threading.Timer(IDLE_RELEASE_TIMEOUT, _release_memory_after_idle)
    _idle_timer.daemon = True
    _idle_timer.start()


def _release_memory_after_idle():
    """Frees cached models and runs gc after IDLE_RELEASE_TIMEOUT seconds without any task."""
    global _idle_timer

    # the lock is held for the whole release, so a task starting meanwhile waits for it instead of racing it
    with _idle_lock:
        _idle_timer = None

        if _idle_tasks_running > 0 or state.job != "":
            # a task slipped in before this callback got the lock; keep watching instead of freeing
            _arm_idle_timer()
            return

        print_message(
            f"No task for {IDLE_RELEASE_TIMEOUT} seconds, releasing memory and running gc",
            level="info",
        )

        release_memory()


def release_memory():
    """Unloads all models and runs gc; shared by the idle timer and the unload button."""
    try:
        unload_all_models()
        # _clear_prompt_cache()
    except Exception:
        print_message("Error releasing memory after idle timeout", level="error")
        print_message(traceback.format_exc(), level="debug")
    finally:
        devices.torch_gc()
        gc.collect()


def _clear_prompt_cache():
    """Drops the cached conditioning tensors as well; they hold memory after the models are gone."""
    from modules.processing import StableDiffusionProcessing

    StableDiffusionProcessing.cached_c = [None, None, None]
    StableDiffusionProcessing.cached_uc = [None, None, None]


def begin_task_tracking():
    """A task entered processing: cancel the pending idle release so memory stays available."""
    global _idle_timer, _idle_tasks_running

    with _idle_lock:
        # _idle_tasks_running += 1

        if _idle_timer is not None:
            _idle_timer.cancel()
            _idle_timer = None


def end_task_tracking():
    """A task left processing: restart the five-minute countdown toward the next idle release."""
    global _idle_tasks_running

    with _idle_lock:
        # _idle_tasks_running = max(_idle_tasks_running - 1, 0)

        # if _idle_tasks_running == 0:
        #     _arm_idle_timer()

        _arm_idle_timer()


# endregion
