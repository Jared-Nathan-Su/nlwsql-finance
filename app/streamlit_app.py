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
                "deepseek": "DeepSeek-V4 (推荐)",
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
        
        # ---- 数据源选择（支持多文件上传） ----
        st.markdown("### � 数据源")
        data_mode = st.radio("选择数据", ["�📊 演示数据（财务）", "📂 上传自定义数据"], 
                            index=0 if not st.session_state.get("use_custom_data", False) else 1)
        
        if "上传" in data_mode:
            uploaded_files = st.file_uploader("上传 CSV / Excel（可多选）", type=["csv","xlsx","xls"],
                                              accept_multiple_files=True,
                                              help="支持同时上传多个文件，系统自动建表并支持跨表查询")
            
            if uploaded_files:
                db = init_db()
                all_schemas = []
                all_tables = []
                for uf in uploaded_files:
                    try:
                        table_name = os.path.splitext(uf.name)[0].replace(" ", "_").replace("-", "_")
                        if uf.name.endswith('.csv'):
                            df = pd.read_csv(uf)
                        else:
                            df = pd.read_excel(uf)
                        db.import_dataframe(df, table_name)
                        schema_text = db.get_table_schema_text(table_name)
                        all_schemas.append(schema_text)
                        all_tables.append(table_name)
                        st.caption(f"✅ {uf.name} → `{table_name}` ({len(df)}行)")
                    except Exception as e:
                        st.error(f"❌ {uf.name}: {e}")
                
                if all_tables:
                    st.session_state.use_custom_data = True
                    st.session_state.custom_tables = all_tables
                    st.session_state.custom_schemas = all_schemas
                    st.session_state.custom_df = db.get_table_preview(all_tables[0], 10)
                    
                    with st.expander("📋 数据预览 & Schema"):
                        for t in all_tables:
                            st.caption(f"**{t}**")
                            st.dataframe(db.get_table_preview(t, 5), use_container_width=True)
                    
                    if st.button("🔄 恢复演示数据", use_container_width=True):
                        st.session_state.use_custom_data = False
                        st.session_state.custom_tables = []
                        st.rerun()
        else:
            st.session_state.use_custom_data = False
            st.session_state.custom_tables = []
        
        st.divider()
        
        # 系统状态（根据数据模式显示准确统计）
        st.markdown("### 系统状态")
        try:
            db = init_db()
            schema = db.get_schema_info()
            use_custom_now = st.session_state.get("use_custom_data", False)
            custom_tbls = st.session_state.get("custom_tables", [])
            
            if use_custom_now and custom_tbls:
                # 只统计上传的表
                custom_rows = sum(schema.get(t, {}).get("row_count", 0) for t in custom_tbls)
                col1, col2 = st.columns(2)
                col1.metric("数据表", f"{len(custom_tbls)}张")
                col2.metric("总记录", f"{custom_rows:,}")
                for t in custom_tbls:
                    info = schema.get(t, {})
                    cols = len(info.get("columns", []))
                    rows = info.get("row_count", 0)
                    st.caption(f"`{t}` — {cols}列 × {rows:,}行")
            else:
                # 演示数据：仅统计 dim_ 和 fact_ 开头的表
                demo_tables = [t for t in schema if t.startswith("dim_") or t.startswith("fact_")]
                demo_rows = sum(schema[t]["row_count"] for t in demo_tables)
                col1, col2 = st.columns(2)
                col1.metric("数据表", f"{len(demo_tables)}张")
                col2.metric("总记录", f"{demo_rows:,}")
            
            if api_key or env_key:
                st.success("API Key 已配置")
            else:
                st.warning("请配置 API Key")
        except Exception as e:
            st.error(f"数据库异常: {e}")
        
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
    use_custom = st.session_state.get("use_custom_data", False)
    custom_tables = st.session_state.get("custom_tables", [])
    
    if use_custom and custom_tables:
        db = init_db()
        total_rows = sum(db.get_schema_info().get(t, {}).get("row_count", 0) for t in custom_tables)
        st.info(f"已加载 {len(custom_tables)} 个数据表 | {total_rows} 行 | 表: {', '.join(custom_tables)}")
    
    tab1, tab2, tab3 = st.tabs(["智能问数", "经营看板", "使用帮助"])
    
    # ==================== Tab1: 智能问数 ====================
    with tab1:
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            question = st.text_input(
                "问题",
                placeholder="请输入您的财务问题，例如：华东区Q2毛利率同比变化？",
                key="question_input",
                label_visibility="collapsed",
            )
        with col2:
            btn_search = st.button("🚀 查询分析", type="primary", width='stretch', key="btn_search")
        with col3:
            btn_random = st.button("🎲 随机示例", width='stretch', key="btn_random")
        
        # 快捷问题分类（根据数据源动态变化）
        st.caption("快捷问题:")
        quick_cols = st.columns(5)
        
        if use_custom and custom_tables:
            db_q = init_db()
            quick_categories = {}
            for t in custom_tables[:5]:
                preview = db_q.get_table_preview(t, 200)
                num_cols = preview.select_dtypes(include=["number"]).columns.tolist()
                cat_cols = preview.select_dtypes(include=["object","string"]).columns.tolist()
                date_cols = [c for c in preview.columns if "date" in c.lower() or "日期" in c or "时间" in c]
                questions = [f"{t} 表共有多少条记录？"]
                if num_cols:
                    questions.append(f"{num_cols[0]} 的平均值和总和是多少？")
                    questions.append(f"{num_cols[0]} 最高的前5条记录")
                if cat_cols and num_cols:
                    questions.append(f"按 {cat_cols[0]} 分组统计 {num_cols[0]} 的合计")
                if date_cols and num_cols:
                    questions.append(f"按 {date_cols[0]} 查看 {num_cols[0]} 的变化趋势")
                quick_categories[f"📋 {t}"] = questions[:3]
            if not quick_categories:
                quick_categories = {"📊 数据查询": ["查看所有记录", "统计总行数"]}
        else:
            quick_categories = {
                "营收相关": ["2024年各区域营收排名", "近三年各季度营收趋势", "2024年月度营收变化"],
                "毛利分析": ["各产品线毛利率排名", "华东区Q2毛利率是多少", "毛利率低于20%的产品"],
                "费用管控": ["预算执行率低于80%的部门", "销售费用占比最大的类型", "费用连续上升的部门"],
                "客户应收": ["营收最高的5个客户", "逾期应收款最多的客户", "回款率最低的客户"],
                "风险预警": ["逾期超过30天的应收", "毛利率下降的产品线", "净利率同比变化"],
            }
        
        for i, (cat, questions_list) in enumerate(quick_categories.items()):
            with quick_cols[i]:
                if not st.session_state.get("quick_dismissed", False):
                    with st.popover(cat, width='stretch'):
                        for j, q in enumerate(questions_list):
                            if st.button(q, key=f"quick_{i}_{j}", width='stretch'):
                                st.session_state.auto_query = q
                                st.session_state.quick_dismissed = True
                                st.rerun()
                else:
                    # 可点击的占位按钮（点击恢复 popover）
                    if st.button(f"{cat} ✓", key=f"quick_done_{i}", width='stretch'):
                        st.session_state.quick_dismissed = False
                        st.rerun()
        
        # 随机示例按钮
        if btn_random:
            import random
            st.session_state.auto_query = random.choice(SAMPLE_QUESTIONS)
            st.session_state.quick_dismissed = True
            st.rerun()
        
        # 处理查询
        auto_q = st.session_state.get("auto_query", "")
        if auto_q:
            st.session_state.auto_query = ""
            process_query(auto_q, model_option, api_key)
            st.session_state.quick_dismissed = False  # 查询完成后恢复
        elif btn_search and question:
            process_query(question, model_option, api_key)
    
    # ==================== Tab2: 经营看板 ====================
    with tab2:
        if use_custom and custom_tables:
            # 自定义数据深度看板
            st.markdown("### 数据深度分析")
            db_t2 = init_db()
            
            for t in custom_tables:
                st.markdown(f"#### 📋 {t}")
                preview = db_t2.get_table_preview(t, 500)
                info = db_t2.get_schema_info().get(t, {})
                cols_info = info.get("columns", [])
                num_cols = preview.select_dtypes(include=["number"]).columns.tolist()
                cat_cols = preview.select_dtypes(include=["object","string"]).columns.tolist()
                
                # KPI行
                kpi_items = []
                kpi_items.append((f"{info.get('row_count',0):,}", "总行数"))
                kpi_items.append((str(len(cols_info)), "字段数"))
                if num_cols:
                    kpi_items.append((f"{preview[num_cols[0]].sum():,.0f}", f"{num_cols[0]} 合计"))
                if cat_cols:
                    kpi_items.append((str(preview[cat_cols[0]].nunique()), f"{cat_cols[0]} 去重数"))
                
                kpi_cols2 = st.columns(len(kpi_items))
                for idx, (v, l) in enumerate(kpi_items):
                    with kpi_cols2[idx]:
                        st.metric(l, v)
                
                # 图表
                chart_cols = st.columns(min(3, max(1, len(num_cols[:2]) + len(cat_cols[:1]))))
                ci = 0
                if cat_cols and num_cols and ci < len(chart_cols):
                    with chart_cols[ci]:
                        sql = f"SELECT {cat_cols[0]}, SUM({num_cols[0]}) AS total FROM '{t}' GROUP BY {cat_cols[0]} ORDER BY total DESC LIMIT 8"
                        try:
                            ok, df, _ = db_t2.execute_query(sql)
                            if ok and len(df) > 0: auto_chart(df)
                        except: pass
                    ci += 1
                if len(num_cols) >= 2 and ci < len(chart_cols):
                    with chart_cols[ci]:
                        try:
                            fig = px.scatter(preview.head(200), x=num_cols[0], y=num_cols[1], 
                                           title=f"{num_cols[0]} vs {num_cols[1]}", template="plotly_white")
                            fig.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20))
                            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                        except: pass
                    ci += 1
                if num_cols and ci < len(chart_cols):
                    with chart_cols[ci]:
                        try:
                            fig = px.histogram(preview.head(500), x=num_cols[0], title=f"{num_cols[0]} 分布",
                                             template="plotly_white", nbins=20)
                            fig.update_layout(height=300, margin=dict(l=20,r=20,t=30,b=20))
                            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                        except: pass
                    ci += 1
                
                st.divider()
        else:
            # 原有财务看板
            st.markdown("### 企业经营概览")
            try:
                render_kpi_cards(db)
            except Exception as e:
                st.warning(f"KPI加载失败: {e}")
            
            st.divider()
            if st.button("生成经营简报", type="primary"):
                with st.spinner("生成中..."):
                    agent = AnalysisAgent(db)
                    st.session_state.briefing = agent.generate_briefing()
            if "briefing" in st.session_state:
                st.code(st.session_state.briefing, language=None)
            
            chart_cols = st.columns(3)
            charts_quick = [
                ("区域营收", "SELECT r.region_group, ROUND(SUM(s.revenue),0) AS revenue FROM fact_sales s JOIN dim_region r ON s.region_id=r.region_id JOIN dim_date d ON s.date_id=d.date_id WHERE d.year=2024 GROUP BY r.region_group ORDER BY revenue DESC"),
                ("产品线毛利率", "SELECT p.product_line, ROUND((SUM(s.revenue)-SUM(c.cost_amount))/SUM(s.revenue)*100,2) AS margin FROM fact_sales s JOIN fact_cost c ON s.date_id=c.date_id AND s.product_id=c.product_id AND s.region_id=c.region_id JOIN dim_product p ON s.product_id=p.product_id JOIN dim_date d ON s.date_id=d.date_id WHERE d.year=2024 GROUP BY p.product_line ORDER BY margin DESC"),
                ("部门预算执行率", "SELECT dept.dept_name, ROUND(SUM(e.actual_amount)/SUM(e.budget_amount)*100,2) AS rate FROM fact_expense e JOIN dim_department dept ON e.dept_id=dept.dept_id JOIN dim_date d ON e.date_id=d.date_id WHERE d.year=2024 GROUP BY dept.dept_name ORDER BY rate DESC"),
            ]
            for i, (title, sql) in enumerate(charts_quick):
                with chart_cols[i]:
                    st.caption(title)
                    try:
                        ok, df, _ = db.execute_query(sql)
                        if ok and len(df) > 0:
                            auto_chart(df)
                    except Exception:
                        st.caption("加载失败")
    
    # ==================== Tab3: 使用帮助 ====================
    with tab3:
        if use_custom and custom_tables:
            # 自定义数据帮助
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 当前数据")
                db_h = init_db()
                for t in custom_tables:
                    info = db_h.get_schema_info().get(t, {})
                    cols = info.get("columns", [])
                    st.markdown(f"**{t}** ({info.get('row_count',0)}行)")
                    col_names = [c["name"] for c in cols[:10]]
                    st.code(", ".join(col_names), language=None)
                st.markdown("---")
                st.markdown("### 提问技巧")
                st.markdown("""
                用自然语言描述你想知道的信息，例如：
                - "共有多少条记录？"
                - "某列的平均值和总和"
                - "按某列分组统计"
                - "最高的前5条记录"
                """)
            with c2:
                st.markdown("### 功能说明")
                st.markdown("""
                - 支持自然语言和SQL两种问数方式
                - AI自动将问题转为SQL并执行
                - 查询结果自动可视化
                - 支持CSV/Excel多文件上传
                - 上传文件自动建表，可跨表查询
                
                ### 技术栈
                `LLM` DeepSeek-V4 / Qwen / GPT  
                `DB` SQLite 动态建表  
                `UI` Streamlit + Plotly
                """)
        else:
            # 演示数据帮助（原有内容）
            st.markdown("""
            ### 使用指南
            
            #### 系统简介
            本系统基于大模型实现自然语言到SQL的全链路自动化，让非技术人员也能通过日常语言自助查询财务经营数据。
            
            #### 如何提问？
            
            | 提问技巧 | 好的示例 | 不好的示例 |
            |---|---|---|
            | 明确时间范围 | 2024年Q2华东区毛利率 | 毛利率 |
            | 指明分析维度 | 各产品线年度营收排名 | 看看数据 |
            | 使用财务术语 | 应收账款周转天数 | 客户欠钱多久还 |
            | 具体指标 | 预算执行率低于80%的部门 | 预算怎么样 |
            
            #### 技术架构
            - NL2SQL引擎: LangChain + LLM (DeepSeek/Qwen/GPT)
            - 数据库: SQLite 星型模型 6维+5事实
            - 前端: Streamlit + Plotly
            - 数据: 3年模拟企业经营数据 (59,720行)
            
            #### 数据范围
            - 时间: 2022-2024 | 区域: 华东/华南/华北/西南
            - 产品: 12条产品线 | 部门: 8个 | 客户: 50个
            """)

# ===================== 查询处理 =====================
def process_query(question: str, model_option: str, api_key: str):
    """处理用户查询"""
    if not api_key:
        st.error("请先在侧边栏配置 API Key")
        return
    
    if not question.strip():
        st.warning("请输入您的问题")
        return
    
    # 初始化引擎
    engine = init_engine(api_key, model_option)
    if engine is None:
        st.error("引擎初始化失败，请检查 API Key 是否正确")
        return
    
    # 自定义数据模式：注入所有表的Schema + 注册表名白名单
    if st.session_state.get("use_custom_data", False) and st.session_state.get("custom_tables"):
        db_ctx = init_db()
        from src.sql_validator import add_allowed_tables, reset_allowed_tables
        reset_allowed_tables()
        add_allowed_tables(st.session_state.custom_tables)
        engine.custom_schema_context = db_ctx.generate_schema_context(st.session_state.custom_tables)
        engine.custom_table = st.session_state.custom_tables[0]
    else:
        from src.sql_validator import reset_allowed_tables
        reset_allowed_tables()
        engine.custom_schema_context = None
        engine.custom_table = None
    
    # 执行查询
    with st.spinner(f"AI 分析中... ({model_option})"):
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
    
    # 显示用户问题
    st.markdown("### 💬 您的问题")
    st.info(f"{question}")
    
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
        st.markdown(result["analysis"])
    
    st.divider()

# ===================== 启动 =====================
if __name__ == "__main__":
    main()
