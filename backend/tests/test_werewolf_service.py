"""
Unit tests for werewolf service.
测试狼人杀游戏核心逻辑
"""

import pytest
from models.agent import Agent
from services.agent_factory import AgentFactory
from services.werewolf_service import WerewolfService
from models.werewolf import (
    WerewolfRole, WerewolfFaction, WerewolfPhase, NightActionType,
    ROLE_DISTRIBUTION
)


class TestWerewolfService:
    """Test werewolf game service."""

    def test_create_game_6_players(self):
        """Test creating a 6-player game."""
        game = WerewolfService(game_id="test_6", player_count=6)

        assert game.game_id == "test_6"
        assert game.player_count == 6
        assert len(game.state.agents) == 6
        assert game.state.phase == WerewolfPhase.NIGHT
        assert game.state.current_round == 1

        # Check role distribution
        roles = [agent.role for agent in game.state.agents.values()]
        expected_dist = ROLE_DISTRIBUTION[6]

        for role, count in expected_dist.items():
            assert roles.count(role) == count

    def test_agent_factory_prefers_character_names(self):
        """Agent factory should reuse historical/myth character names when available."""
        factory = AgentFactory()
        generated = {factory._generate_name("ENTP"), factory._generate_name("INTJ")}

        assert "孙悟空" in generated or "诸葛亮" in generated

    def test_build_personality_profile_includes_distinctive_and_iq_guidance(self):
        """Prompt profile should include both persona fingerprint and IQ guidance."""
        profile = WerewolfService._build_personality_profile("INTJ", "High")

        assert "人设原型" in profile
        assert "语言习惯" in profile
        assert "禁止滑向" in profile
        assert "IQ 表达层次" in profile

    def test_discussion_prompt_forbids_generic_template_language(self):
        """Discussion prompt should explicitly discourage generic placeholder speech."""
        game = WerewolfService(game_id="test_discussion_prompt", player_count=6)
        speaker = next(iter(game.state.agents.values()))

        prompt = game._build_discussion_prompt(speaker)

        assert "禁止使用泛化模板" in prompt
        assert "鲜明的个人语言动作" in prompt
        assert "私密思考边界" in prompt
        assert "公开发言可以伪装" in prompt
        assert "已知事实" in prompt
        assert "个人推测" in prompt

    def test_private_knowledge_rules_for_good_role_forbid_wolf_view(self):
        """Good roles should be explicitly forbidden from using wolf-private perspective."""
        game = WerewolfService(game_id="test_private_knowledge", player_count=6)
        villager = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.VILLAGER)

        rules = game._build_private_knowledge_rules(villager)

        assert "你是好人阵营" in rules
        assert "狼队策略" in rules
        assert "我的狼人同伴" in rules
        assert "只剩我和提利昂两个狼人" in rules
        assert "狼队昨晚杀预言家是合理策略" in rules

    def test_sanitize_role_consistent_thought_replaces_impossible_identity_claim(self):
        """Thoughts that contradict the agent's true role should be neutralized."""
        game = WerewolfService(game_id="test_role_consistency", player_count=6)
        villager = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.VILLAGER)

        sanitized = game._sanitize_role_consistent_thought(
            villager,
            "作为狼人，我要继续伪装并保护我的狼人同伴。",
        )

        assert "作为狼人" not in sanitized
        assert "真实身份" in sanitized

    def test_sanitize_role_consistent_thought_replaces_good_role_wolf_team_claim(self):
        """Good-role thoughts should not be allowed to claim wolf-team private knowledge."""
        game = WerewolfService(game_id="test_role_private_leak", player_count=9)
        guard = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.GUARD)

        sanitized = game._sanitize_role_consistent_thought(
            guard,
            "作为守卫，我昨晚守了甘道夫，诸葛亮和孙悟空是狼队同伴，只剩我和提利昂两个狼人。",
        )

        assert "狼队同伴" not in sanitized
        assert "只剩我和提利昂两个狼人" not in sanitized
        assert "真实身份" in sanitized

    def test_sanitize_role_consistent_thought_replaces_good_role_claim_about_wolf_strategy_as_fact(self):
        """Good-role thoughts should not narrate wolf strategy as if privately known."""
        game = WerewolfService(game_id="test_role_strategy_leak", player_count=9)
        witch = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.WITCH)

        sanitized = game._sanitize_role_consistent_thought(
            witch,
            "作为女巫，我知道诸葛亮作为狼人同伴在引导注意力，狼队昨晚杀预言家是合理策略，这对狼队有利。",
        )

        assert "狼人同伴在引导" not in sanitized
        assert "狼队昨晚" not in sanitized
        assert "对狼队有利" not in sanitized
        assert "真实身份" in sanitized

    def test_agent_factory_fallback_names_are_not_trait_placeholders(self):
        """Fallback names should use recognizable characters rather than adjective-style placeholders."""
        factory = AgentFactory()
        generated = factory.NAMES_BY_PERSONALITY["ISFJ"] + factory.NAMES_BY_PERSONALITY["INTP"]

        assert "江细心" not in generated
        assert "邓分析" not in generated
        assert "美国队长" in generated or "爱因斯坦" in generated

    def test_create_game_12_players(self):
        """Test creating a 12-player game."""
        game = WerewolfService(game_id="test_12", player_count=12)

        assert game.player_count == 12
        assert len(game.state.agents) == 12

        # Check role distribution
        roles = [agent.role for agent in game.state.agents.values()]
        expected_dist = ROLE_DISTRIBUTION[12]

        for role, count in expected_dist.items():
            assert roles.count(role) == count

    def test_invalid_player_count(self):
        """Test that invalid player counts raise error."""
        with pytest.raises(ValueError):
            WerewolfService(game_id="test_invalid", player_count=5)

        with pytest.raises(ValueError):
            WerewolfService(game_id="test_invalid", player_count=13)

    def test_get_alive_agents(self):
        """Test getting alive agents."""
        game = WerewolfService(game_id="test_alive", player_count=6)

        alive = game.get_alive_agents()
        assert len(alive) == 6

        # Kill one agent
        first_agent_id = list(game.state.agents.keys())[0]
        game.state.agents[first_agent_id].is_alive = False

        alive = game.get_alive_agents()
        assert len(alive) == 5

    def test_get_alive_werewolves(self):
        """Test getting alive werewolves."""
        game = WerewolfService(game_id="test_wolves", player_count=6)

        werewolves = game.get_alive_werewolves()
        assert len(werewolves) == 2  # 6-player game has 2 werewolves

        # Kill one werewolf
        werewolf_id = werewolves[0].agent_id
        game.state.agents[werewolf_id].is_alive = False

        werewolves = game.get_alive_werewolves()
        assert len(werewolves) == 1

    def test_werewolf_kill(self):
        """Test werewolf kill action."""
        game = WerewolfService(game_id="test_kill", player_count=6)

        # Find werewolf and target
        werewolf = game.get_alive_werewolves()[0]
        good_players = game.get_alive_good_players()
        target = good_players[0]

        # Execute kill
        result = game.werewolf_kill(werewolf.agent_id, target.agent_id)

        assert result["success"] is True
        assert game.state.werewolf_kill_target == target.agent_id
        assert len(game.state.night_actions) == 1
        assert game.state.night_actions[0].action_type == NightActionType.WEREWOLF_KILL

    def test_werewolf_cannot_kill_werewolf(self):
        """Test that werewolves cannot kill each other."""
        game = WerewolfService(game_id="test_no_friendly_fire", player_count=6)

        werewolves = game.get_alive_werewolves()
        werewolf1 = werewolves[0]
        werewolf2 = werewolves[1]

        with pytest.raises(ValueError, match="Werewolves cannot kill each other"):
            game.werewolf_kill(werewolf1.agent_id, werewolf2.agent_id)

    def test_seer_check(self):
        """Test seer check action."""
        game = WerewolfService(game_id="test_seer", player_count=6)

        # Find seer
        seer = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.SEER:
                seer = agent
                break

        assert seer is not None

        # Find a werewolf to check
        werewolf = game.get_alive_werewolves()[0]

        # Execute check
        result = game.seer_check(seer.agent_id, werewolf.agent_id)

        assert result["success"] is True
        assert result["is_werewolf"] is True
        assert result["faction"] == WerewolfFaction.WEREWOLF.value
        assert werewolf.agent_id in seer.seer_checked_ids
        assert seer.seer_check_results[werewolf.agent_id] == WerewolfFaction.WEREWOLF

    def test_seer_cannot_check_twice(self):
        """Test that seer cannot check the same player twice."""
        game = WerewolfService(game_id="test_seer_twice", player_count=6)

        # Find seer and target
        seer = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.SEER:
                seer = agent
                break

        target = next(
            agent for agent in game.get_alive_good_players()
            if agent.agent_id != seer.agent_id
        )

        # First check
        game.seer_check(seer.agent_id, target.agent_id)

        # Second check should fail
        with pytest.raises(ValueError, match="already checked"):
            game.seer_check(seer.agent_id, target.agent_id)

    def test_witch_save(self):
        """Test witch save action."""
        game = WerewolfService(game_id="test_witch_save", player_count=6)

        # Find witch
        witch = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.WITCH:
                witch = agent
                break

        assert witch is not None
        assert witch.witch_potions.antidote is True

        # Set up a kill target
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        # Witch saves
        result = game.witch_save(witch.agent_id, target.agent_id)

        assert result["success"] is True
        assert witch.witch_potions.antidote is False

    def test_witch_cannot_save_twice(self):
        """Test that witch can only use antidote once."""
        game = WerewolfService(game_id="test_witch_once", player_count=6)

        # Find witch
        witch = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.WITCH:
                witch = agent
                break

        # Use antidote
        witch.witch_potions.antidote = False

        # Try to save
        target = game.get_alive_good_players()[0]
        game.state.werewolf_kill_target = target.agent_id

        with pytest.raises(ValueError, match="already used antidote"):
            game.witch_save(witch.agent_id, target.agent_id)

    def test_witch_poison(self):
        """Test witch poison action."""
        game = WerewolfService(game_id="test_witch_poison", player_count=6)

        # Find witch
        witch = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.WITCH:
                witch = agent
                break

        assert witch.witch_potions.poison is True

        # Poison a werewolf
        werewolf = game.get_alive_werewolves()[0]
        result = game.witch_poison(witch.agent_id, werewolf.agent_id)

        assert result["success"] is True
        assert witch.witch_potions.poison is False

    def test_guard_protect(self):
        """Test guard protect action."""
        game = WerewolfService(game_id="test_guard", player_count=8)

        # Find guard
        guard = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.GUARD:
                guard = agent
                break

        assert guard is not None

        # Protect someone
        target = game.get_alive_good_players()[0]
        result = game.guard_protect(guard.agent_id, target.agent_id)

        assert result["success"] is True
        assert guard.guard_last_protected == target.agent_id

    def test_guard_cannot_protect_same_twice(self):
        """Test that guard cannot protect same person two nights in a row."""
        game = WerewolfService(game_id="test_guard_rule", player_count=8)

        # Find guard
        guard = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.GUARD:
                guard = agent
                break

        # Protect someone
        target = game.get_alive_good_players()[0]
        game.guard_protect(guard.agent_id, target.agent_id)

        # Try to protect same person again
        with pytest.raises(ValueError, match="cannot protect the same person"):
            game.guard_protect(guard.agent_id, target.agent_id)

    @pytest.mark.asyncio
    async def test_run_discussion_turn_records_llm_speech(self, monkeypatch):
        """Discussion turn should record actual generated speech."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_generate_description(self, system_prompt, conversation_history, current_round):
            return {
                "thought": "我怀疑发言最激进的人。",
                "speech": f"{self.config.name} 觉得今天应该先看投票站位。",
                "suspicion": {"werewolf_agent_2": 6},
            }

        monkeypatch.setattr(Agent, "generate_description", fake_generate_description)

        game = WerewolfService(game_id="test_discussion_turn", player_count=6)
        game.start_discussion_phase()
        speaker_id = game.get_alive_agents()[0].agent_id

        result = await game.run_discussion_turn(speaker_id)

        assert result["type"] == "discussion"
        assert "应该先看投票站位" in result["content"]
        assert result["suspicion"] == {"werewolf_agent_2": 6}
        assert game.state.conversation_history[-1]["content"] == result["content"]

    def test_get_discussion_agents_for_round_respects_fast_mode_limit(self):
        game = WerewolfService(
            game_id="test_fast_discussion_limit",
            player_count=6,
            game_config={"fast_mode": True, "discussion_turn_limit": 2},
        )

        agents = game.get_discussion_agents_for_round()

        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_run_voting_turn_records_llm_vote(self, monkeypatch):
        """Voting turn should use the generated vote target."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_generate_vote(self, system_prompt, conversation_history, valid_agent_ids, current_round):
            return {
                "thought": "这个人前后逻辑不一致。",
                "vote": valid_agent_ids[0],
                "confidence": 0.88,
            }

        monkeypatch.setattr(Agent, "generate_vote", fake_generate_vote)

        game = WerewolfService(game_id="test_vote_turn", player_count=6)
        game.start_voting_phase()
        voter_id = game.get_alive_agents()[0].agent_id

        result = await game.run_voting_turn(voter_id)

        assert result["voter_id"] == voter_id
        assert result["target_id"] != voter_id
        assert result["confidence"] == 0.88
        assert game.state.votes_this_round[voter_id] == result["target_id"]
        assert "投票给" in game.state.conversation_history[-1]["content"]

    @pytest.mark.asyncio
    async def test_run_voting_turn_preserves_vote_fallback_marker(self, monkeypatch):
        """Voting fallback should be visible to replays and reports."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_generate_vote(self, system_prompt, conversation_history, valid_agent_ids, current_round):
            return {
                "thought": "模型投票生成失败；这次投票应视为系统保底而非完整推理。",
                "vote": valid_agent_ids[0],
                "confidence": 0.5,
                "used_llm": False,
            }

        monkeypatch.setattr(Agent, "generate_vote", fake_generate_vote)

        game = WerewolfService(game_id="test_vote_turn_fallback_marker", player_count=6)
        game.start_voting_phase()
        voter_id = game.get_alive_agents()[0].agent_id

        result = await game.run_voting_turn(voter_id)

        assert result["used_llm"] is False
        assert "系统保底" in result["thought"]
        assert game.state.conversation_history[-1]["used_llm"] is False

    @pytest.mark.asyncio
    async def test_decide_werewolf_kill_uses_llm_choice(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        game = WerewolfService(game_id="test_night_wolf_llm", player_count=6)

        async def fake_generate_json_decision(agent_id, prompt, max_tokens=480, **kwargs):
            target = game.get_alive_good_players()[0]
            return {"thought": "先刀神职。", "vote": target.agent_id, "confidence": 0.91}

        monkeypatch.setattr(game, "_generate_json_decision", fake_generate_json_decision)
        result = await game.decide_werewolf_kill()

        assert result["success"] is True
        assert result["used_llm"] is True
        assert game.state.werewolf_kill_target == result["target_id"]
        assert result["confidence"] == 0.91

    @pytest.mark.asyncio
    async def test_decide_seer_check_uses_llm_choice(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        game = WerewolfService(game_id="test_night_seer_llm", player_count=6)
        seer_id = next(agent.agent_id for agent in game.state.agents.values() if agent.role == WerewolfRole.SEER)

        async def fake_generate_json_decision(agent_id, prompt, max_tokens=480, **kwargs):
            seer = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.SEER)
            target = next(agent for agent in game.get_alive_agents() if agent.agent_id != seer.agent_id)
            return {"thought": "这个人最可疑。", "vote": target.agent_id, "confidence": 0.84}

        monkeypatch.setattr(game, "_generate_json_decision", fake_generate_json_decision)
        result = await game.decide_seer_check()

        assert result["success"] is True
        assert result["used_llm"] is True
        seer = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.SEER)
        assert result["target_id"] in seer.seer_checked_ids
        assert result["confidence"] == 0.84

    @pytest.mark.asyncio
    async def test_decide_werewolf_kill_marks_invalid_json_choice_fallback_as_not_llm(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        game = WerewolfService(game_id="test_night_wolf_vote_fallback", player_count=6)

        async def fake_generate_json_decision(agent_id, prompt, max_tokens=480, **kwargs):
            return {"thought": "我选宙斯。", "vote": "not_a_valid_agent", "confidence": 0.5}

        monkeypatch.setattr(game, "_generate_json_decision", fake_generate_json_decision)

        result = await game.decide_werewolf_kill()

        assert result["success"] is True
        assert result["used_llm"] is False
        assert game.state.werewolf_kill_target == result["target_id"]

    @pytest.mark.asyncio
    async def test_choose_target_via_vote_schema_accepts_target_name_alias(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        game = WerewolfService(game_id="test_target_alias", player_count=6)
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]

        async def fake_generate_json_decision(agent_id, prompt, max_tokens=480, **kwargs):
            return {"thought": "这个名字像神职，先下手。", "vote": target.name, "confidence": "0.73"}

        monkeypatch.setattr(game, "_generate_json_decision", fake_generate_json_decision)

        result = await game._choose_target_via_vote_schema(
            werewolf.agent_id,
            [target],
            action_name="狼人夜间淘汰",
            action_summary="选择淘汰目标。",
        )

        assert result["target_id"] == target.agent_id
        assert result["confidence"] == pytest.approx(0.73)
        assert result["used_llm"] is True

    @pytest.mark.asyncio
    async def test_choose_option_via_vote_schema_accepts_agent_name_alias(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        game = WerewolfService(game_id="test_option_alias", player_count=8)
        witch = next(agent for agent in game.state.agents.values() if agent.role == WerewolfRole.WITCH)
        poison_target = next(
            agent for agent in game.get_alive_agents()
            if agent.agent_id != witch.agent_id
        )

        async def fake_generate_json_decision(agent_id, prompt, max_tokens=480, **kwargs):
            return {"thought": "他身位太危险，直接处理。", "vote": poison_target.name, "confidence": "0.66"}

        monkeypatch.setattr(game, "_generate_json_decision", fake_generate_json_decision)

        result = await game._choose_option_via_vote_schema(
            witch.agent_id,
            action_name="女巫是否使用毒药",
            action_summary="选择是否用毒。",
            options={
                "skip": "不使用毒药，选择观望",
                poison_target.agent_id: f"使用毒药毒杀 {poison_target.name}({poison_target.agent_id})",
            },
        )

        assert result["choice"] == poison_target.agent_id
        assert result["confidence"] == pytest.approx(0.66)
        assert result["used_llm"] is True

    @pytest.mark.asyncio
    async def test_decide_witch_action_can_save(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_choose_option(self, chooser_id, **kwargs):
            if kwargs["action_name"] == "女巫是否使用解药":
                return {"choice": "save", "thought": "首夜先救。", "confidence": 0.8, "used_llm": True}
            return {"choice": "skip", "thought": "先留毒。", "confidence": 0.6, "used_llm": True}

        monkeypatch.setattr(WerewolfService, "_choose_option_via_vote_schema", fake_choose_option)

        game = WerewolfService(game_id="test_night_witch_llm", player_count=6)
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        result = await game.decide_witch_action()

        assert result["used_llm"] is True
        assert result["save_result"]["target_id"] == target.agent_id

    @pytest.mark.asyncio
    async def test_decide_witch_action_can_poison(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_choose_option(self, chooser_id, **kwargs):
            if kwargs["action_name"] == "女巫是否使用解药":
                return {"choice": "skip", "thought": "先不救。", "confidence": 0.55, "used_llm": True}
            poison_target = next(
                option_id for option_id in kwargs["options"].keys()
                if option_id != "skip"
            )
            return {"choice": poison_target, "thought": "毒掉最可疑的人。", "confidence": 0.77, "used_llm": True}

        monkeypatch.setattr(WerewolfService, "_choose_option_via_vote_schema", fake_choose_option)

        game = WerewolfService(game_id="test_night_witch_poison_llm", player_count=8)
        werewolf = game.get_alive_werewolves()[0]
        kill_target = next(agent for agent in game.get_alive_agents() if agent.agent_id != werewolf.agent_id)
        game.werewolf_kill(werewolf.agent_id, kill_target.agent_id)

        result = await game.decide_witch_action()

        assert result["used_llm"] is True
        assert result["poison_result"]["target_id"] != kill_target.agent_id

    @pytest.mark.asyncio
    async def test_decide_guard_protect_uses_llm_choice(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_choose_target(self, chooser_id, valid_targets, **kwargs):
            guard = next(agent for agent in self.state.agents.values() if agent.role == WerewolfRole.GUARD)
            target = next(agent for agent in valid_targets if agent.agent_id != guard.agent_id)
            return {
                "thought": "先保关键位。",
                "target_id": target.agent_id,
                "confidence": 0.83,
                "used_llm": True,
            }

        monkeypatch.setattr(WerewolfService, "_choose_target_via_vote_schema", fake_choose_target)

        game = WerewolfService(game_id="test_night_guard_llm", player_count=8)
        result = await game.decide_guard_protect()

        assert result["success"] is True
        assert result["used_llm"] is True
        assert result["confidence"] == 0.83

    @pytest.mark.asyncio
    async def test_decide_guard_protect_marks_vote_fallback_as_not_llm(self, monkeypatch):
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        async def fake_choose_target(self, chooser_id, valid_targets, **kwargs):
            return {
                "thought": "投票中...",
                "target_id": valid_targets[0].agent_id,
                "confidence": 0.5,
                "used_llm": False,
            }

        monkeypatch.setattr(WerewolfService, "_choose_target_via_vote_schema", fake_choose_target)

        game = WerewolfService(game_id="test_night_guard_vote_fallback", player_count=8)
        result = await game.decide_guard_protect()

        assert result["success"] is True
        assert result["used_llm"] is False

    def test_resolve_night_with_kill(self):
        """Test resolving night with werewolf kill."""
        game = WerewolfService(game_id="test_resolve", player_count=6)

        # Werewolf kills
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        # Resolve night
        result = game.resolve_night()

        assert len(result["deaths"]) == 1
        assert target.agent_id in result["deaths"]
        assert game.state.agents[target.agent_id].is_alive is False

    def test_resolve_night_with_guard_save(self):
        """Test resolving night with guard saving kill target."""
        game = WerewolfService(game_id="test_guard_save", player_count=8)

        # Find guard
        guard = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.GUARD:
                guard = agent
                break

        # Werewolf kills
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        # Guard protects same target
        game.guard_protect(guard.agent_id, target.agent_id)

        # Resolve night
        result = game.resolve_night()

        assert len(result["deaths"]) == 0
        assert result["saved_by_guard"] is True
        assert game.state.agents[target.agent_id].is_alive is True

    def test_resolve_night_with_witch_save(self):
        """Test resolving night with witch saving kill target."""
        game = WerewolfService(game_id="test_witch_save_resolve", player_count=6)

        # Find witch
        witch = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.WITCH:
                witch = agent
                break

        # Werewolf kills
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        # Witch saves
        game.witch_save(witch.agent_id, target.agent_id)

        # Resolve night
        result = game.resolve_night()

        assert len(result["deaths"]) == 0
        assert result["saved_by_witch"] is True
        assert game.state.agents[target.agent_id].is_alive is True

    def test_resolve_night_with_poison(self):
        """Test resolving night with witch poison."""
        game = WerewolfService(game_id="test_poison_resolve", player_count=6)

        # Find witch
        witch = None
        for agent in game.state.agents.values():
            if agent.role == WerewolfRole.WITCH:
                witch = agent
                break

        # Werewolf kills one
        werewolf = game.get_alive_werewolves()[0]
        target1 = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target1.agent_id)

        # Witch poisons another
        target2 = game.get_alive_good_players()[1]
        game.witch_poison(witch.agent_id, target2.agent_id)

        # Resolve night
        result = game.resolve_night()

        assert len(result["deaths"]) == 2
        assert target1.agent_id in result["deaths"]
        assert target2.agent_id in result["deaths"]

    def test_voting(self):
        """Test voting mechanism."""
        game = WerewolfService(game_id="test_vote", player_count=6)
        game.start_voting_phase()

        alive = game.get_alive_agents()
        voter = alive[0]
        target = alive[1]

        # Record vote
        result = game.record_vote(voter.agent_id, target.agent_id)

        assert result["voter_id"] == voter.agent_id
        assert result["target_id"] == target.agent_id
        assert game.state.votes_this_round[voter.agent_id] == target.agent_id

    def test_resolve_voting(self):
        """Test resolving voting and elimination."""
        game = WerewolfService(game_id="test_vote_resolve", player_count=6)
        game.start_voting_phase()

        alive = game.get_alive_agents()
        target = alive[0]

        # Everyone votes for target
        for voter in alive[1:]:
            game.record_vote(voter.agent_id, target.agent_id)

        # Resolve voting
        result = game.resolve_voting()

        assert result["eliminated"] is True
        assert result["eliminated_id"] == target.agent_id
        assert game.state.agents[target.agent_id].is_alive is False

    def test_win_condition_werewolves_win(self):
        """Test werewolves win condition."""
        game = WerewolfService(game_id="test_wolves_win", player_count=6)

        # Kill all good players except one
        good_players = game.get_alive_good_players()
        for player in good_players[1:]:
            game.state.agents[player.agent_id].is_alive = False

        # Check win condition (2 werewolves, 1 good player)
        result = game.check_win_condition()

        assert result is not None
        assert result["game_over"] is True
        assert result["winner"] == WerewolfFaction.WEREWOLF.value

    def test_win_condition_good_wins(self):
        """Test good faction win condition."""
        game = WerewolfService(game_id="test_good_win", player_count=6)

        # Kill all werewolves
        werewolves = game.get_alive_werewolves()
        for werewolf in werewolves:
            game.state.agents[werewolf.agent_id].is_alive = False

        # Check win condition
        result = game.check_win_condition()

        assert result is not None
        assert result["game_over"] is True
        assert result["winner"] == WerewolfFaction.GOOD.value

    def test_win_condition_game_continues(self):
        """Test that game continues when no win condition met."""
        game = WerewolfService(game_id="test_continue", player_count=6)

        # Kill one good player
        good_players = game.get_alive_good_players()
        game.state.agents[good_players[0].agent_id].is_alive = False

        # Check win condition (2 werewolves, 3 good players)
        result = game.check_win_condition()

        assert result is None

    def test_advance_to_next_round(self):
        """Test advancing to next round."""
        game = WerewolfService(game_id="test_advance", player_count=6)

        assert game.state.current_round == 1

        game.advance_to_next_round()

        assert game.state.current_round == 2
        assert game.state.phase == WerewolfPhase.NIGHT
        assert len(game.state.night_actions) == 0
        assert len(game.state.death_tonight) == 0
        assert game.state.werewolf_kill_target is None

    def test_full_game_flow(self):
        """Test a complete game flow."""
        game = WerewolfService(game_id="test_full_flow", player_count=6)

        # Round 1 - Night
        assert game.state.phase == WerewolfPhase.NIGHT

        # Werewolf kills
        werewolf = game.get_alive_werewolves()[0]
        target = game.get_alive_good_players()[0]
        game.werewolf_kill(werewolf.agent_id, target.agent_id)

        # Resolve night
        game.resolve_night()

        # Dawn
        game.start_day_phase()
        assert game.state.phase == WerewolfPhase.DAWN

        # Discussion
        game.start_discussion_phase()
        assert game.state.phase == WerewolfPhase.DAY_DISCUSSION

        # Voting
        game.start_voting_phase()
        assert game.state.phase == WerewolfPhase.DAY_VOTING

        # Vote for a werewolf
        alive = game.get_alive_agents()
        for voter in alive:
            if voter.agent_id != werewolf.agent_id:
                game.record_vote(voter.agent_id, werewolf.agent_id)

        # Resolve voting
        game.resolve_voting()

        # Check if game continues
        win_result = game.check_win_condition()

        if not win_result:
            # Advance to next round
            game.advance_to_next_round()
            assert game.state.current_round == 2
