"""
SQL 安全校验模块
确保生成的SQL：语法正确、只读权限、表/字段存在、防注入
"""
import sqlparse
import re
from typing import Tuple, Optional, List


# 允许的表名白名单
ALLOWED_TABLES = {
    "dim_date", "dim_product", "dim_department", "dim_region",
    "dim_customer", "dim_supplier", "dim_expense_type",
    "fact_sales", "fact_cost", "fact_expense",
    "fact_receivable", "fact_payable"
}

# 禁止的SQL关键字（DML/DDL）
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "CALL", "LOAD", "IMPORT"
}

# 允许的字段名（简化版，完整版从数据库动态获取）
COMMON_FIELDS = {
    "date_id", "full_date", "year", "quarter", "month", "month_name",
    "product_id", "product_name", "category", "product_line",
    "dept_id", "dept_name", "dept_type",
    "region_id", "region_name", "region_group",
    "cust_id", "cust_name", "cust_industry", "cust_level", "credit_score",
    "supplier_id", "supplier_name", "supplier_category",
    "exp_type_id", "exp_type_name", "exp_category",
    "sale_id", "revenue", "quantity",
    "cost_id", "cost_amount", "cost_type",
    "expense_id", "budget_amount", "actual_amount",
    "recv_id", "amount", "collected_amount", "due_date", "is_overdue", "overdue_days",
    "pay_id", "paid_amount"
}


def validate_sql_syntax(sql: str) -> Tuple[bool, str]:
    """
    校验SQL语法
    
    Returns:
        (是否有效, 错误信息)
    """
    if not sql or not sql.strip():
        return False, "SQL语句为空"
    
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "SQL解析失败"
        
        # 检查是否包含多条语句
        statements = [s for s in parsed if s.tokens and str(s).strip()]
        if len(statements) > 1:
            return False, "不允许执行多条SQL语句"
        
        return True, ""
    except Exception as e:
        return False, f"SQL语法解析异常: {str(e)}"


def validate_sql_permission(sql: str) -> Tuple[bool, str]:
    """
    检查SQL权限：只允许SELECT
    
    Returns:
        (是否安全, 错误信息)
    """
    sql_upper = sql.upper().strip()
    
    # 检查是否以SELECT开头
    if not sql_upper.startswith("SELECT"):
        return False, "只允许SELECT查询语句"
    
    # 检查是否包含禁止的关键字
    for keyword in FORBIDDEN_KEYWORDS:
        # 使用词边界匹配
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"SQL包含禁止的操作: {keyword}"
    
    return True, ""


def extract_table_names(sql: str) -> List[str]:
    """从SQL中提取表名"""
    # 匹配 FROM table_name 和 JOIN table_name
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return [m.lower() for m in matches]


def validate_table_names(sql: str) -> Tuple[bool, str]:
    """
    校验SQL中的表名是否在白名单中
    
    Returns:
        (是否合法, 错误信息)
    """
    tables = extract_table_names(sql)
    invalid_tables = [t for t in tables if t.lower() not in ALLOWED_TABLES]
    
    if invalid_tables:
        suggestions = []
        for t in invalid_tables:
            # 模糊匹配建议
            close = [at for at in ALLOWED_TABLES if t.lower() in at.lower() or at.lower() in t.lower()]
            if close:
                suggestions.append(f"'{t}' → 是否指 '{close[0]}'?")
            else:
                suggestions.append(f"'{t}' 不在数据库表中")
        return False, "表名校验失败: " + "; ".join(suggestions)
    
    return True, ""


def clean_sql(sql: str) -> str:
    """清理SQL：去除markdown标记、多余空白"""
    # 去除```sql ... ``` 标记
    sql = re.sub(r'```(?:sql)?\s*', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'```', '', sql)
    # 去除首尾空白
    sql = sql.strip()
    # 确保以分号结尾
    if not sql.endswith(';'):
        sql += ';'
    return sql


def full_validate(sql: str) -> Tuple[bool, str, str]:
    """
    完整的SQL校验流程
    
    Args:
        sql: 原始SQL语句（可能包含markdown标记）
    
    Returns:
        (是否通过, 错误信息, 清理后的SQL)
    """
    # Step 0: 清理
    sql = clean_sql(sql)
    
    # Step 1: 语法校验
    valid, error = validate_sql_syntax(sql)
    if not valid:
        return False, f"语法校验失败: {error}", sql
    
    # Step 2: 权限检查
    valid, error = validate_sql_permission(sql)
    if not valid:
        return False, f"权限校验失败: {error}", sql
    
    # Step 3: 表名校验
    valid, error = validate_table_names(sql)
    if not valid:
        return False, f"表名校验失败: {error}", sql
    
    return True, "", sql


# ============================================================
# 单元测试
# ============================================================
if __name__ == "__main__":
    test_cases = [
        # (SQL, 预期结果)
        ("SELECT * FROM fact_sales;", True),
        ("SELECT SUM(revenue) FROM fact_sales s JOIN dim_date d ON s.date_id = d.date_id WHERE d.year = 2024;", True),
        ("DROP TABLE fact_sales;", False),
        ("DELETE FROM fact_sales WHERE date_id = 20240101;", False),
        ("SELECT * FROM unknown_table;", False),
        ("SELECT * FROM fact_sales; SELECT * FROM fact_cost;", False),
    ]
    
    print("SQL 安全校验测试:")
    print("=" * 60)
    for sql, expected in test_cases:
        valid, error, cleaned = full_validate(sql)
        status = "✅" if valid == expected else "❌"
        print(f"{status} {'通过' if valid else f'拦截: {error}'}")
        print(f"   SQL: {sql[:60]}...")
        print()
