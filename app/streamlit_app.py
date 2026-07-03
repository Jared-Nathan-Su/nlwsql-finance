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
/* ----- 主容器 ----- */
.stApp { background: #f8fafc; }

/* ----- 标题区 ----- */
.main-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    color: white;
    padding: 1.8rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    text-align: center;
    box-shadow: 0 4px 15px rgba(26,115,232,0.25);
}
.main-header h1 { font-size: 1.8rem; margin: 0; font-weight: 700; }
.main-header p { margin: 0.4rem 0 0; opacity: 0.9; font-size: 0.95rem; }

/* ----- KPI 卡片 ----- */
.kpi-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 1rem 0.8rem;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border-top: 3px solid #1a73e8;
}
.kpi-card.warn { border-top-color: #c0392b; }
.kpi-value { font-size: 1.5rem; font-weight: 700; color: #1a73e8; }
.kpi-card.warn .kpi-value { color: #c0392b; }
.kpi-label { font-size: 0.78rem; color: #7f8c8d; margin-top: 0.3rem; }

/* ----- SQL 代码框 ----- */
.sql-box {
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 8px;
    padding: 14px 18px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 0.82rem;
    line-height: 1.6;
    overflow-x: auto;
}

/* ----- AI 分析框 ----- */
.analysis-box {
    background: linear-gradient(135deg, #eff6ff 0%, #faf5ff 100%);
    border-left: 4px solid #1a73e8;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 1rem 0;
    font-size: 0.92rem;
    line-height: 1.7;
}

/* ----- 侧边栏 ----- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

/* ----- 按钮 ----- */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px); }

/* ----- 输入框 ----- */
.stTextInput > div > div > input {
    border-radius: 8px !important;
    border: 2px solid #e1e8ed !important;
    padding: 0.6rem 1rem !important;
    font-size: 0.95rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #1a73e8 !important;
    box-shadow: 0 0 0 3px rgba(26,115,232,0.15) !important;
}

/* ----- Tabs ----- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: #ffffff;
    border-radius: 10px;
    padding: 0.3rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 0.5rem 1.2rem !important;
    font-weight: 600 !important;
}

/* ----- 隐藏默认元素 ----- */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
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
        # Logo 区
        st.markdown("""
        <div style="text-align:center; padding:1rem 0 0.5rem;">
            <span style="font-size:2.5rem;">🏢</span>
            <h3 style="margin:0.3rem 0; color:#1a73e8;">财务智能问数</h3>
            <p style="font-size:0.75rem; color:#888; margin:0;">NL2SQL · AI 驱动</p>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        
        # 模型选择
        st.markdown("#### 🤖 模型设置")
        model_option = st.selectbox(
            "AI 模型",
            options=["deepseek", "qwen", "openai"],
            format_func=lambda x: {
                "deepseek": "DeepSeek-V3",
                "qwen": "通义千问 Qwen-Max",
                "openai": "GPT-4o"
            }[x],
            index=0,
        )
        
        # API Key — 安全机制：不预填实际值，仅显示脱敏提示
        env_map = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "DASHSCOPE_API_KEY", "openai": "OPENAI_API_KEY"}
        env_key = os.environ.get(env_map.get(model_option, ""), "")
        try:
            secret_key = st.secrets.get(env_map.get(model_option, ""), "")
            if secret_key and not env_key:
                env_key = secret_key
        except Exception:
            pass
        
        # 密码输入框，始终为空初始值（不泄露Key）
        api_key = st.text_input(
            "API Key",
            type="password",
            value="",
            placeholder="已自动注入，无需填写" if env_key else "请输入 API Key",
            help="密钥通过环境变量/Secrets注入，不会明文展示。获取: platform.deepseek.com"
        )
        # 用户手动填写的优先，否则用环境变量
        effective_key = api_key if api_key else env_key
        if effective_key:
            masked = effective_key[:6] + "****" + effective_key[-4:]
            st.caption(f"🔒 已注入: `{masked}`")
        else:
            st.caption("⚠️ 未配置 API Key")
        
        st.divider()
        
        # 系统状态
        st.markdown("#### 📊 数据状态")
        try:
            db = init_db()
            schema = db.get_schema_info()
            total_rows = sum(info["row_count"] for info in schema.values())
            col1, col2 = st.columns(2)
            with col1:
                st.metric("数据表", f"{len(schema)}张")
            with col2:
                st.metric("总记录", f"{total_rows:,}行")
            if effective_key:
                st.success("🟢 系统就绪")
            else:
                st.warning("🟡 等待 API Key")
        except Exception as e:
            st.error(f"数据库连接失败: {e}")
        
        st.divider()
        
        # 历史记录
        st.markdown("#### 📜 查询历史")
        if "history" in st.session_state and st.session_state.history:
            for i, h in enumerate(reversed(st.session_state.history[-6:])):
                with st.expander(f"{h['question'][:28]}...", expanded=False):
                    st.caption(f"⏱️ {h.get('elapsed_ms', '?')}ms | 📊 {h.get('rows', '?')}行")
                    if st.button(f"🔄 重新查询", key=f"replay_{i}"):
                        st.session_state.question_input = h["question"]
                        st.rerun()
        else:
            st.caption("暂无查询记录")
        
        st.divider()
        st.caption(f"© 2026 NL2SQL · 经营分析赛道")
    
    return model_option, effective_key

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
        ("💰 总营收(2024)", f"¥{kpis.get('total_revenue_2024', 0):,.0f}", False),
        ("📈 毛利率", f"{kpis.get('gross_margin_pct', 0):.1f}%", False),
        ("💵 预算执行率", f"{kpis.get('budget_execution_pct', 0):.1f}%", False),
        ("🧾 回款率", f"{kpis.get('collection_rate_pct', 0):.1f}%", False),
        ("⚠️ 逾期应收", f"¥{kpis.get('overdue_receivable', 0):,.0f}", True),
    ]
    
    for i, (label, value, warn) in enumerate(metrics):
        with cols[i]:
            cls = "kpi-card warn" if warn else "kpi-card"
            st.markdown(f"""
            <div class="{cls}">
                <div class="kpi-value">{value}</div>
                <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

# ===================== 主页面 =====================
def main():
    # 标题
    st.markdown("""
    <div class="main-header">
        <h1>🏢 企业财务智能问数与经营分析系统</h1>
        <p>基于大模型的 NL2SQL 财务助手 · 自然语言问数 · 秒级响应 · AI 自动解读</p>
    </div>
    """, unsafe_allow_html=True)

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
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            question = st.text_input(
                "问题",
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
                            st.session_state.question_input = q
                            st.rerun()
        
        # 随机示例按钮
        if btn_random:
            import random
            random_q = random.choice(SAMPLE_QUESTIONS)
            st.session_state.question_input = random_q
            st.rerun()
        
        # 处理查询
        if btn_search and question:
            process_query(question, model_option, api_key)
        elif question and "current_question" in st.session_state:
            process_query(st.session_state.current_question, model_option, api_key)
    
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
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            ### 🎯 系统简介
            基于**大语言模型**实现自然语言 → SQL → 数据 → 分析的全链路自动化。
            
            ### 💡 提问技巧
            | ✅ 好的提问 | ❌ 不好的提问 |
            |---|---|
            | 2024年Q2华东区毛利率 | 毛利率 |
            | 各产品线年度营收排名 | 看看数据 |
            | 预算执行率低于80%的部门 | 预算怎么样 |
            """)
        with c2:
            st.markdown("""
            ### 🔧 技术栈
            - **LLM**: DeepSeek-V3 / Qwen / GPT
            - **数据库**: SQLite (星型模型 6维+5事实)
            - **前端**: Streamlit + Plotly
            - **安全**: SQL校验 + 仅SELECT
            
            ### 📊 数据范围
            - 时间: 2022-2024 (3年)
            - 区域: 华东/华南/华北/西南
            - 产品: 12条产品线 · 50个客户
            - 规模: 59,720 条记录
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
        st.code(result["sql"], language="sql", line_numbers=False)
    
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
