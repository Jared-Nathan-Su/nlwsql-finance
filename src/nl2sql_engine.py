"""
NL2SQL 核心引擎
- 调用大模型API生成SQL
- SQL校验与自动纠错
- 结果分析与解读
"""
import os
import re
import time
from typing import Tuple, Optional, Dict
import pandas as pd

# 尝试导入 openai（兼容多种大模型API）
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from .sql_validator import full_validate, clean_sql
from .prompt_templates import (
    build_nl2sql_prompt,
    build_analysis_prompt
)
from .db_manager import get_db


class NL2SQLEngine:
    """NL2SQL 核心引擎"""
    
    # 支持的模型配置
    MODEL_CONFIGS = {
        "deepseek": {
            "name": "DeepSeek-V4",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        "qwen": {
            "name": "通义千问 Qwen-Max",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-max",
            "api_key_env": "DASHSCOPE_API_KEY",
        },
        "openai": {
            "name": "GPT-4o",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
        },
    }
    
    def __init__(
        self,
        model_provider: str = "deepseek",
        api_key: str = None,
        max_retries: int = 3,
        db_path: str = None
    ):
        """
        初始化NL2SQL引擎
        
        Args:
            model_provider: 模型提供商 (deepseek/qwen/openai)
            api_key: API密钥，不传则从环境变量读取
            max_retries: SQL纠错最大重试次数
            db_path: 数据库路径
        """
        self.model_provider = model_provider
        self.max_retries = max_retries
        self.db = get_db(db_path)
        
        # 配置模型
        if model_provider not in self.MODEL_CONFIGS:
            raise ValueError(f"不支持的模型提供商: {model_provider}。可选: {list(self.MODEL_CONFIGS.keys())}")
        
        config = self.MODEL_CONFIGS[model_provider]
        self.model_name = config["name"]
        
        # 获取API Key
        if api_key is None:
            api_key = os.environ.get(config["api_key_env"], "")
        
        if not api_key and HAS_OPENAI:
            raise ValueError(
                f"未设置API Key！请设置环境变量 {config['api_key_env']} "
                f"或在初始化时传入 api_key 参数"
            )
        
        # 初始化OpenAI客户端
        if HAS_OPENAI:
            self.client = OpenAI(
                api_key=api_key,
                base_url=config["base_url"]
            )
            self.model = config["model"]
        else:
            self.client = None
            print("⚠️ 未安装 openai 库，请运行: pip install openai")
        
        self.query_history = []  # 查询历史
    
    def _call_llm(self, prompt: str, temperature: float = 0.1) -> str:
        """
        调用大模型API
        
        Args:
            prompt: 完整的提示词
            temperature: 温度参数（SQL生成用低温度保证一致性）
        
        Returns:
            模型返回的文本
        """
        if self.client is None:
            return "ERROR: OpenAI客户端未初始化"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=1024,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"ERROR: API调用失败 - {str(e)}"
    
    def generate_sql(self, question: str) -> Tuple[bool, str, str]:
        """
        自然语言 → SQL
        
        Args:
            question: 用户自然语言问题
        
        Returns:
            (是否成功, SQL语句, 错误信息)
        """
        # Step 1: 构建Prompt并调用LLM
        prompt = build_nl2sql_prompt(question)
        raw_response = self._call_llm(prompt, temperature=0.1)
        
        if raw_response.startswith("ERROR:"):
            return False, "", raw_response
        
        if "UNABLE_TO_ANSWER" in raw_response:
            return False, "", "抱歉，我无法理解这个问题，请尝试换一种问法。"
        
        # Step 2: 清理SQL
        sql = clean_sql(raw_response)
        
        # Step 3: 校验SQL
        valid, error, cleaned_sql = full_validate(sql)
        
        # Step 4: 校验失败则进入重试循环（反馈错误给LLM）
        retry_count = 0
        while not valid and retry_count < self.max_retries:
            retry_count += 1
            retry_prompt = f"""{prompt}

## ⚠️ 上次生成的SQL有错误：
{raw_response}

## 错误信息：
{error}

请修正SQL并重新生成。确保：
1. 只使用上述Schema中定义的表名和字段名
2. 只生成SELECT语句
3. SQL语法正确，可直接执行

请生成修正后的SQL："""
            
            raw_response = self._call_llm(retry_prompt, temperature=0.1)
            if raw_response.startswith("ERROR:"):
                return False, "", raw_response
            
            sql = clean_sql(raw_response)
            valid, error, cleaned_sql = full_validate(sql)
        
        if not valid:
            return False, "", f"SQL校验失败（已重试{self.max_retries}次）: {error}"
        
        return True, cleaned_sql, ""
    
    def execute_question(self, question: str) -> Dict:
        """
        完整问数流程：NL → SQL → 执行 → 返回结果
        
        Args:
            question: 用户自然语言问题
        
        Returns:
            包含完整信息的字典
        """
        start_time = time.time()
        result = {
            "question": question,
            "success": False,
            "sql": "",
            "data": None,
            "analysis": "",
            "error": "",
            "elapsed_ms": 0,
        }
        
        # Step 1: 生成SQL
        ok, sql, error = self.generate_sql(question)
        result["sql"] = sql
        
        if not ok:
            result["error"] = error
            result["elapsed_ms"] = int((time.time() - start_time) * 1000)
            return result
        
        # Step 2: 执行SQL
        ok, df, error = self.db.execute_query(sql)
        
        if not ok:
            # SQL执行失败，尝试反馈给LLM修正
            retry_prompt = f"""{build_nl2sql_prompt(question)}

## ⚠️ 上次生成的SQL执行失败：
{sql}

## 数据库错误信息：
{error}

请分析错误原因，修正SQL后重新生成。确保字段名、表名、JOIN条件都正确。

请生成修正后的SQL："""
            
            for retry in range(self.max_retries):
                raw_response = self._call_llm(retry_prompt, temperature=0.1)
                sql = clean_sql(raw_response)
                valid, v_error, sql = full_validate(sql)
                if not valid:
                    continue
                ok, df, error = self.db.execute_query(sql)
                if ok:
                    result["sql"] = sql
                    break
            
            if not ok:
                result["error"] = f"SQL执行失败（已重试{self.max_retries}次）: {error}"
                result["elapsed_ms"] = int((time.time() - start_time) * 1000)
                return result
        
        result["success"] = True
        result["data"] = df
        
        # Step 3: AI分析解读
        if len(df) > 0:
            analysis = self.analyze_result(question, sql, df)
            result["analysis"] = analysis
        else:
            result["analysis"] = "查询结果为空，请尝试调整查询条件。"
        
        result["elapsed_ms"] = int((time.time() - start_time) * 1000)
        
        # 记录历史
        self.query_history.append({
            "question": question,
            "sql": result["sql"],
            "success": result["success"],
            "rows": len(df) if df is not None else 0,
            "elapsed_ms": result["elapsed_ms"],
        })
        
        return result
    
    def analyze_result(self, question: str, sql: str, df: pd.DataFrame) -> str:
        """
        对查询结果进行AI分析解读
        """
        # 格式化结果为文本
        if len(df) > 20:
            result_text = df.head(20).to_string(index=False)
            result_text += f"\n\n... (共{len(df)}行，仅显示前20行)"
        else:
            result_text = df.to_string(index=False)
        
        # 截断过长结果（给分析留足够token）
        if len(result_text) > 1500:
            result_text = result_text[:1500] + "\n... (结果已截断)"
        
        prompt = build_analysis_prompt(question, sql, result_text)
        analysis = self._call_llm(prompt, temperature=0.5)
        
        # 清理 markdown 代码块标记
        if analysis and not analysis.startswith("ERROR:"):
            analysis = analysis.replace("```markdown", "").replace("```", "").strip()
        
        # 如果分析为空或失败，返回简单摘要
        if not analysis or analysis.startswith("ERROR:"):
            analysis = f"查询完成，共返回 {len(df)} 条记录。"
        
        return analysis
    
    def get_history(self) -> list:
        """获取查询历史"""
        return self.query_history
    
    def clear_history(self):
        """清空查询历史"""
        self.query_history = []


# ============================================================
# 工厂函数
# ============================================================
def create_engine(
    model_provider: str = "deepseek",
    api_key: str = None,
    db_path: str = None
) -> NL2SQLEngine:
    """
    创建NL2SQL引擎实例
    
    Args:
        model_provider: deepseek / qwen / openai
        api_key: API密钥
        db_path: 数据库路径
    
    Returns:
        NL2SQLEngine实例
    """
    return NL2SQLEngine(
        model_provider=model_provider,
        api_key=api_key,
        db_path=db_path
    )


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 NL2SQL 引擎测试")
    print("=" * 60)
    
    # 此测试需要有API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("⚠️ 请设置 DEEPSEEK_API_KEY 环境变量后运行测试")
        print("   export DEEPSEEK_API_KEY=your_key_here")
        exit(0)
    
    engine = NL2SQLEngine(model_provider="deepseek", api_key=api_key)
    
    test_questions = [
        "2024年总营收是多少？",
        "华东区各产品线的毛利率排名",
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"❓ 问题: {q}")
        result = engine.execute_question(q)
        
        print(f"📝 SQL: {result['sql'][:200]}...")
        print(f"⏱️ 耗时: {result['elapsed_ms']}ms")
        
        if result["success"]:
            print(f"📊 结果 ({len(result['data'])}行):")
            print(result["data"].to_string(index=False))
            print(f"\n🤖 AI分析: {result['analysis'][:300]}")
        else:
            print(f"❌ 错误: {result['error']}")
