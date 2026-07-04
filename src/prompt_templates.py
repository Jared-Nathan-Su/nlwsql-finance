"""
NL2SQL 核心引擎 — Prompt 模板管理
采用分层注入策略：系统角色 → Schema → 业务规则 → Few-shot → 用户问题
"""
import json

# ============================================================
# Layer 1: 系统角色设定
# ============================================================
SYSTEM_ROLE = """你是一位资深的企业财务数据分析师，精通SQL语言和财务分析。
你的任务是将用户的自然语言问题，转换为准确的SQLite SQL查询语句。

## 你的能力：
1. 理解财务业务术语（毛利率、净利率、同比、环比、预算执行率、应收周转等）
2. 将模糊的自然语言精确化为SQL查询
3. 选择合适的聚合函数、JOIN方式、排序和过滤条件
4. 只生成SELECT查询，绝不生成INSERT/UPDATE/DELETE/DROP等修改语句

## 输出要求：
- 只输出纯净的SQL语句，不要包含```sql```标记
- 不要包含任何解释性文字
- SQL语句以分号结尾
- 如果问题无法回答，输出: UNABLE_TO_ANSWER"""

# ============================================================
# Layer 2: 数据库 Schema 注入
# ============================================================
SCHEMA_CONTEXT = """
## 数据库Schema

### 维度表
**dim_date** — 日期维度
- date_id (INTEGER PK): 日期ID，格式YYYYMMDD
- full_date (DATE): 完整日期
- year (INTEGER): 年份
- quarter (INTEGER): 季度 1-4
- month (INTEGER): 月份 1-12
- month_name (TEXT): 月份英文名
- day_of_month (INTEGER): 日
- day_of_week (INTEGER): 星期几 0=周一
- is_weekend (INTEGER): 是否周末 0/1

**dim_product** — 产品维度
- product_id (INTEGER PK): 产品ID
- product_name (TEXT): 产品名称
- category (TEXT): 品类（硬件/软件/服务）
- product_line (TEXT): 产品线

**dim_department** — 部门维度
- dept_id (INTEGER PK): 部门ID
- dept_name (TEXT): 部门名称
- dept_type (TEXT): 部门类型（前台/中台/后台）

**dim_region** — 区域维度
- region_id (INTEGER PK): 区域ID
- region_name (TEXT): 城市名称
- region_group (TEXT): 大区（华东/华南/华北/西南）

**dim_customer** — 客户维度
- cust_id (INTEGER PK): 客户ID
- cust_name (TEXT): 客户名称
- cust_industry (TEXT): 行业
- cust_level (TEXT): 客户等级 A/B/C
- credit_score (REAL): 信用评分

**dim_supplier** — 供应商维度
- supplier_id (INTEGER PK)
- supplier_name (TEXT)
- supplier_category (TEXT)

**dim_expense_type** — 费用类型维度
- exp_type_id (INTEGER PK)
- exp_type_name (TEXT): 费用名称
- exp_category (TEXT): 费用大类（销售费用/管理费用/研发费用/财务费用）

### 事实表
**fact_sales** — 销售事实表
- sale_id (INTEGER PK)
- date_id (INTEGER FK→dim_date)
- product_id (INTEGER FK→dim_product)
- region_id (INTEGER FK→dim_region)
- dept_id (INTEGER FK→dim_department)
- cust_id (INTEGER FK→dim_customer)
- revenue (REAL): 销售收入
- quantity (INTEGER): 销售数量

**fact_cost** — 成本事实表
- cost_id (INTEGER PK)
- date_id (INTEGER FK→dim_date)
- product_id (INTEGER FK→dim_product)
- region_id (INTEGER FK→dim_region)
- cost_amount (REAL): 成本金额
- cost_type (TEXT): direct/indirect

**fact_expense** — 费用事实表（含预算vs实际）
- expense_id (INTEGER PK)
- date_id (INTEGER FK→dim_date)
- dept_id (INTEGER FK→dim_department)
- region_id (INTEGER FK→dim_region)
- exp_type_id (INTEGER FK→dim_expense_type)
- budget_amount (REAL): 预算金额
- actual_amount (REAL): 实际金额

**fact_receivable** — 应收账款表
- recv_id (INTEGER PK)
- date_id (INTEGER FK→dim_date)
- cust_id (INTEGER FK→dim_customer)
- amount (REAL): 应收金额
- collected_amount (REAL): 已收金额
- due_date (DATE): 到期日
- is_overdue (INTEGER): 是否逾期
- overdue_days (INTEGER): 逾期天数

**fact_payable** — 应付账款表
- pay_id (INTEGER PK)
- date_id (INTEGER FK→dim_date)
- supplier_id (INTEGER FK→dim_supplier)
- amount (REAL): 应付金额
- paid_amount (REAL): 已付金额
- due_date (DATE)
- is_overdue (INTEGER)
- overdue_days (INTEGER)

### 表关联关系
- fact_sales.date_id → dim_date.date_id
- fact_sales.product_id → dim_product.product_id
- fact_sales.region_id → dim_region.region_id
- fact_sales.dept_id → dim_department.dept_id
- fact_sales.cust_id → dim_customer.cust_id
- fact_cost.date_id → dim_date.date_id
- fact_cost.product_id → dim_product.product_id
- fact_cost.region_id → dim_region.region_id
- fact_expense.date_id → dim_date.date_id
- fact_expense.dept_id → dim_department.dept_id
- fact_expense.region_id → dim_region.region_id
- fact_expense.exp_type_id → dim_expense_type.exp_type_id
- fact_receivable.date_id → dim_date.date_id
- fact_receivable.cust_id → dim_customer.cust_id
- fact_payable.date_id → dim_date.date_id
- fact_payable.supplier_id → dim_supplier.supplier_id
"""

# ============================================================
# Layer 3: 业务规则
# ============================================================
BUSINESS_RULES = """
## 核心业务规则

1. **毛利率** = (SUM(revenue) - SUM(cost_amount)) / SUM(revenue) × 100%
   需要 JOIN fact_sales 和 fact_cost，关联条件：date_id, product_id, region_id
   
2. **净利率** = (SUM(revenue) - SUM(cost_amount) - SUM(actual_amount)) / SUM(revenue) × 100%

3. **费用率** = SUM(actual_amount) / SUM(revenue) × 100%

4. **预算执行率** = SUM(actual_amount) / SUM(budget_amount) × 100%

5. **同比增长(YoY)** = (本期值 - 去年同期值) / 去年同期值 × 100%
   使用自连接或子查询，year条件偏移1

6. **环比增长(MoM)** = (本月值 - 上月值) / 上月值 × 100%

7. **回款率** = SUM(collected_amount) / SUM(amount) × 100%

8. **应收周转天数** = AVG(amount - collected_amount) / (SUM(revenue) / 365)

9. **时间表述映射**：
   - "今年" = year = 2024
   - "去年" = year = 2023
   - "Q1/Q2/Q3/Q4" = quarter IN (1,2,3,4)
   - "上半年" = month IN (1,2,3,4,5,6)
   - "下半年" = month IN (7,8,9,10,11,12)

10. **区域表述映射**：
    - "华东" = region_group = '华东' (通过 dim_region 表)
    - "华南"、"华北"、"西南" 同理
    - 大区包含多个城市

11. **数值格式化**：使用 ROUND(value, 2) 保留2位小数
    - 比率类结果建议乘以100并加%符号，但SQL中只返回数值

12. **NULL处理**：使用 COALESCE 或 IFNULL 处理可能的NULL值
"""

# ============================================================
# Layer 4: Few-shot 示例
# ============================================================
FEW_SHOT_EXAMPLES = """
## 参考示例 (Few-shot Examples)

### 示例1：简单聚合查询
用户问题："2024年总营收是多少？"
SQL:
SELECT ROUND(SUM(s.revenue), 2) AS total_revenue
FROM fact_sales s
JOIN dim_date d ON s.date_id = d.date_id
WHERE d.year = 2024;

### 示例2：多维分组查询
用户问题："华东区各产品线2024年的销售收入，按收入降序排列"
SQL:
SELECT p.product_line, ROUND(SUM(s.revenue), 2) AS total_revenue
FROM fact_sales s
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_region r ON s.region_id = r.region_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE r.region_group = '华东' AND d.year = 2024
GROUP BY p.product_line
ORDER BY total_revenue DESC;

### 示例3：毛利率计算
用户问题："2024年Q2的毛利率是多少？"
SQL:
SELECT ROUND((SUM(s.revenue) - SUM(c.cost_amount)) / SUM(s.revenue) * 100, 2) AS gross_margin_pct
FROM fact_sales s
JOIN fact_cost c ON s.date_id = c.date_id AND s.product_id = c.product_id AND s.region_id = c.region_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE d.year = 2024 AND d.quarter = 2;

### 示例4：同比分析
用户问题："2024年Q2毛利率同比2023年Q2变化了多少？"
SQL:
WITH q2_2024 AS (
    SELECT ROUND((SUM(s.revenue) - SUM(c.cost_amount)) / SUM(s.revenue) * 100, 2) AS margin
    FROM fact_sales s
    JOIN fact_cost c ON s.date_id = c.date_id AND s.product_id = c.product_id AND s.region_id = c.region_id
    JOIN dim_date d ON s.date_id = d.date_id
    WHERE d.year = 2024 AND d.quarter = 2
),
q2_2023 AS (
    SELECT ROUND((SUM(s.revenue) - SUM(c.cost_amount)) / SUM(s.revenue) * 100, 2) AS margin
    FROM fact_sales s
    JOIN fact_cost c ON s.date_id = c.date_id AND s.product_id = c.product_id AND s.region_id = c.region_id
    JOIN dim_date d ON s.date_id = d.date_id
    WHERE d.year = 2023 AND d.quarter = 2
)
SELECT q2_2024.margin AS margin_2024, q2_2023.margin AS margin_2023,
       ROUND(q2_2024.margin - q2_2023.margin, 2) AS yoy_change
FROM q2_2024, q2_2023;

### 示例5：预算执行率
用户问题："2024年哪些部门的预算执行率低于80%？"
SQL:
SELECT dept.dept_name, 
       ROUND(SUM(e.actual_amount) / SUM(e.budget_amount) * 100, 2) AS execution_rate
FROM fact_expense e
JOIN dim_department dept ON e.dept_id = dept.dept_id
JOIN dim_date d ON e.date_id = d.date_id
WHERE d.year = 2024
GROUP BY dept.dept_name
HAVING execution_rate < 80
ORDER BY execution_rate ASC;

### 示例6：应收账款分析
用户问题："逾期超过30天的应收账款，按客户统计"
SQL:
SELECT c.cust_name, COUNT(*) AS overdue_count,
       ROUND(SUM(r.amount - r.collected_amount), 2) AS outstanding_amount,
       MAX(r.overdue_days) AS max_overdue_days
FROM fact_receivable r
JOIN dim_customer c ON r.cust_id = c.cust_id
WHERE r.is_overdue = 1 AND r.overdue_days > 30
GROUP BY c.cust_name
ORDER BY outstanding_amount DESC;

### 示例7：TopN排名
用户问题："2024年销售收入最高的5个客户是谁？"
SQL:
SELECT c.cust_name, ROUND(SUM(s.revenue), 2) AS total_revenue
FROM fact_sales s
JOIN dim_customer c ON s.cust_id = c.cust_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE d.year = 2024
GROUP BY c.cust_name
ORDER BY total_revenue DESC
LIMIT 5;
"""

# ============================================================
# 结果分析 Prompt
# ============================================================
ANALYSIS_PROMPT_TEMPLATE = """基于以下财务查询结果，请用专业财务分析视角做简要解读。

## 用户问题
{user_question}

## 生成的SQL
{sql_query}

## 查询结果
{query_result}

## 要求
请按以下结构输出分析（控制在200字以内）：

1. 📊 **核心数据摘要**（1-2句，提取最关键的数字）
2. 🔍 **关键发现**（与业务关联的分析）
3. ⚠️ **风险提示**（如有异常或值得关注的点，无则写"无明显风险"）
4. 💡 **行动建议**（1条可落地的建议，无则写"持续关注"）

注意：
- 如果查询结果为空或只有一行，直接说明
- 使用百分比或对比时注明基准
- 语言简洁，面向管理层"""

# ============================================================
# Prompt 构建函数
# ============================================================
def build_nl2sql_prompt(user_question: str) -> str:
    """
    构建完整的NL2SQL Prompt（5层注入）
    
    Args:
        user_question: 用户自然语言问题
    
    Returns:
        完整的Prompt字符串
    """
    prompt = f"""{SYSTEM_ROLE}

{SCHEMA_CONTEXT}

{BUSINESS_RULES}

{FEW_SHOT_EXAMPLES}

## 用户问题
{user_question}

请生成SQL："""
    return prompt


def build_analysis_prompt(user_question: str, sql_query: str, query_result: str) -> str:
    """构建查询结果分析Prompt"""
    return ANALYSIS_PROMPT_TEMPLATE.format(
        user_question=user_question,
        sql_query=sql_query,
        query_result=query_result
    )


# ============================================================
# 示例问题库（用于前端展示）
# ============================================================
SAMPLE_QUESTIONS = [
    "2024年总营收是多少？",
    "华东区Q2的毛利率是多少？",
    "各产品线的年度销售收入排名",
    "2024年Q2毛利率同比变化了多少？",
    "哪些部门预算执行率低于80%？",
    "销售收入最高的5个客户是谁？",
    "逾期超过30天的应收账款有哪些？",
    "近三年各季度的营收趋势",
    "销售费用中占比最大的费用类型是什么？",
    "毛利率低于20%的产品线有哪些？",
    "2024年各区域营收占总营收的比例",
    "费用率连续上升的部门有哪些？",
    "回款率最低的3个客户是谁？",
    "给我一份2024年Q2的经营简报",
]

# 分类快捷问题
QUICK_QUESTIONS = {
    "💰 营收": [
        "2024年总营收是多少？",
        "各区域2024年营收排名",
        "近三年各季度营收趋势",
    ],
    "📊 毛利": [
        "2024年Q2毛利率是多少？",
        "毛利率同比变化了多少？",
        "毛利率低于20%的产品线",
    ],
    "📉 费用": [
        "2024年费用率是多少？",
        "预算执行率低于80%的部门",
        "销售费用占比最大的类型",
    ],
    "👥 客户": [
        "营收最高的5个客户",
        "回款率最低的客户",
        "逾期应收款最多的客户",
    ],
    "⚠️ 风险": [
        "逾期超过30天的应收账款",
        "毛利率连续下降的产品线",
        "费用率超预算的部门",
    ],
}

# ============================================================
# 通用 NL2SQL Prompt 构建器（支持自定义数据）
# ============================================================
GENERIC_SYSTEM_ROLE = """你是一位资深的数据分析师，精通SQL语言。
你的任务是将用户的自然语言问题，转换为准确的SQLite SQL查询语句。

## 你的能力：
1. 理解数据分析术语（求和、平均、排序、分组、筛选、同比、环比等）
2. 将模糊的自然语言精确化为SQL查询
3. 选择合适的聚合函数、JOIN方式、排序和过滤条件
4. 只生成SELECT查询，绝不生成INSERT/UPDATE/DELETE/DROP等修改语句

## 输出要求：
- 只输出纯净的SQL语句，不要包含```sql```标记
- 不要包含任何解释性文字
- SQL语句以分号结尾
- 优先使用 English 字段名（如SQL中出现的列名）
- 如果问题无法回答，输出: UNABLE_TO_ANSWER"""

GENERIC_FEW_SHOT = """
## 参考示例

用户问题："总共有多少条记录？"
SQL: SELECT COUNT(*) AS total FROM {table};

用户问题："按{group_col}分组统计{agg_col}的合计"
SQL: SELECT {group_col}, SUM({agg_col}) AS total FROM {table} GROUP BY {group_col} ORDER BY total DESC;

用户问题："{agg_col}最高的前5条记录"
SQL: SELECT * FROM {table} ORDER BY {agg_col} DESC LIMIT 5;
"""


def build_generic_prompt(question: str, schema_context: str, table_name: str = "uploaded_data") -> str:
    """为任意上传数据构建 NL2SQL Prompt"""
    # 尝试猜测分组列和聚合列
    prompt = f"""{GENERIC_SYSTEM_ROLE}

{schema_context}

## 业务规则
1. 时间和日期字段可以直接比较和过滤
2. 数值字段支持 SUM/AVG/MAX/MIN/COUNT 聚合
3. 文本字段支持 GROUP BY 分组和 WHERE 筛选
4. 同比(YoY) = (本期值 - 去年同期值) / 去年同期值 * 100
5. 使用 ROUND(value, 2) 保留2位小数

{GENERIC_FEW_SHOT.format(table=table_name, group_col="请根据问题选择合适的分组列", agg_col="请根据问题选择合适的数值列")}

## 用户问题
{question}

请生成SQL："""
    return prompt
