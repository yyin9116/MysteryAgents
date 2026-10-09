"""
Character Prompt Builder for creating deep cosplay mode prompts.

角色扮演提示词构建器
"""

import logging
from datetime import datetime
from typing import Optional

from models.character import Character, GeneratedProfession
from services import prompt_registry

logger = logging.getLogger(__name__)


class CharacterPromptBuilder:
    """角色扮演提示词构建器"""

    @staticmethod
    def build_character_cosplay_prompt(
        character: Character,
        profession: GeneratedProfession,
        topic: str,
        iq_level: str = "Mid"
    ) -> str:
        """
        构建深度角色扮演提示词（模板来自 prompt_registry，可经提示词管理界面自定义）

        Args:
            character: 角色信息
            profession: 动态生成的职业
            topic: 讨论话题
            iq_level: IQ 等级 (High/Mid/Low)

        Returns:
            str: 完整的角色扮演提示词
        """
        # 根据 IQ 级别设置发言长度指导
        if iq_level == "High":
            speech_length_guide = "300-500字，深入分析，引用具体案例、数据或理论"
            depth_guide = "进行多层次分析，考虑历史背景、现实影响、未来趋势，引用具体例子"
        elif iq_level == "Mid":
            speech_length_guide = "200-300字，结合个人经验和常识，逻辑清晰"
            depth_guide = "结合实际生活经验，用通俗易懂的方式表达观点，可以举例说明"
        else:  # Low
            speech_length_guide = "100-200字，简单直接，基于直觉"
            depth_guide = "用简单直白的语言表达想法，可以基于个人感受和直觉"

        # 构建名言列表
        quotes_list = character.famous_quotes.split("|")
        quotes_formatted = "\n".join([f"  - 「{q.strip()}」" for q in quotes_list if q.strip()])

        return prompt_registry.render("debate_cosplay_prompt", {
            "character_name": character.name,
            "original_era": character.original_era,
            "source": character.source,
            "background_story": character.background_story,
            "signature_events": character.signature_events,
            "signature_event_first": character.signature_events.split("、")[0] if character.signature_events else "",
            "quotes_formatted": quotes_formatted,
            "current_year": str(datetime.now().year),
            "profession_name": profession.profession_name,
            "workplace": profession.workplace,
            "daily_work": profession.daily_work,
            "connection_to_past": profession.connection_to_past,
            "relevance_to_topic": profession.relevance_to_topic,
            "personality_traits": character.personality_traits,
            "speaking_style": character.speaking_style,
            "modern_perspective": character.modern_perspective,
            "topic": topic,
            "speech_length_guide": speech_length_guide,
            "depth_guide": depth_guide,
        })

    @staticmethod
    def build_character_introduction(
        character: Character,
        profession: GeneratedProfession
    ) -> str:
        """
        构建角色自我介绍

        Args:
            character: 角色信息
            profession: 职业信息

        Returns:
            str: 自我介绍文本
        """
        intro = f"""大家好，我是{character.name}！

我来自{character.original_era}，{character.background_story[:100]}...

现在我在现代社会做{profession.profession_name}，工作地点是{profession.workplace}。

我的性格嘛，{character.personality_traits.split('、')[0]}、{character.personality_traits.split('、')[1]}，说话比较{character.speaking_style.split('，')[0]}。

很高兴和大家一起讨论！"""

        return intro

    @staticmethod
    def build_short_character_context(
        character: Character,
        profession: GeneratedProfession
    ) -> str:
        """
        构建简短的角色上下文（用于系统消息）

        Args:
            character: 角色信息
            profession: 职业信息

        Returns:
            str: 简短上下文
        """
        return f"""你是{character.name}（{character.source}），现在是{profession.profession_name}。
性格：{character.personality_traits}
说话风格：{character.speaking_style}
记住：你就是{character.name}，用你的方式说话和思考！"""


# Global prompt builder instance
_prompt_builder: Optional[CharacterPromptBuilder] = None


def get_character_prompt_builder() -> CharacterPromptBuilder:
    """获取全局提示词构建器实例"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = CharacterPromptBuilder()
    return _prompt_builder
