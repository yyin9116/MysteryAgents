#!/usr/bin/env python3
"""
讨论模式端到端测试
测试完整讨论流程：创建讨论 -> 启动 -> Agent 发言 -> 用户插话 -> 暂停/恢复 -> 结束
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

import httpx
from datetime import datetime


class DiscussionModeTester:
    """讨论模式测试器"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.discussion_id = None
        
    async def test_create_discussion(self):
        """测试创建讨论"""
        print("\n" + "="*60)
        print("测试 1: 创建讨论")
        print("="*60)
        
        payload = {
            "topic": "人工智能的未来发展",
            "agent_count": 4,
            "use_balanced_team": True,
            "use_characters": True
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/discussion/create",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                self.discussion_id = data["discussion_id"]
                print(f"✅ 讨论创建成功")
                print(f"   讨论 ID: {self.discussion_id}")
                print(f"   主题: {payload['topic']}")
                print(f"   Agent 数量: {len(data['agents'])}")
                
                # 显示 Agent 信息
                print(f"\n   Agent 列表:")
                for agent in data['agents']:
                    print(f"     - {agent['name']} ({agent['mbti_type']})")
                
                # 显示角色信息（如果有）
                if 'characters' in data and data['characters']:
                    print(f"\n   角色列表:")
                    for char_info in data['characters']:
                        char = char_info['character']
                        prof = char_info['profession']
                        print(f"     - {char['name']} ({char['source']})")
                        print(f"       职业: {prof['title']}")
                
                return True
            else:
                print(f"❌ 创建失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 创建讨论异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_start_discussion(self):
        """测试启动讨论"""
        print("\n" + "="*60)
        print("测试 2: 启动讨论")
        print("="*60)
        
        if not self.discussion_id:
            print("❌ 没有讨论 ID")
            return False
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/discussion/start",
                json={"discussion_id": self.discussion_id}
            )
            
            if response.status_code == 200:
                print(f"✅ 讨论启动成功")
                return True
            else:
                print(f"❌ 启动失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 启动讨论异常: {e}")
            return False
    
    async def test_discussion_stream(self, max_messages=5):
        """测试讨论流式输出"""
        print("\n" + "="*60)
        print(f"测试 3: 讨论流式输出（最多 {max_messages} 条消息）")
        print("="*60)
        
        if not self.discussion_id:
            print("❌ 没有讨论 ID")
            return False
        
        try:
            print(f"   连接到流式端点...")
            
            message_count = 0
            
            async with self.client.stream(
                "GET",
                f"{self.base_url}/api/discussion/stream/{self.discussion_id}"
            ) as response:
                
                if response.status_code != 200:
                    print(f"❌ 连接失败: {response.status_code}")
                    return False
                
                print(f"   ✅ 连接成功，开始接收事件...\n")
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    try:
                        import json
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        
                        if event_type == "discussion_start":
                            print(f"   📢 讨论开始")
                        
                        elif event_type == "agent_thinking":
                            print(f"   🤔 {data['agent_name']} 正在思考...")
                        
                        elif event_type == "agent_speaking":
                            message_count += 1
                            speech = data['speech']
                            # 截断过长的发言
                            if len(speech) > 100:
                                speech = speech[:100] + "..."
                            print(f"\n   💬 {data['agent_name']}:")
                            print(f"      {speech}")
                            
                            if data.get('thought'):
                                thought = data['thought'][:80] + "..." if len(data['thought']) > 80 else data['thought']
                                print(f"      💭 内心想法: {thought}")
                            
                            # 达到最大消息数后停止
                            if message_count >= max_messages:
                                print(f"\n   ⏸️  已接收 {max_messages} 条消息，停止测试")
                                break
                        
                        elif event_type == "round_complete":
                            print(f"\n   ✅ 回合 {data['round']} 完成")
                        
                        elif event_type == "discussion_end":
                            print(f"\n   🏁 讨论结束")
                            break
                        
                        elif event_type == "error":
                            print(f"   ⚠️  错误: {data['message']}")
                    
                    except json.JSONDecodeError:
                        continue
                
                print(f"\n   统计:")
                print(f"     - 收到消息数: {message_count}")
                
                if message_count > 0:
                    print(f"✅ 流式输出测试成功")
                    return True
                else:
                    print(f"❌ 没有收到任何消息")
                    return False
                
        except Exception as e:
            print(f"❌ 流式输出异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_pause_resume(self):
        """测试暂停和恢复"""
        print("\n" + "="*60)
        print("测试 4: 暂停和恢复讨论")
        print("="*60)
        
        if not self.discussion_id:
            print("❌ 没有讨论 ID")
            return False
        
        try:
            # 暂停
            print("   暂停讨论...")
            response = await self.client.post(
                f"{self.base_url}/api/discussion/pause",
                json={"discussion_id": self.discussion_id}
            )
            
            if response.status_code == 200:
                print(f"   ✅ 暂停成功")
            else:
                print(f"   ⚠️  暂停失败: {response.status_code}")
            
            # 等待一下
            await asyncio.sleep(1)
            
            # 恢复
            print("   恢复讨论...")
            response = await self.client.post(
                f"{self.base_url}/api/discussion/resume",
                json={"discussion_id": self.discussion_id}
            )
            
            if response.status_code == 200:
                print(f"   ✅ 恢复成功")
                return True
            else:
                print(f"   ❌ 恢复失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 暂停/恢复异常: {e}")
            return False
    
    async def test_user_speak(self):
        """测试用户发言"""
        print("\n" + "="*60)
        print("测试 5: 用户发言")
        print("="*60)
        
        if not self.discussion_id:
            print("❌ 没有讨论 ID")
            return False
        
        try:
            payload = {
                "discussion_id": self.discussion_id,
                "speech": "我认为 AI 应该更注重伦理和安全性。",
                "mention_agents": []
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/discussion/user-speak",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 用户发言成功")
                print(f"   消息 ID: {data.get('message_id')}")
                return True
            else:
                print(f"❌ 发言失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 用户发言异常: {e}")
            return False
    
    async def test_end_discussion(self):
        """测试结束讨论"""
        print("\n" + "="*60)
        print("测试 6: 结束讨论")
        print("="*60)
        
        if not self.discussion_id:
            print("❌ 没有讨论 ID")
            return False
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/discussion/end",
                json={"discussion_id": self.discussion_id}
            )
            
            if response.status_code == 200:
                print(f"✅ 讨论结束成功")
                return True
            else:
                print(f"❌ 结束失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 结束讨论异常: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        await self.client.aclose()
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🧪 讨论模式端到端测试")
        print("="*60)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"后端地址: {self.base_url}")
        
        results = {}
        
        # 测试 1: 创建讨论
        results['create'] = await self.test_create_discussion()
        
        if not results['create']:
            print("\n❌ 创建讨论失败，终止测试")
            await self.cleanup()
            return results
        
        # 测试 2: 启动讨论
        results['start'] = await self.test_start_discussion()
        
        if not results['start']:
            print("\n❌ 启动讨论失败，跳过后续测试")
            await self.cleanup()
            return results
        
        # 测试 3: 流式输出（只接收几条消息）
        results['stream'] = await self.test_discussion_stream(max_messages=3)
        
        # 测试 4: 暂停/恢复
        results['pause_resume'] = await self.test_pause_resume()
        
        # 测试 5: 用户发言
        results['user_speak'] = await self.test_user_speak()
        
        # 测试 6: 结束讨论
        results['end'] = await self.test_end_discussion()
        
        # 总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"{test_name}: {status}")
        
        total = len(results)
        passed = sum(results.values())
        print(f"\n总计: {passed}/{total} 通过")
        
        if passed == total:
            print("✅ 所有测试通过！")
        else:
            print("❌ 部分测试失败")
        
        print("="*60)
        
        await self.cleanup()
        return results


async def main():
    """主函数"""
    tester = DiscussionModeTester()
    
    try:
        results = await tester.run_all_tests()
        
        if all(results.values()):
            sys.exit(0)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        await tester.cleanup()
        sys.exit(130)
    
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        await tester.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
