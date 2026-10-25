from enum import Enum
from typing import Union

from sqlalchemy import Column, String
from sqlalchemy.orm import Session

from ..log import print_message
from .base import BaseTableManager, Base


class AppStateKey(str, Enum):
    # 應用程式層級的狀態鍵值定義；集中管理可避免字串打字錯誤
    Version = "version"
    QueueState = "queue_state"  # paused or running


class AppState:
    # 應用程式狀態的純資料物件（非 ORM），便於在業務層與資料表物件之間轉換
    def __init__(self, key: str, value: str):
        self.key: str = key
        self.value: str = value

    @staticmethod
    def from_table(table: "AppStateTable"):
        # 由 ORM 資料表物件轉回純資料物件
        return AppState(table.key, table.value)

    def to_table(self):
        # 轉換為 ORM 資料表物件以寫入資料庫
        return AppStateTable(key=self.key, value=self.value)


class AppStateTable(Base):
    # 應用程式狀態的 ORM 資料表對應（key-value 儲存）
    __tablename__ = "app_state"

    key = Column(String(64), primary_key=True)
    value = Column(String(255), nullable=True)

    def __repr__(self):
        return f"AppState(key={self.key!r}, value={self.value!r})"


class AppStateManager(BaseTableManager):
    # 封裝 app_state 資料表的讀寫操作，對外隱藏 session 生命週期
    def get_value(self, key: str) -> Union[str, None]:
        session = Session(self.engine)
        try:
            result = session.get(AppStateTable, key)
            # 命中則回傳儲存值，否則視為無該筆狀態
            if result:
                return result.value
            else:
                return None
        except Exception as e:
            print_message(f"Exception getting value from database: {e}", level="error")
            raise e
        finally:
            session.close()

    def set_value(self, key: str, value: str):
        session = Session(self.engine)
        try:
            result = session.get(AppStateTable, key)
            # 已存在則更新，否則新增一筆（upsert 語意）
            if result:
                result.value = value
            else:
                result = AppStateTable(key=key, value=value)
                session.add(result)
            session.commit()
        except Exception as e:
            print_message(f"Exception setting value in database: {e}", level="error")
            raise e
        finally:
            session.close()

    def delete_value(self, key: str):
        session = Session(self.engine)
        try:
            result = session.get(AppStateTable, key)
            # 僅在該鍵存在時才執行刪除，避免對不存在資料拋錯
            if result:
                session.delete(result)
                session.commit()
        except Exception as e:
            print_message(f"Exception deleting value from database: {e}", level="error")
            raise e
        finally:
            session.close()
