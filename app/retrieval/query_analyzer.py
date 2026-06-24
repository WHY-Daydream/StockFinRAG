"""QueryAnalyzer — LLM-driven question type classifier for retrieval routing.

Classifies a user question into one of three types:
- "simple"   — concrete entity / metric / event / time point
- "abstract" — broad questions without a specific entity
- "complex"  — multi-dimensional questions with parallel entities

Uses DeepSeek (OpenAI-compatible API) as the judge LLM.
"""

import json
from typing import Dict

from openai import OpenAI
from loguru import logger

from config import Config

_JUDGE_PROMPT = """你是一个金融检索路由专家。请分析以下问题的类型，判断应该使用哪种检索策略。

策略定义：
1. simple — 简单具体：问题指向一个具体实体、指标、事件或时间点。
   例："2024年GDP是多少"、"反洗钱法的处罚标准是什么"
2. abstract — 抽象宽泛：使用"有哪些""什么是""如何"等泛问词，没有具体实体。
   例："金融合规包含哪些风险"、"如何进行风险管理"
3. complex — 复杂多维度：问题包含多个并列维度/实体，使用"和""与""以及"连接。
   例："GDP和利率对银行股的影响"、"量化宽松和加息政策哪个对市场影响大"

仅输出 JSON：
{{"type": "simple", "reason": "有具体实体GDP"}}

问题：{question}"""


class QueryAnalyzer:
    """Analyzes a user question and returns a classification dict."""

    def __init__(self):
        self._client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )
        self._model = Config.LLM_MODEL

    def analyze(self, question: str) -> Dict[str, str]:
        """Classify question into simple / abstract / complex.

        Args:
            question: The user's question text.

        Returns:
            Dict with keys "type" (str) and "reason" (str).
            On failure returns {"type": "simple", "reason": "fallback"}.
        """
        prompt = _JUDGE_PROMPT.format(question=question)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            result = json.loads(content)
            qtype = result.get("type", "simple")
            reason = result.get("reason", "")
            # Validate type
            if qtype not in ("simple", "abstract", "complex"):
                logger.warning("Unexpected type '{}' from LLM, falling back", qtype)
                return {"type": "simple", "reason": "unexpected_type_fallback"}
            return {"type": qtype, "reason": reason}
        except Exception as exc:
            logger.error("QueryAnalyzer fallback due to: {}", exc)
            return {"type": "simple", "reason": "fallback"}