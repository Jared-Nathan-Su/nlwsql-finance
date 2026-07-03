"""
AI 分析解读模块 — 对查询结果进行深度经营分析
支持：异常检测、趋势分析、经营简报生成
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class AnalysisAgent:
    """AI经营分析代理（规则引擎 + LLM增强）"""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
    
    def detect_anomalies(self, df: pd.DataFrame, column: str, method: str = "iqr") -> Dict:
        """
        异常检测
        
        Args:
            df: 数据DataFrame
            column: 要检测的数值列
            method: 检测方法 (iqr / zscore / pct_change)
        
        Returns:
            异常检测结果
        """
        if column not in df.columns or len(df) < 3:
            return {"has_anomaly": False, "anomalies": [], "method": method}
        
        values = df[column].dropna()
        anomalies = []
        
        if method == "iqr":
            Q1 = values.quantile(0.25)
            Q3 = values.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            anomaly_mask = (values < lower) | (values > upper)
            anomalies = values[anomaly_mask].index.tolist()
        
        elif method == "zscore":
            z = (values - values.mean()) / values.std()
            anomaly_mask = abs(z) > 2
            anomalies = values[anomaly_mask].index.tolist()
        
        elif method == "pct_change":
            pct = values.pct_change().abs()
            anomaly_mask = pct > 0.3  # 变化超过30%
            anomalies = values[anomaly_mask].index.tolist()
        
        return {
            "has_anomaly": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomaly_indices": anomalies,
            "method": method,
            "thresholds": f"IQR: [{lower:.2f}, {upper:.2f}]" if method == "iqr" else "Z>2" if method == "zscore" else "变化>30%"
        }
    
    def analyze_trend(self, df: pd.DataFrame, date_col: str, value_col: str) -> Dict:
        """
        趋势分析
        
        Args:
            df: 数据（需包含日期列和数值列）
            date_col: 日期列名
            value_col: 数值列名
        
        Returns:
            趋势分析结果
        """
        if date_col not in df.columns or value_col not in df.columns:
            return {"trend": "unknown", "reason": "列不存在"}
        
        df = df.sort_values(date_col)
        values = df[value_col].values
        
        if len(values) < 2:
            return {"trend": "insufficient_data"}
        
        # 简单线性回归算趋势
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        # 趋势判断
        avg = values.mean()
        if avg == 0:
            return {"trend": "flat"}
        
        slope_pct = slope / avg * 100
        
        if slope_pct > 5:
            trend = "显著上升"
        elif slope_pct > 1:
            trend = "小幅上升"
        elif slope_pct > -1:
            trend = "基本平稳"
        elif slope_pct > -5:
            trend = "小幅下降"
        else:
            trend = "显著下降"
        
        # 波动性
        volatility = np.std(values) / avg * 100 if avg != 0 else 0
        
        return {
            "trend": trend,
            "slope_pct": round(slope_pct, 2),
            "volatility_pct": round(volatility, 2),
            "start_value": round(float(values[0]), 2),
            "end_value": round(float(values[-1]), 2),
            "change_pct": round((values[-1] - values[0]) / values[0] * 100, 2) if values[0] != 0 else 0,
            "max_value": round(float(values.max()), 2),
            "min_value": round(float(values.min()), 2),
        }
    
    def calculate_kpi_summary(self) -> Dict:
        """计算核心KPI摘要"""
        if self.db is None:
            return {}
        
        kpis = {}
        
        # 1. 2024年总营收
        sql = """
        SELECT ROUND(SUM(s.revenue), 2) AS total_revenue
        FROM fact_sales s JOIN dim_date d ON s.date_id = d.date_id
        WHERE d.year = 2024
        """
        ok, df, _ = self.db.execute_query(sql)
        if ok and len(df) > 0:
            kpis["total_revenue_2024"] = float(df.iloc[0, 0])
        
        # 2. 毛利率
        sql = """
        SELECT ROUND((SUM(s.revenue) - SUM(c.cost_amount)) / SUM(s.revenue) * 100, 2)
        FROM fact_sales s
        JOIN fact_cost c ON s.date_id = c.date_id AND s.product_id = c.product_id AND s.region_id = c.region_id
        JOIN dim_date d ON s.date_id = d.date_id
        WHERE d.year = 2024
        """
        ok, df, _ = self.db.execute_query(sql)
        if ok and len(df) > 0:
            kpis["gross_margin_pct"] = float(df.iloc[0, 0])
        
        # 3. 应收逾期金额
        sql = """
        SELECT ROUND(SUM(amount - collected_amount), 2)
        FROM fact_receivable WHERE is_overdue = 1
        """
        ok, df, _ = self.db.execute_query(sql)
        if ok and len(df) > 0:
            kpis["overdue_receivable"] = float(df.iloc[0, 0]) if df.iloc[0, 0] else 0
        
        # 4. 预算执行率
        sql = """
        SELECT ROUND(SUM(actual_amount) / SUM(budget_amount) * 100, 2)
        FROM fact_expense e JOIN dim_date d ON e.date_id = d.date_id
        WHERE d.year = 2024
        """
        ok, df, _ = self.db.execute_query(sql)
        if ok and len(df) > 0:
            kpis["budget_execution_pct"] = float(df.iloc[0, 0])
        
        # 5. 回款率
        sql = """
        SELECT ROUND(SUM(collected_amount) / SUM(amount) * 100, 2)
        FROM fact_receivable
        """
        ok, df, _ = self.db.execute_query(sql)
        if ok and len(df) > 0:
            kpis["collection_rate_pct"] = float(df.iloc[0, 0])
        
        return kpis
    
    def generate_briefing(self) -> str:
        """生成经营简报文本"""
        kpis = self.calculate_kpi_summary()
        
        if not kpis:
            return "无法获取经营数据，请检查数据库。"
        
        lines = [
            "=" * 50,
            f"📊 企业经营简报 ({datetime.now().strftime('%Y年%m月%d日')})",
            "=" * 50,
            "",
            "【核心经营指标】",
            f"  💰 总营收: ¥{kpis.get('total_revenue_2024', 0):,.0f}",
            f"  📈 毛利率: {kpis.get('gross_margin_pct', 0):.1f}%",
            f"  💵 预算执行率: {kpis.get('budget_execution_pct', 0):.1f}%",
            f"  🧾 回款率: {kpis.get('collection_rate_pct', 0):.1f}%",
            f"  ⚠️ 逾期应收: ¥{kpis.get('overdue_receivable', 0):,.0f}",
            "",
            "【风险提示】",
        ]
        
        if kpis.get("overdue_receivable", 0) > 1000000:
            lines.append("  ⚠️ 逾期应收款较高，建议加强催收力度")
        if kpis.get("budget_execution_pct", 100) > 110:
            lines.append("  ⚠️ 预算执行率超110%，需关注费用管控")
        if kpis.get("gross_margin_pct", 30) < 20:
            lines.append("  ⚠️ 毛利率偏低，建议分析成本结构")
        
        if len(lines) == 9:  # 没添加风险
            lines.append("  ✅ 暂无明显风险指标")
        
        lines.extend([
            "",
            "【建议】",
            "  💡 持续关注毛利率变化趋势，及时调整定价策略",
            "  💡 加强应收账款管理，降低逾期比例",
            f"",
            f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ])
        
        return "\n".join(lines)


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from src.db_manager import get_db
    
    db = get_db()
    agent = AnalysisAgent(db)
    
    print(agent.generate_briefing())
