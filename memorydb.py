import sqlite3
import json
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
import shutil
import logging

log = logging.getLogger(__name__)
class MemoryDB:
    def __init__(self, db_path: str = 'memory.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 记忆表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                entities TEXT NOT NULL DEFAULT '[]',
                topics TEXT NOT NULL DEFAULT '[]',
                connections TEXT NOT NULL DEFAULT '[]',
                importance REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                consolidated INTEGER NOT NULL DEFAULT 0
            )
            ''')
            # 整合表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS consolidations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_ids TEXT NOT NULL,
                summary TEXT NOT NULL,
                insight TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            ''')
            # 已处理文件表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                path TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
            ''')
            conn.commit()
    
    def store_memory(self, raw_text: str, summary: str, entities: list[str], 
                    topics: list[str], importance: float, source: str = "") -> dict[str, Any]:
        """存储记忆"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO memories (source, raw_text, summary, entities, topics, importance, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (source, raw_text, summary, json.dumps(entities), json.dumps(topics), importance, now)
            )
            memory_id = cursor.lastrowid
            conn.commit()
        log.info(f"📥 Stored memory #{memory_id}: {summary[:60]}...")
        return {"memory_id": memory_id, "status": "stored", "summary": summary}
    
    def read_unconsolidated_memories(self) -> dict[str, Any]:
        """读取未整合的记忆"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM memories WHERE consolidated = 0 ORDER BY created_at DESC LIMIT 10'''
            )
            memories = []
            for row in cursor.fetchall():
                memories.append({
                    "id": row["id"],
                    "summary": row["summary"],
                    "entities": json.loads(row["entities"]),
                    "topics": json.loads(row["topics"]),
                    "importance": row["importance"],
                    "created_at": row["created_at"]
                })
        return {"memories": memories, "count": len(memories)}
    
    def store_consolidation(self, source_ids: list[int], summary: str, 
                          insight: str, connections: list[dict[str, Any]]) -> dict[str, Any]:
        """存储整合结果"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO consolidations (source_ids, summary, insight, created_at) 
                VALUES (?, ?, ?, ?)''',
                (json.dumps(source_ids), summary, insight, now)
            )
            # 更新连接的记忆
            for conn_item in connections:
                from_id, to_id = conn_item.get("from_id"), conn_item.get("to_id")
                rel = conn_item.get("relationship", "")
                if from_id and to_id:
                    for mid in [from_id, to_id]:
                        row = cursor.execute("SELECT connections FROM memories WHERE id = ?", (mid,)).fetchone()
                        if row:
                            existing = json.loads(row["connections"])
                            existing.append({"linked_to": to_id if mid == from_id else from_id, "relationship": rel})
                            cursor.execute("UPDATE memories SET connections = ? WHERE id = ?", (json.dumps(existing), mid))
            # 标记源记忆为已整合
            placeholders = ",".join("?" * len(source_ids))
            cursor.execute(f"UPDATE memories SET consolidated = 1 WHERE id IN ({placeholders})", source_ids)
            conn.commit()
        log.info(f"🔄 Consolidated {len(source_ids)} memories. Insight: {insight[:80]}...")
        return {"status": "consolidated", "memories_processed": len(source_ids), "insight": insight}
    
    def read_all_memories(self) -> dict[str, Any]:
        """读取所有记忆"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM memories ORDER BY created_at DESC LIMIT 50'''
            )
            memories = []
            for row in cursor.fetchall():
                memories.append({
                    "id": row["id"],
                    "source": row["source"],
                    "summary": row["summary"],
                    "entities": json.loads(row["entities"]),
                    "topics": json.loads(row["topics"]),
                    "importance": row["importance"],
                    "connections": json.loads(row["connections"]),
                    "created_at": row["created_at"],
                    "consolidated": bool(row["consolidated"])
                })
        return {"memories": memories, "count": len(memories)}
    
    def read_consolidation_history(self) -> dict[str, Any]:
        """读取整合历史"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT * FROM consolidations ORDER BY created_at DESC LIMIT 10'''
            )
            consolidations = []
            for row in cursor.fetchall():
                consolidations.append({
                    "summary": row["summary"],
                    "insight": row["insight"],
                    "source_ids": row["source_ids"]
                })
        return {"consolidations": consolidations, "count": len(consolidations)}
    
    def get_memory_stats(self) -> dict[str, Any]:
        """获取记忆统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 总记忆数
            cursor.execute("SELECT COUNT(*) as c FROM memories")
            total_memories = cursor.fetchone()["c"]
            # 未整合记忆数
            cursor.execute("SELECT COUNT(*) as c FROM memories WHERE consolidated = 0")
            unconsolidated_memories = cursor.fetchone()["c"]
            # 整合次数
            cursor.execute("SELECT COUNT(*) as c FROM consolidations")
            consolidation_count = cursor.fetchone()["c"]
        return {
            "total_memories": total_memories,
            "unconsolidated": unconsolidated_memories,
            "consolidations": consolidation_count
        }
    
    def delete_memory(self, memory_id: int) -> dict[str, Any]:
        """删除记忆"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row = cursor.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return {"status": "not_found", "memory_id": memory_id}
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
        log.info(f"🗑️  Deleted memory #{memory_id}")
        return {"status": "deleted", "memory_id": memory_id}
    
    def clear_all_memories(self, inbox_path: str | None = None) -> dict[str, Any]:
        """清空所有记忆"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM memories")
            mem_count = cursor.fetchone()["c"]
            cursor.execute("DELETE FROM memories")
            cursor.execute("DELETE FROM consolidations")
            cursor.execute("DELETE FROM processed_files")
            conn.commit()
        
        # 清空收件箱文件夹
        files_deleted = 0
        if inbox_path:
            folder = Path(inbox_path)
            if folder.is_dir():
                for f in folder.iterdir():
                    if f.name.startswith("."):
                        continue  # 保留隐藏文件如 .gitkeep
                    try:
                        if f.is_file():
                            f.unlink()
                            files_deleted += 1
                        elif f.is_dir():
                            shutil.rmtree(f)
                            files_deleted += 1
                    except OSError as e:
                        log.error(f"Failed to delete {f.name}: {e}")
        
        log.info(f"🗑️  Cleared all {mem_count} memories, deleted {files_deleted} inbox files")
        return {"status": "cleared", "memories_deleted": mem_count, "files_deleted": files_deleted}
    
    def mark_file_processed(self, file_path: str) -> None:
        """标记文件为已处理"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO processed_files (path, processed_at) VALUES (?, ?)",
                (file_path, now)
            )
            conn.commit()
    
    def is_file_processed(self, file_path: str) -> bool:
        """检查文件是否已处理"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT 1 FROM processed_files WHERE path = ?", (file_path,)
            ).fetchone()
            return row is not None
