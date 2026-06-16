#!/usr/bin/env python3
"""
狼人杀游戏端到端测试
测试完整游戏流程：创建游戏 -> 启动 -> Agent 发言 -> 投票 -> 淘汰 -> 游戏结束
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import httpx
from datetime import datetime


class UndercoverGameTester:
    """狼人杀游戏测试器"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.game_id = None
        
    async def test_create_game(self):
        """测试创建游戏"""
        print("\n" + "="*60)
        print("测试 1: 创建狼人杀游戏")
        print("="*60)
        
        payload = {
            "agent_count": 6,
            "civilian_word": "苹果",
            "undercover_word": "香蕉",
            "use_balanced_team": True
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/game/create",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                self.game_id = data["game_id"]
                print(f"✅ 游戏创建成功")
                print(f"   游戏 ID: {self.game_id}")
                print(f"   Agent 数量: {len(data['agents'])}")
                print(f"   平民词汇: {payload['civilian_word']}")
                print(f"   卧底词汇: {payload['undercover_word']}")
                
                # 显示 Agent 信息
                print(f"\n   Agent 列表:")
                for agent in data['agents']:
                    print(f"     - {agent['name']} ({agent['mbti_type']}, {agent['iq_level']})")
                
                return True
            else:
                print(f"❌ 创建失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 创建游戏异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_get_game_state(self):
        """测试获取游戏状态"""
        print("\n" + "="*60)
        print("测试 2: 获取游戏状态")
        print("="*60)
        
        if not self.game_id:
            print("❌ 没有游戏 ID")
            return False
        
        try:
            response = await self.client.get(
                f"{self.base_url}/api/game/{self.game_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 获取状态成功")
                print(f"   回合: {data['round']}")
                print(f"   阶段: {data['phase']}")
                print(f"   存活 Agent: {len([a for a in data['agents'] if a['is_alive']])}")
                print(f"   游戏结束: {data['game_over']}")
                return True
            else:
                print(f"❌ 获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取状态异常: {e}")
            return False
    
    async def test_next_round_stream(self):
        """测试下一回合（流式）"""
        print("\n" + "="*60)
        print("测试 3: 执行游戏回合（流式）")
        print("="*60)
        
        if not self.game_id:
            print("❌ 没有游戏 ID")
            return False
        
        try:
            print(f"   开始执行回合...")
            
            async with self.client.stream(
                "GET",
                f"{self.base_url}/api/game/{self.game_id}/next-round-stream"
            ) as response:
                
                if response.status_code != 200:
                    print(f"❌ 请求失败: {response.status_code}")
                    return False
                
                event_count = 0
                agent_speeches = []
                votes = []
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    try:
                        import json
                        data = json.loads(line[6:])  # 去掉 "data: " 前缀
                        event_type = data.get("type")
                        event_count += 1
                        
                        if event_type == "round_start":
                            print(f"\n   📢 回合 {data['round']} 开始 - {data['phase']}")
                        
                        elif event_type == "agent_thinking":
                            print(f"   🤔 {data['agent_name']} 正在思考... ({data['index']}/{data['total']})")
                        
                        elif event_type == "agent_speaking":
                            speech = data['speech'][:50] + "..." if len(data['speech']) > 50 else data['speech']
                            print(f"   💬 {data['agent_name']}: {speech}")
                            agent_speeches.append(data['agent_name'])
                        
                        elif event_type == "voting_start":
                            print(f"\n   🗳️  投票阶段开始")
                        
                        elif event_type == "agent_voting":
                            print(f"   ✋ {data['agent_name']} 投票给 {data['voted_for_name']} (置信度: {data['confidence']}%)")
                            votes.append((data['agent_name'], data['voted_for_name']))
                        
                        elif event_type == "elimination":
                            print(f"\n   ❌ {data['eliminated_name']} 被淘汰!")
                            print(f"      角色: {data['eliminated_role']}")
                            print(f"      词汇: {data['eliminated_word']}")
                            print(f"      得票: {data['vote_count']}")
                        
                        elif event_type == "game_over":
                            print(f"\n   🏁 游戏结束: {data['message']}")
                            print(f"      结果: {data['result']}")
                        
                        elif event_type == "round_complete":
                            print(f"\n   ✅ 回合 {data['round']} 完成")
                            print(f"      剩余 Agent: {data['remaining_agents']}")
                        
                        elif event_type == "error":
                            print(f"   ⚠️  错误: {data['message']}")
                    
                    except json.JSONDecodeError:
                        continue
                
                print(f"\n   统计:")
                print(f"     - 总事件数: {event_count}")
                print(f"     - 发言 Agent: {len(agent_speeches)}")
                print(f"     - 投票数: {len(votes)}")
                
                if event_count > 0:
                    print(f"✅ 回合执行成功")
                    return True
                else:
                    print(f"❌ 没有收到任何事件")
                    return False
                
        except Exception as e:
            print(f"❌ 执行回合异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_model_configs(self):
        """测试模型配置 API"""
        print("\n" + "="*60)
        print("测试 4: 模型配置 API")
        print("="*60)
        
        try:
            # 获取模型配置列表
            response = await self.client.get(
                f"{self.base_url}/api/model-configs?skip=0&limit=10"
            )
            
            if response.status_code == 200:
                configs = response.json()
                print(f"✅ 获取模型配置成功")
                print(f"   配置数量: {len(configs)}")
                
                if configs:
                    print(f"\n   配置列表:")
                    for config in configs:
                        default_mark = " [默认]" if config.get('is_default') else ""
                        print(f"     - {config['name']}{default_mark}")
                        print(f"       提供商: {config['provider']}, 模型: {config['model']}")
                else:
                    print(f"   ⚠️  没有配置的模型")
                
                return True
            else:
                print(f"❌ 获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 测试模型配置异常: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        await self.client.aclose()
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🧪 狼人杀游戏端到端测试")
        print("="*60)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"后端地址: {self.base_url}")
        
        results = {}
        
        # 测试 1: 创建游戏
        results['create_game'] = await self.test_create_game()
        
        if not results['create_game']:
            print("\n❌ 创建游戏失败，终止测试")
            await self.cleanup()
            return results
        
        # 测试 2: 获取状态
        results['get_state'] = await self.test_get_game_state()
        
        # 测试 3: 执行回合
        results['next_round'] = await self.test_next_round_stream()
        
        # 测试 4: 模型配置
        results['model_configs'] = await self.test_model_configs()
        
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
    tester = UndercoverGameTester()
    
    try:
        results = await tester.run_all_tests()
        
        # 返回退出码
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
