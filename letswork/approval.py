import os
import uuid
import difflib
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass
class PendingChange:
    id: str
    user_id: str
    path: str
    new_content: str
    old_content: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)

class ApprovalQueue:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._pending: dict[str, PendingChange] = {}
        self._history: list[PendingChange] = []

    def submit(self, user_id: str, path: str, new_content: str) -> PendingChange:
        change_id = str(uuid.uuid4())[:8]
        abs_path = os.path.join(self.project_root, path)
        
        if os.path.isfile(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                old_content = f.read()
        else:
            old_content = ""
            
        change = PendingChange(
            id=change_id,
            user_id=user_id,
            path=path,
            new_content=new_content,
            old_content=old_content
        )
        self._pending[change_id] = change
        return change

    def approve(self, change_id: str) -> bool:
        if change_id not in self._pending:
            return False
            
        change = self._pending[change_id]
        abs_root = os.path.abspath(self.project_root)
        abs_path = os.path.abspath(os.path.join(self.project_root, change.path))
        if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
            change.status = ApprovalStatus.REJECTED
            self._history.append(change)
            del self._pending[change_id]
            return False

        dirname = os.path.dirname(abs_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
            
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(change.new_content)
            
        change.status = ApprovalStatus.APPROVED
        self._history.append(change)
        del self._pending[change_id]
        return True

    def reject(self, change_id: str) -> bool:
        if change_id not in self._pending:
            return False
            
        change = self._pending[change_id]
        change.status = ApprovalStatus.REJECTED
        self._history.append(change)
        del self._pending[change_id]
        return True

    def get_pending(self) -> list[PendingChange]:
        return list(self._pending.values())

    def get_diff(self, change_id: str) -> str:
        if change_id not in self._pending:
            return "Change not found"
            
        change = self._pending[change_id]
        diff_lines = list(difflib.unified_diff(
            change.old_content.split("\n"),
            change.new_content.split("\n"),
            fromfile=f"a/{change.path}",
            tofile=f"b/{change.path}",
            lineterm=""
        ))
        
        diff_str = "\n".join(diff_lines)
        if not diff_str:
            return "No changes detected"
            
        return diff_str
