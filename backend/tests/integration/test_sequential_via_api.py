"""
通过 API 测试 Agent 顺序发言功能
"""

import asyncio
import httpx

async def test_sequential_speaking_via_api():
    """通过 API 测试顺序发言"""
    
    print("=" * 80)
    print("测试 Agent 顺序发言（通过 API）")
    print("=" * 80)
    
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 创建游戏
        print("\n1. 创建游戏...")
        create_response = await client.post(
            f"{base_url}/api/game/create",
            json={
                "agent_count": 3,
                "civilian_word": "牛奶",
                "undercover_word": "豆浆",
                "max_rounds": 3,
                "use_balanced_team": True
            }
        )
        
        if create_response.status_code != 200:
            print(f"❌ 创建游戏失败: {create_response.status_code}")
            print(create_response.text)
            return
        
        game_data = create_response.json()
        game_id = game_data["game_id"]
        agents = game_data["agents"]
        
        print(f"✅ 游戏创建成功: {game_id}")
        print(f"\n创建了 {len(agents)} 个 Agents:")
        for agent in agents:
            print(f"  - {agent['id']}: {agent['mbti_type']} / {agent['iq_level']} / {agent['role']}")
            print(f"    名字: {agent.get('name', 'N/A')}")
        
        # 2. 开始游戏（第一轮描述）
        print("\n2. 开始第一轮（描述阶段）...")
        print("=" * 80)
        
        start_response = await client.post(
            f"{base_url}/api/game/start",
            json={"game_id": game_id}
        )
        
        if start_response.status_code != 200:
            print(f"❌ 开始游戏失败: {start_response.status_code}")
            print(start_response.text)
            return
        
        round_data = start_response.json()
        
        print(f"\n第 {round_data['round']} 轮 - 阶段: {round_data['phase']}")
        print("=" * 80)
        
        responses = round_data.get("responses", [])
        print(f"\n收到 {len(responses)} 个发言:")
        
        for idx, response in enumerate(responses, 1):
            agent_id = response['agent_id']
            content = response['content']
            thought = response.get('thought', '')
            suspicion = response.get('suspicion', {})
            
            print(f"\n[{idx}] {agent_id}:")
            print(f"  💭 思考: {thought[:150]}..." if len(thought) > 150 else f"  💭 思考: {thought}")
            print(f"  💬 发言: {content}")
            if suspicion:
                print(f"  🔍 怀疑: {suspicion}")
        
        # 3. 获取游戏状态，查看对话历史
        print("\n" + "=" * 80)
        print("3. 查看对话历史")
        print("=" * 80)
        
        state_response = await client.get(f"{base_url}/api/game/state/{game_id}")
        
        if state_response.status_code != 200:
            print(f"❌ 获取状态失败: {state_response.status_code}")
            return
        
        state = state_response.json()
        history = state.get("conversation_history", [])
        
        print(f"\n对话历史共 {len(history)} 条消息:")
        for idx, msg in enumerate(history, 1):
            print(f"{idx}. [第{msg['round']}轮] {msg['agent_id']}: {msg['content'][:60]}...")
        
        # 4. 验证顺序
        print("\n" + "=" * 80)
        print("验证结果")
        print("=" * 80)
        
        if len(history) == 3:
            print("✅ 所有 3 个 Agent 都发言了")
            
            agent_ids = [msg['agent_id'] for msg in history]
            print(f"✅ 发言顺序: {' -> '.join(agent_ids)}")
            
            # 检查后面的 Agent 是否能看到前面的发言
            print("\n检查 Agent 是否能看到前面的发言:")
            
            for idx in range(1, len(history)):
                current_agent = history[idx]['agent_id']
                current_thought = history[idx].get('thought', '')
                previous_agents = [history[i]['agent_id'] for i in range(idx)]
                previous_speeches = [history[i]['content'] for i in range(idx)]
                
                print(f"\n{current_agent} (第 {idx+1} 个发言):")
                print(f"  前面发言的 Agents: {previous_agents}")
                
                # 检查思考中是否提到了前面的内容
                mentions_count = 0
                for prev_agent in previous_agents:
                    if prev_agent in current_thought:
                        mentions_count += 1
                
                # 检查是否提到了前面的发言内容关键词
                content_mentions = 0
                for speech in previous_speeches:
                    # 提取关键词（简单方法：取前几个字）
                    keywords = speech[:10]
                    if keywords in current_thought:
                        content_mentions += 1
                
                if mentions_count > 0:
                    print(f"  ✅ 思考中提到了 {mentions_count} 个前面的 Agent")
                elif idx == 1:
                    print(f"  ℹ️  第二个发言的 Agent，可能还没有足够信息进行分析")
                else:
                    print(f"  ⚠️  思考中未明确提到前面的 Agent")
                
                # 显示思考内容的前100字
                print(f"  思考片段: {current_thought[:100]}...")
        else:
            print(f"❌ 发言数量不对: 期望 3，实际 {len(history)}")
        
        print("\n" + "=" * 80)
        print("测试完成!")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_sequential_speaking_via_api())
