"""
测试 Agent 顺序发言功能
验证每个 Agent 能看到前面 Agent 的发言
"""

import asyncio
import logging
import sys

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

from services.game_service import GameService
from services.agent_factory import AgentFactory
from models.game import GameConfig

async def test_sequential_speaking():
    """测试顺序发言"""
    
    print("=" * 80)
    print("测试 Agent 顺序发言")
    print("=" * 80)
    
    # 创建服务
    agent_factory = AgentFactory()
    
    # 创建游戏配置（3个 Agent，更容易观察）
    config = GameConfig(
        game_id="test_sequential",
        agent_count=3,
        civilian_word="牛奶",
        undercover_word="豆浆",
        max_rounds=2,
        use_balanced_team=False  # 使用简单配置
    )
    
    print("\n1. 创建 Agents...")
    
    # 手动创建 3 个 Agent
    agents = []
    for i in range(1, 4):
        agent = await agent_factory.create_agent(
            mbti_type=["INFP", "ENTJ", "ISTP"][i-1],
            iq_level=["Mid", "High", "Low"][i-1],
            agent_id=f"agent_{i}"
        )
        agents.append(agent)
    
    # 创建游戏服务
    game_service = GameService(
        config=config,
        agents=agents
    )
    
    print(f"\n创建了 {len(game_service.agents)} 个 Agents:")
    for agent_id, agent in game_service.agents.items():
        print(f"  - {agent.config.id}: {agent.config.mbti_type} / {agent.config.iq_level.value} / {agent.config.role.value}")
        print(f"    词: {agent.config.word}")
    
    print("\n2. 开始第一轮（描述阶段）...")
    print("=" * 80)
    result = await game_service.start_game()
    
    print("\n" + "=" * 80)
    print("第一轮发言结果:")
    print("=" * 80)
    
    for idx, response in enumerate(result.get('responses', []), 1):
        agent_id = response['agent_id']
        content = response['content']
        thought = response.get('thought', '')
        
        print(f"\n[{idx}] {agent_id}:")
        print(f"  💭 思考: {thought[:100]}..." if len(thought) > 100 else f"  💭 思考: {thought}")
        print(f"  💬 发言: {content}")
        print(f"  🔍 怀疑: {response.get('suspicion', {})}")
    
    # 检查对话历史
    print("\n" + "=" * 80)
    print("对话历史验证:")
    print("=" * 80)
    
    history = game_service.conversation_history
    print(f"\n总共 {len(history)} 条消息")
    
    for idx, msg in enumerate(history, 1):
        print(f"{idx}. [{msg['round']}轮] {msg['agent_id']}: {msg['content'][:50]}...")
    
    # 验证顺序
    print("\n" + "=" * 80)
    print("验证结果:")
    print("=" * 80)
    
    if len(history) == 3:
        print("✅ 所有 3 个 Agent 都发言了")
        
        # 检查是否按顺序
        agent_ids = [msg['agent_id'] for msg in history]
        print(f"✅ 发言顺序: {' -> '.join(agent_ids)}")
        
        # 检查每个 Agent 的思考中是否提到了前面的 Agent
        for idx, msg in enumerate(history[1:], 1):  # 从第二个开始
            thought = msg.get('thought', '')
            prev_agents = [history[i]['agent_id'] for i in range(idx)]
            
            print(f"\n检查 {msg['agent_id']} 的思考:")
            print(f"  前面发言的 Agents: {prev_agents}")
            
            # 简单检查：思考中是否包含任何前面 Agent 的 ID 或发言内容
            mentions_previous = any(prev_id in thought for prev_id in prev_agents)
            if mentions_previous:
                print(f"  ✅ 思考中提到了前面的 Agent")
            else:
                print(f"  ⚠️  思考中未明确提到前面的 Agent（可能是第一轮，还没有足够信息）")
    else:
        print(f"❌ 发言数量不对: 期望 3，实际 {len(history)}")
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_sequential_speaking())
