from pathlib import Path

from fastapi.testclient import TestClient

import main
from api import game as game_api
from models.agent import Agent


def test_save_and_load_restores_active_game(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Agent, "_create_autogen_agent", lambda _self: None)
    game_api.active_games.clear()
    game_api.state_service.storage_path = tmp_path
    game_api.state_service.storage_path.mkdir(parents=True, exist_ok=True)

    with TestClient(main.app) as client:
        create_response = client.post(
            "/api/game/create",
            json={
                "agent_count": 3,
                "civilian_word": "苹果",
                "undercover_word": "香蕉",
                "use_balanced_team": True,
            },
        )
        assert create_response.status_code == 200
        create_data = create_response.json()
        game_id = create_data["game_id"]
        agent_id = create_data["agents"][0]["id"]

        possess_response = client.post(
            "/api/game/possess",
            json={"game_id": game_id, "agent_id": agent_id},
        )
        assert possess_response.status_code == 200

        save_response = client.post(
            "/api/game/save",
            json={"game_id": game_id, "snapshot_name": "manual_test"},
        )
        assert save_response.status_code == 200
        snapshot_id = save_response.json()["snapshot_id"]
        assert snapshot_id.endswith("manual_test")

        snapshots_response = client.get(f"/api/game/snapshots?game_id={game_id}")
        assert snapshots_response.status_code == 200
        snapshots = snapshots_response.json()["snapshots"]
        assert len(snapshots) == 1
        assert snapshots[0]["timestamp"]
        assert snapshots[0]["snapshot_type"] == "manual"
        assert snapshots[0]["alive_count"] == 3

        game_api.active_games.clear()

        load_response = client.post("/api/game/load", json={"snapshot_id": snapshot_id})
        assert load_response.status_code == 200
        load_data = load_response.json()

        assert load_data["success"] is True
        assert load_data["game_id"] == game_id
        assert load_data["phase"] == "description"

        state_response = client.get(f"/api/game/state/{game_id}")
        assert state_response.status_code == 200
        state_data = state_response.json()

        assert state_data["game_id"] == game_id
        restored_agent = next(agent for agent in state_data["agents"] if agent["id"] == agent_id)
        assert restored_agent["is_possessed"] is True

    game_api.active_games.clear()
