"""
Profession Generator Service for dynamically generating modern professions.

动态职业生成服务
"""

import json
import logging
import asyncio
from typing import Dict, Optional, Any

from models.character import Character, GeneratedProfession
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ProfessionGeneratorService:
    """现代职业生成服务"""
    
    def __init__(self, llm_service=None):
        """
        初始化职业生成服务
        
        Args:
            llm_service: LLM 服务实例（可选，如果不提供则使用默认）
        """
        self.llm_service = llm_service or LLMService()
        self.cache: Dict[str, GeneratedProfession] = {}
        # Character profession generation is optional, so we keep a bounded timeout,
        # but it needs to tolerate slower local models.
        self.generation_timeout = 20.0
    
    async def generate_profession(
        self,
        character: Character,
        topic: str,
        use_cache: bool = True,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> GeneratedProfession:
        """
        为角色生成现代职业
        
        Args:
            character: 角色信息
            topic: 讨论话题
            use_cache: 是否使用缓存
            
        Returns:
            GeneratedProfession: 生成的职业信息
        """
        # Check cache
        cache_key = f"{character.id}_{topic}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using cached profession for {character.name} on topic '{topic}'")
            return self.cache[cache_key]
        
        try:
            logger.info(
                "Profession generation start: character=%s timeout=%s instance=%s model=%s",
                character.name,
                self.generation_timeout,
                hex(id(self)),
                (model_config or {}).get("model", "default"),
            )
            # Generate profession with timeout
            profession = await asyncio.wait_for(
                self._generate_profession_internal(character, topic, model_config=model_config),
                timeout=self.generation_timeout
            )
            
            # Cache result
            self.cache[cache_key] = profession
            
            logger.info(f"Generated profession for {character.name}: {profession.profession_name}")
            return profession
            
        except asyncio.TimeoutError:
            logger.warning(f"Profession generation timeout for {character.name}, using fallback")
            return self._get_fallback_profession(character, topic)
        except Exception as e:
            logger.error(f"Failed to generate profession for {character.name}: {e}")
            return self._get_fallback_profession(character, topic)
    
    async def _generate_profession_internal(
        self,
        character: Character,
        topic: str,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> GeneratedProfession:
        """内部职业生成方法"""
        # Build prompt
        prompt = self._build_profession_prompt(character, topic)
        
        response = await self.llm_service.generate(
            prompt=prompt,
            temperature=0.8,
            max_tokens=500,
            model_config=model_config,
        )
        
        # Parse JSON response
        profession = self._parse_profession_response(response)
        
        return profession
    
    def _build_profession_prompt(
        self,
        character: Character,
        topic: str
    ) -> str:
        """构建职业生成提示词"""
        return f"""你是一个创意职业设计师。请为以下角色设计一个创意幽默且符合人设的现代职业。

角色信息：
- 名字：{character.name}
- 原始时代：{character.original_era}
- 背景故事：{character.background_story}
- 性格特征：{character.personality_traits}
- 标志性事件：{character.signature_events}
- 说话风格：{character.speaking_style}

讨论话题：{topic}

要求：
1. 职业必须创意幽默，让人眼前一亮
2. 职业必须符合角色的性格和背景
3. 职业必须能帮助角色理解和讨论现代话题
4. 职业描述要包含工作环境和日常
5. 要体现角色"穿越"到现代的有趣对比

请以 JSON 格式输出：
{{
  "profession_name": "职业名称（创意且符合人设）",
  "workplace": "工作地点/环境",
  "daily_work": "日常工作描述（50-100字）",
  "connection_to_past": "与原始故事的联系",
  "relevance_to_topic": "如何帮助理解讨论话题"
}}

示例（仅供参考，不要照抄）：
- 孙悟空讨论"AI伦理" → AI系统压力测试工程师，花果山科技公司
- 诸葛亮讨论"环保" → 智慧城市规划师，卧龙环保咨询公司
- 林黛玉讨论"社交媒体" → 情感博主，潇湘文化工作室

只输出 JSON，不要有其他内容！"""
    
    def _parse_profession_response(self, response: str) -> GeneratedProfession:
        """解析 LLM 响应"""
        try:
            # Try to extract JSON from response
            json_str = self._extract_json_from_text(response)
            
            if not json_str:
                raise ValueError("No valid JSON found in response")
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Validate required fields
            required_fields = [
                "profession_name",
                "workplace",
                "daily_work",
                "connection_to_past",
                "relevance_to_topic"
            ]
            
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Create GeneratedProfession
            profession = GeneratedProfession(**data)
            
            return profession
            
        except Exception as e:
            logger.error(f"Failed to parse profession response: {e}")
            logger.error(f"Response was: {response[:200]}")
            raise
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Try to find JSON object
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            return text[start_idx:end_idx + 1]
        
        return None
    
    def _get_fallback_profession(
        self,
        character: Character,
        topic: str
    ) -> GeneratedProfession:
        """获取后备职业（生成失败时使用）"""
        logger.info(f"Using fallback profession for {character.name}")
        
        # Simple rule-based fallback based on character source
        profession_map = {
            "神话传说": ("神话顾问", "文化创意公司", "将古代神话故事改编成现代内容"),
            "历史人物": ("历史文化顾问", "文化传播机构", "用历史智慧解读现代问题"),
            "古典文学": ("文学顾问", "文化工作室", "将古典文学精神应用于现代生活"),
        }
        
        # Find matching profession type
        profession_type = None
        for key in profession_map.keys():
            if key in character.source:
                profession_type = key
                break
        
        if not profession_type:
            profession_type = "历史人物"
        
        base_name, base_workplace, base_work = profession_map[profession_type]
        
        return GeneratedProfession(
            profession_name=f"{base_name}（{character.name}）",
            workplace=base_workplace,
            daily_work=f"{base_work}，运用{character.name}的特长和经验。",
            connection_to_past=f"延续{character.name}在{character.original_era}的传统和智慧。",
            relevance_to_topic=f"从{character.name}的独特视角参与关于'{topic}'的讨论。"
        )
    
    async def generate_professions_batch(
        self,
        characters: list[Character],
        topic: str,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> list[GeneratedProfession]:
        """
        批量生成职业（并发）
        
        Args:
            characters: 角色列表
            topic: 讨论话题
            
        Returns:
            List[GeneratedProfession]: 生成的职业列表
        """
        logger.info(
            "Generating professions for %s characters on topic '%s' with timeout=%s instance=%s",
            len(characters),
            topic,
            self.generation_timeout,
            hex(id(self)),
        )
        
        # Create tasks for concurrent generation
        tasks = [
            self.generate_profession(char, topic, model_config=model_config)
            for char in characters
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        professions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to generate profession for {characters[i].name}: {result}")
                # Use fallback
                professions.append(self._get_fallback_profession(characters[i], topic))
            else:
                professions.append(result)
        
        logger.info(f"Successfully generated {len(professions)} professions")
        return professions
    
    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        logger.info("Profession cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            "cache_size": len(self.cache),
            "cached_items": list(self.cache.keys())
        }


# Global profession generator instance
_profession_generator: Optional[ProfessionGeneratorService] = None


def get_profession_generator() -> ProfessionGeneratorService:
    """获取全局职业生成器实例"""
    global _profession_generator
    if _profession_generator is None:
        _profession_generator = ProfessionGeneratorService()
    return _profession_generator
