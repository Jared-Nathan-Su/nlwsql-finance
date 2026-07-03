"""
NL2SQL 财务智能问数与经营分析系统 — Streamlit 前端
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db_manager import DatabaseManager, get_db
from src.nl2sql_engine import NL2SQLEngine, create_engine
from src.analysis_agent import AnalysisAgent
from src.prompt_templates import SAMPLE_QUESTIONS, QUICK_QUESTIONS

# ===================== 页面配置 =====================
st.set_page_config(
    page_title="企业财务智能问数系统",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================== 样式 =====================
st.markdown("""
<style>
.main-title {
    font-size: 2rem;
    font-weight: bold;
    color: #1f77b4;
    text-align: center;
    margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 0.9rem;
    color: #666;
    text-align: center;
    margin-bottom: 1.5rem;
}
.sql-box {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 10px;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    overflow-x: auto;
}
.analysis-box {
    background-color: #f0f8ff;
    border-left: 4px solid #1f77b4;
    border-radius: 5px;
    padding: 15px;
    margin: 10px 0;
}
.metric-card {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 15px;
    text-align: center;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
}
.metric-value {
    font-size: 1.5rem;
    font-weight: bold;
    color: #1f77b4;
}
.metric-label {
    font-size: 0.8rem;
    color: #888;
}
</style>
""", unsafe_allow_html=True)

# ===================== 初始化 =====================
@st.cache_resource
def init_db():
    """初始化数据库连接（缓存）"""
    return get_db()

@st.cache_resource
def init_engine(_api_key: str, _model: str):
    """初始化NL2SQL引擎（缓存）"""
    # API Key 优先级: 侧边栏输入 > Streamlit Secrets > 环境变量
    if not _api_key:
        # 尝试从 Streamlit Secrets 读取
        try:
            _api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
        except Exception:
            pass
    if not _api_key:
        # 尝试从环境变量读取
        env_map = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "DASHSCOPE_API_KEY", "openai": "OPENAI_API_KEY"}
        _api_key = os.environ.get(env_map.get(_model, ""), "")
    if not _api_key:
        return None
    try:
        return create_engine(model_provider=_model, api_key=_api_key)
    except Exception as e:
        st.error(f"引擎初始化失败: {e}")
        return None

# ===================== 侧边栏 =====================
def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
        st.markdown("## ⚙️ 系统设置")
        
        # 模型选择
        model_option = st.selectbox(
            "🤖 AI 模型",
            options=["deepseek", "qwen", "openai"],
            format_func=lambda x: {
                "deepseek": "DeepSeek-V3 (推荐)",
                "qwen": "通义千问 Qwen-Max",
                "openai": "GPT-4o"
            }[x],
            index=0,
        )
        
        # API Key — 优先级: 侧边栏 > Streamlit Secrets > 环境变量
        env_map = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "DASHSCOPE_API_KEY", "openai": "OPENAI_API_KEY"}
        env_key = os.environ.get(env_map.get(model_option, ""), "")
        # 也尝试从 Streamlit Secrets 读取
        try:
            secret_key = st.secrets.get(env_map.get(model_option, ""), "")
            if secret_key and not env_key:
                env_key = secret_key
        except Exception:
            pass
        
        api_key = st.text_input(
            "🔑 API Key",
            type="password",
            value=env_key if env_key else "",
            placeholder="请输入API Key...（已自动读取）" if env_key else "请输入API Key...",
            help="DeepSeek: https://platform.deepseek.com\n千问: https://dashscope.aliyun.com\nOpenAI: https://platform.openai.com"
        )
        
        st.divider()
        
        # 系统状态
        st.markdown("### 📊 系统状态")
        try:
            db = init_db()
            schema = db.get_schema_info()
            total_rows = sum(info["row_count"] for info in schema.values())
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("数据表", f"{len(schema)}张")
            with col2:
                st.metric("总记录", f"{total_rows:,}行")
            
            if api_key or env_key:
                st.success("✅ API Key 已配置")
            else:
                st.warning("⚠️ 请配置 API Key")
        except Exception as e:
            st.error(f"数据库连接失败: {e}")
        
        st.divider()
        
        # 历史记录
        st.markdown("### 📜 查询历史")
        if "history" in st.session_state and st.session_state.history:
            for i, h in enumerate(reversed(st.session_state.history[-10:])):
                with st.expander(f"Q: {h['question'][:30]}...", expanded=False):
                    st.caption(f"⏱️ {h.get('elapsed_ms', '?')}ms | 📊 {h.get('rows', '?')}行")
                    if st.button(f"🔄 重新查询", key=f"replay_{i}"):
                        st.session_state.current_question = h["question"]
                        st.rerun()
        else:
            st.caption("暂无查询记录")
        
        st.divider()
        st.caption(f"© 2026 NL2SQL 财务智能问数系统")
        st.caption(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    return model_option, api_key

# ===================== 图表自动选择 =====================
def auto_chart(df: pd.DataFrame):
    """根据数据特征自动选择图表类型"""
    if df is None or len(df) == 0:
        return
    
    cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns.tolist()
    
    if len(numeric_cols) == 0:
        return
    
    # 情况1: 日期/月份 + 数值 → 折线图
    date_keywords = ["date", "year", "month", "quarter", "日期", "年份", "月份", "季度"]
    date_col = None
    for col in cols:
        if any(kw in col.lower() for kw in date_keywords):
            date_col = col
            break
    
    if date_col and len(numeric_cols) >= 1:
        val_col = numeric_cols[0]
        if len(df) <= 50:
            fig = px.line(df, x=date_col, y=val_col, markers=True,
                         title=f"{val_col} 趋势图")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            return
    
    # 情况2: 1个分类列 + 1个数值列 → 柱状图
    cat_cols = [c for c in cols if c not in numeric_cols]
    if len(cat_cols) >= 1 and len(numeric_cols) >= 1:
        cat_col = cat_cols[0]
        val_col = numeric_cols[0]
        
        if len(df) <= 15:
            fig = px.bar(df, x=cat_col, y=val_col, text_auto=".2s",
                        title=f"{val_col} 对比", color=cat_col)
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 如果有第二个数值列，也可以用饼图展示占比
            if len(df) <= 8 and len(df) > 1:
                col1, col2 = st.columns([1, 1])
                with col2:
                    fig2 = px.pie(df, values=val_col, names=cat_col,
                                 title=f"{val_col} 占比")
                    fig2.update_layout(height=350)
                    st.plotly_chart(fig2, use_container_width=True)
            return
    
    # 情况3: 多个数值列 → 柱状图对比
    if len(numeric_cols) >= 2 and len(df) <= 10:
        fig = px.bar(df, x=cols[0], y=numeric_cols,
                    title="多指标对比", barmode="group")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
        return
    
    # 默认：仅显示第一个数值列
    if len(numeric_cols) >= 1 and len(df) > 1:
        fig = px.bar(df, x=df.index if df.index.name else cols[0],
                    y=numeric_cols[0], title=f"{numeric_cols[0]} 概览")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

# ===================== KPI 指标卡 =====================
def render_kpi_cards(db):
    """渲染KPI指标卡片"""
    agent = AnalysisAgent(db)
    kpis = agent.calculate_kpi_summary()
    
    if not kpis:
        return
    
    cols = st.columns(5)
    
    metrics = [
        ("💰 总营收(2024)", f"¥{kpis.get('total_revenue_2024', 0):,.0f}", None),
        ("📈 毛利率", f"{kpis.get('gross_margin_pct', 0):.1f}%", "delta"),
        ("💵 预算执行率", f"{kpis.get('budget_execution_pct', 0):.1f}%", None),
        ("🧾 回款率", f"{kpis.get('collection_rate_pct', 0):.1f}%", None),
        ("⚠️ 逾期应收", f"¥{kpis.get('overdue_receivable', 0):,.0f}", "inverse"),
    ]
    
    for i, (label, value, flag) in enumerate(metrics):
        with cols[i]:
            color = "#e74c3c" if flag == "inverse" else "#1f77b4"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color:{color}">{value}</div>
            </div>
            """, unsafe_allow_html=True)

# ===================== 主页面 =====================
def main():
    # 标题
    st.markdown('<div class="main-title">🏢 企业财务智能问数与经营分析系统</div>', 
                unsafe_allow_html=True)
    st.markdown('<div class="sub-title">基于大模型的 NL2SQL 财务助手 — 自然语言问数，秒级响应</div>',
                unsafe_allow_html=True)
    
    # 侧边栏
    model_option, api_key = render_sidebar()
    
    # 初始化数据库（首次启动自动生成模拟数据，需等待数秒）
    import os as _os
    db_file = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "data", "finance.db")
    if not _os.path.exists(db_file):
        with st.spinner("🔧 首次启动，正在生成模拟财务数据（约10秒）..."):
            db = init_db()
        st.success("✅ 数据生成完成！")
    else:
        db = init_db()
    
    # 主区域 Tabs
    tab1, tab2, tab3 = st.tabs(["💬 智能问数", "📊 经营看板", "📖 使用帮助"])
    
    # ==================== Tab1: 智能问数 ====================
    with tab1:
        # 输入区域 - 使用 columns + button，通过 on_click 回调触发
        # 检查是否有待处理的快捷问题
        pending_q = st.session_state.get("pending_query", "")
        
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            question = st.text_input(
                "问题",
                value=pending_q,
                placeholder="请输入您的财务问题，例如：华东区Q2毛利率同比变化？",
                key="question_input",
                label_visibility="collapsed",
            )
        with col2:
            btn_search = st.button("🚀 查询分析", type="primary", use_container_width=True, key="btn_search")
        with col3:
            btn_random = st.button("🎲 随机示例", use_container_width=True, key="btn_random")
        
        # 快捷问题分类
        st.caption("💡 快捷问题:")
        quick_cols = st.columns(5)
        quick_categories = {
            "💰 营收相关": ["2024年各区域营收排名", "近三年各季度营收趋势", "2024年月度营收变化"],
            "📊 毛利分析": ["各产品线毛利率排名", "华东区Q2毛利率是多少", "毛利率低于20%的产品"],
            "📉 费用管控": ["预算执行率低于80%的部门", "销售费用占比最大的类型", "费用连续上升的部门"],
            "👥 客户应收": ["营收最高的5个客户", "逾期应收款最多的客户", "回款率最低的客户"],
            "⚠️ 风险预警": ["逾期超过30天的应收", "毛利率下降的产品线", "净利率同比变化"],
        }
        
        for i, (cat, questions) in enumerate(quick_categories.items()):
            with quick_cols[i]:
                with st.popover(cat, use_container_width=True):
                    for q in questions:
                        if st.button(q, key=f"quick_{cat}_{q[:10]}", use_container_width=True):
                            st.session_state.pending_query = q
                            st.session_state.auto_search = True
                            st.rerun()
        
        # 随机示例按钮
        if btn_random:
            import random
            st.session_state.pending_query = random.choice(SAMPLE_QUESTIONS)
            st.session_state.auto_search = True
            st.rerun()
        
        # 处理查询后清除 pending
        if (btn_search and question) or st.session_state.get("auto_search", False):
            query_text = question if question else pending_q
            st.session_state.pending_query = ""
            st.session_state.auto_search = False
            process_query(query_text, model_option, api_key)
    
    # ==================== Tab2: 经营看板 ====================
    with tab2:
        st.markdown("### 📊 企业经营概览")
        try:
            render_kpi_cards(db)
        except Exception as e:
            st.warning(f"KPI加载失败: {e}")
        
        st.divider()
        
        # 经营简报
        st.markdown("### 🤖 AI 经营简报")
        if st.button("🔄 生成最新简报", type="primary"):
            with st.spinner("正在生成经营简报..."):
                agent = AnalysisAgent(db)
                briefing = agent.generate_briefing()
                st.code(briefing, language=None)
        
        # 快速图表
        st.markdown("### 📈 快速图表")
        chart_cols = st.columns(3)
        
        charts_quick = [
            ("区域营收分布", """
                SELECT r.region_group, ROUND(SUM(s.revenue),0) AS revenue
                FROM fact_sales s
                JOIN dim_region r ON s.region_id = r.region_id
                JOIN dim_date d ON s.date_id = d.date_id
                WHERE d.year=2024 GROUP BY r.region_group ORDER BY revenue DESC
            """),
            ("产品线毛利率排名", """
                SELECT p.product_line,
                ROUND((SUM(s.revenue)-SUM(c.cost_amount))/SUM(s.revenue)*100,2) AS margin
                FROM fact_sales s
                JOIN fact_cost c ON s.date_id=c.date_id AND s.product_id=c.product_id AND s.region_id=c.region_id
                JOIN dim_product p ON s.product_id=p.product_id
                JOIN dim_date d ON s.date_id=d.date_id
                WHERE d.year=2024 GROUP BY p.product_line ORDER BY margin DESC
            """),
            ("部门费用预算执行率", """
                SELECT dept.dept_name,
                ROUND(SUM(e.actual_amount)/SUM(e.budget_amount)*100,2) AS execution_rate
                FROM fact_expense e
                JOIN dim_department dept ON e.dept_id=dept.dept_id
                JOIN dim_date d ON e.date_id=d.date_id
                WHERE d.year=2024 GROUP BY dept.dept_name ORDER BY execution_rate DESC
            """),
        ]
        
        for i, (title, sql) in enumerate(charts_quick):
            with chart_cols[i]:
                st.caption(title)
                try:
                    ok, df, _ = db.execute_query(sql)
                    if ok and len(df) > 0:
                        auto_chart(df)
                except:
                    st.caption("加载失败")
    
    # ==================== Tab3: 使用帮助 ====================
    with tab3:
        st.markdown("""
        ### 📖 使用指南
        
        #### 🎯 系统简介
        本系统基于大模型（LLM）实现 **自然语言 → SQL → 数据查询 → AI分析** 的全链路自动化，
        让非技术人员也能通过日常语言自助查询企业财务经营数据。
        
        #### 💡 如何提问？
        
        | 提问技巧 | 好的示例 ✅ | 不好的示例 ❌ |
        |----------|------------|-------------|
        | 明确时间范围 | "2024年Q2华东区毛利率" | "毛利率"（时间不明确） |
        | 指明分析维度 | "各产品线年度营收排名" | "看看数据"（维度不明确） |
        | 使用财务术语 | "应收账款周转天数" | "客户欠钱多久还" |
        | 具体指标 | "预算执行率低于80%的部门" | "预算怎么样" |
        
        #### 🔧 技术架构
        - **NL2SQL引擎**: LangChain + LLM（DeepSeek/Qwen/GPT）
        - **数据库**: SQLite（星型模型，6维5事实）
        - **前端**: Streamlit + Plotly
        - **数据**: 3年模拟企业经营数据（10万+行）
        
        #### ⚠️ 注意事项
        - 仅支持查询（SELECT），不支持数据修改
        - 复杂问题建议拆分为多个简单问题
        - SQL生成准确率约 85%+，如结果不对请换种问法
        - API Key 仅用于调用大模型，不会上传您的数据
        
        #### 📊 数据范围
        - 时间: 2022年1月 - 2024年12月
        - 区域: 华东/华南/华北/西南
        - 产品: 12个产品线（硬件/软件/服务）
        - 部门: 8个部门
        - 客户: 50个
        """)

# ===================== 查询处理 =====================
def process_query(question: str, model_option: str, api_key: str):
    """处理用户查询"""
    if not api_key:
        st.error("⚠️ 请先在侧边栏配置 API Key")
        return
    
    if not question.strip():
        st.warning("请输入您的问题")
        return
    
    # 初始化引擎
    engine = init_engine(api_key, model_option)
    if engine is None:
        st.error("引擎初始化失败，请检查 API Key 是否正确")
        return
    
    # 执行查询
    with st.spinner(f"🤔 正在分析您的问题... ({model_option})"):
        result = engine.execute_question(question)
    
    # 显示耗时
    elapsed = result.get("elapsed_ms", 0)
    if elapsed < 1000:
        st.caption(f"⏱️ 响应时间: {elapsed}ms")
    else:
        st.caption(f"⏱️ 响应时间: {elapsed/1000:.1f}s")
    
    # 错误处理
    if not result["success"]:
        st.error(f"❌ 查询失败: {result.get('error', '未知错误')}")
        return
    
    # 保存历史
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append({
        "question": question,
        "sql": result["sql"],
        "rows": len(result["data"]) if result["data"] is not None else 0,
        "elapsed_ms": elapsed,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    })
    
    # ===== 展示结果 =====
    st.divider()
    
    # SQL展示区
    with st.expander("📝 查看生成的 SQL", expanded=False):
        st.markdown(f'<div class="sql-box">{result["sql"]}</div>', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 10])
        with col1:
            if st.button("📋", key="copy_sql", help="复制SQL"):
                st.toast("SQL 已复制!")
    
    # 数据表格
    st.markdown("### 📋 查询结果")
    df = result["data"]
    if df is not None and len(df) > 0:
        st.dataframe(df, use_container_width=True, height=300)
        st.caption(f"共 {len(df)} 行 × {len(df.columns)} 列")
        
        # 下载按钮
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 导出 CSV",
            csv,
            f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
        )
    else:
        st.info("查询结果为空")
    
    # 可视化图表
    if df is not None and len(df) > 0 and len(df) <= 50:
        st.markdown("### 📈 可视化图表")
        try:
            auto_chart(df)
        except Exception as e:
            st.caption(f"图表生成失败: {e}")
    
    # AI分析解读
    if result.get("analysis"):
        st.markdown("### 🤖 AI 经营分析解读")
        st.markdown(f'<div class="analysis-box">{result["analysis"]}</div>', 
                   unsafe_allow_html=True)
    
    st.divider()

# ===================== 启动 =====================
if __name__ == "__main__":
    main()
