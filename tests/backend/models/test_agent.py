import pytest

from models.agent import Agent, AgentConfig, IQLevel
from services.llm_service import AgentResponse, VoteResponse
from services.memory_service import AgentMemorySystem


class StubLLMService:
    def __init__(self) -> None:
        self.calls = []

    async def generate_agent_response(self, **kwargs):
        self.calls.append({"type": "description", **kwargs})
        return AgentResponse(
            thought="thinking",
            speech="hello",
            suspicion={"agent_2": 3},
            agree_with=["agent_2"],
            sentiment="neutral",
        )

    async def generate_vote_response(self, **kwargs):
        self.calls.append({"type": "vote", **kwargs})
        return VoteResponse(thought="voting", vote="agent_2", confidence=0.9)


@pytest.mark.asyncio
async def test_agent_generate_description_uses_llm_service(monkeypatch):
    monkeypatch.setattr(Agent, "_create_autogen_agent", lambda _self: None)

    stub = StubLLMService()
    config = AgentConfig(id="agent_1", mbti_type="ENTJ", iq_level=IQLevel.MID, word="apple")
    memory_system = AgentMemorySystem(agent_id="agent_1", iq_level=IQLevel.MID.value)
    agent = Agent(config=config, memory_system=memory_system, llm_service=stub)

    response = await agent.generate_description(
        system_prompt="system",
        conversation_history=[{"agent_id": "agent_2", "content": "hi"}],
        current_round=1,
    )

    assert response["speech"] == "hello"
    assert response["agree_with"] == ["agent_2"]
    assert agent.suspicion_scores["agent_2"] == 3
    assert memory_system.memories

    call = stub.calls[0]
    assert "## 你的记忆:" in call["system_prompt"]
    assert call["conversation_history"][0]["content"] == "agent_2: hi"


@pytest.mark.asyncio
async def test_agent_generate_vote_uses_llm_service(monkeypatch):
    monkeypatch.setattr(Agent, "_create_autogen_agent", lambda _self: None)

    stub = StubLLMService()
    config = AgentConfig(id="agent_1", mbti_type="ENTJ", iq_level=IQLevel.MID, word="apple")
    memory_system = AgentMemorySystem(agent_id="agent_1", iq_level=IQLevel.MID.value)
    agent = Agent(config=config, memory_system=memory_system, llm_service=stub)

    response = await agent.generate_vote(
        system_prompt="vote",
        conversation_history=[],
        valid_agent_ids=["agent_1", "agent_2"],
        current_round=1,
    )

    assert response["vote"] == "agent_2"
    assert agent.vote_history[-1]["voted_for"] == "agent_2"


def test_format_conversation_history_for_llm_merges_user_messages(monkeypatch):
    monkeypatch.setattr(Agent, "_create_autogen_agent", lambda _self: None)

    stub = StubLLMService()
    config = AgentConfig(id="agent_1", mbti_type="ENTJ", iq_level=IQLevel.MID, word="apple")
    memory_system = AgentMemorySystem(agent_id="agent_1", iq_level=IQLevel.MID.value)
    agent = Agent(config=config, memory_system=memory_system, llm_service=stub)

    formatted = agent._format_conversation_history_for_llm(
        [
            {"agent_id": "agent_2", "content": "第一句"},
            {"agent_id": "system", "content": "系统提示"},
            {"agent_id": "agent_3", "content": "第二句"},
            {"agent_id": "agent_4", "content": "第三句"},
        ]
    )

    assert formatted == [
        {
            "role": "user",
            "content": "agent_2: 第一句\n系统: 系统提示\nagent_3: 第二句\nagent_4: 第三句",
        }
    ]
