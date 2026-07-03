# 🏢 NL2SQL 财务智能问数与经营分析系统

> **基于大模型的企业财务智能问数助手**  
> 赛道：经营分析 | AI工具：DeepSeek-V3 / Qwen-Max / GPT-4o

---

## 🎯 一句话简介

让企业管理层像聊天一样查询经营数据——自然语言输入，秒级返回数据+图表+AI分析解读。把传统1-3天的取数流程缩短到3秒。

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd AI

# 安装依赖
pip install -r requirements.txt
```

### 2. 创建虚拟环境 & 安装依赖

```bash
cd AI
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 3. 生成模拟数据

```bash
python data/generate_data.py
```

生成后会在 `data/` 目录下创建 `finance.db`（约10万+行财务数据）。

### 4. 配置 API Key

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "your_deepseek_api_key"

# 或使用千问
$env:DASHSCOPE_API_KEY = "your_qwen_api_key"

# 或使用 OpenAI
$env:OPENAI_API_KEY = "your_openai_api_key"
```

> 💡 DeepSeek API Key 获取: https://platform.deepseek.com  
> 💡 千问 API Key 获取: https://dashscope.aliyun.com

### 5. 启动系统

```bash
streamlit run app/streamlit_app.py
```

浏览器访问 `http://localhost:8501` 即可使用。

### 6. 运行测试

```bash
python tests/test_queries.py
```

---

## 📂 项目结构

```
AI/
├── data/
│   ├── schema.sql              # 数据库建表脚本（12张表）
│   ├── generate_data.py        # 模拟数据生成（3年，10万+行）
│   └── finance.db              # SQLite数据库（运行后生成）
├── src/
│   ├── __init__.py             # 包初始化
│   ├── db_manager.py           # 数据库管理器
│   ├── nl2sql_engine.py        # NL2SQL核心引擎
│   ├── prompt_templates.py     # Prompt模板（5层注入）
│   ├── sql_validator.py        # SQL安全校验与纠错
│   └── analysis_agent.py       # AI经营分析解读
├── app/
│   └── streamlit_app.py        # Streamlit前端主程序
├── tests/
│   └── test_queries.py         # 测试用例集（20+测试）
├── docs/
│   ├── requirements.md         # 需求分析文档
│   ├── system_design.md        # 系统设计文档
│   ├── ppt_outline.md          # PPT展示大纲（18页详细内容）
│   ├── defense_qa.md           # 答辩三问 + 追问预案
│   └── prompts.md              # Prompt工程文档
├── requirements.txt
└── README.md
```

---

## 🧠 核心技术

### NL2SQL 引擎 — 五层Prompt注入策略

```
Layer 1: 系统角色 → "资深财务数据分析师"
Layer 2: Schema注入 → 12张表完整结构
Layer 3: 业务规则 → 毛利率/同比环比等12条规则
Layer 4: Few-shot  → 7个典型问数示例
Layer 5: 用户问题 → 自然语言输入
        ↓
    大模型 → SQL → 校验 → 执行 → AI解读
```

### SQL 安全校验流水线

```
语法校验 → 权限检查(仅SELECT) → 表名/字段名校验 → 执行验证
失败时自动反馈LLM重试（最多3次）
```

---

## 📊 数据模型（星型模式）

```
维度表(6):  dim_date | dim_product | dim_department | dim_region | dim_customer | dim_supplier
事实表(5):  fact_sales | fact_cost | fact_expense | fact_receivable | fact_payable

时间范围: 2022-2024（3年）
数据规模: 10万+行
```

---

## 💬 典型问数场景

| 类型 | 示例问题 |
|------|----------|
| 聚合查询 | "2024年总营收是多少？" |
| 多维分析 | "华东区各产品线的毛利率排名" |
| 同比对比 | "Q2毛利率同比变化了多少？" |
| 预算管控 | "哪些部门预算执行率低于80%？" |
| 客户分析 | "销售收入最高的5个客户是谁？" |
| 风险预警 | "逾期超过30天的应收账款有哪些？" |
| 费用结构 | "销售费用中占比最大的类型是什么？" |

---

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Streamlit + Plotly | 快速原型、交互图表 |
| LLM | DeepSeek-V3 / Qwen-Max / GPT-4o | 多模型可替换 |
| 框架 | LangChain + OpenAI SDK | 统一API调用 |
| 数据库 | SQLite | 零配置、轻量级 |
| 安全 | sqlparse + 自定义校验器 | SQL语法+权限+字段校验 |

---

## 🎓 答辩三问速答

| 问题 | 核心答案 |
|------|----------|
| ① 解决什么问题？ | 管理层"看数难"——传统问数需1-3天，依赖BI团队，沟通成本高 |
| ② AI扮演什么角色？ | 财务翻译官——自然语言→SQL→分析解读，非AI不可因为自然语言有无限多样性 |
| ③ 业务价值？ | 效率提升99%+，SQL准确率88%，年节省人力成本约21万，风险发现从"事后"变"事中" |

> 详细答辩材料见 `docs/` 目录

---

## 📝 License

MIT License — 仅供学习和竞赛使用

---

## 👥 团队

- 赛道方向：经营分析
- AI工具：DeepSeek-V3 / LangChain / Streamlit
- 完成时间：2026年7月
