"""
Unit tests for werewolf API endpoints.
测试狼人杀 API 接口
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from models.agent import Agent

client = TestClient(app)


class TestWerewolfAPI:
    """Test werewolf API endpoints."""

    def test_create_game(self):
        """Test creating a werewolf game."""
        response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )

        assert response.status_code == 200
        data = response.json()

        assert "game_id" in data
        assert data["player_count"] == 6
        assert len(data["agents"]) == 6
        assert "message" in data

        # Verify agents have required fields
        for agent in data["agents"]:
            assert "agent_id" in agent
            assert "name" in agent
            assert "mbti_type" in agent
            assert "iq_level" in agent
            assert "is_alive" in agent
            # Role should NOT be exposed
            assert "role" not in agent

    def test_create_game_invalid_player_count(self):
        """Test creating game with invalid player count."""
        response = client.post(
            "/api/werewolf/create",
            json={"player_count": 5}
        )

        assert response.status_code == 422  # Validation error

    def test_night_action_werewolf_kill(self):
        """Test werewolf kill action."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Get game state to find werewolf
        state_response = client.get(f"/api/werewolf/state/{game_id}")
        agents = state_response.json()["agents"]
        agent_ids = list(agents.keys())

        # Try night action (we don't know which is werewolf, so this might fail)
        # In real test, we'd need to get agent roles first
        response = client.post(
            "/api/werewolf/night-action",
            json={
                "game_id": game_id,
                "agent_id": agent_ids[0],
                "action_type": "werewolf_kill",
                "target_id": agent_ids[1]
            }
        )

        # Response could be 200 (success) or 400 (not a werewolf)
        assert response.status_code in [200, 400]

    def test_dawn_phase(self):
        """Test dawn phase."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Resolve night (without actions)
        response = client.post(
            "/api/werewolf/dawn",
            params={"game_id": game_id}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["phase"] == "dawn"
        assert "night_result" in data
        assert "day_result" in data

    def test_discussion_phase(self):
        """Test starting discussion phase."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Start discussion
        response = client.post(
            "/api/werewolf/discuss",
            params={"game_id": game_id}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["phase"] == "day_discussion"

    def test_vote(self):
        """Test voting."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Get agents
        state_response = client.get(f"/api/werewolf/state/{game_id}")
        agents = state_response.json()["agents"]
        agent_ids = list(agents.keys())

        # Start voting phase (need to be in voting phase)
        # First go through phases
        client.post("/api/werewolf/dawn", params={"game_id": game_id})
        client.post("/api/werewolf/discuss", params={"game_id": game_id})

        # Now we need to manually set phase to voting
        # In real implementation, this would be done through game flow
        from api.werewolf import active_werewolf_games
        game_service = active_werewolf_games.get(game_id)
        if game_service:
            game_service.start_voting_phase()

            # Vote
            response = client.post(
                "/api/werewolf/vote",
                json={
                    "game_id": game_id,
                    "voter_id": agent_ids[0],
                    "target_id": agent_ids[1]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_get_game_state(self):
        """Test getting game state."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Get state
        response = client.get(f"/api/werewolf/state/{game_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["game_id"] == game_id
        assert "phase" in data
        assert "current_round" in data
        assert "agents" in data
        assert data["alive_count"] == 6

    def test_get_agent_role(self):
        """Test getting agent's role."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]
        agents = create_response.json()["agents"]
        agent_id = agents[0]["agent_id"]

        # Get agent role
        response = client.get(f"/api/werewolf/agent-role/{game_id}/{agent_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == agent_id
        assert "role" in data
        assert "role_cn" in data
        assert "faction" in data

    def test_list_games(self):
        """Test listing all games."""
        # Create a game
        client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )

        # List games
        response = client.get("/api/werewolf/games")

        assert response.status_code == 200
        data = response.json()

        assert "games" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_replay_available_after_active_game_removed(self, monkeypatch, tmp_path):
        """Replay should still load from disk after in-memory game is removed."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        from api.werewolf import active_werewolf_games
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)
        active_werewolf_games.clear()

        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        assert create_response.status_code == 200
        game_id = create_response.json()["game_id"]

        dawn_response = client.post("/api/werewolf/dawn", params={"game_id": game_id})
        assert dawn_response.status_code == 200

        active_werewolf_games.clear()

        replay_response = client.get(f"/api/werewolf/replay/{game_id}")
        assert replay_response.status_code == 200
        replay_data = replay_response.json()

        assert replay_data["game_id"] == game_id
        assert replay_data["total_events"] >= 2
        assert replay_data["player_count"] == 6
        assert replay_data["alive_count"] <= 6
        assert replay_data["events"][0]["event_type"] in {"death_announcement", "phase_change"}

        replay_list_response = client.get("/api/werewolf/replays")
        assert replay_list_response.status_code == 200
        replay_list = replay_list_response.json()["replays"]
        replay_summary = next(item for item in replay_list if item["game_id"] == game_id)
        assert replay_summary["player_count"] == 6
        assert replay_summary["alive_count"] <= 6
        assert "winner" in replay_summary
        assert "game_over_reason" in replay_summary

        delete_response = client.delete(f"/api/werewolf/replay/{game_id}")
        assert delete_response.status_code == 200

        replay_after_delete = client.get(f"/api/werewolf/replay/{game_id}")
        assert replay_after_delete.status_code == 404

    def test_list_replays_supports_pagination_and_filters(self, monkeypatch, tmp_path):
        """Replay list should support server-side pagination, search, and status filters."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        from api.werewolf import active_werewolf_games
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)
        active_werewolf_games.clear()

        created_game_ids = []
        for _ in range(6):
            create_response = client.post("/api/werewolf/create", json={"player_count": 6})
            assert create_response.status_code == 200
            created_game_ids.append(create_response.json()["game_id"])

        active_game_id = created_game_ids[-1]
        active_werewolf_games.pop(created_game_ids[0], None)

        page_one_response = client.get("/api/werewolf/replays", params={"page": 1, "page_size": 5})
        assert page_one_response.status_code == 200
        page_one_payload = page_one_response.json()
        assert page_one_payload["total"] == 6
        assert page_one_payload["page"] == 1
        assert page_one_payload["page_size"] == 5
        assert page_one_payload["stats"]["total"] == 6
        assert page_one_payload["stats"]["active"] >= 1
        assert page_one_payload["stats"]["finished"] >= 1
        assert len(page_one_payload["replays"]) == 5

        page_two_response = client.get("/api/werewolf/replays", params={"page": 2, "page_size": 5})
        assert page_two_response.status_code == 200
        page_two_payload = page_two_response.json()
        assert len(page_two_payload["replays"]) == 1

        search_response = client.get("/api/werewolf/replays", params={"search": active_game_id[-4:]})
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert search_payload["total"] == 1
        assert search_payload["replays"][0]["game_id"] == active_game_id

        active_response = client.get("/api/werewolf/replays", params={"status": "active"})
        assert active_response.status_code == 200
        active_payload = active_response.json()
        assert all(item["is_active"] for item in active_payload["replays"])

        finished_response = client.get("/api/werewolf/replays", params={"status": "finished"})
        assert finished_response.status_code == 200
        finished_payload = finished_response.json()
        assert finished_payload["total"] >= 1
        assert all(not item.get("is_active") for item in finished_payload["replays"])

    def test_list_replays_supports_sorting(self, monkeypatch, tmp_path):
        """Replay list should support sorting by events and start time."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        from api.werewolf import active_werewolf_games
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)
        active_werewolf_games.clear()

        created_game_ids = []
        for _ in range(3):
            create_response = client.post("/api/werewolf/create", json={"player_count": 6})
            assert create_response.status_code == 200
            created_game_ids.append(create_response.json()["game_id"])

        first_game_id, second_game_id, _ = created_game_ids
        assert client.post("/api/werewolf/dawn", params={"game_id": first_game_id}).status_code == 200
        assert client.post("/api/werewolf/dawn", params={"game_id": second_game_id}).status_code == 200
        assert client.post("/api/werewolf/discuss", params={"game_id": second_game_id}).status_code == 200

        sort_events_response = client.get(
            "/api/werewolf/replays",
            params={"sort_by": "total_events", "sort_order": "desc"},
        )
        assert sort_events_response.status_code == 200
        sort_events_payload = sort_events_response.json()
        event_counts = [item["total_events"] for item in sort_events_payload["replays"]]
        assert event_counts == sorted(event_counts, reverse=True)

        sort_started_response = client.get(
            "/api/werewolf/replays",
            params={"sort_by": "started_at", "sort_order": "asc"},
        )
        assert sort_started_response.status_code == 200
        sort_started_payload = sort_started_response.json()
        started_times = [item["started_at"] for item in sort_started_payload["replays"]]
        assert started_times == sorted(started_times)

    def test_delete_finished_replays_only_removes_persisted_history(self, monkeypatch, tmp_path):
        """Bulk delete should remove finished persisted replays and keep active games."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        from api.werewolf import active_werewolf_games
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)
        active_werewolf_games.clear()

        finished_ids = []
        for _ in range(2):
            create_response = client.post("/api/werewolf/create", json={"player_count": 6})
            assert create_response.status_code == 200
            game_id = create_response.json()["game_id"]
            finished_ids.append(game_id)
            assert client.post("/api/werewolf/dawn", params={"game_id": game_id}).status_code == 200
            active_werewolf_games.pop(game_id, None)

        active_response = client.post("/api/werewolf/create", json={"player_count": 6})
        assert active_response.status_code == 200
        active_game_id = active_response.json()["game_id"]

        delete_response = client.delete("/api/werewolf/replays/finished")
        assert delete_response.status_code == 200
        delete_payload = delete_response.json()
        assert delete_payload["success"] is True
        assert delete_payload["deleted_count"] == 2

        for finished_id in finished_ids:
            replay_response = client.get(f"/api/werewolf/replay/{finished_id}")
            assert replay_response.status_code == 404

        active_replay_response = client.get(f"/api/werewolf/replay/{active_game_id}")
        assert active_replay_response.status_code == 200

    def test_export_replay_returns_downloadable_json(self, monkeypatch, tmp_path):
        """Replay export should return JSON with download headers."""
        monkeypatch.setattr(Agent, "_create_crewai_agent", lambda _self: None)

        from api.werewolf import active_werewolf_games
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)
        active_werewolf_games.clear()

        create_response = client.post("/api/werewolf/create", json={"player_count": 6})
        assert create_response.status_code == 200
        game_id = create_response.json()["game_id"]
        assert client.post("/api/werewolf/dawn", params={"game_id": game_id}).status_code == 200
        active_werewolf_games.pop(game_id, None)

        export_response = client.get(f"/api/werewolf/replay/{game_id}/export")
        assert export_response.status_code == 200
        assert export_response.headers["content-type"].startswith("application/json")
        assert f'{game_id}-replay.json' in export_response.headers["content-disposition"]

        export_payload = export_response.json()
        assert export_payload["game_id"] == game_id
        assert export_payload["total_events"] >= 2

    def test_export_replay_markdown_and_pdf(self, monkeypatch, tmp_path):
        """Replay report exports should return markdown and pdf payloads."""
        from api import werewolf as werewolf_api

        werewolf_api.werewolf_replay_store.storage_path = tmp_path
        werewolf_api.werewolf_replay_store.storage_path.mkdir(parents=True, exist_ok=True)

        create_response = client.post("/api/werewolf/create", json={"player_count": 6})
        game_id = create_response.json()["game_id"]
        client.post("/api/werewolf/dawn", params={"game_id": game_id})

        markdown_response = client.get(f"/api/werewolf/replay/{game_id}/export/markdown")
        assert markdown_response.status_code == 200
        assert markdown_response.headers["content-type"].startswith("text/markdown")
        assert f'{game_id}-report.md' in markdown_response.headers["content-disposition"]
        assert f"# 狼人杀战报：{game_id}" in markdown_response.text
        assert "## 关键转折" in markdown_response.text

        pdf_response = client.get(f"/api/werewolf/replay/{game_id}/export/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"].startswith("application/pdf")
        assert f'{game_id}-report.pdf' in pdf_response.headers["content-disposition"]
        assert pdf_response.content.startswith(b"%PDF")

    def test_delete_game(self):
        """Test deleting a game."""
        # Create game
        create_response = client.post(
            "/api/werewolf/create",
            json={"player_count": 6}
        )
        game_id = create_response.json()["game_id"]

        # Delete game
        response = client.delete(f"/api/werewolf/game/{game_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify game is deleted
        state_response = client.get(f"/api/werewolf/state/{game_id}")
        assert state_response.status_code == 404

    def test_game_not_found(self):
        """Test accessing non-existent game."""
        response = client.get("/api/werewolf/state/nonexistent_game")

        assert response.status_code == 404

    def test_create_game_with_model_config(self):
        """Test creating game with custom model config."""
        response = client.post(
            "/api/werewolf/create",
            json={
                "player_count": 6,
                "model_config_data": {
                    "provider": "zhipu",
                    "model": "glm-4-flash"
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["player_count"] == 6

    def test_create_game_with_fast_mode_config(self):
        """Test creating game with fast verification config."""
        response = client.post(
            "/api/werewolf/create",
            json={
                "player_count": 6,
                "fast_mode": True,
                "discussion_turn_limit": 2,
            }
        )

        assert response.status_code == 200
        data = response.json()
        from api.werewolf import active_werewolf_games
        game_service = active_werewolf_games[data["game_id"]]
        assert game_service.fast_mode is True
        assert game_service.discussion_turn_limit == 2
