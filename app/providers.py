import json
import os
from typing import Any


def enhance_result(task: str, result: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]]:
    provider = os.getenv("MODEL_PROVIDER", "mock").lower()
    if provider != "openai":
        return result, "mock", []
    api_key, model = os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return result, "mock-fallback", ["OpenAI 模式缺少 OPENAI_API_KEY 或 OPENAI_MODEL，已回退到确定性结果。"]
    try:
        from openai import OpenAI
        response = OpenAI(api_key=api_key).responses.create(
            model=model,
            store=False,
            instructions=(
                "You enhance a deterministic cross-border ecommerce analysis. "
                "Do not change numeric facts or approved safety boundaries. "
                "Return concise JSON with summary and actions."
            ),
            input=json.dumps({"task": task, "deterministic_result": result}, ensure_ascii=False),
            text={"format": {"type": "json_schema", "name": "agent_enhancement", "strict": True,
                "schema": {"type": "object", "properties": {
                    "summary": {"type": "string"},
                    "actions": {"type": "array", "items": {"type": "string"}}
                }, "required": ["summary", "actions"], "additionalProperties": False}}},
        )
        enhanced = dict(result)
        enhanced["ai_enhancement"] = json.loads(response.output_text)
        return enhanced, "openai", []
    except Exception as exc:
        return result, "mock-fallback", [f"模型增强失败，已回退：{type(exc).__name__}"]

