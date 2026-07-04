"""
数据库管理模块 — 连接管理、查询执行、Schema信息获取
"""
import sqlite3
import os
import sys
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
            
            # 切换到项目根目录执行生成脚本
            old_cwd = os.getcwd()
            old_path = sys.path.copy()
            try:
                os.chdir(project_root)
                sys.path.insert(0, project_root)
                with open(generate_script, "r", encoding="utf-8") as f:
                    code = compile(f.read(), generate_script, "exec")
                exec(code, {"__name__": "__main__", "__file__": generate_script})
            except Exception as e:
                raise RuntimeError(
                    f"数据库自动生成失败: {str(e)}\n"
                    f"脚本路径: {generate_script}"
                ) from e
            finally:
                os.chdir(old_cwd)
                sys.path = old_path
            
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
    
    def import_dataframe(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, str]:
        """
        导入 DataFrame 到新表（如果表已存在则替换）
        """
        try:
            with self.get_connection() as conn:
                df.to_sql(table_name, conn, if_exists="replace", index=False)
            return True, f"成功导入 {len(df)} 行到表 '{table_name}'"
        except Exception as e:
            return False, str(e)
    
    def import_csv(self, file_path: str, table_name: str) -> Tuple[bool, str, pd.DataFrame]:
        """导入 CSV 文件到数据库"""
        try:
            df = pd.read_csv(file_path)
            ok, msg = self.import_dataframe(df, table_name)
            return ok, msg, df
        except Exception as e:
            return False, str(e), pd.DataFrame()
    
    def get_table_schema_text(self, table_name: str) -> str:
        """获取单表的 Schema 文本描述"""
        schema = self.get_schema_info()
        if table_name not in schema:
            return ""
        info = schema[table_name]
        cols = info["columns"]
        lines = [f"表名: {table_name} ({info['row_count']} 行)"]
        lines.append("字段:")
        for c in cols:
            pk_flag = " (主键)" if c["pk"] else ""
            lines.append(f"  - {c['name']} ({c['type']}){pk_flag}")
        return "\n".join(lines)
    
    def generate_schema_context(self, tables: List[str] = None) -> str:
        """生成所有表（或指定表）的 Schema 上下文文本"""
        schema = self.get_schema_info()
        if tables is None:
            tables = list(schema.keys())
        lines = ["## 数据库 Schema"]
        for t in tables:
            if t in schema:
                info = schema[t]
                cols = [f"{c['name']}({c['type']})" for c in info["columns"]]
                lines.append(f"\n**{t}** ({info['row_count']} 行)")
                lines.append(f"字段: {', '.join(cols)}")
        return "\n".join(lines)
    
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
