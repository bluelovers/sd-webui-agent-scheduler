"""
task_output.py — 任務輸出資料夾的清理與原因報告

本模組在任務結束後維護該次任務的輸出資料夾：
1. 由內往外移除任務資料夾底下的空子目錄（例如未產出任何圖的 samples／grids）。
2. 若任務資料夾本身已完全變空，則連同該資料夾一併刪除，並在原位置寫入同名的
   .txt 報告，列出資料夾為空的可能原因（硬碟滿、無法寫入、佇列被傾空、取消任務、
   任務出錯、其他／未知原因）。
3. 所有檔案系統操作皆包在例外捕捉中，磁碟滿、無權限或路徑損毀都只記錄日誌，
   不會讓排程執行緒崩潰。
4. 提供路徑分析工具（find_scheduler_index / find_scheduler_prefix /
   repair_stale_outdir），用於修復「上次任務在 restore_shared_opts() 之前中斷」
   所殘留的巢狀輸出路徑，避免下次執行從上次的任務目錄繼續往下疊。
This module maintains a task's output folder after the task ends:
1. Remove empty sub-directories bottom-up (e.g. samples/grids with no images).
2. When the task folder itself ends up completely empty, delete it too and write a
   same-named .txt report at its former location listing the possible reasons
   (disk full, not writable, queue purged, task cancelled, task failed, unknown).
3. Every filesystem call is wrapped in exception handling so a full disk, missing
   permission or broken path is only logged and never crashes the runner thread.
4. Provides path analysis helpers (find_scheduler_index / find_scheduler_prefix /
   repair_stale_outdir) that repair the nested output paths left behind when a
   previous task died before restore_shared_opts(), so the next run never nests
   another level under the previous task folder.
"""

import os
import re
import errno
import shutil
from pathlib import Path, PurePath
from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

# 日誌從獨立的 log 模組取得（純標準庫），本模組因此不需 gradio / webui 即可被匯入，
# 單元測試也才能在任何 Python 解釋器下執行。
# Take the logger from the standalone log module (standard library only) so this
# module imports without gradio / webui, which is what lets the unit tests run under
# any Python interpreter.
from .log import log

# 任務狀態文字常數，與 db.TaskStatus 的值一致。
# 刻意不 import .db：本模組只做檔案系統維護，避免引入資料庫（及其上游 modules.*）相依，
# 讓它在 sd-webui 之外也能獨立測試。
# Status literals mirroring db.TaskStatus values. The .db module is deliberately not
# imported: this module only does filesystem maintenance, so it stays free of the
# database dependency (and its upstream modules.*) and remains testable standalone.
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
STATUS_INTERRUPTED = "interrupted"

# 以下兩種路徑不是任務資料夾，一律不得刪除：
# 1. 當日資料夾（YYYY-MM-DD）：任務資料夾與其同名 .txt 報告的容器。
# 2. 排程輸出根目錄（agent-scheduler）：整棵輸出樹的根。
# The following two paths are not task folders and are never deleted:
# 1. The day folder (YYYY-MM-DD): the container of task folders and their
#    same-named .txt reports.
# 2. The scheduler output root (agent-scheduler): the root of the whole tree.
DAY_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OUTPUT_ROOT_NAME = "agent-scheduler"

# 任務標籤資料夾（本版：HH-MM-SS_task(...)；舊版：YYYY-MM-DD_HH-MM-SS_task(...)）。
# Task label folder (current: HH-MM-SS_task(...); legacy: YYYY-MM-DD_HH-MM-SS_task(...)).
TASK_LABEL_PATTERN = re.compile(r"^\d{2}-\d{2}-\d{2}_.+")
LEGACY_TASK_LABEL_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_.+")


def _is_day_part(part: str) -> bool:
    """是否為當日資料夾層"""
    return bool(DAY_FOLDER_PATTERN.match(part))


def _is_task_label(part: str) -> bool:
    """是否為任務標籤層（含新舊格式）"""
    return bool(TASK_LABEL_PATTERN.match(part)) or bool(LEGACY_TASK_LABEL_PATTERN.match(part))


def _is_tree_part(part: str) -> bool:
    """是否為排程輸出樹的「骨架層」：輸出根、日期層、任務標籤層。
    Whether the part is structural to the scheduler output tree: the output root,
    the day layer or a task label layer.
    """
    return part == OUTPUT_ROOT_NAME or _is_day_part(part) or _is_task_label(part)


def find_scheduler_index(path: Union[Path, str]) -> Optional[int]:
    """
    找出路徑中「排程輸出樹的起點索引」；不在樹內則回傳 None。
    Locate the index where the scheduler output tree begins inside the path;
    return None when the path is not part of that tree.

    判定條件
    1. 路徑必須含任務標籤層（HH-MM-SS_xxx 或舊版格式）——真正的使用者目錄幾乎不可能
       命中，可避免把一般日期資料夾誤判為巢狀殘留。
       The path must contain a task label layer — a real user directory almost never
       matches one, which prevents date-named folders from being misread as leftovers.
    2. 有 agent-scheduler 層時以其為錨點（比日期層可靠）；否則退回第一個日期／標籤層。
       When an agent-scheduler segment exists it is used as the anchor (more reliable
       than the day layer); otherwise fall back to the first day/label segment.
    """
    # 非路徑型別一律視為「不是樹內路徑」，讓呼叫端不必自行做型別判斷
    # Anything that is not path-like is treated as "not inside the tree" so callers
    # do not need their own type checks.
    if not isinstance(path, (str, PurePath)):
        return None

    parts = Path(path).parts

    if not any(_is_task_label(part) for part in parts):
        return None

    if OUTPUT_ROOT_NAME in parts:
        index = parts.index(OUTPUT_ROOT_NAME)
    else:
        index = next(
            (i for i, part in enumerate(parts) if _is_day_part(part) or _is_task_label(part)),
            None,
        )
        if index is None:
            return None

    # index 0 代表相對路徑開頭就是樹根，無法推回前綴 → 視為不可修復
    # index 0 means the tree starts the relative path, so no prefix can be derived
    # → treat it as unrecoverable.
    return index if index > 0 else None


def find_scheduler_prefix(path: Union[Path, str]) -> Optional[Path]:
    """回傳排程輸出樹之前的前綴路徑；不在樹內回傳 None。
    Return the prefix in front of the scheduler output tree, or None if absent."""
    index = find_scheduler_index(path)
    if index is None:
        return None
    return Path(*Path(path).parts[:index])


def repair_stale_outdir(value: Any) -> Optional[Path]:
    """
    修復「上次任務中斷未還原設定」而殘留在 shared.opts 的巢狀輸出路徑。
    Repair a nested output path left behind in shared.opts when the previous task
    was interrupted before its settings were restored.

    例如
    ``D:/out/agent-scheduler/2026-10-10/11-16-47_task(a)/samples``
    → ``D:/out/samples``（去掉整棵排程輸出樹，只保留原始目錄名）

    回傳
    -------
    修正後的路徑；不是巢狀殘留、或無法推回原始目錄名時回傳 None。
    The repaired path, or None when the value is not a leftover or when the
    original directory name cannot be derived.
    """
    if not isinstance(value, (str, PurePath)):
        return None

    path = Path(value)
    index = find_scheduler_index(path)
    if index is None:
        return None

    parts = path.parts
    rest = list(parts[index + 1 :])

    # 樹的骨架（日期層／標籤層／輸出根）不算原始目錄名，由尾端逐一剝除
    # Structural parts (day/label/output root) are not the original directory name;
    # strip them from the tail one by one.
    while rest and _is_tree_part(rest[-1]):
        rest.pop()

    # 剝完沒有剩餘段落 → 原始目錄名不可考 → 不猜、回傳 None
    # Nothing left after stripping → the original name is unrecoverable → do not
    # guess, return None.
    if not rest:
        return None

    return Path(*parts[:index]).joinpath(rest[-1])


def resolve_samples_base(samples_base: Union[Path, str]) -> Path:
    """
    解析「本次任務要用的 samples 基準目錄」，把上次中斷殘留的巢狀路徑修復回原始目錄。
    Resolve the samples base for this task, repairing a nested path left over from a
    previously interrupted task back to the original directory.

    兩種殘留情況
    1. 可修復（原始目錄名可考）→ 回傳修復後的路徑並記錄 warning。
       Recoverable (original directory name derivable) → return the repaired path
       and log a warning.
    2. 不可修復（只剩標籤層、原始目錄名不可考）→ 原樣回傳並記錄 warning，
       由 compose_output_root() 的根目錄守門接手，保證不會往下疊層。
       Unrecoverable (only label layers left, original name unknown) → return it
       unchanged with a warning and let the root guard in compose_output_root()
       take over, which still guarantees no extra nesting.
    """
    base = Path(samples_base)

    repaired = repair_stale_outdir(base)
    if repaired is not None:
        log.warning(
            "[AgentScheduler] 上次任務中斷殘留巢狀輸出路徑，已修復 / "
            "stale nested output path left by an interrupted task, repaired: "
            f"{base.as_posix()} -> {repaired.as_posix()}"
        )
        return repaired

    if find_scheduler_prefix(base) is not None:
        log.warning(
            "[AgentScheduler] 殘留路徑的原始目錄名不可考，交由根目錄守門處理 / "
            "original directory name of the leftover path is unknown, deferring to the "
            f"root guard: {base.as_posix()}"
        )

    return base


def compose_output_root(samples_base: Union[Path, str]) -> Path:
    """
    由 samples 基準目錄推導本次任務的輸出根目錄（agent-scheduler）。
    Derive this task's output root (agent-scheduler) from the samples base.

    正常情況：基準往上一層再接 'agent-scheduler'（維持既有行為）。
    Normal case: base's parent plus 'agent-scheduler' (unchanged behavior).

    根目錄守門
    若（修復後的）基準仍落在排程輸出樹內，表示它是上次中斷殘留的路徑，
    改用「樹之前的前綴 + agent-scheduler」當根目錄，確保不會再多疊一層。
    If the (possibly repaired) base still sits inside the scheduler output tree it is
    a leftover from an interrupted run, so use "prefix before the tree +
    'agent-scheduler'" as the root instead, guaranteeing no extra level is stacked.
    """
    base = repair_stale_outdir(samples_base) or Path(samples_base)

    prefix = find_scheduler_prefix(base)
    if prefix is not None:
        return prefix.joinpath(OUTPUT_ROOT_NAME)

    return base.joinpath("..").joinpath(OUTPUT_ROOT_NAME)


def _status_value(status: Any) -> Optional[str]:
    """正規化任務狀態：支援 TaskStatus 列舉與一般字串，回傳其字串值。
    Normalize a task status: accepts either the TaskStatus enum or a plain string
    and returns the underlying string value.
    """
    if status is None:
        return None
    return getattr(status, "value", None) or str(status)


# 低於此剩餘空間即視為「硬碟滿了」的候選原因（64 MB）
# Below this much free space the disk is treated as a candidate cause (64 MB).
LOW_DISK_THRESHOLD = 64 * 1024 * 1024

# 錯誤文字中代表磁碟滿／無法寫入的關鍵字（大小寫不敏感）
# Case-insensitive markers in error text that mean disk full / not writable.
DISK_FULL_MARKERS = (
    "no space left",
    "disk full",
    "not enough space",
    "there is not enough space",
    "磁碟空間不足",
    "空間不足",
)


def remove_empty_subdirs(root: Union[Path, str]) -> None:
    """
    由內往外刪除 root 底下的空子目錄；root 本身不刪，符號連結一律跳過。
    Delete empty sub-directories under root bottom-up; root itself is kept and
    symlinks are always skipped so a link target is never traversed.

    失敗（無權限、資料夾剛被寫入、Windows 檔案佔用）只記錄除錯日誌。
    Failures (permission denied, folder just written, Windows file locking) are
    only logged at debug level.
    """
    try:
        root_path = Path(root)
        if root_path.is_symlink() or not root_path.is_dir():
            return
        children = list(root_path.iterdir())
    except OSError as e:
        log.debug(f"[AgentScheduler] 無法列舉目錄 {root}: {e}")
        return

    # 先處理子層再刪自己，才能把最深的空目錄先清掉
    # parent so the deepest empty directory is removed first.
    for child in children:
        try:
            if child.is_symlink() or not child.is_dir():
                continue
            remove_empty_subdirs(child)
            child.rmdir()
            log.debug(f"[AgentScheduler] 已刪除空資料夾 {child}")
        except OSError as e:
            # 非空、無權限或被占用：保留原狀即可
            log.debug(f"[AgentScheduler] 略過目錄 {child}: {e}")


def _is_dir_empty(path: Path) -> bool:
    """判斷目錄是否存在且完全沒有任何項目；無法判讀時視為「非空」以保留資料。
    Check whether the directory exists and holds no entry at all; an unreadable
    directory counts as non-empty so nothing is deleted by mistake.
    """
    try:
        return path.is_dir() and next(path.iterdir(), None) is None
    except OSError:
        return False


def _probe_dir_state(task_dir: Path) -> Tuple[bool, bool, List[str]]:
    """
    探測任務資料夾的磁碟空間與可寫入狀態。
    Probe the task folder for free disk space and writability.

    回傳
    -------
    (disk_full, not_writable, notes)
        notes 為可供報告引用的雙語說明文字。
        notes holds bilingual detail lines for the report.
    """
    disk_full = False
    not_writable = False
    notes: List[str] = []

    # 磁碟剩餘空間
    try:
        free = shutil.disk_usage(str(task_dir)).free
        free_gb = free / (1024 ** 3)
        if free < LOW_DISK_THRESHOLD:
            disk_full = True
            notes.append(f"硬碟剩餘空間不足: {free_gb:.2f} GB")
        else:
            notes.append(f"硬碟剩餘空間: {free_gb:.2f} GB")
    except Exception as e:
        notes.append(f"無法檢測磁碟空間: {e}")

    # 實際寫入一個探測檔：磁碟滿與無權限在這裡最能被如實反映
    # Write a probe file: this is the most faithful test for a full disk or missing permission.
    probe = task_dir.joinpath(f".agent_scheduler_probe_{os.getpid()}")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        probe.unlink()
        notes.append("資料夾可寫入")
    except OSError as e:
        # 探測檔若已建立失敗也要清掉，避免殘留隱藏檔
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass

        # EDQUOT 在各平台不一定存在，用 getattr 取代直接引用，避免例外被誤判為無法寫入
        # EDQUOT is not present on every platform; getattr keeps a missing constant from
        # being misread as a write failure.
        if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", -1)):
            disk_full = True
            notes.append(f"磁碟已滿，無法寫入: {e}")
        elif e.errno in (errno.EACCES, errno.EPERM):
            not_writable = True
            notes.append(f"無寫入權限: {e}")
        else:
            not_writable = True
            notes.append(f"無法寫入: {e}")
    except Exception as e:
        notes.append(f"寫入測試失敗: {e}")

    return disk_full, not_writable, notes


def _detect_reasons(
    task_dir: Path,
    *,
    status: Any,
    failed: bool,
    error: Any,
    interrupted: bool,
    queue_purged: bool,
) -> Tuple[List[str], List[str]]:
    """
    判定任務資料夾為空的可能原因；回傳 (命中原因列表, 補充說明)。
    Determine the possible reasons why the task folder is empty; returns
    (hit reasons, supplementary notes).

    允許同時命中多項，也允許「其他／未知原因」作為唯一命中項。
    Multiple hits are allowed, and "other / unknown reason" may be the only hit.
    """
    hits: List[str] = []
    notes: List[str] = []

    error_text = str(error) if error is not None else ""
    status_value = _status_value(status)

    # 取消任務
    if interrupted or status_value == STATUS_INTERRUPTED:
        hits.append("取消任務")

    # 任務出錯
    if failed or status_value == STATUS_FAILED:
        hits.append("任務出錯" + (f": {error_text}" if error_text else ""))
    elif error_text:
        notes.append(f"錯誤訊息: {error_text}")

    # 佇列被傾空：任務仍停在 pending，代表還沒輪到執行就被清空／移除
    # Queue purged: still pending means it was cleared before ever running.
    if queue_purged and not failed and not interrupted:
        hits.append("佇列被傾空，任務未執行或已被清除")

    # 錯誤文字直接透露磁碟滿
    lowered = error_text.lower()
    disk_full_text = any(marker in lowered for marker in DISK_FULL_MARKERS)

    disk_full, not_writable, probe_notes = _probe_dir_state(task_dir)
    notes.extend(probe_notes)

    if disk_full or disk_full_text:
        hits.append("硬碟滿了，無法寫入新內容")

    if not_writable:
        hits.append("無法寫入（權限或路徑問題） / cannot write (permission or path issue)")

    # 全部條件皆不成立 → 允許以「其他／未知原因」結案
    if not hits:
        hits.append("其他／未知原因")

    return hits, notes


def _format_mtime(path: Path) -> str:
    """取得資料夾的修改時間字串；失敗時回傳 unknown。
    Format the folder's modification time; fall back to "unknown" on failure.
    """
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return "unknown"


def _write_cleanup_report(
    task_dir: Path,
    *,
    task_id: str,
    status: Any,
    hits: List[str],
    notes: List[str],
    deleted: bool,
    delete_error: Optional[str],
    folder_mtime: str,
) -> Optional[Path]:
    """
    在被刪除的任務資料夾原位置寫入同名 .txt 報告，說明該資料夾為空的原因。
    Write a same-named .txt report where the empty task folder used to be,
    explaining why that folder was empty.

    報告寫入失敗（磁碟滿、無權限）只記錄日誌，不向上拋出。
    Report write failures (full disk, no permission) are logged, never raised.
    """
    report_path = task_dir.with_name(task_dir.name + ".txt")
    status_text = _status_value(status) or "unknown"

    # 逐項加上 是否命中的標記
    hit_lines = "\n".join(f"  - {reason}" for reason in hits)
    note_lines = "\n".join(f"  - {note}" for note in notes) if notes else "  - (none)"

    if deleted:
        delete_text = "是，空資料夾已刪除"
    elif delete_error:
        delete_text = f"否 ({delete_error})"
    else:
        delete_text = "否"

    content = "\n".join(
        [
            "[AgentScheduler] 任務資料夾清理報告",
            "=" * 60,
            f"任務 ID : {task_id}",
            f"資料夾  : {task_dir.parent.name}/{task_dir.name}",
            f"建立時間: {folder_mtime}",
            f"清理時間: {datetime.now().isoformat(timespec='seconds')}",
            f"任務狀態: {status_text}",
            f"刪除結果: {delete_text}",
            "",
            "判定原因:",
            hit_lines,
            "",
            "補充說明:",
            note_lines,
            "",
        ]
    )

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"[AgentScheduler] 已寫入空資料夾報告: {report_path}")
        return report_path
    except Exception as e:
        log.warning(f"[AgentScheduler] 無法寫入空資料夾報告: {e}")
        return None


def cleanup_task_output_dir(
    task_dir: Union[Path, str, None],
    *,
    task_id: str,
    status: Any = None,
    failed: bool = False,
    error: Any = None,
    interrupted: bool = False,
    queue_purged: bool = False,
) -> None:
    """
    任務結束後清理該次任務資料夾：刪除其下的空子目錄，若資料夾本身已全空則一併刪除，
    並在原位置寫入同名 .txt 報告記錄原因。
    After a task ends, clean the task folder: remove empty sub-directories, delete the
    folder itself when it is completely empty, and leave a same-named .txt report
    recording the reason at its former location.

    任何例外皆在函式內被捕捉，只記錄日誌，不影響後續任務。
    Every exception is caught inside this function and only logged, so the next task
    is never affected.

    注意
    只會作用於「單一任務資料夾」；當日資料夾（YYYY-MM-DD）與輸出根目錄會被防禦性略過，
    因為同名 .txt 報告必須保留在當日資料夾內。
    Only a single task folder is processed; the day folder (YYYY-MM-DD) and the output
    root are defensively skipped, since the same-named .txt reports must stay inside
    the day folder.
    """
    if not task_dir:
        return

    try:
        task_dir_path = Path(task_dir)

        # 符號連結／junction 不處理，避免連動到連結目標的內容
        # Never process a symlink/junction so the link target is left untouched.
        if task_dir_path.is_symlink() or not task_dir_path.is_dir():
            return

        # 防禦性檢查：若誤將當日資料夾（或輸出根目錄）當成任務資料夾傳入，
        # 直接略過，確保清空永遠不會移除存放 .txt 報告的當日資料夾。
        # Defensive check: if the day folder (or the output root) is ever passed in
        # by mistake, skip it entirely, so cleanup can never remove the day folder
        # that holds the .txt reports.
        if DAY_FOLDER_PATTERN.match(task_dir_path.name) or task_dir_path.name == OUTPUT_ROOT_NAME:
            log.debug(f"[AgentScheduler] 略過非任務資料夾: {task_dir_path}")
            return

        remove_empty_subdirs(task_dir_path)

        # 任務有產出（資料夾非空）→ 不刪除、不報告
        if not _is_dir_empty(task_dir_path):
            return

        hits, notes = _detect_reasons(
            task_dir_path,
            status=status,
            failed=failed,
            error=error,
            interrupted=interrupted,
            queue_purged=queue_purged,
        )

        # 資料夾刪除後就讀不到時間戳，先取好供報告使用
        # The timestamp is unreadable once the folder is gone, so capture it first.
        folder_mtime = _format_mtime(task_dir_path)

        deleted = False
        delete_error: Optional[str] = None
        try:
            task_dir_path.rmdir()
            deleted = True
            log.info(f"[AgentScheduler] 已刪除空任務資料夾 {task_dir_path}")
        except OSError as e:
            # 常見於無權限或資料夾被占用；保留原狀並寫進報告
            # locking related; keep the folder and record this in the report.
            delete_error = str(e)
            log.warning(f"[AgentScheduler] 無法刪除任務資料夾 {task_dir_path}: {e}")

        _write_cleanup_report(
            task_dir_path,
            task_id=task_id,
            status=status,
            hits=hits,
            notes=notes,
            deleted=deleted,
            delete_error=delete_error,
            folder_mtime=folder_mtime,
        )
    except Exception as e:
        # 兜底捕捉：清理永遠不應讓排程執行緒崩潰
        # crash the runner thread.
        log.warning(f"[AgentScheduler] 清理任務資料夾失敗 {task_dir}: {e}")
