"""
测试流式 API 功能
"""

import asyncio
import httpx

async def test_streaming():
    """测试流式 API"""
    
    base_url = "http://127.0.0.1:8000"
    
    print("=" * 80)
    print("测试流式 API")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
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
            print(f"  - {agent['id']}: {agent.get('name', 'N/A')}")
            print(f"    MBTI: {agent['mbti_type']}, IQ: {agent['iq_level']}, Role: {agent['role']}")
        
        # 2. 测试流式 API
        print("\n2. 开始流式回合...")
        print("=" * 80)
        
        stream_url = f"{base_url}/api/game/stream/start"
        
        async with client.stream(
            "POST",
            stream_url,
            json={"game_id": game_id},
            timeout=120.0
        ) as response:
            if response.status_code != 200:
                print(f"❌ 流式请求失败: {response.status_code}")
                text = await response.aread()
                print(text.decode())
                return
            
            print("✅ 流式连接建立")
            print()
            
            event_count = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_count += 1
                    data_str = line[6:]  # 移除 "data: " 前缀
                    
                    try:
                        import json
                        event = json.loads(data_str)
                        event_type = event.get("type")
                        
                        if event_type == "round_start":
                            phase = event.get('phase', 'unknown')
                            print(f"\n🎮 回合 {event.get('round')} 开始 - {phase}")
                            print("-" * 80)
                        
                        elif event_type == "agent_thinking":
                            agent_name = event.get("agent_name", "Unknown")
                            index = event.get("index")
                            total = event.get("total")
                            phase = event.get("phase", "")
                            phase_text = f"[{phase}]" if phase else ""
                            print(f"\n💭 [{index}/{total}] {agent_name} 正在思考{phase_text}...")
                        
                        elif event_type == "agent_speaking":
                            agent_name = event.get("agent_name", "Unknown")
                            speech = event.get("speech", "")
                            thought = event.get("thought", "")
                            suspicion = event.get("suspicion", {})
                            
                            print(f"\n💬 {agent_name}:")
                            print(f"   发言: {speech}")
                            print(f"   思考: {thought[:100]}..." if len(thought) > 100 else f"   思考: {thought}")
                            if suspicion:
                                print(f"   怀疑: {suspicion}")
                        
                        elif event_type == "voting_start":
                            print(f"\n🗳️  投票阶段开始")
                            print("-" * 80)
                        
                        elif event_type == "agent_voting":
                            agent_name = event.get("agent_name", "Unknown")
                            voted_for_name = event.get("voted_for_name", "Unknown")
                            confidence = event.get("confidence", 0)
                            thought = event.get("thought", "")
                            
                            print(f"\n✅ {agent_name} 投票给 {voted_for_name} (置信度: {confidence:.2f})")
                            print(f"   思考: {thought[:100]}..." if len(thought) > 100 else f"   思考: {thought}")
                        
                        elif event_type == "elimination":
                            eliminated_name = event.get("eliminated_name", "Unknown")
                            eliminated_role = event.get("eliminated_role", "Unknown")
                            eliminated_word = event.get("eliminated_word", "Unknown")
                            vote_count = event.get("vote_count", 0)
                            
                            print(f"\n💀 淘汰结果:")
                            print(f"   {eliminated_name} 被淘汰！")
                            print(f"   角色: {eliminated_role}")
                            print(f"   词汇: {eliminated_word}")
                            print(f"   得票数: {vote_count}")
                            print("-" * 80)
                        
                        elif event_type == "game_over":
                            result = event.get("result", "unknown")
                            message = event.get("message", "")
                            print(f"\n🏁 游戏结束！")
                            print(f"   结果: {result}")
                            print(f"   {message}")
                            print("=" * 80)
                        
                        elif event_type == "agent_error":
                            agent_id = event.get("agent_id")
                            message = event.get("message")
                            print(f"\n⚠️  {agent_id} 出错: {message}")
                        
                        elif event_type == "round_complete":
                            round_num = event.get("round")
                            print(f"\n✅ 回合 {round_num} 完成")
                            print("=" * 80)
                        
                        elif event_type == "error":
                            message = event.get("message")
                            print(f"\n❌ 错误: {message}")
                    
                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON 解析错误: {e}")
                        print(f"   数据: {data_str[:100]}")
        
        print(f"\n总共接收到 {event_count} 个事件")
        
        # 3. 获取最终状态
        print("\n3. 获取游戏状态...")
        state_response = await client.get(f"{base_url}/api/game/state/{game_id}")
        
        if state_response.status_code == 200:
            state = state_response.json()
            print(f"✅ 当前回合: {state['round']}")
            print(f"✅ 对话历史: {len(state['conversation_history'])} 条消息")
            
            print("\n最新的 3 条消息:")
            for msg in state['conversation_history'][-3:]:
                print(f"  [{msg['round']}轮] {msg['agent_id']}: {msg['content'][:50]}...")
        
        print("\n" + "=" * 80)
        print("测试完成!")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_streaming())
