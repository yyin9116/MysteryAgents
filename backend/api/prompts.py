"""
API endpoints for prompt template management (提示词管理).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import prompt_registry
from services.llm_service import LLMService
from services.model_config_service import ModelConfigNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="模板全文，使用 {variable} 占位符")


class PromptTestRunRequest(BaseModel):
    llm_config: Optional[Dict[str, Any]] = Field(
        None, description="模型配置 dict（与创建对局接口的 llm_config 同形状；缺省用默认模型）"
    )
    sample_vars: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7
    max_tokens: int = 8000


@router.get("")
def list_prompts():
    """列出全部提示词模板及状态。"""
    return prompt_registry.list_templates()


@router.get("/{key}")
def get_prompt(key: str):
    """读取单个模板详情（当前生效内容 + 元信息）。"""
    try:
        meta = prompt_registry.get_meta(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown prompt template: {key}")

    custom = prompt_registry.get_custom_text(key)
    content = custom if custom is not None else prompt_registry.DEFAULT_TEMPLATES[key]
    return {
        "key": key,
        "name": meta["name"],
        "group": meta["group"],
        "description": meta["description"],
        "content": content,
        "default_content": prompt_registry.DEFAULT_TEMPLATES[key],
        "source": "custom" if custom is not None else "default",
        "variables": prompt_registry.extract_variables(content),
        "sample_vars": meta["sample_vars"],
        "tokens": prompt_registry.estimate_tokens(content),
        "lines": content.count("\n") + 1,
    }


@router.put("/{key}")
def update_prompt(key: str, payload: PromptUpdateRequest):
    """保存自定义模板（写入 prompts.yaml，先做渲染校验）。"""
    try:
        result = prompt_registry.save_template(key, payload.content)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown prompt template: {key}")

    if not result.get("saved"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "模板校验失败：请检查占位符拼写（如 {agent_name}）",
                "missing_vars": result.get("missing_vars", []),
                "unused_vars": result.get("unused_vars", []),
                "error": result.get("error"),
            },
        )
    return {"key": key, "saved": True, "source": "custom", **result}


@router.post("/{key}/reset")
def reset_prompt(key: str):
    """移除自定义模板，恢复内置默认。"""
    try:
        prompt_registry.get_meta(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown prompt template: {key}")
    removed = prompt_registry.reset_template(key)
    return {"key": key, "reset": True, "had_custom": removed, "source": "default"}


@router.post("/{key}/test-run")
async def test_run_prompt(key: str, payload: PromptTestRunRequest):
    """用样例变量渲染模板并真实调用一次模型，返回原始输出。"""
    try:
        meta = prompt_registry.get_meta(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown prompt template: {key}")

    variables = dict(meta["sample_vars"])
    for var_key, value in (payload.sample_vars or {}).items():
        if value is not None and str(value).strip() != "":
            variables[var_key] = value

    try:
        rendered = prompt_registry.render(key, variables)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"模板渲染失败：{exc}")

    model_config = payload.llm_config

    llm = LLMService()
    try:
        output = await llm.generate(
            prompt=rendered,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            model_config=model_config,
            json_mode=False,
        )
    except Exception as exc:
        logger.warning("Prompt test-run failed for %s: %s", key, exc)
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}")

    return {
        "key": key,
        "rendered_prompt": rendered,
        "variables_used": variables,
        "output": output,
    }
