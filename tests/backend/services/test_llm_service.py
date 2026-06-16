import pytest
from litellm.utils import Usage

import services.llm_service as llm_service_module
from services.llm_service import LLMService


class FakeUsageStore:
    def __init__(self) -> None:
        self.records = []

    def record_usage(self, model: str, tokens: int, cost: float, session_id=None):
        self.records.append(
            {
                "model": model,
                "tokens": tokens,
                "cost": cost,
                "session_id": session_id,
            }
        )


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]
        self.usage = Usage(prompt_tokens=5, completion_tokens=7, total_tokens=12)


@pytest.mark.asyncio
async def test_generate_agent_response_logs_usage(monkeypatch):
    async def fake_acompletion(*_args, **_kwargs):
        return FakeResponse('{"thought": "t", "speech": "hello", "suspicion": {"agent_2": 4}}')

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.12)

    store = FakeUsageStore()
    service = LLMService(usage_store=store)

    result = await service.generate_agent_response(
        system_prompt="system",
        conversation_history=[],
        iq_level="Mid",
        model_config={
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
        },
    )

    assert result.speech == "hello"
    assert store.records == [
        {
            "model": "openai/gpt-4o",
            "tokens": 12,
            "cost": 0.12,
            "session_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_generate_returns_content(monkeypatch):
    async def fake_acompletion(*_args, **_kwargs):
        return FakeResponse("pong")

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.0)

    store = FakeUsageStore()
    service = LLMService(usage_store=store)

    result = await service.generate(
        prompt="ping",
        max_tokens=1,
        model_config={
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
        },
    )

    assert result == "pong"
    assert store.records


@pytest.mark.asyncio
async def test_generate_agent_response_normalizes_zhipu_to_openai_compatible(monkeypatch):
    captured = {}

    async def fake_acompletion(*_args, **kwargs):
        captured.update(kwargs)
        return FakeResponse('{"thought": "t", "speech": "狼人先别着急站边。", "suspicion": {"werewolf_agent_2": 4}}')

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.01)

    service = LLMService(usage_store=FakeUsageStore())
    result = await service.generate_agent_response(
        system_prompt="system",
        conversation_history=[],
        iq_level="Mid",
        model_config={
            "provider": "zhipu",
            "model": "glm-4.5-air",
            "api_key": "test-key",
        },
    )

    assert result.speech == "狼人先别着急站边。"
    assert captured["model"] == "openai/glm-4.5-air"
    assert captured["api_key"] == "test-key"
    assert captured["api_base"] == "https://open.bigmodel.cn/api/paas/v4"
    assert captured["messages"][0] == {"role": "system", "content": "system"}
    assert captured["messages"][1]["role"] == "user"
    assert "只输出 JSON" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_agent_response_accepts_float_suspicion_scores(monkeypatch):
    async def fake_acompletion(*_args, **_kwargs):
        return FakeResponse('{"thought": "t", "speech": "我先听一轮。", "suspicion": {"werewolf_agent_2": 0.6, "werewolf_agent_3": 4.2}}')

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.0)

    service = LLMService(usage_store=FakeUsageStore())
    result = await service.generate_agent_response(
        system_prompt="system",
        conversation_history=[],
        iq_level="Mid",
        model_config={
            "provider": "zhipu",
            "model": "glm-4.5-air",
            "api_key": "test-key",
        },
    )

    assert result.suspicion == {"werewolf_agent_2": 1, "werewolf_agent_3": 4}


@pytest.mark.asyncio
async def test_generate_vote_response_retries_with_strict_json_prompt(monkeypatch):
    calls = []

    async def fake_acompletion(*_args, **kwargs):
        calls.append(kwargs["messages"])
        if len(calls) == 1:
            return FakeResponse("我想投 1 号，因为他发言奇怪。")
        return FakeResponse('{"thought":"二次纠正后给出结构化结果","vote":"werewolf_agent_2","confidence":0.82}')

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.0)

    service = LLMService(usage_store=FakeUsageStore())
    service.max_retries = 2

    result = await service.generate_vote_response(
        system_prompt="system",
        conversation_history=[],
        iq_level="Mid",
        valid_agent_ids=["werewolf_agent_1", "werewolf_agent_2"],
        model_config={
            "provider": "zhipu",
            "model": "glm-4.5-air",
            "api_key": "test-key",
        },
    )

    assert result.vote == "werewolf_agent_2"
    assert result.confidence == 0.82
    assert len(calls) == 2
    assert "只输出一行合法 JSON" in calls[1][-1]["content"]


@pytest.mark.asyncio
async def test_generate_vote_response_extracts_fenced_json(monkeypatch):
    async def fake_acompletion(*_args, **_kwargs):
        return FakeResponse('```json\n{"thought":"结构化正常","vote":"werewolf_agent_1","confidence":0.61}\n```')

    monkeypatch.setattr(llm_service_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_service_module, "completion_cost", lambda **_kwargs: 0.0)

    service = LLMService(usage_store=FakeUsageStore())

    result = await service.generate_vote_response(
        system_prompt="system",
        conversation_history=[],
        iq_level="Mid",
        valid_agent_ids=["werewolf_agent_1", "werewolf_agent_2"],
        model_config={
            "provider": "zhipu",
            "model": "glm-4.5-air",
            "api_key": "test-key",
        },
    )

    assert result.vote == "werewolf_agent_1"
    assert result.confidence == 0.61
