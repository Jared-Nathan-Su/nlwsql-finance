"""
数据库管理模块 — 连接管理、查询执行、Schema信息获取
"""
import sqlite3
import os
import sys
import subprocess
import pandas as pd
from typing import List, Tuple, Dict, Optional
from contextlib import contextmanager


class DatabaseManager:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，默认为 data/finance.db
        """
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "finance.db"
            )
        self.db_path = os.path.abspath(db_path)
        self._verify_db()
    
    def _verify_db(self):
        """验证数据库文件是否存在，不存在则自动生成"""
        if not os.path.exists(self.db_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            generate_script = os.path.join(project_root, "data", "generate_data.py")
            
            if not os.path.exists(generate_script):
                raise FileNotFoundError(
                    f"数据库文件不存在且无法自动生成: {self.db_path}"
                )
            
            # 方法1: 直接用 subprocess 执行脚本（最可靠）
            import subprocess as _sp
            result = _sp.run(
                [sys.executable, generate_script],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"数据库自动生成失败:\n{result.stderr[:500]}"
                )
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"数据库生成后仍找不到文件: {self.db_path}"
                )
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """
        执行SQL查询
        
        Args:
            sql: SQL查询语句
        
        Returns:
            (是否成功, DataFrame结果, 错误信息)
        """
        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(sql, conn)
                return True, df, ""
        except Exception as e:
            return False, pd.DataFrame(), str(e)
    
    def get_schema_info(self) -> Dict[str, List[Dict]]:
        """获取完整的数据库Schema信息"""
        schema = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"PRAGMA table_info('{table}')")
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "pk": bool(row[5])
                    }
                    for row in cursor.fetchall()
                ]
                
                # 获取行数
                cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
                row_count = cursor.fetchone()[0]
                
                schema[table] = {
                    "columns": columns,
                    "row_count": row_count
                }
        
        return schema
    
    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return [row[0] for row in cursor.fetchall()]
    
    def get_all_fields(self) -> List[str]:
        """获取所有字段名"""
        fields = set()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table in self.get_table_names():
                cursor.execute(f"PRAGMA table_info('{table}')")
                for row in cursor.fetchall():
                    fields.add(row[1])
        return sorted(fields)
    
    def get_table_preview(self, table: str, limit: int = 5) -> pd.DataFrame:
        """预览表数据"""
        with self.get_connection() as conn:
            return pd.read_sql_query(f"SELECT * FROM '{table}' LIMIT {limit}", conn)
    
    def print_schema_summary(self) -> str:
        """打印Schema摘要"""
        schema = self.get_schema_info()
        lines = ["=" * 60, "📊 数据库 Schema 摘要", "=" * 60]
        
        total_rows = 0
        for table, info in schema.items():
            cols = [c["name"] for c in info["columns"]]
            rows = info["row_count"]
            total_rows += rows
            table_type = "维度" if table.startswith("dim_") else "事实"
            lines.append(f"\n[{table_type}] {table} ({rows:,} 行)")
            lines.append(f"  字段: {', '.join(cols[:8])}")
            if len(cols) > 8:
                lines.append(f"        {', '.join(cols[8:])}")
        
        lines.append(f"\n{'=' * 60}")
        lines.append(f"总计: {len(schema)} 张表, {total_rows:,} 行")
        return "\n".join(lines)


# ============================================================
# 单例模式
# ============================================================
_db_instance = None

def get_db(db_path: str = None) -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(db_path)
    return _db_instance


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    db = DatabaseManager()
    print(db.print_schema_summary())
    
    # 测试查询
    print("\n" + "=" * 60)
    print("🔍 测试查询: 2024年各区域营收")
    sql = """
    SELECT r.region_group, ROUND(SUM(s.revenue), 2) AS total_revenue
    FROM fact_sales s
    JOIN dim_region r ON s.region_id = r.region_id
    JOIN dim_date d ON s.date_id = d.date_id
    WHERE d.year = 2024
    GROUP BY r.region_group
    ORDER BY total_revenue DESC
    """
    ok, df, err = db.execute_query(sql)
    if ok:
        print(df.to_string(index=False))
    else:
        print(f"❌ 查询失败: {err}")
