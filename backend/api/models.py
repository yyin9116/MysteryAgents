"""
Models API endpoints.

Handles LLM model listing and configuration.
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
logger = logging.getLogger(__name__)

from services.llm_service import LLMService

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    name: str
    provider: str
    description: str
    recommended_for: List[str] = []


class ModelListResponse(BaseModel):
    """Response with available models."""
    models: List[ModelInfo]
    providers: List[str]


# Predefined model catalog
MODEL_CATALOG = {
    # OpenAI Models
    "openai/gpt-4o": {
        "name": "GPT-4o",
        "provider": "OpenAI",
        "description": "最新的 GPT-4 优化模型，速度快，性能强",
        "recommended_for": ["High"]
    },
    "openai/gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "provider": "OpenAI",
        "description": "GPT-4 的快速版本，性价比高",
        "recommended_for": ["High", "Mid"]
    },
    "openai/gpt-4": {
        "name": "GPT-4",
        "provider": "OpenAI",
        "description": "强大的 GPT-4 模型",
        "recommended_for": ["High"]
    },
    "openai/gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "provider": "OpenAI",
        "description": "快速且经济的模型",
        "recommended_for": ["Mid", "Low"]
    },
    
    # Alibaba Qwen Models
    "alibaba/qwen-max": {
        "name": "通义千问 Max",
        "provider": "Alibaba",
        "description": "阿里云最强大的模型",
        "recommended_for": ["High"]
    },
    "alibaba/qwen-plus": {
        "name": "通义千问 Plus",
        "provider": "Alibaba",
        "description": "平衡性能和成本",
        "recommended_for": ["High", "Mid"]
    },
    "alibaba/qwen-turbo": {
        "name": "通义千问 Turbo",
        "provider": "Alibaba",
        "description": "快速响应，适合高频调用",
        "recommended_for": ["Mid", "Low"]
    },
    
    # Anthropic Claude Models
    "anthropic/claude-3-opus": {
        "name": "Claude 3 Opus",
        "provider": "Anthropic",
        "description": "Claude 最强大的模型",
        "recommended_for": ["High"]
    },
    "anthropic/claude-3-sonnet": {
        "name": "Claude 3 Sonnet",
        "provider": "Anthropic",
        "description": "平衡性能和速度",
        "recommended_for": ["High", "Mid"]
    },
    "anthropic/claude-3-haiku": {
        "name": "Claude 3 Haiku",
        "provider": "Anthropic",
        "description": "快速且经济",
        "recommended_for": ["Mid", "Low"]
    },
    
    # Ollama Local Models
    "ollama/llama3": {
        "name": "Llama 3",
        "provider": "Ollama",
        "description": "本地运行的开源模型",
        "recommended_for": ["Mid"]
    },
    "ollama/mistral": {
        "name": "Mistral",
        "provider": "Ollama",
        "description": "高效的本地模型",
        "recommended_for": ["Mid", "Low"]
    },
    "ollama/qwen2": {
        "name": "Qwen 2",
        "provider": "Ollama",
        "description": "本地运行的千问模型",
        "recommended_for": ["Mid"]
    }
}


_llm_service: Optional[LLMService] = None


def _get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


@router.get("/list", response_model=ModelListResponse)
async def list_models(provider: str = None, iq_level: str = None):
    """
    Get list of available models.
    
    Args:
        provider: Filter by provider (OpenAI, Alibaba, Anthropic, Ollama)
        iq_level: Filter by recommended IQ level (High, Mid, Low)
        
    Returns:
        List of available models with metadata
    """
    try:
        models = []
        providers_set = set()
        
        for model_id, info in MODEL_CATALOG.items():
            # Apply filters
            if provider and info["provider"] != provider:
                continue
            
            if iq_level and iq_level not in info["recommended_for"]:
                continue
            
            models.append(ModelInfo(
                id=model_id,
                name=info["name"],
                provider=info["provider"],
                description=info["description"],
                recommended_for=info["recommended_for"]
            ))
            
            providers_set.add(info["provider"])
        
        return ModelListResponse(
            models=models,
            providers=sorted(list(providers_set))
        )
        
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def list_providers():
    """
    Get list of available providers.
    
    Returns:
        List of provider names
    """
    providers = set()
    for info in MODEL_CATALOG.values():
        providers.add(info["provider"])
    
    return {
        "providers": sorted(list(providers))
    }


@router.post("/health-check")
async def check_model_health(model_id: str):
    """
    Check if a specific model is accessible.
    
    Args:
        model_id: Model identifier (e.g., "openai/gpt-4o")
        
    Returns:
        Health status of the model
    """
    try:
        # Simple health check - just verify model exists in catalog
        if model_id in MODEL_CATALOG:
            return {
                "model": model_id,
                "status": "healthy",
                "provider": MODEL_CATALOG[model_id]["provider"]
            }
        else:
            return {
                "model": model_id,
                "status": "unknown",
                "error": "Model not found in catalog"
            }
    except Exception as e:
        logger.error(f"Health check failed for {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_model_recommendations():
    """
    Get recommended models for each IQ level.
    
    Returns:
        Recommended models grouped by IQ level
    """
    recommendations = {
        "High": [],
        "Mid": [],
        "Low": []
    }
    
    for model_id, info in MODEL_CATALOG.items():
        for iq_level in info["recommended_for"]:
            recommendations[iq_level].append({
                "id": model_id,
                "name": info["name"],
                "provider": info["provider"],
                "description": info["description"]
            })
    
    return recommendations


class ListModelsWithKeyRequest(BaseModel):
    """Request to list models with API key."""
    provider: str
    api_key: str


class TestApiKeyRequest(BaseModel):
    """Request to test API key validity."""
    provider: str
    api_key: str


class TestModelRequest(BaseModel):
    """Request to test if a specific model is available."""
    model_id: str
    api_key: Optional[str] = None


@router.post("/list-with-key", response_model=ModelListResponse)
async def list_models_with_key(request: ListModelsWithKeyRequest):
    """
    Get list of available models by actually querying the provider API with the given key.
    
    This endpoint actually calls the provider's API to get real available models,
    rather than returning mock data.
    
    Args:
        request: Provider name and API key
        
    Returns:
        List of actually available models from the provider
    """
    try:
        provider = request.provider.lower()
        api_key = request.api_key.strip()
        
        if not api_key:
            return ModelListResponse(models=[], providers=[])
        
        models = []
        
        if provider == "openai":
            # Query OpenAI API for available models
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # Filter for GPT chat models
                        chat_models = [
                            m for m in data.get("data", [])
                            if "gpt" in m.get("id", "").lower() and ("chat" in m.get("id", "").lower() or "gpt-4" in m.get("id", "").lower() or "gpt-3.5" in m.get("id", "").lower())
                        ]
                        # Remove duplicates and sort
                        seen_ids = set()
                        for model in chat_models:
                            model_id = model.get("id", "")
                            if model_id in seen_ids:
                                continue
                            seen_ids.add(model_id)
                            
                            # Map to our format
                            if "gpt-4o" in model_id.lower():
                                iq_levels = ["High"]
                                name = "GPT-4o"
                            elif "gpt-4-turbo" in model_id.lower() or "gpt-4-1106" in model_id.lower():
                                iq_levels = ["High", "Mid"]
                                name = "GPT-4 Turbo"
                            elif "gpt-4" in model_id.lower():
                                iq_levels = ["High"]
                                name = "GPT-4"
                            elif "gpt-3.5-turbo" in model_id.lower():
                                iq_levels = ["Mid", "Low"]
                                name = "GPT-3.5 Turbo"
                            else:
                                iq_levels = ["High"]
                                name = model_id.replace("gpt-", "GPT-").replace("-", " ").title()
                            
                            models.append(ModelInfo(
                                id=f"openai/{model_id}",
                                name=name,
                                provider="OpenAI",
                                description=f"OpenAI {model_id}",
                                recommended_for=iq_levels
                            ))
                    else:
                        logger.warning(f"OpenAI API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Failed to query OpenAI API: {e}")
                
        elif provider == "alibaba":
            # Query Alibaba DashScope API for available models (compatible with OpenAI format)
            try:
                import httpx
                from config.settings import settings
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{settings.ALIBABA_BASE_URL}/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # Filter for Qwen chat models (exclude specialized models like TTS, ASR, OCR, etc.)
                        chat_models = [
                            m for m in data.get("data", [])
                            if "qwen" in m.get("id", "").lower()
                            and not any(skip in m.get("id", "").lower() for skip in [
                                "tts", "asr", "ocr", "image-edit", "mt-", "math-", "coder-",
                                "livetranslate", "s2s", "omni", "deep-search"
                            ])
                        ]
                        
                        # Group models by base name (without date suffix)
                        # e.g., qwen-plus, qwen-plus-2025-12-01 -> base: qwen-plus
                        import re
                        model_groups = {}
                        
                        for model in chat_models:
                            model_id = model.get("id", "")
                            model_id_lower = model_id.lower()
                            
                            # Extract base model name (remove date suffix like -2025-12-01)
                            # Pattern: model-name-YYYY-MM-DD or model-name-latest
                            base_match = re.match(r'^(.+?)(?:-\d{4}-\d{2}-\d{2}|-latest|-preview)?$', model_id_lower)
                            if base_match:
                                base_name = base_match.group(1)
                            else:
                                base_name = model_id_lower
                            
                            if base_name not in model_groups:
                                model_groups[base_name] = []
                            model_groups[base_name].append((model_id, model.get("created", 0)))
                        
                        # For each group, prefer base model (without date), or latest version
                        seen_ids = set()
                        for base_name, model_list in model_groups.items():
                            # Sort: prefer base name (exact match), then by created time (newest first)
                            model_list.sort(key=lambda x: (x[0] != base_name, -x[1]))
                            
                            # Select the best model from this group
                            selected_model_id = None
                            for model_id, _ in model_list:
                                if model_id not in seen_ids:
                                    selected_model_id = model_id
                                    break
                            
                            if not selected_model_id:
                                continue
                            
                            seen_ids.add(selected_model_id)
                            
                            # Use original model ID as name (e.g., qwen3-vl-2.5-2025.11.09)
                            name = selected_model_id
                            model_id_lower = selected_model_id.lower()
                            description = f"阿里云 {selected_model_id}"
                            iq_levels = []
                            
                            # Determine IQ levels based on model name
                            if "max" in model_id_lower:
                                iq_levels = ["High"]
                                if "longcontext" in model_id_lower:
                                    description = "支持超长上下文"
                                else:
                                    description = "阿里云最强大的模型"
                            elif "plus" in model_id_lower:
                                iq_levels = ["High", "Mid"]
                                description = "平衡性能和成本"
                            elif "turbo" in model_id_lower:
                                iq_levels = ["Mid", "Low"]
                                if "audio" in model_id_lower:
                                    description = "音频理解模型"
                                else:
                                    description = "快速响应，适合高频调用"
                            elif "72b" in model_id_lower or "72-b" in model_id_lower:
                                iq_levels = ["High", "Mid"]
                                description = "72B 参数模型"
                            elif "14b" in model_id_lower or "14-b" in model_id_lower:
                                iq_levels = ["Mid"]
                                description = "14B 参数模型"
                            elif "7b" in model_id_lower or "7-b" in model_id_lower:
                                iq_levels = ["Mid", "Low"]
                                description = "7B 参数模型"
                            elif "1.8b" in model_id_lower or "1-8b" in model_id_lower:
                                iq_levels = ["Low"]
                                description = "轻量级模型"
                            elif "vl" in model_id_lower:
                                if "max" in model_id_lower:
                                    iq_levels = ["High"]
                                    description = "视觉语言模型"
                                elif "plus" in model_id_lower:
                                    iq_levels = ["High", "Mid"]
                                    description = "视觉语言模型 Plus"
                                else:
                                    iq_levels = ["High", "Mid"]
                                    description = "视觉语言模型"
                            else:
                                # Default for other Qwen models
                                iq_levels = ["Mid"]
                            
                            models.append(ModelInfo(
                                id=f"alibaba/{selected_model_id}",
                                name=name,
                                provider="Alibaba",
                                description=description,
                                recommended_for=iq_levels
                            ))
                    else:
                        logger.warning(f"Alibaba API returned status {response.status_code}: {response.text}")
            except httpx.RequestError as e:
                logger.error(f"Failed to query Alibaba API (request error): {e}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to query Alibaba API (HTTP error): {e.response.status_code} - {e.response.text}")
            except Exception as e:
                logger.error(f"Failed to query Alibaba API: {e}")
                
        elif provider == "zhipu":
            # Zhipu AI models - query API for available models (OpenAI compatible)
            try:
                import httpx
                from config.settings import settings
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{settings.ZHIPU_BASE_URL}/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # Filter for GLM chat models
                        chat_models = [
                            m for m in data.get("data", [])
                            if "glm" in m.get("id", "").lower()
                        ]
                        
                        seen_ids = set()
                        for model in chat_models:
                            model_id = model.get("id", "")
                            if model_id in seen_ids:
                                continue
                            seen_ids.add(model_id)
                            
                            # Map to our format
                            model_id_lower = model_id.lower()
                            if "glm-4-plus" in model_id_lower or "glm-4-0520" in model_id_lower:
                                iq_levels = ["High"]
                                name = "GLM-4-Plus"
                                description = "智谱最强大的模型"
                            elif "glm-4-flash" in model_id_lower or "glm-4-flashx" in model_id_lower:
                                iq_levels = ["Mid", "Low"]
                                name = "GLM-4-Flash"
                                description = "快速响应，适合高频调用"
                            elif "glm-4-air" in model_id_lower or "glm-4-airx" in model_id_lower:
                                iq_levels = ["Mid"]
                                name = "GLM-4-Air"
                                description = "平衡性能和成本"
                            elif "glm-4" in model_id_lower:
                                iq_levels = ["High", "Mid"]
                                name = "GLM-4"
                                description = "智谱 GLM-4 模型"
                            elif "glm-3" in model_id_lower:
                                iq_levels = ["Mid", "Low"]
                                name = "GLM-3"
                                description = "智谱 GLM-3 模型"
                            else:
                                iq_levels = ["Mid"]
                                name = model_id
                                description = f"智谱 {model_id}"
                            
                            models.append(ModelInfo(
                                id=f"zhipu/{model_id}",
                                name=name,
                                provider="Zhipu",
                                description=description,
                                recommended_for=iq_levels
                            ))
                    else:
                        logger.warning(f"Zhipu API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Failed to query Zhipu API: {e}")
                
        elif provider == "anthropic":
            # Anthropic models - verify key and return known models
            known_models = [
                ("anthropic/claude-3-opus-20240229", "Claude 3 Opus", "Claude 最强大的模型", ["High"]),
                ("anthropic/claude-3-sonnet-20240229", "Claude 3 Sonnet", "平衡性能和速度", ["High", "Mid"]),
                ("anthropic/claude-3-haiku-20240307", "Claude 3 Haiku", "快速且经济", ["Mid", "Low"]),
            ]
            
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Test API key
                    test_response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "claude-3-haiku-20240307",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    )
                    if test_response.status_code == 200:
                        # Key is valid
                        for model_id, name, desc, iq_levels in known_models:
                            models.append(ModelInfo(
                                id=model_id,
                                name=name,
                                provider="Anthropic",
                                description=desc,
                                recommended_for=iq_levels
                            ))
                    else:
                        logger.warning(f"Anthropic API key validation failed: {test_response.status_code}")
            except Exception as e:
                logger.error(f"Failed to validate Anthropic API key: {e}")
                
        elif provider == "ollama":
            # Ollama local models - query local Ollama API
            try:
                import httpx
                from config.settings import settings
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        for model in data.get("models", []):
                            model_name = model.get("name", "")
                            # Map common Ollama models
                            if "llama3" in model_name.lower():
                                models.append(ModelInfo(
                                    id=f"ollama/{model_name}",
                                    name=f"Llama 3 ({model_name})",
                                    provider="Ollama",
                                    description="本地运行的开源模型",
                                    recommended_for=["Mid"]
                                ))
                            elif "mistral" in model_name.lower():
                                models.append(ModelInfo(
                                    id=f"ollama/{model_name}",
                                    name=f"Mistral ({model_name})",
                                    provider="Ollama",
                                    description="高效的本地模型",
                                    recommended_for=["Mid", "Low"]
                                ))
                            elif "qwen" in model_name.lower():
                                models.append(ModelInfo(
                                    id=f"ollama/{model_name}",
                                    name=f"Qwen ({model_name})",
                                    provider="Ollama",
                                    description="本地运行的千问模型",
                                    recommended_for=["Mid"]
                                ))
                    else:
                        logger.warning(f"Ollama API returned status {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to query Ollama API: {e}")
        
        return ModelListResponse(
            models=models,
            providers=[request.provider] if models else []
        )
        
    except Exception as e:
        logger.error(f"Failed to list models with key: {e}")
        # Return empty list instead of raising error
        return ModelListResponse(models=[], providers=[])


@router.post("/test-api-key")
async def test_api_key(request: TestApiKeyRequest):
    """
    Test if an API key is valid for a specific provider.
    
    Args:
        request: Provider name and API key
        
    Returns:
        Test result with validity status
    """
    try:
        import httpx
        from config.settings import settings
        
        provider = request.provider.lower()
        api_key = request.api_key.strip()
        
        if not api_key:
            return {"valid": False, "message": "API key is empty"}
        
        # Test the API key with a minimal request that doesn't depend on specific models
        try:
            if provider == "openai":
                # Use the /models endpoint which only requires valid API key
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    if response.status_code == 200:
                        return {"valid": True, "message": "API key is valid"}
                    elif response.status_code == 401:
                        return {"valid": False, "message": "API key 无效或已过期"}
                    else:
                        return {"valid": False, "message": f"验证失败: {response.status_code}"}
                        
            elif provider == "alibaba":
                # Use the /models endpoint which only requires valid API key
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{settings.ALIBABA_BASE_URL}/models",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                    )
                    if response.status_code == 200:
                        return {"valid": True, "message": "API key is valid"}
                    elif response.status_code == 401:
                        return {"valid": False, "message": "API key 无效或已过期"}
                    else:
                        error_text = response.text[:200] if response.text else ""
                        return {"valid": False, "message": f"验证失败: {response.status_code} - {error_text}"}
                        
            elif provider == "zhipu":
                # Use the /models endpoint which only requires valid API key
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{settings.ZHIPU_BASE_URL}/models",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                    )
                    if response.status_code == 200:
                        return {"valid": True, "message": "API key is valid"}
                    elif response.status_code == 401:
                        return {"valid": False, "message": "API key 无效或已过期"}
                    else:
                        error_text = response.text[:200] if response.text else ""
                        return {"valid": False, "message": f"验证失败: {response.status_code} - {error_text}"}
                        
            elif provider == "anthropic":
                # Anthropic doesn't have a models endpoint, use a minimal LiteLLM call
                try:
                    llm_service = _get_llm_service()
                    await llm_service.generate(
                        prompt="hi",
                        max_tokens=1,
                        temperature=0.0,
                        model_config={
                            "provider": "anthropic",
                            "model": "claude-3-haiku-20240307",
                            "api_key": api_key,
                        },
                    )
                    return {"valid": True, "message": "API key is valid"}
                except Exception as e:
                    error_text = str(e).lower()
                    if "404" in error_text or "not found" in error_text:
                        return {"valid": True, "message": "API key is valid (但测试模型不可用)"}
                    return {"valid": False, "message": f"验证失败: {str(e)[:200]}"}
                        
            elif provider == "ollama":
                # Ollama doesn't require API key, just check if service is available
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        return {"valid": True, "message": "Ollama service is available"}
                    else:
                        return {"valid": False, "message": f"Ollama 服务不可用: {response.status_code}"}
            else:
                return {"valid": False, "message": f"Unknown provider: {provider}"}
                
        except httpx.RequestError as e:
            return {"valid": False, "message": f"Network error: {str(e)}"}
        except httpx.HTTPStatusError as e:
            return {"valid": False, "message": f"HTTP error: {e.response.status_code} - {e.response.text[:200]}"}
        except Exception as e:
            return {"valid": False, "message": f"Error: {str(e)}"}
            
    except Exception as e:
        logger.error(f"Failed to test API key: {e}")
        return {"valid": False, "message": f"Test failed: {str(e)}"}


@router.post("/test-model")
async def test_model(request: TestModelRequest):
    """
    Test if a specific model is available and working.
    
    Args:
        request: Model ID and optional API key
        
    Returns:
        Test result with availability status
    """
    try:
        import httpx
        from config.settings import settings
        
        model_id = request.model_id.strip()
        if not model_id:
            return {"available": False, "message": "Model ID is empty"}
        
        # Parse model ID (format: provider/model-name)
        parts = model_id.split('/')
        if len(parts) != 2:
            return {"available": False, "message": f"Invalid model ID format: {model_id}"}
        
        provider = parts[0].lower()
        model_name = parts[1]
        
        # Get API key from request or settings
        api_key = request.api_key
        if not api_key:
            if provider == "openai":
                api_key = settings.OPENAI_API_KEY
            elif provider == "alibaba":
                api_key = settings.ALIBABA_API_KEY
            elif provider == "zhipu":
                api_key = settings.ZHIPU_API_KEY
            elif provider == "anthropic":
                api_key = settings.ANTHROPIC_API_KEY
            elif provider == "ollama":
                # Ollama doesn't need API key
                api_key = None
            else:
                return {"available": False, "message": f"Unknown provider: {provider}"}
        
        if not api_key and provider != "ollama":
            return {"available": False, "message": f"API key not configured for {provider}"}
        
        # Test the model with a minimal request
        try:
            if provider == "ollama":
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Check if model is installed
                    response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        if model_name in models or any(model_name in m for m in models):
                            return {"available": True, "message": "模型可用"}
                        else:
                            return {"available": False, "message": f"模型 {model_name} 未安装"}
                    else:
                        return {"available": False, "message": f"Ollama 服务不可用: {response.status_code}"}

            llm_service = _get_llm_service()
            model_config = {
                "provider": provider,
                "model": model_name,
                "api_key": api_key,
            }
            if provider == "alibaba":
                model_config["base_url"] = settings.ALIBABA_BASE_URL
            elif provider == "zhipu":
                model_config["base_url"] = settings.ZHIPU_BASE_URL

            await llm_service.generate(
                prompt="test",
                max_tokens=1,
                temperature=0.0,
                model_config=model_config,
            )
            return {"available": True, "message": "模型可用"}
                
        except httpx.RequestError as e:
            return {"available": False, "message": f"网络错误: {str(e)}"}
        except httpx.HTTPStatusError as e:
            error_text = e.response.text[:200] if e.response.text else ""
            return {"available": False, "message": f"HTTP 错误: {e.response.status_code} - {error_text}"}
        except Exception as e:
            return {"available": False, "message": f"错误: {str(e)}"}
            
    except Exception as e:
        logger.error(f"Failed to test model: {e}")
        return {"available": False, "message": f"测试失败: {str(e)}"}
