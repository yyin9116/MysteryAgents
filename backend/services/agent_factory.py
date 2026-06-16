"""
Agent Factory using Factory pattern.

Supports creating agents with different configurations and templates.
Agents are backed by the runtime implemented in models.agent.
"""

from typing import Optional, Dict, Any, List
import logging
logger = logging.getLogger(__name__)

from models.agent import AgentConfig, Agent
from services.memory_service import AgentMemorySystem


class AgentFactory:
    """Factory for creating agents with different configurations."""
    
    # 预定义的中文名字池（按性格分类）
    # 这些名字只在角色库缺人时作为兜底使用，因此优先保证“知名人物/角色感”
    # 而不是旧版的“性格形容词+姓氏”风格。
    NAMES_BY_PERSONALITY = {
        "ENTJ": ["曹操", "武则天", "夜神月", "凯撒", "王熙凤"],
        "INTJ": ["诸葛亮", "牛顿", "甘道夫", "斯内普", "达芬奇"],
        "INFP": ["林黛玉", "哈姆雷特", "千寻", "小王子", "梵高"],
        "ENFJ": ["林肯", "奥巴马", "X教授", "擎天柱", "唐僧"],
        "INTP": ["爱因斯坦", "福尔摩斯", "霍金", "居里夫人", "图灵"],
        "ISTP": ["杨过", "李小龙", "汉索罗", "印第安纳琼斯", "令狐冲"],
        "ENFP": ["李白", "彼得帕克", "阿拉丁", "韦小宝", "苏轼"],
        "ESFP": ["玛丽莲梦露", "猪八戒", "哈莉奎茵", "杰克船长", "小燕子"],
        "ESTJ": ["包拯", "秦始皇", "赫敏", "华盛顿", "海瑞"],
        "ISFP": ["王昭君", "哈利波特", "琼恩雪诺", "嫦娥", "紫霞仙子"],
        "ENTP": ["孙悟空", "钢铁侠", "洛基", "提利昂", "周伯通"],
        "ISFJ": ["伊丽莎白二世", "花木兰", "唐僧", "山姆", "美国队长"],
        "ESFJ": ["刘备", "宝钗", "灰姑娘", "多萝西", "宋江"],
        "ESTP": ["哪吒", "鲁智深", "杰克船长", "韩信", "柯克船长"],
        "INFJ": ["王阳明", "邓布利多", "梅林", "阿尔敏", "观音"],
        "ISTJ": ["武松", "狄仁杰", "阿拉贡", "于谦", "展昭"]
    }
    
    # Predefined agent templates
    TEMPLATES = {
        "strategic_high": {
            "mbti_type": "ENTJ",
            "iq_level": "High",
            "description": "Strategic commander with high analytical ability"
        },
        "analytical_high": {
            "mbti_type": "INTJ",
            "iq_level": "High",
            "description": "Analytical mastermind with logical reasoning"
        },
        "emotional_mid": {
            "mbti_type": "INFP",
            "iq_level": "Mid",
            "description": "Emotional mediator with intuitive insights"
        },
        "social_mid": {
            "mbti_type": "ENFJ",
            "iq_level": "Mid",
            "description": "Social protagonist with persuasive skills"
        },
        "simple_low": {
            "mbti_type": "ISTP",
            "iq_level": "Low",
            "description": "Simple craftsman with practical approach"
        },
        "impulsive_low": {
            "mbti_type": "ESFP",
            "iq_level": "Low",
            "description": "Impulsive entertainer with spontaneous reactions"
        }
    }
    
    def __init__(self):
        """Initialize factory."""
        self.agent_counter = 0
        self.used_names = set()  # 跟踪已使用的名字
    
    def _generate_name(self, mbti_type: str) -> str:
        """
        为 agent 生成一个唯一的名字
        
        Args:
            mbti_type: MBTI 性格类型
            
        Returns:
            生成的名字
        """
        try:
            from services.character_selection_service import get_character_selection_service

            selection_service = get_character_selection_service()
            character = selection_service._select_character_for_mbti(mbti_type.upper(), [])
            if character.name not in self.used_names:
                self.used_names.add(character.name)
                logger.info("Using historical/myth character name for %s: %s", mbti_type, character.name)
                return character.name
        except Exception as exc:
            logger.debug("Character-based naming unavailable for %s: %s", mbti_type, exc)

        # 获取该 MBTI 类型的名字列表
        names = self.NAMES_BY_PERSONALITY.get(mbti_type.upper(), [])
        
        # 如果没有预定义名字，使用通用名字
        if not names:
            names = ["小明", "小红", "小刚", "小丽", "小华", "小强", "小芳", "小军"]
        
        # 找一个未使用的名字
        available_names = [name for name in names if name not in self.used_names]
        
        # 如果所有名字都用完了，添加数字后缀
        if not available_names:
            name = f"{names[0]}{self.agent_counter}"
        else:
            import random
            name = random.choice(available_names)
        
        self.used_names.add(name)
        return name
    
    def create_agent(
        self,
        mbti_type: str,
        iq_level: str,
        word: Optional[str] = None,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Agent:
        """
        Create an agent with specified configuration.

        Args:
            mbti_type: MBTI personality type
            iq_level: IQ level (High/Mid/Low)
            word: Assigned word for the game
            agent_id: Optional custom agent ID
            name: Optional agent name (auto-generated if not provided)
            llm_config: Optional model configuration dict

        Returns:
            Configured Agent instance
        """
        if not agent_id:
            self.agent_counter += 1
            agent_id = f"agent_{self.agent_counter}"
        
        # 如果没有提供名字，自动生成
        if not name:
            name = self._generate_name(mbti_type)
        
        config = AgentConfig(
            id=agent_id,
            mbti_type=mbti_type,
            iq_level=iq_level,
            word=word,
            name=name
        )
        
        # Build memory system
        memory_system = AgentMemorySystem(
            agent_id=config.id,
            iq_level=config.iq_level
        )
        
        # Create Agent with optional model config.
        agent = Agent(
            config=config,
            memory_system=memory_system,
            model_config=llm_config
        )

        logger.info(f"Created Agent: {agent.config.id} ({agent.config.name}, {agent.config.mbti_type}, {agent.config.iq_level})")
        if llm_config:
            logger.info(f"  Using custom model: {llm_config.get('provider')}/{llm_config.get('model')}")
        return agent
    
    def create_from_template(
        self,
        template_name: str,
        word: Optional[str] = None,
        agent_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> Agent:
        """
        Create an agent from a predefined template.
        
        Args:
            template_name: Name of the template
            word: Assigned word for the game
            agent_id: Optional custom agent ID
            name: Optional agent name
            
        Returns:
            Configured Agent instance
        """
        if template_name not in self.TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(self.TEMPLATES.keys())}")
        
        template = self.TEMPLATES[template_name]
        return self.create_agent(
            mbti_type=template["mbti_type"],
            iq_level=template["iq_level"],
            word=word,
            agent_id=agent_id,
            name=name
        )
    
    def create_batch(
        self,
        configs: List[Dict[str, str]],
        words: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> List[Agent]:
        """
        Create multiple agents at once.

        Args:
            configs: List of config dicts with mbti_type and iq_level
            words: Optional list of words to assign (must match length of configs)
            llm_config: Optional model configuration dict

        Returns:
            List of Agent instances
        """
        if words and len(words) != len(configs):
            raise ValueError("Number of words must match number of configs")
        
        agents = []
        for i, config in enumerate(configs):
            word = words[i] if words else None
            agent = self.create_agent(
                mbti_type=config["mbti_type"],
                iq_level=config["iq_level"],
                word=word,
                llm_config=llm_config
            )
            agents.append(agent)
        
        logger.info(f"Created batch of {len(agents)} agents")
        return agents
    
    def create_balanced_team(
        self,
        count: int = 6,
        words: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> List[Agent]:
        """
        Create a balanced team with mixed IQ levels and personalities.

        Args:
            count: Number of agents to create
            words: Optional list of words to assign
            llm_config: Optional model configuration dict

        Returns:
            List of Agent instances
        """
        if count < 3:
            raise ValueError("Team must have at least 3 agents")
        
        # Distribute IQ levels
        high_count = count // 3
        low_count = count // 3
        mid_count = count - high_count - low_count
        
        configs = []
        
        # Add high IQ agents
        high_templates = ["strategic_high", "analytical_high"]
        for i in range(high_count):
            template = self.TEMPLATES[high_templates[i % len(high_templates)]]
            configs.append({
                "mbti_type": template["mbti_type"],
                "iq_level": "High"
            })
        
        # Add mid IQ agents
        mid_templates = ["emotional_mid", "social_mid"]
        for i in range(mid_count):
            template = self.TEMPLATES[mid_templates[i % len(mid_templates)]]
            configs.append({
                "mbti_type": template["mbti_type"],
                "iq_level": "Mid"
            })
        
        # Add low IQ agents
        low_templates = ["simple_low", "impulsive_low"]
        for i in range(low_count):
            template = self.TEMPLATES[low_templates[i % len(low_templates)]]
            configs.append({
                "mbti_type": template["mbti_type"],
                "iq_level": "Low"
            })
        
        return self.create_batch(configs, words, llm_config=llm_config)
    
    @staticmethod
    def get_available_templates() -> Dict[str, Dict[str, str]]:
        """Get all available agent templates."""
        return AgentFactory.TEMPLATES.copy()
