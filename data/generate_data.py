"""
模拟财务数据生成脚本
生成3年（2022-2024）的企业经营数据，包含：
- 6个区域、12个产品、8个部门、50个客户、20个供应商
- 销售收入、成本、费用（含预算）、应收应付
- 数据符合真实财务逻辑（毛利率15%-60%、季节性波动、增长趋势）
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# ===================== 配置参数 =====================
DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")
START_DATE = "2022-01-01"
END_DATE = "2024-12-31"
np.random.seed(42)

# ===================== 工具函数 =====================
def create_db():
    """创建数据库并执行建表脚本"""
    conn = sqlite3.connect(DB_PATH)
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn

# ===================== 1. 生成日期维度表 =====================
def generate_dim_date():
    """生成日期维度"""
    dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    df = pd.DataFrame({
        "date_id": [int(d.strftime("%Y%m%d")) for d in dates],
        "full_date": dates.strftime("%Y-%m-%d"),
        "year": dates.year,
        "quarter": dates.quarter,
        "month": dates.month,
        "month_name": dates.strftime("%B"),
        "day_of_month": dates.day,
        "day_of_week": dates.dayofweek,
        "is_weekend": (dates.dayofweek >= 5).astype(int),
    })
    return df

# ===================== 2. 生成业务维度表 =====================
def generate_dim_product():
    """12个产品"""
    data = [
        ("企业ERP系统", "软件", "管理软件"),
        ("智能财务中台", "软件", "管理软件"),
        ("数据分析平台", "软件", "数据产品"),
        ("云服务器ECS", "硬件", "云计算"),
        ("云存储OSS", "硬件", "云计算"),
        ("网络安全网关", "硬件", "网络安全"),
        ("数据备份一体机", "硬件", "数据存储"),
        ("IT运维服务", "服务", "技术服务"),
        ("系统集成服务", "服务", "技术服务"),
        ("管理咨询", "服务", "咨询服务"),
        ("AI算法引擎", "软件", "AI产品"),
        ("物联网平台", "软件", "IoT产品"),
    ]
    df = pd.DataFrame(data, columns=["product_name", "category", "product_line"])
    df.index.name = "product_id"
    df = df.reset_index()
    df["product_id"] += 1
    return df

def generate_dim_department():
    """8个部门"""
    data = [
        ("销售一部", "前台"),
        ("销售二部", "前台"),
        ("市场部", "前台"),
        ("研发中心", "中台"),
        ("技术支持部", "中台"),
        ("财务部", "后台"),
        ("人力资源部", "后台"),
        ("行政管理部", "后台"),
    ]
    df = pd.DataFrame(data, columns=["dept_name", "dept_type"])
    df.index.name = "dept_id"
    df = df.reset_index()
    df["dept_id"] += 1
    return df

def generate_dim_region():
    """6个区域（城市级，归属于大区）"""
    data = [
        ("上海", "华东"),
        ("杭州", "华东"),
        ("广州", "华南"),
        ("深圳", "华南"),
        ("北京", "华北"),
        ("成都", "西南"),
    ]
    df = pd.DataFrame(data, columns=["region_name", "region_group"])
    df.index.name = "region_id"
    df = df.reset_index()
    df["region_id"] += 1
    return df

def generate_dim_customer():
    """50个客户"""
    industries = ["制造业", "金融", "互联网", "零售", "医疗", "教育", "政府", "能源"]
    levels = ["A", "B", "C"]
    regions = ["华东", "华南", "华北", "西南"]
    
    customers = []
    for i in range(1, 51):
        cust_name = f"客户_{i:02d}"
        industry = np.random.choice(industries)
        level = np.random.choice(levels, p=[0.2, 0.5, 0.3])
        credit = np.random.normal(80, 10) if level == "A" else np.random.normal(65, 12)
        credit = max(30, min(100, credit))
        region = np.random.choice(regions)
        customers.append((cust_name, industry, level, round(credit, 1), region))
    
    df = pd.DataFrame(customers, columns=["cust_name", "cust_industry", "cust_level", "credit_score", "region_group"])
    df.index.name = "cust_id"
    df = df.reset_index()
    df["cust_id"] += 1
    return df

def generate_dim_supplier():
    """20个供应商"""
    categories = ["原材料", "软件授权", "云服务", "物流", "咨询"]
    regions = ["华东", "华南", "华北", "西南", "华中"]
    suppliers = []
    for i in range(1, 21):
        name = f"供应商_{i:02d}"
        cat = np.random.choice(categories)
        reg = np.random.choice(regions)
        suppliers.append((name, cat, reg))
    df = pd.DataFrame(suppliers, columns=["supplier_name", "supplier_category", "region_group"])
    df.index.name = "supplier_id"
    df = df.reset_index()
    df["supplier_id"] += 1
    return df

def generate_dim_expense_type():
    """10种费用类型"""
    data = [
        ("差旅交通费", "销售费用"),
        ("业务招待费", "销售费用"),
        ("广告推广费", "销售费用"),
        ("办公场地费", "管理费用"),
        ("人员薪酬", "管理费用"),
        ("折旧摊销", "管理费用"),
        ("研发材料费", "研发费用"),
        ("测试认证费", "研发费用"),
        ("利息支出", "财务费用"),
        ("汇兑损益", "财务费用"),
    ]
    df = pd.DataFrame(data, columns=["exp_type_name", "exp_category"])
    df.index.name = "exp_type_id"
    df = df.reset_index()
    df["exp_type_id"] += 1
    return df

# ===================== 3. 生成事实表 =====================
def generate_fact_sales(dim_date, dim_product, dim_region, dim_dept, dim_customer):
    """
    销售事实表：每月每产品每区域每天 ≈ 随机分配
    构造方式：每月每产品每区域每部门生成1条记录
    记录数 = 36月 × 12产品 × 6区域 × 8部门 ≈ 20736条（再随机选客户，扩充到~30000）
    """
    records = []
    months = dim_date[["year", "month", "date_id"]].drop_duplicates(subset=["year","month"])
    
    # 产品基准价格和利润率
    product_base = {
        1: (500000, 0.55),  2: (400000, 0.50),  3: (300000, 0.60),
        4: (200000, 0.35),  5: (150000, 0.40),  6: (180000, 0.45),
        7: (160000, 0.38),  8: (100000, 0.30),  9: (120000, 0.28),
        10: (250000, 0.65), 11: (350000, 0.58), 12: (220000, 0.42),
    }
    
    region_factor = {1: 1.3, 2: 1.0, 3: 1.2, 4: 1.1, 5: 1.4, 6: 0.8}  # 区域规模因子
    dept_factor = {1: 0.35, 2: 0.25, 3: 0.15, 4: 0.08, 5: 0.07, 6: 0.05, 7: 0.03, 8: 0.02}  # 部门销售贡献
    
    for _, month_row in months.iterrows():
        y, m = int(month_row["year"]), int(month_row["month"])
        # 年度增长率 10-20%
        growth = 1 + 0.12 * (y - 2022) + np.random.normal(0, 0.03)
        seasonal = 1 + 0.15 * np.sin(np.pi * (m - 3) / 6)  # Q2/Q3偏高
        
        for pid, (base_price, margin) in product_base.items():
            for rid, rf in region_factor.items():
                for did, dfactor in dept_factor.items():
                    # 选一个客户
                    cust_id = np.random.choice(dim_customer["cust_id"].values)
                    # 找一个当月日期
                    month_dates = dim_date[(dim_date["year"] == y) & (dim_date["month"] == m)]
                    if len(month_dates) == 0:
                        continue
                    date_id = int(month_dates.sample(1)["date_id"].values[0])
                    
                    # 收入 = 基准×区域因子×增长×季节×部门贡献 + 噪声
                    revenue = base_price * rf * growth * seasonal * dfactor
                    revenue *= np.random.normal(1, 0.15)
                    revenue = max(revenue, 1000)
                    quantity = max(1, int(revenue / (base_price / 100) * np.random.uniform(0.8, 1.2)))
                    
                    records.append((date_id, pid, rid, did, cust_id, round(revenue, 2), quantity))
    
    df = pd.DataFrame(records, columns=["date_id", "product_id", "region_id", "dept_id", "cust_id", "revenue", "quantity"])
    return df

def generate_fact_cost(dim_date, dim_product, dim_region, fact_sales):
    """成本事实表：与销售关联，每条销售记录对应一条成本记录"""
    records = []
    # 成本率（1-毛利率），产品对应
    cost_ratio = {
        1: 0.45, 2: 0.50, 3: 0.40, 4: 0.65, 5: 0.60, 6: 0.55,
        7: 0.62, 8: 0.70, 9: 0.72, 10: 0.35, 11: 0.42, 12: 0.58,
    }
    
    # 按月汇总销售，生成对应成本
    sales_grouped = fact_sales.groupby(["date_id", "product_id", "region_id"])["revenue"].sum().reset_index()
    
    for _, row in sales_grouped.iterrows():
        pid = int(row["product_id"])
        ratio = cost_ratio.get(pid, 0.5)
        cost = row["revenue"] * ratio * np.random.normal(1, 0.05)
        cost = max(cost, 100)
        cost_type = "direct" if np.random.random() > 0.3 else "indirect"
        records.append((int(row["date_id"]), pid, int(row["region_id"]), round(cost, 2), cost_type))
    
    df = pd.DataFrame(records, columns=["date_id", "product_id", "region_id", "cost_amount", "cost_type"])
    return df

def generate_fact_expense(dim_date, dim_department, dim_region, dim_expense_type):
    """费用事实表：每月每部门每区域每费用类型，含预算vs实际"""
    records = []
    months = dim_date[["year", "month", "date_id"]].drop_duplicates(subset=["year", "month"])
    
    # 各部门月度费用基准
    dept_base = {1: 80000, 2: 60000, 3: 120000, 4: 200000, 5: 90000, 6: 40000, 7: 50000, 8: 30000}
    # 费用类型占比（归一化）
    exp_weights = {1: 0.10, 2: 0.08, 3: 0.12, 4: 0.15, 5: 0.30, 6: 0.05, 7: 0.08, 8: 0.03, 9: 0.05, 10: 0.04}
    
    for _, month_row in months.iterrows():
        y, m = int(month_row["year"]), int(month_row["month"])
        growth = 1 + 0.08 * (y - 2022)
        
        for did, base in dept_base.items():
            for rid in dim_region["region_id"]:
                for etid, weight in exp_weights.items():
                    month_dates = dim_date[(dim_date["year"] == y) & (dim_date["month"] == m)]
                    if len(month_dates) == 0:
                        continue
                    date_id = int(month_dates.sample(1)["date_id"].values[0])
                    
                    budget = base * weight * growth * np.random.normal(1, 0.1)
                    budget = max(budget, 500)
                    
                    # 实际：有时超预算，有时节余
                    actual = budget * np.random.normal(1.02, 0.12)  # 平均超预算2%
                    actual = max(actual, 200)
                    
                    records.append((date_id, did, rid, etid, round(budget, 2), round(actual, 2)))
    
    df = pd.DataFrame(records, columns=["date_id", "dept_id", "region_id", "exp_type_id", "budget_amount", "actual_amount"])
    return df

def generate_fact_receivable(dim_date, dim_customer):
    """应收账款：每月产生若干应收记录"""
    records = []
    start = datetime(2022, 1, 1)
    end = datetime(2024, 12, 31)
    
    for cust_id in dim_customer["cust_id"]:
        cust_level = dim_customer[dim_customer["cust_id"] == cust_id]["cust_level"].values[0]
        credit = dim_customer[dim_customer["cust_id"] == cust_id]["credit_score"].values[0]
        
        # A级客户每月1-2笔，B级每月1笔，C级每2月1笔
        if cust_level == "A":
            freq = np.random.choice([1, 2])
        elif cust_level == "B":
            freq = 1
        else:
            freq = 0.5
        
        current = start
        while current <= end:
            if np.random.random() < freq:
                date_id = int(current.strftime("%Y%m%d"))
                amount = np.random.lognormal(10, 1.2) * (10000 if cust_level == "A" else 5000)
                amount = round(amount, 2)
                
                # 回款概率
                pay_prob = credit / 100
                collected = amount * min(1, pay_prob * np.random.uniform(0.8, 1.0))
                
                due_days = int(np.random.choice([30, 60, 90]))
                due_date = current + timedelta(days=due_days)
                days_diff = (datetime(2024, 12, 31) - due_date).days
                is_overdue = 1 if (amount - collected > 100 and days_diff > 0) else 0
                overdue_days = max(0, days_diff) if is_overdue else 0
                
                records.append((date_id, cust_id, amount, round(collected, 2), 
                               due_date.strftime("%Y-%m-%d"), is_overdue, overdue_days))
            
            current += timedelta(days=30)
    
    df = pd.DataFrame(records, columns=["date_id", "cust_id", "amount", "collected_amount", "due_date", "is_overdue", "overdue_days"])
    return df

def generate_fact_payable(dim_date, dim_supplier):
    """应付账款：类似应收，但规模更小"""
    records = []
    start = datetime(2022, 1, 1)
    end = datetime(2024, 12, 31)
    
    for sup_id in dim_supplier["supplier_id"]:
        current = start
        while current <= end:
            if np.random.random() < 0.6:  # 每月60%概率产生应付
                date_id = int(current.strftime("%Y%m%d"))
                amount = round(np.random.lognormal(9.5, 1.0), 2)
                paid = amount * np.random.uniform(0.7, 1.0)
                due_days = int(np.random.choice([30, 45, 60]))
                due_date = current + timedelta(days=due_days)
                days_diff = (datetime(2024, 12, 31) - due_date).days
                is_overdue = 1 if (amount - paid > 50 and days_diff > 0) else 0
                overdue_days = max(0, days_diff) if is_overdue else 0
                
                records.append((date_id, sup_id, amount, round(paid, 2),
                               due_date.strftime("%Y-%m-%d"), is_overdue, overdue_days))
            current += timedelta(days=30)
    
    df = pd.DataFrame(records, columns=["date_id", "supplier_id", "amount", "paid_amount", "due_date", "is_overdue", "overdue_days"])
    return df

# ===================== 4. 主函数 =====================
def main():
    print("=" * 60)
    print("🔧 开始生成模拟财务数据集...")
    print("=" * 60)
    
    # 生成维度表
    print("📅 生成日期维度...")
    dim_date = generate_dim_date()
    print(f"   → {len(dim_date)} 条记录")
    
    print("📦 生成产品维度...")
    dim_product = generate_dim_product()
    print(f"   → {len(dim_product)} 条记录")
    
    print("🏢 生成部门维度...")
    dim_department = generate_dim_department()
    print(f"   → {len(dim_department)} 条记录")
    
    print("🗺️  生成区域维度...")
    dim_region = generate_dim_region()
    print(f"   → {len(dim_region)} 条记录")
    
    print("👥 生成客户维度...")
    dim_customer = generate_dim_customer()
    print(f"   → {len(dim_customer)} 条记录")
    
    print("🚚 生成供应商维度...")
    dim_supplier = generate_dim_supplier()
    print(f"   → {len(dim_supplier)} 条记录")
    
    print("💰 生成费用类型维度...")
    dim_expense_type = generate_dim_expense_type()
    print(f"   → {len(dim_expense_type)} 条记录")
    
    # 生成事实表
    print("💵 生成销售事实表...")
    fact_sales = generate_fact_sales(dim_date, dim_product, dim_region, dim_department, dim_customer)
    print(f"   → {len(fact_sales)} 条记录, 总营收: ¥{fact_sales['revenue'].sum():,.0f}")
    
    print("📉 生成成本事实表...")
    fact_cost = generate_fact_cost(dim_date, dim_product, dim_region, fact_sales)
    print(f"   → {len(fact_cost)} 条记录, 总成本: ¥{fact_cost['cost_amount'].sum():,.0f}")
    
    print("📊 生成费用事实表...")
    fact_expense = generate_fact_expense(dim_date, dim_department, dim_region, dim_expense_type)
    print(f"   → {len(fact_expense)} 条记录")
    
    print("🧾 生成应收账款表...")
    fact_receivable = generate_fact_receivable(dim_date, dim_customer)
    print(f"   → {len(fact_receivable)} 条记录, 总应收: ¥{fact_receivable['amount'].sum():,.0f}")
    
    print("📋 生成应付账款表...")
    fact_payable = generate_fact_payable(dim_date, dim_supplier)
    print(f"   → {len(fact_payable)} 条记录, 总应付: ¥{fact_payable['amount'].sum():,.0f}")
    
    # 写入数据库
    print("\n💾 写入 SQLite 数据库...")
    conn = create_db()
    
    tables = {
        "dim_date": dim_date,
        "dim_product": dim_product,
        "dim_department": dim_department,
        "dim_region": dim_region,
        "dim_customer": dim_customer,
        "dim_supplier": dim_supplier,
        "dim_expense_type": dim_expense_type,
        "fact_sales": fact_sales,
        "fact_cost": fact_cost,
        "fact_expense": fact_expense,
        "fact_receivable": fact_receivable,
        "fact_payable": fact_payable,
    }
    
    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"   ✓ {name}: {len(df)} 行")
    
    conn.commit()
    conn.close()
    
    # 统计输出
    print("\n" + "=" * 60)
    print("✅ 数据生成完成!")
    print(f"📁 数据库文件: {DB_PATH}")
    print(f"📏 总表数: {len(tables)}")
    print(f"📊 总记录数: {sum(len(df) for df in tables.values()):,}")
    print(f"📐 数据库大小: {os.path.getsize(DB_PATH) / 1024 / 1024:.1f} MB")
    
    # 关键指标验证
    total_revenue = fact_sales["revenue"].sum()
    total_cost = fact_cost["cost_amount"].sum()
    total_expense = fact_expense["actual_amount"].sum()
    gross_margin = (total_revenue - total_cost) / total_revenue * 100
    net_margin = (total_revenue - total_cost - total_expense) / total_revenue * 100
    print(f"\n📈 关键指标验证:")
    print(f"   总营收: ¥{total_revenue:,.0f}")
    print(f"   毛利率: {gross_margin:.1f}%")
    print(f"   净利率: {net_margin:.1f}%")
    print("=" * 60)

if __name__ == "__main__":
    main()
