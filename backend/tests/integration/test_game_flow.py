"""
测试游戏流程 - 验证创建游戏后不会自动开始
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.agent_factory import AgentFactory
from services.game_service import GameService
from models.game import GameConfig

async def test_game_creation():
    """测试游戏创建流程"""
    print("=" * 60)
    print("测试：游戏创建后不自动开始")
    print("=" * 60)
    
    # 创建服务
    factory = AgentFactory()
    
    # 创建 Agent
    print("\n1. 创建 5 个 Agent...")
    agents = await factory.create_balanced_team(5)
    print(f"   ✓ 创建了 {len(agents)} 个 Agent")
    for agent in agents:
        print(f"     - {agent.config.name} ({agent.config.mbti_type}, {agent.config.iq_level})")
    
    # 创建游戏配置
    config = GameConfig(
        game_id="test_game",
        agent_count=len(agents),
        civilian_word="牛奶",
        undercover_word="豆浆",
        max_rounds=10
    )
    
    # 创建游戏服务
    print("\n2. 创建游戏服务...")
    game_service = GameService(config, agents)
    print(f"   ✓ 游戏 ID: {config.game_id}")
    print(f"   ✓ 当前回合: {game_service.current_round}")
    print(f"   ✓ 当前阶段: {game_service.phase.value}")
    print(f"   ✓ 对话历史: {len(game_service.conversation_history)} 条")
    
    # 验证游戏状态
    print("\n3. 验证初始状态...")
    assert game_service.current_round == 0, "回合应该是 0"
    assert len(game_service.conversation_history) == 0, "对话历史应该为空"
    assert game_service.phase.value == "description", "阶段应该是 description"
    print("   ✓ 初始状态正确：回合 0，无对话历史")
    
    # 手动开始第一轮
    print("\n4. 手动开始第一轮...")
    game_service.start_new_round()
    print(f"   ✓ 当前回合: {game_service.current_round}")
    
    # 选择第一个发言人
    print("\n5. 选择第一个发言人...")
    next_speaker = game_service.select_next_speaker(strategy="round_robin")
    print(f"   ✓ 下一个发言人: {next_speaker}")
    
    # 让第一个 Agent 发言
    print("\n6. 第一个 Agent 发言...")
    result = await game_service.agent_speak(next_speaker)
    print(f"   ✓ 发言: {result['speech']}")
    print(f"   ✓ 思考: {result['thought'][:50]}...")
    print(f"   ✓ 对话历史: {len(game_service.conversation_history)} 条")
    
    print("\n" + "=" * 60)
    print("✓ 测试通过：游戏创建后不会自动开始")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_game_creation())
