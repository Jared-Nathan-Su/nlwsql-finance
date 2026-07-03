-- ============================================
-- NL2SQL 财务智能问数系统 - 数据库建表脚本
-- 星型模型：6个维度表 + 5个事实表
-- ============================================

-- =====================
-- 维度表
-- =====================

-- 日期维度表（3年 × 365天 ≈ 1096 行）
CREATE TABLE IF NOT EXISTS dim_date (
    date_id INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend INTEGER NOT NULL DEFAULT 0
);

-- 产品维度表
CREATE TABLE IF NOT EXISTS dim_product (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,          -- 硬件 / 软件 / 服务
    product_line TEXT NOT NULL       -- 产品线名称
);

-- 部门维度表
CREATE TABLE IF NOT EXISTS dim_department (
    dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_name TEXT NOT NULL,
    dept_type TEXT NOT NULL          -- 前台 / 中台 / 后台
);

-- 区域维度表
CREATE TABLE IF NOT EXISTS dim_region (
    region_id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_name TEXT NOT NULL,       -- 如：上海、杭州、广州
    region_group TEXT NOT NULL       -- 大区：华东/华南/华北/华中/西南/西北
);

-- 客户维度表
CREATE TABLE IF NOT EXISTS dim_customer (
    cust_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cust_name TEXT NOT NULL,
    cust_industry TEXT,              -- 行业
    cust_level TEXT DEFAULT 'B',     -- 客户等级 A/B/C
    credit_score REAL DEFAULT 80.0,  -- 信用评分 0-100
    region_group TEXT                -- 所属大区
);

-- 供应商维度表
CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    supplier_category TEXT,          -- 原材料/服务/物流/其他
    region_group TEXT
);

-- 费用类型维度表
CREATE TABLE IF NOT EXISTS dim_expense_type (
    exp_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_type_name TEXT NOT NULL,     -- 差旅费/办公费/市场费/人力成本/研发费等
    exp_category TEXT NOT NULL       -- 销售费用/管理费用/研发费用/财务费用
);

-- =====================
-- 事实表
-- =====================

-- 销售事实表（~36000行：12产品 × 6区域 × 8部门 × 50客户，3年按月）
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    dept_id INTEGER NOT NULL,
    cust_id INTEGER NOT NULL,
    revenue REAL NOT NULL DEFAULT 0,       -- 销售收入（元）
    quantity INTEGER NOT NULL DEFAULT 0,   -- 销售数量
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id),
    FOREIGN KEY (dept_id) REFERENCES dim_department(dept_id),
    FOREIGN KEY (cust_id) REFERENCES dim_customer(cust_id)
);

-- 成本事实表
CREATE TABLE IF NOT EXISTS fact_cost (
    cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    cost_amount REAL NOT NULL DEFAULT 0,   -- 成本金额
    cost_type TEXT DEFAULT 'direct',       -- direct/indirect
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id)
);

-- 费用事实表（含预算与实际对比）
CREATE TABLE IF NOT EXISTS fact_expense (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL,
    dept_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    exp_type_id INTEGER NOT NULL,
    budget_amount REAL NOT NULL DEFAULT 0,  -- 预算金额
    actual_amount REAL NOT NULL DEFAULT 0,  -- 实际金额
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (dept_id) REFERENCES dim_department(dept_id),
    FOREIGN KEY (region_id) REFERENCES dim_region(region_id),
    FOREIGN KEY (exp_type_id) REFERENCES dim_expense_type(exp_type_id)
);

-- 应收账款事实表
CREATE TABLE IF NOT EXISTS fact_receivable (
    recv_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL,              -- 应收产生日期
    cust_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 0,        -- 应收金额
    collected_amount REAL NOT NULL DEFAULT 0, -- 已收金额
    due_date DATE NOT NULL,                -- 到期日
    is_overdue INTEGER DEFAULT 0,          -- 是否逾期
    overdue_days INTEGER DEFAULT 0,        -- 逾期天数
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (cust_id) REFERENCES dim_customer(cust_id)
);

-- 应付账款事实表
CREATE TABLE IF NOT EXISTS fact_payable (
    pay_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 0,        -- 应付金额
    paid_amount REAL NOT NULL DEFAULT 0,   -- 已付金额
    due_date DATE NOT NULL,
    is_overdue INTEGER DEFAULT 0,
    overdue_days INTEGER DEFAULT 0,
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (supplier_id) REFERENCES dim_supplier(supplier_id)
);

-- =====================
-- 索引（加速查询）
-- =====================
CREATE INDEX IF NOT EXISTS idx_sales_date ON fact_sales(date_id);
CREATE INDEX IF NOT EXISTS idx_sales_product ON fact_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_region ON fact_sales(region_id);
CREATE INDEX IF NOT EXISTS idx_sales_dept ON fact_sales(dept_id);
CREATE INDEX IF NOT EXISTS idx_cost_date ON fact_cost(date_id);
CREATE INDEX IF NOT EXISTS idx_cost_product ON fact_cost(product_id);
CREATE INDEX IF NOT EXISTS idx_expense_date ON fact_expense(date_id);
CREATE INDEX IF NOT EXISTS idx_expense_dept ON fact_expense(dept_id);
CREATE INDEX IF NOT EXISTS idx_receivable_date ON fact_receivable(date_id);
CREATE INDEX IF NOT EXISTS idx_receivable_cust ON fact_receivable(cust_id);
CREATE INDEX IF NOT EXISTS idx_payable_date ON fact_payable(date_id);
