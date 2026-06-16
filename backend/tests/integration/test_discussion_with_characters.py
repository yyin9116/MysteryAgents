"""
Test script for Discussion with Characters integration.

测试带角色的讨论集成
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from services.discussion_factory import DiscussionFactory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_discussion_with_characters():
    """测试带角色的讨论创建"""
    logger.info("=" * 60)
    logger.info("Testing Discussion with Characters Integration")
    logger.info("=" * 60)
    
    factory = DiscussionFactory()
    
    # Test 1: Create discussion with characters
    logger.info("\n1. Creating discussion with characters")
    
    topic = "人工智能对未来社会的影响"
    agent_count = 4
    mbti_list = ["ENTP", "INTJ", "INFP", "ESTP"]
    
    logger.info(f"Topic: {topic}")
    logger.info(f"Agent count: {agent_count}")
    logger.info(f"MBTI types: {mbti_list}")
    
    try:
        discussion, service = await factory.create_discussion_with_characters(
            topic=topic,
            agent_count=agent_count,
            mbti_list=mbti_list
        )
        
        logger.info(f"\n✓ Discussion created successfully!")
        logger.info(f"  Discussion ID: {discussion.id}")
        logger.info(f"  Topic: {discussion.topic}")
        logger.info(f"  Status: {discussion.status.value}")
        logger.info(f"  Agents: {len(service.agents)}")
        
        # Check agents
        logger.info(f"\n  Agents:")
        for agent_id in service.agents.keys():
            agent = service.get_agent(agent_id)
            char_with_prof = service.get_character_for_agent(agent_id)
            
            if agent and char_with_prof:
                logger.info(f"    - {agent_id}:")
                logger.info(f"        Name: {agent.config.name}")
                logger.info(f"        Character: {char_with_prof.character.name}")
                logger.info(f"        MBTI: {agent.config.mbti_type}")
                logger.info(f"        IQ: {agent.config.iq_level.value}")
                logger.info(f"        Profession: {char_with_prof.profession.profession_name}")
                logger.info(f"        Workplace: {char_with_prof.profession.workplace}")
        
        # Test 2: Check prompt building
        logger.info(f"\n2. Testing prompt building")
        
        agent = service.get_agent("agent_1")
        if agent:
            prompt = service._build_discussion_prompt(agent)
            
            logger.info(f"\n  Prompt for {agent.config.name}:")
            logger.info(f"    Length: {len(prompt)} characters")
            logger.info(f"    Lines: {len(prompt.split(chr(10)))}")
            
            # Check key elements
            char_with_prof = service.get_character_for_agent("agent_1")
            if char_with_prof:
                checks = {
                    "角色名字": char_with_prof.character.name in prompt,
                    "职业": char_with_prof.profession.profession_name in prompt,
                    "话题": topic in prompt,
                    "输出格式": "JSON" in prompt,
                    "示例": "示例" in prompt
                }
                
                logger.info(f"\n  Prompt checks:")
                for check_name, passed in checks.items():
                    status = "✓" if passed else "✗"
                    logger.info(f"    {status} {check_name}")
        
        # Test 3: Test without characters (original mode)
        logger.info(f"\n3. Testing discussion without characters (original mode)")
        
        discussion2, service2 = await factory.create_discussion_without_characters(
            topic="测试话题",
            agent_count=3,
            mbti_list=["ENTP", "INTJ", "INFP"]
        )
        
        logger.info(f"\n✓ Discussion without characters created!")
        logger.info(f"  Discussion ID: {discussion2.id}")
        logger.info(f"  Has characters: {len(service2.characters) > 0}")
        
        # Check agents
        logger.info(f"\n  Agents:")
        for agent_id in service2.agents.keys():
            agent = service2.get_agent(agent_id)
            if agent:
                logger.info(f"    - {agent_id}: {agent.config.name} ({agent.config.mbti_type})")
        
    except Exception as e:
        logger.error(f"✗ Failed to create discussion: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    logger.info("\n" + "=" * 60)
    logger.info("Discussion with Characters Integration Test Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_discussion_with_characters())
