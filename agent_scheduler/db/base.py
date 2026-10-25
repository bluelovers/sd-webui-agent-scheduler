import os

from sqlalchemy import create_engine
from sqlalchemy.schema import MetaData
from sqlalchemy.orm import declarative_base

from modules import scripts
from modules import shared
from ..log import print_message

if hasattr(shared.cmd_opts, "agent_scheduler_sqlite_file"):
    # 若使用者指定了 sqlite 檔案路徑，優先採用

    # if relative path, join with basedir
    # 相對路徑需以腳本所在目錄為基準拼接，確保在不同工作目錄下都能找到檔案
    if not os.path.isabs(shared.cmd_opts.agent_scheduler_sqlite_file):
        db_file = os.path.join(scripts.basedir(), shared.cmd_opts.agent_scheduler_sqlite_file)
    else:
        db_file = os.path.abspath(shared.cmd_opts.agent_scheduler_sqlite_file)
else:
    # 未指定時回退至預設檔名，保持向後相容
    db_file = os.path.join(scripts.basedir(), "task_scheduler.sqlite3")

print_message(f"Using sqlite file: {db_file}")


Base = declarative_base()
metadata: MetaData = Base.metadata


class BaseTableManager:
    # 所有資料表管理器的基底類別，統一持有 SQLAlchemy engine
    def __init__(self, engine = None):
        # Get the db connection object, making the file and tables if needed.
        # 建立（或接收）資料庫連線；若檔案或資料表不存在則由 SQLAlchemy 自動建立
        try:
            self.engine = engine if engine else create_engine(f"sqlite:///{db_file}")
        except Exception as e:
            print_message(f"Exception connecting to database: {e}", level="error")
            raise e

    def get_engine(self):
        # 對外提供 engine，供需要直接操作連線的呼叫端使用
        return self.engine

    # Commit and close the database connection.
    def quit(self):
        # 釋放連線池資源
        self.engine.dispose()
