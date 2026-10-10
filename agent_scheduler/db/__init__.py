# 資料庫套件入口：匯出管理器與初始化邏輯，並在啟動時執行結構遷移。
# DB package entry point: exports managers and init logic, and runs schema migrations on startup.
from pathlib import Path
from sqlalchemy import create_engine, inspect, text, String, Text

from .base import Base, metadata, db_file
from .app_state import AppStateKey, AppState, AppStateManager
from .task import TaskStatus, Task, TaskManager

# 資料庫結構版本號；用於判斷是否需要執行舊版遷移
version = "2"

# 模組層級單例管理器，供整個擴充功能共用同一連線
state_manager = AppStateManager()
task_manager = TaskManager()


def init():
    # 初始化資料庫：建表並執行舊版結構遷移，確保升級後相容
    engine = create_engine(f"sqlite:///{db_file}")

    metadata.create_all(engine)

    # 記錄目前結構版本
    state_manager.set_value(AppStateKey.Version, version)
    # check if app state exists
    # 首次啟動時初始化佇列狀態為執行中
    if state_manager.get_value(AppStateKey.QueueState) is None:
        # create app state
        state_manager.set_value(AppStateKey.QueueState, "running")

    inspector = inspect(engine)
    with engine.connect() as conn:
        task_columns = inspector.get_columns("task")
        # add result column
        # 遷移：若缺少 result 欄位則補上
        if not any(col["name"] == "result" for col in task_columns):
            conn.execute(text("ALTER TABLE task ADD COLUMN result TEXT"))

        # add api_task_id column
        # 遷移：補上外部 API 任務編號欄位
        if not any(col["name"] == "api_task_id" for col in task_columns):
            conn.execute(text("ALTER TABLE task ADD COLUMN api_task_id VARCHAR(64)"))

        # add api_task_callback column
        # 遷移：補上 API 回呼欄位
        if not any(col["name"] == "api_task_callback" for col in task_columns):
            conn.execute(text("ALTER TABLE task ADD COLUMN api_task_callback VARCHAR(255)"))

        # add name column
        # 遷移：補上任務名稱欄位
        if not any(col["name"] == "name" for col in task_columns):
            conn.execute(text("ALTER TABLE task ADD COLUMN name VARCHAR(255)"))

        # add bookmarked column
        # 遷移：補上書籤欄位，預設為否
        if not any(col["name"] == "bookmarked" for col in task_columns):
            conn.execute(text("ALTER TABLE task ADD COLUMN bookmarked BOOLEAN DEFAULT FALSE"))

        # 舊版 params 為非 TEXT 型別時，需重建資料表以擴充欄位長度
        params_column = next(col for col in task_columns if col["name"] == "params")
        if version > "1" and not isinstance(params_column["type"], Text):
            transaction = conn.begin()
            # 建立新結構的暫存表，複製資料後更名，完成無損欄位類型升級
            conn.execute(
                text(
                    """
                    CREATE TABLE task_temp (
                        id VARCHAR(64) NOT NULL,
                        type VARCHAR(20) NOT NULL,
                        params TEXT NOT NULL,
                        script_params BLOB NOT NULL,
                        priority INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        created_at DATETIME DEFAULT (datetime('now')) NOT NULL,
                        updated_at DATETIME DEFAULT (datetime('now')) NOT NULL,
                        result TEXT,
                        PRIMARY KEY (id)
                    )"""
                )
            )
            conn.execute(text("INSERT INTO task_temp SELECT * FROM task"))
            conn.execute(text("DROP TABLE task"))
            conn.execute(text("ALTER TABLE task_temp RENAME TO task"))
            transaction.commit()

        conn.close()


__all__ = [
    "init",
    "Base",
    "metadata",
    "db_file",
    "AppStateKey",
    "AppState",
    "TaskStatus",
    "Task",
    "task_manager",
    "state_manager",
]
