"""
Configuration export/import service for sharing game setups.
"""

import json
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging
logger = logging.getLogger(__name__)


class AgentConfigExport(BaseModel):
    """Agent configuration for export."""
    id: str
    mbti_type: str
    iq_level: str
    template: Optional[str] = None


class PersonalityPresetExport(BaseModel):
    """Personality preset for export."""
    mbti_type: str
    traits: str
    speaking_style: str
    thinking_pattern: str


class GameConfigExport(BaseModel):
    """Complete game configuration for export/import."""
    version: str = "1.0.0"
    name: str = Field(..., description="配置名称")
    description: Optional[str] = Field(None, description="配置描述")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Game settings
    agent_count: int = Field(..., ge=3, le=10)
    civilian_word: str
    undercover_word: str
    max_rounds: int = Field(default=10)
    
    # Agent configurations
    agents: List[AgentConfigExport]
    
    # Personality presets (optional, only if customized)
    custom_personalities: Optional[List[PersonalityPresetExport]] = None
    
    # Memory settings
    memory_decay_high: float = Field(default=0.05)
    memory_decay_mid: float = Field(default=0.15)
    memory_decay_low: float = Field(default=0.30)
    memory_cascade_probability: float = Field(default=0.5)
    
    # Model settings (optional)
    model_high_iq: Optional[str] = None
    model_mid_iq: Optional[str] = None
    model_low_iq: Optional[str] = None


class ConfigExportService:
    """Service for exporting and importing game configurations."""
    
    @staticmethod
    def export_config(
        config: Dict[str, Any],
        agents: List[Dict[str, Any]],
        custom_personalities: Optional[List[Dict[str, Any]]] = None,
        name: str = "My Game Config",
        description: Optional[str] = None
    ) -> GameConfigExport:
        """
        Export game configuration.
        
        Args:
            config: Game configuration dict
            agents: List of agent configurations
            custom_personalities: Optional list of custom personality presets
            name: Configuration name
            description: Configuration description
            
        Returns:
            GameConfigExport object
        """
        agent_exports = [
            AgentConfigExport(
                id=agent.get("id", f"agent_{i+1}"),
                mbti_type=agent.get("mbti_type", "ENTJ"),
                iq_level=agent.get("iq_level", "Mid"),
                template=agent.get("template")
            )
            for i, agent in enumerate(agents)
        ]
        
        personality_exports = None
        if custom_personalities:
            personality_exports = [
                PersonalityPresetExport(**p)
                for p in custom_personalities
            ]
        
        export_config = GameConfigExport(
            name=name,
            description=description,
            agent_count=len(agents),
            civilian_word=config.get("civilian_word", "牛奶"),
            undercover_word=config.get("undercover_word", "豆浆"),
            max_rounds=config.get("max_rounds", 10),
            agents=agent_exports,
            custom_personalities=personality_exports,
            memory_decay_high=config.get("memory_decay_high", 0.05),
            memory_decay_mid=config.get("memory_decay_mid", 0.15),
            memory_decay_low=config.get("memory_decay_low", 0.30),
            memory_cascade_probability=config.get("memory_cascade_probability", 0.5),
            model_high_iq=config.get("model_high_iq"),
            model_mid_iq=config.get("model_mid_iq"),
            model_low_iq=config.get("model_low_iq")
        )
        
        logger.info(f"Exported config: {name} with {len(agents)} agents")
        return export_config
    
    @staticmethod
    def export_to_json(export_config: GameConfigExport, pretty: bool = True) -> str:
        """
        Export configuration to JSON string.
        
        Args:
            export_config: Configuration to export
            pretty: Whether to format JSON with indentation
            
        Returns:
            JSON string
        """
        if pretty:
            return export_config.json(indent=2, ensure_ascii=False)
        return export_config.json(ensure_ascii=False)
    
    @staticmethod
    def export_to_yaml(export_config: GameConfigExport) -> str:
        """
        Export configuration to YAML string.
        
        Args:
            export_config: Configuration to export
            
        Returns:
            YAML string
        """
        config_dict = export_config.dict(exclude_none=True)
        return yaml.dump(config_dict, allow_unicode=True, sort_keys=False)
    
    @staticmethod
    def import_from_json(json_str: str) -> GameConfigExport:
        """
        Import configuration from JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            GameConfigExport object
            
        Raises:
            ValueError: If JSON is invalid or doesn't match schema
        """
        try:
            config_dict = json.loads(json_str)
            return GameConfigExport(**config_dict)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise ValueError(f"Failed to import configuration: {e}")
    
    @staticmethod
    def import_from_yaml(yaml_str: str) -> GameConfigExport:
        """
        Import configuration from YAML string.
        
        Args:
            yaml_str: YAML string
            
        Returns:
            GameConfigExport object
            
        Raises:
            ValueError: If YAML is invalid or doesn't match schema
        """
        try:
            config_dict = yaml.safe_load(yaml_str)
            return GameConfigExport(**config_dict)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise ValueError(f"Failed to import configuration: {e}")
    
    @staticmethod
    def validate_config(export_config: GameConfigExport) -> Dict[str, Any]:
        """
        Validate imported configuration.
        
        Args:
            export_config: Configuration to validate
            
        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        
        # Check agent count
        if len(export_config.agents) != export_config.agent_count:
            issues.append(f"Agent count mismatch: declared {export_config.agent_count}, found {len(export_config.agents)}")
        
        # Check for duplicate agent IDs
        agent_ids = [a.id for a in export_config.agents]
        if len(agent_ids) != len(set(agent_ids)):
            issues.append("Duplicate agent IDs found")
        
        # Check MBTI types
        valid_mbti = [
            "INTJ", "INTP", "ENTJ", "ENTP",
            "INFJ", "INFP", "ENFJ", "ENFP",
            "ISTJ", "ISFJ", "ESTJ", "ESFJ",
            "ISTP", "ISFP", "ESTP", "ESFP"
        ]
        for agent in export_config.agents:
            if agent.mbti_type not in valid_mbti:
                issues.append(f"Invalid MBTI type for {agent.id}: {agent.mbti_type}")
        
        # Check IQ levels
        valid_iq = ["High", "Mid", "Low"]
        for agent in export_config.agents:
            if agent.iq_level not in valid_iq:
                issues.append(f"Invalid IQ level for {agent.id}: {agent.iq_level}")
        
        # Check words
        if export_config.civilian_word == export_config.undercover_word:
            warnings.append("Civilian and undercover words are the same")
        
        # Check memory decay values
        if not (0 <= export_config.memory_decay_high <= 1):
            issues.append(f"Invalid memory_decay_high: {export_config.memory_decay_high}")
        if not (0 <= export_config.memory_decay_mid <= 1):
            issues.append(f"Invalid memory_decay_mid: {export_config.memory_decay_mid}")
        if not (0 <= export_config.memory_decay_low <= 1):
            issues.append(f"Invalid memory_decay_low: {export_config.memory_decay_low}")
        
        is_valid = len(issues) == 0
        
        return {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings
        }
    
    @staticmethod
    def get_example_config() -> GameConfigExport:
        """
        Get an example configuration.
        
        Returns:
            Example GameConfigExport
        """
        return GameConfigExport(
            name="经典6人局",
            description="平衡的6人游戏配置，包含不同IQ等级和MBTI类型",
            agent_count=6,
            civilian_word="牛奶",
            undercover_word="豆浆",
            max_rounds=10,
            agents=[
                AgentConfigExport(id="agent_1", mbti_type="ENTJ", iq_level="High", template="strategic_high"),
                AgentConfigExport(id="agent_2", mbti_type="INTJ", iq_level="High", template="analytical_high"),
                AgentConfigExport(id="agent_3", mbti_type="ENFP", iq_level="Mid", template="emotional_mid"),
                AgentConfigExport(id="agent_4", mbti_type="ISFJ", iq_level="Mid", template="social_mid"),
                AgentConfigExport(id="agent_5", mbti_type="ISTP", iq_level="Low", template="simple_low"),
                AgentConfigExport(id="agent_6", mbti_type="ESFP", iq_level="Low", template="impulsive_low"),
            ]
        )
