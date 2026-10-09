"""
Discussion mode API endpoints.
自由讨论模式 API 端点
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)

from models.discussion import DiscussionConfig, Discussion, DiscussionStatus
from services.discussion_service import DiscussionService
from services.agent_factory import AgentFactory
from services.discussion_factory import DiscussionFactory
from services.character_service import get_character_service

router = APIRouter(prefix="/api/discussion", tags=["discussion"])

# 全局状态
active_discussions: Dict[str, DiscussionService] = {}


class CreateDiscussionRequest(BaseModel):
    topic: str
    agent_count: int = 6
    use_balanced_team: bool = True
    max_rounds: Optional[int] = None
    agents: List[Dict[str, str]] = []
    # 角色系统
    use_characters: bool = False  # 是否使用角色系统
    # 模型配置 (新格式：统一的 llm_config 对象)
    llm_config: Optional[Dict[str, str]] = None
    # 主题角色阵容（名字+MBTI+性别绑定），三游戏统一
    roster: Optional[List[Dict[str, Any]]] = None
    roster_work: Optional[str] = None
    # 智能模型分配（按 IQ 分档）
    auto_assign: Optional[Dict[str, Any]] = None


class UserSpeakRequest(BaseModel):
    discussion_id: str
    speech: str
    mention_agents: List[str] = []


class DiscussionActionRequest(BaseModel):
    discussion_id: str


class GenerateTopicRequest(BaseModel):
    """LLM 生成讨论话题请求。"""
    hint: str = Field("", max_length=100, description="可选的话题方向提示，如 科技 / 生活 / 教育")
    model_config_data: Optional[Dict[str, Any]] = Field(None, description="用于生成的模型配置")


@router.post("/generate-topic")
async def generate_topic(request: GenerateTopicRequest):
    """LLM 生成一个辩论/讨论话题，避免玩家面对空白话题无从开始。"""
    from services.llm_service import LLMService

    llm = LLMService()
    hint = (request.hint or "").strip()
    prompt = (
        "请为一个多人 AI 辩论会想一个有趣、有争议性、适合多个角色轮流发言的话题。\n"
        + (f"方向提示：{hint}\n" if hint else "")
        + "要求：\n"
        "1. 一句话命题，15-30 个字，中文；可以是「该不该 / 是不是 / 谁更」式的争议命题。\n"
        "2. 有明显的正反两面，能引发争论，不要有标准答案。\n"
        "3. 面向大众，不要过于小众或专业。\n"
        '只输出 JSON：{"topic": "..."}，不要解释。'
    )
    try:
        raw = await llm.generate(
            prompt,
            temperature=0.9,
            max_tokens=120,
            model_config=request.model_config_data,
            json_mode=True,
            session_id=f"topic:{uuid.uuid4().hex[:6]}",
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"模型未返回 JSON: {raw[:120]}")
        topic = str(json.loads(raw[start:end + 1]).get("topic") or "").strip().strip('"')
        if not topic:
            raise ValueError("话题为空")
        return {"success": True, "topic": topic}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Generate topic failed: %s", exc)
        raise HTTPException(400, f"话题生成失败: {exc}")


@router.post("/create")
async def create_discussion(request: CreateDiscussionRequest):
    """创建讨论会话"""
    try:
        discussion_id = f"disc_{uuid.uuid4().hex[:8]}"

        # 使用新的统一 llm_config 格式
        llm_config = request.llm_config
        if llm_config:
            logger.info(f"Using custom model config: {llm_config.get('model')}")

        # 使用 DiscussionFactory 创建讨论（支持角色系统）
        if request.use_characters:
            logger.info(f"Creating discussion with character system: {request.topic}")
            discussion_factory = DiscussionFactory()
            
            # Generate balanced MBTI list from available characters
            char_service = get_character_service()
            available_mbti = list(char_service.get_mbti_distribution().keys())
            
            # Use available MBTI types, cycling if needed
            mbti_list = []
            for i in range(request.agent_count):
                mbti_list.append(available_mbti[i % len(available_mbti)])
            
            logger.info(f"Using MBTI list: {mbti_list}")
            
            discussion, service = await discussion_factory.create_discussion_with_characters(
                topic=request.topic,
                agent_count=request.agent_count,
                mbti_list=mbti_list,
                model_config=llm_config
            )

            # 三游戏统一：主题阵容覆盖 + 智能模型分配（按 IQ 分档）
            created_agents = list(service.agents.values())
            if request.roster:
                from services.auto_assign import apply_roster, normalize_roster
                apply_roster(created_agents, normalize_roster(request.roster))
            if request.auto_assign:
                from services.auto_assign import apply_auto_assign, iq_tier_of
                apply_auto_assign(created_agents, request.auto_assign, llm_config, iq_tier_of)

            # Override discussion ID
            discussion.id = discussion_id
            service.discussion.id = discussion_id
            
            # Get character information for response
            characters_info = []
            if hasattr(service, 'characters') and service.characters:
                # service.agents is a dict, get the list of agents
                agent_list = list(service.agents.values())
                char_list = list(service.characters.values())
                
                for agent, char_with_prof in zip(agent_list, char_list):
                    characters_info.append({
                        "agent_id": agent.config.id,
                        "agent_name": agent.config.name,
                        "character": {
                            "id": char_with_prof.character.id,
                            "name": char_with_prof.character.name,
                            "mbti_type": char_with_prof.character.mbti,
                            "source": char_with_prof.character.source,
                            "avatar_url": char_with_prof.character.avatar_url
                        },
                        "profession": {
                            "title": char_with_prof.profession.profession_name,
                            "description": char_with_prof.profession.daily_work
                        }
                    })
        else:
            # 不使用角色系统，使用原有逻辑
            logger.info(f"Creating discussion without characters: {request.topic}")
            factory = AgentFactory()
            
            if request.use_balanced_team:
                agents = factory.create_balanced_team(request.agent_count, llm_config=llm_config)
            else:
                agents = factory.create_batch(request.agents, llm_config=llm_config)

            # 三游戏统一：主题阵容覆盖 + 智能模型分配（按 IQ 分档）
            if request.roster:
                from services.auto_assign import apply_roster, normalize_roster
                apply_roster(agents, normalize_roster(request.roster))
            if request.auto_assign:
                from services.auto_assign import apply_auto_assign, iq_tier_of
                apply_auto_assign(agents, request.auto_assign, llm_config, iq_tier_of)
            
            # 创建讨论对象
            discussion = Discussion(
                id=discussion_id,
                topic=request.topic,
                agents=[],  # Will be populated later
                status=DiscussionStatus.CREATED
            )
            
            # 创建讨论服务
            service = DiscussionService(discussion, agents)
            
            # Update discussion with agent dicts
            discussion.agents = [agent.to_dict() for agent in agents]
            
            characters_info = None
        
        # 保存到全局状态
        active_discussions[discussion_id] = service
        
        logger.info(f"Created discussion {discussion_id}: {request.topic}")
        
        # Get agent list from service (service.agents is a dict)
        agent_list = list(service.agents.values())
        
        response = {
            "discussion_id": discussion_id,
            "topic": request.topic,
            "agents": [agent.to_dict() for agent in agent_list],
            "status": service.discussion.status.value,
            "llm_config": llm_config if llm_config else "default",
            "use_characters": request.use_characters
        }
        
        # 如果使用角色系统，添加角色信息
        if request.use_characters and characters_info:
            response["characters"] = characters_info
        
        return response
    
    except Exception as e:
        logger.error(f"Failed to create discussion: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to create discussion: {str(e)}")


@router.post("/start")
async def start_discussion(request: DiscussionActionRequest):
    """开始讨论（激活状态）"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[request.discussion_id]
    service.discussion.status = DiscussionStatus.ACTIVE
    service.discussion.current_round = 1
    
    return {"success": True, "status": "active"}


@router.get("/stream/{discussion_id}")
async def stream_discussion(discussion_id: str):
    """流式输出讨论过程"""
    if discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[discussion_id]
    
    async def event_generator():
        """生成 SSE 事件流"""
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'discussion_start', 'topic': service.discussion.topic})}\n\n"
            
            # 持续让 agents 轮流发言
            while not service.is_ended:
                if service.is_paused:
                    await asyncio.sleep(1)
                    continue
                
                # 获取存活的 agents
                alive_agents = service.get_alive_agents()
                if not alive_agents:
                    break
                
                # 轮流让每个 agent 发言
                for agent in alive_agents:
                    if service.is_paused or service.is_ended:
                        break
                    
                    # 发送思考事件
                    yield f"data: {json.dumps({'type': 'agent_thinking', 'agent_id': agent.config.id, 'agent_name': agent.config.name or agent.config.id})}\n\n"
                    
                    # Agent 发言
                    try:
                        response = await service.agent_discuss(agent.config.id)
                        
                        # 发送发言事件
                        yield f"data: {json.dumps({'type': 'agent_speaking', **response})}\n\n"
                        
                    except Exception as e:
                        logger.error(f"Agent {agent.config.id} discussion failed: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'agent_id': agent.config.id, 'message': str(e)})}\n\n"
                    
                    # 短暂延迟
                    await asyncio.sleep(0.5)
                
                # 一轮结束
                service.discussion.current_round += 1
                yield f"data: {json.dumps({'type': 'round_complete', 'round': service.discussion.current_round - 1})}\n\n"
                
                # 检查是否达到最大轮数
                if service.discussion.current_round > 100:  # 防止无限循环
                    service.end()
                    break
            
            # 发送结束事件
            yield f"data: {json.dumps({'type': 'discussion_end'})}\n\n"
        
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/possess")
async def possess_agent(request: DiscussionActionRequest, agent_id: str):
    """夺席：玩家接管某个 AI 角色。被接管的角色不再自动发言，玩家可通过
    user_speak 代其发言。"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    service = active_discussions[request.discussion_id]
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent not found: {agent_id}")
    agent.is_possessed = True
    return {"success": True, "agent_id": agent_id, "is_possessed": True}


@router.post("/release")
async def release_agent(request: DiscussionActionRequest, agent_id: str):
    """释放夺席：归还角色给 AI。"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    service = active_discussions[request.discussion_id]
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent not found: {agent_id}")
    agent.is_possessed = False
    return {"success": True, "agent_id": agent_id, "is_possessed": False}


@router.post("/user-speak")
async def user_speak(request: UserSpeakRequest):
    """用户发言"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[request.discussion_id]
    
    try:
        message = service.user_speak(request.speech, request.mention_agents)
        return {
            "success": True,
            "message_id": message.id,
            "timestamp": message.timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"User speak failed: {e}")
        raise HTTPException(500, f"Failed to process user speech: {str(e)}")


@router.post("/pause")
async def pause_discussion(request: DiscussionActionRequest):
    """暂停讨论"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[request.discussion_id]
    service.pause()
    
    return {"success": True, "status": "paused"}


@router.post("/resume")
async def resume_discussion(request: DiscussionActionRequest):
    """继续讨论"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[request.discussion_id]
    service.resume()
    
    return {"success": True, "status": "active"}


@router.post("/end")
async def end_discussion(request: DiscussionActionRequest):
    """结束讨论"""
    if request.discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[request.discussion_id]
    service.end()
    
    return {"success": True, "status": "ended"}


@router.get("/{discussion_id}")
async def get_discussion(discussion_id: str):
    """获取讨论详情"""
    if discussion_id not in active_discussions:
        raise HTTPException(404, "Discussion not found")
    
    service = active_discussions[discussion_id]
    
    return {
        "discussion": service.discussion.dict(),
        "is_paused": service.is_paused,
        "is_ended": service.is_ended
    }
