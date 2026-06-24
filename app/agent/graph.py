from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from openai import OpenAI
import json
import time
from loguru import logger
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from retrieval.hybrid_searcher import HybridSearcher
from retrieval.cache import ResultCache


class AgentState(TypedDict):
    question: str
    session_id: str
    retrieved_context: list
    analysis_result: str
    final_answer: str
    compliance_check: str
    compliance_reason: str
    start_time: float  # 用于计算 latency_ms


def retrieval_node(state: AgentState) -> dict:
    """检索 Agent: 混合检索或缓存命中"""
    cache = ResultCache()
    cached = cache.get(state["question"])
    if cached:
        logger.info(f"Cache hit: {state['question'][:50]}...")
        return {"retrieved_context": cached}

    searcher = HybridSearcher()
    results = searcher.search(state["question"], top_k=10)
    cache.set(state["question"], results)
    return {"retrieved_context": results}


def analysis_node(state: AgentState) -> dict:
    """分析 Agent: 基于检索结果生成回答"""
    context = state["retrieved_context"]
    if not context:
        logger.warning(f"No context retrieved for question: {state['question'][:50]}")
        return {
            "analysis_result": "⚠️ 未检索到与问题相关的金融资料。请尝试重新表述问题，或补充相关数据后再查询。",
        }
    context_text = "\n---\n".join(
        [f"[{c['type']} | score={c.get('rerank_score', c['score']):.4f}]\n{c['content']}"
         for c in context]
    )
    client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL)
    prompt = f"""你是一位专业的金融分析师助手。请基于以下检索到的金融资料，回答用户的问题。

## 检索到的上下文
{context_text}

## 用户问题
{state['question']}

## 要求
1. 优先使用上下文中的信息回答，如信息不足请明确说明
2. 回答必须基于事实，不得编造数据
3. 对于财务数据，需要注明来源和时间
4. 使用简洁清晰的语言
"""
    try:
        resp = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return {"analysis_result": resp.choices[0].message.content}
    except Exception as e:
        logger.error(f"Analysis API call failed: {e}")
        return {
            "analysis_result": f"⚠️ 分析服务暂时不可用，无法生成回答。错误: {str(e)}",
        }


def compliance_node(state: AgentState) -> dict:
    """合规 Agent: 检查回答是否符合金融合规要求"""
    client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL)
    check_prompt = f"""你是一位金融合规审核官。请审核以下分析师回答是否存在合规风险：

## 用户问题
{state['question']}

## 分析师回答
{state['analysis_result']}

## 需要检查的风险项
1. 是否包含明确的投资建议（如"买入/卖出/持有"）
2. 是否对未来股价或收益率做出承诺性预测
3. 是否使用绝对化表述（如"必然"/"一定"）
4. 是否包含内幕信息或未公开数据
5. 是否包含歧视性或误导性内容

## 输出格式（必须是 JSON）
{{"decision": "pass" 或 "reject", "reason": "具体说明"}}
"""
    try:
        resp = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[{"role": "user", "content": check_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        result = json.loads(resp.choices[0].message.content)
        return {
            "compliance_check": result.get("decision", "reject"),
            "compliance_reason": result.get("reason", "合规审核解析失败"),
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.error(f"Compliance check failed: {e}")
        return {
            "compliance_check": "reject",
            "compliance_reason": f"合规审核异常: {str(e)}",
        }


def route_after_compliance(state: AgentState) -> Literal["reject_handler", "format_output"]:
    return "reject_handler" if state["compliance_check"] == "reject" else "format_output"


def reject_handler(state: AgentState) -> dict:
    return {
        "final_answer": (
            f"⚠️ 该回答因合规校验未通过，已拦截。\n\n"
            f"**原因**: {state.get('compliance_reason', '未通过合规审核')}\n\n"
            f"请重新表述问题，避免涉及具体的投资建议或预测性陈述。"
        ),
    }


def format_output(state: AgentState) -> dict:
    """仅输出最终回答（审计日志由服务层负责写入）"""
    return {"final_answer": state["analysis_result"]}


def build_qa_graph():
    builder = StateGraph(AgentState)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("compliance", compliance_node)
    builder.add_node("reject_handler", reject_handler)
    builder.add_node("format_output", format_output)

    builder.set_entry_point("retrieval")
    builder.add_edge("retrieval", "analysis")
    builder.add_edge("analysis", "compliance")
    builder.add_conditional_edges("compliance", route_after_compliance)
    builder.add_edge("format_output", END)
    builder.add_edge("reject_handler", END)

    return builder.compile(checkpointer=MemorySaver())


_qa_graph = None

def get_qa_graph():
    global _qa_graph
    if _qa_graph is None:
        _qa_graph = build_qa_graph()
    return _qa_graph
