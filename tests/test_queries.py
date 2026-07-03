"""
NL2SQL 系统测试用例集
覆盖不同问数类型：查询/聚合/排序/同比/环比/异常/多表JOIN
"""
import sys
import os
import unittest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db_manager import DatabaseManager, get_db
from src.sql_validator import full_validate, clean_sql


class TestDatabaseManager(unittest.TestCase):
    """数据库管理器测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()
    
    def test_db_exists(self):
        """测试数据库文件存在"""
        self.assertTrue(os.path.exists(self.db.db_path))
    
    def test_get_table_names(self):
        """测试获取表名"""
        tables = self.db.get_table_names()
        self.assertGreater(len(tables), 0)
        self.assertIn("fact_sales", tables)
        self.assertIn("dim_date", tables)
    
    def test_get_schema_info(self):
        """测试获取Schema"""
        schema = self.db.get_schema_info()
        self.assertIn("fact_sales", schema)
        self.assertIn("dim_product", schema)
    
    def test_execute_query_simple(self):
        """测试简单查询"""
        ok, df, err = self.db.execute_query("SELECT COUNT(*) AS cnt FROM fact_sales")
        self.assertTrue(ok)
        self.assertGreater(df.iloc[0, 0], 0)
    
    def test_execute_query_join(self):
        """测试JOIN查询"""
        sql = """
        SELECT r.region_group, COUNT(*) AS cnt
        FROM fact_sales s
        JOIN dim_region r ON s.region_id = r.region_id
        GROUP BY r.region_group
        """
        ok, df, err = self.db.execute_query(sql)
        self.assertTrue(ok)
        self.assertGreater(len(df), 0)
    
    def test_execute_query_invalid(self):
        """测试无效SQL"""
        ok, df, err = self.db.execute_query("SELECT * FROM nonexistent_table")
        self.assertFalse(ok)


class TestSQLValidator(unittest.TestCase):
    """SQL安全校验测试"""
    
    def test_valid_select(self):
        """测试合法SELECT"""
        valid, err, cleaned = full_validate("SELECT * FROM fact_sales")
        self.assertTrue(valid)
    
    def test_forbidden_drop(self):
        """测试拦截DROP"""
        valid, err, cleaned = full_validate("DROP TABLE fact_sales")
        self.assertFalse(valid)
    
    def test_forbidden_delete(self):
        """测试拦截DELETE"""
        valid, err, cleaned = full_validate("DELETE FROM fact_sales WHERE 1=1")
        self.assertFalse(valid)
    
    def test_unknown_table(self):
        """测试未知表名"""
        valid, err, cleaned = full_validate("SELECT * FROM unknown_table")
        self.assertFalse(valid)
    
    def test_clean_markdown(self):
        """测试清理Markdown标记"""
        cleaned = clean_sql("```sql\nSELECT * FROM fact_sales;\n```")
        self.assertNotIn("```", cleaned)
        self.assertTrue(cleaned.startswith("SELECT"))
    
    def test_multiple_statements(self):
        """测试拦截多条语句"""
        valid, err, cleaned = full_validate(
            "SELECT * FROM fact_sales; SELECT * FROM fact_cost;"
        )
        self.assertFalse(valid)


class TestDataIntegrity(unittest.TestCase):
    """数据完整性测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()
    
    def test_sales_data_exists(self):
        """测试销售数据存在"""
        ok, df, _ = self.db.execute_query("SELECT COUNT(*) AS cnt FROM fact_sales")
        self.assertGreater(df.iloc[0, 0], 1000)
    
    def test_date_range(self):
        """测试日期范围"""
        ok, df, _ = self.db.execute_query(
            "SELECT MIN(full_date) as min_d, MAX(full_date) as max_d FROM dim_date"
        )
        self.assertIn("2022", str(df.iloc[0, 0]))
        self.assertIn("2024", str(df.iloc[0, 1]))
    
    def test_positive_revenue(self):
        """测试营收为正"""
        ok, df, _ = self.db.execute_query(
            "SELECT MIN(revenue) as min_rev FROM fact_sales"
        )
        self.assertGreater(df.iloc[0, 0], 0)
    
    def test_gross_margin_range(self):
        """测试毛利率在合理范围"""
        sql = """
        SELECT ROUND((SUM(s.revenue)-SUM(c.cost_amount))/SUM(s.revenue)*100, 2) as margin
        FROM fact_sales s
        JOIN fact_cost c ON s.date_id=c.date_id AND s.product_id=c.product_id AND s.region_id=c.region_id
        JOIN dim_date d ON s.date_id=d.date_id
        WHERE d.year=2024
        """
        ok, df, _ = self.db.execute_query(sql)
        margin = df.iloc[0, 0]
        self.assertGreater(margin, 10)
        self.assertLess(margin, 70)
    
    def test_budget_execution_reasonable(self):
        """测试预算执行率合理"""
        sql = """
        SELECT ROUND(SUM(actual_amount)/SUM(budget_amount)*100, 2) as rate
        FROM fact_expense e JOIN dim_date d ON e.date_id=d.date_id
        WHERE d.year=2024
        """
        ok, df, _ = self.db.execute_query(sql)
        rate = df.iloc[0, 0]
        self.assertGreater(rate, 50)
        self.assertLess(rate, 150)


class TestBusinessQueries(unittest.TestCase):
    """业务查询场景测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager()
    
    def run_query(self, sql, desc=""):
        """辅助方法：运行查询并验证成功"""
        ok, df, err = self.db.execute_query(sql)
        self.assertTrue(ok, f"{desc}\nSQL: {sql[:100]}\nError: {err}")
        return df
    
    def test_q1_total_revenue(self):
        """Q1: 2024年总营收"""
        df = self.run_query("""
            SELECT ROUND(SUM(s.revenue), 2) AS total_revenue
            FROM fact_sales s JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024
        """, "总营收")
        self.assertGreater(df.iloc[0, 0], 0)
    
    def test_q2_region_revenue(self):
        """Q2: 各区域营收排名"""
        df = self.run_query("""
            SELECT r.region_group, ROUND(SUM(s.revenue), 2) AS revenue
            FROM fact_sales s
            JOIN dim_region r ON s.region_id = r.region_id
            JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY r.region_group
            ORDER BY revenue DESC
        """, "区域营收")
        self.assertGreater(len(df), 1)
    
    def test_q3_gross_margin(self):
        """Q3: 毛利率计算"""
        df = self.run_query("""
            SELECT ROUND((SUM(s.revenue)-SUM(c.cost_amount))/SUM(s.revenue)*100, 2) AS margin
            FROM fact_sales s
            JOIN fact_cost c ON s.date_id=c.date_id AND s.product_id=c.product_id AND s.region_id=c.region_id
            JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024 AND d.quarter = 2
        """, "毛利率")
        self.assertGreater(df.iloc[0, 0], 0)
    
    def test_q4_product_margin_rank(self):
        """Q4: 产品线毛利率排名"""
        df = self.run_query("""
            SELECT p.product_line,
            ROUND((SUM(s.revenue)-SUM(c.cost_amount))/SUM(s.revenue)*100, 2) AS margin
            FROM fact_sales s
            JOIN fact_cost c ON s.date_id=c.date_id AND s.product_id=c.product_id AND s.region_id=c.region_id
            JOIN dim_product p ON s.product_id = p.product_id
            JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY p.product_line
            ORDER BY margin DESC
        """, "产品线毛利率")
        self.assertGreater(len(df), 0)
    
    def test_q5_budget_execution(self):
        """Q5: 预算执行率"""
        df = self.run_query("""
            SELECT dept.dept_name,
            ROUND(SUM(e.actual_amount)/SUM(e.budget_amount)*100, 2) AS execution_rate
            FROM fact_expense e
            JOIN dim_department dept ON e.dept_id = dept.dept_id
            JOIN dim_date d ON e.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY dept.dept_name
            HAVING execution_rate < 80
            ORDER BY execution_rate ASC
        """, "预算执行率")
        # 不一定有结果，但查询应该成功
    
    def test_q6_top_customers(self):
        """Q6: Top5客户"""
        df = self.run_query("""
            SELECT c.cust_name, ROUND(SUM(s.revenue), 2) AS total_revenue
            FROM fact_sales s
            JOIN dim_customer c ON s.cust_id = c.cust_id
            JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY c.cust_name
            ORDER BY total_revenue DESC
            LIMIT 5
        """, "Top5客户")
        self.assertEqual(len(df), 5)
    
    def test_q7_overdue_receivable(self):
        """Q7: 逾期应收"""
        df = self.run_query("""
            SELECT c.cust_name,
            ROUND(SUM(r.amount - r.collected_amount), 2) AS outstanding,
            MAX(r.overdue_days) AS max_days
            FROM fact_receivable r
            JOIN dim_customer c ON r.cust_id = c.cust_id
            WHERE r.is_overdue = 1 AND r.overdue_days > 30
            GROUP BY c.cust_name
            ORDER BY outstanding DESC
        """, "逾期应收")
    
    def test_q8_quarterly_trend(self):
        """Q8: 季度营收趋势"""
        df = self.run_query("""
            SELECT d.year, d.quarter, ROUND(SUM(s.revenue), 2) AS revenue
            FROM fact_sales s JOIN dim_date d ON s.date_id = d.date_id
            GROUP BY d.year, d.quarter
            ORDER BY d.year, d.quarter
        """, "季度趋势")
        self.assertGreater(len(df), 4)
    
    def test_q9_expense_structure(self):
        """Q9: 费用结构"""
        df = self.run_query("""
            SELECT et.exp_type_name,
            ROUND(SUM(e.actual_amount), 2) AS total_amount
            FROM fact_expense e
            JOIN dim_expense_type et ON e.exp_type_id = et.exp_type_id
            JOIN dim_date d ON e.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY et.exp_type_name
            ORDER BY total_amount DESC
        """, "费用结构")
        self.assertGreater(len(df), 0)
    
    def test_q10_revenue_by_month(self):
        """Q10: 月度营收"""
        df = self.run_query("""
            SELECT d.year, d.month, ROUND(SUM(s.revenue), 2) AS revenue
            FROM fact_sales s JOIN dim_date d ON s.date_id = d.date_id
            WHERE d.year = 2024
            GROUP BY d.year, d.month
            ORDER BY d.month
        """, "月度营收")
        self.assertEqual(len(df), 12)


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 NL2SQL 系统测试套件")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSQLValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestDataIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestBusinessQueries))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 汇总
    print("\n" + "=" * 60)
    print(f"✅ 通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"⚠️  错误: {len(result.errors)}")
    print(f"📊 总计: {result.testsRun}")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    run_all_tests()
