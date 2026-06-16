"""
End-to-end test: create a game, let agents talk for several rounds using real LLMs,
and inspect the outputs for different IQ/model tiers.

Usage:
    cd backend
    pytest tests/test_full_game_llm_flow.py -s

Requirements:
    - At least one of OPENAI_API_KEY / ALIBABA_API_KEY / ANTHROPIC_API_KEY is set
    - Model mappings in settings (MODEL_HIGH_IQ / MODEL_MID_IQ / MODEL_LOW_IQ) point to valid models
"""

import os
import asyncio
from typing import Dict, Any, List

import pytest
from httpx import AsyncClient, ASGITransport

from config.settings import settings
from main import app


def _has_any_llm_key() -> bool:
    """Check if at least one LLM provider key is configured."""
    return any(
        [
            settings.OPENAI_API_KEY,
            settings.ALIBABA_API_KEY,
            settings.ANTHROPIC_API_KEY,
        ]
    )


@pytest.mark.asyncio
async def test_full_game_llm_flow():
    """
    Create a game, run several rounds, and print agent outputs.

    This test is primarily for manual verification and smoke testing:
    - Verifies that game creation works end-to-end
    - Verifies that agents can generate LLM-based descriptions
    - Runs a few description/voting rounds to exercise the flow
    """
    if not _has_any_llm_key():
        pytest.skip(
            "No LLM API keys configured (OPENAI_API_KEY / ALIBABA_API_KEY / "
            "ANTHROPIC_API_KEY). Set at least one to run this test."
        )

    # Show which models will be used for each IQ tier
    print("\n=== Model mapping from settings ===")
    print(f"HIGH IQ  -> {settings.MODEL_HIGH_IQ}")
    print(f"MID  IQ  -> {settings.MODEL_MID_IQ}")
    print(f"LOW  IQ  -> {settings.MODEL_LOW_IQ}")
    print("===================================\n")

    # Use ASGITransport to talk directly to the FastAPI app (no real network)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) Create game with balanced team (mixed IQ + MBTI)
        create_payload: Dict[str, Any] = {
            "agent_count": 4,
            "civilian_word": "牛奶",
            "undercover_word": "豆浆",
            "max_rounds": 5,
            "use_balanced_team": True,
            "agents": [],
        }

        print(">>> Creating game...")
        resp = await client.post("/api/game/create", json=create_payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        game_id = data["game_id"]
        agents: List[Dict[str, Any]] = data["agents"]

        print(f"Game created: {game_id}")
        print("Agents:")
        for a in agents:
            print(
                f"  - {a['id']}: MBTI={a['mbti_type']}, "
                f"IQ={a['iq_level']}, role={a['role']}"
            )
        print()

        # 2) Start game (first description round)
        print(">>> Starting game (description phase)...")
        resp = await client.post("/api/game/start", json={"game_id": game_id})
        assert resp.status_code == 200, resp.text
        round_data = resp.json()

        print(f"Round {round_data['round']} phase={round_data['phase']}")
        for msg in round_data.get("responses", []):
            print(
                f"[ROUND {msg['round']}] {msg['agent_id']} "
                f"said: {msg['content']}"
            )
        print()

        # 3) Run a few next-round steps (vote + new descriptions)
        max_steps = 4
        for step in range(max_steps):
            print(f">>> /api/game/next-round step {step + 1}/{max_steps}")
            resp = await client.post(
                "/api/game/next-round", json={"game_id": game_id}
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()

            # Voting complete branch
            if data.get("phase") == "voting_complete":
                elimination = data.get("elimination")
                print("Voting complete.")
                if elimination:
                    print(
                        f"Eliminated: {elimination['eliminated_id']} "
                        f"(role={elimination['eliminated_role']}, "
                        f"word={elimination['eliminated_word']})"
                    )
                if data.get("game_over"):
                    print(f"Game over: result={data.get('result')}")
                    break
                print()
                continue

            # New description round (be tolerant if some fields are missing)
            round_no = data.get("round")
            phase = data.get("phase")
            print(
                f"Round {round_no} phase={phase} "
                f"game_over={data.get('game_over')}"
            )
            for msg in data.get("responses", []):
                r = msg.get("round")
                aid = msg.get("agent_id")
                content = msg.get("content")
                print(f"[ROUND {r}] {aid} said: {content}")

            if data.get("game_over"):
                print(f"Game over: result={data.get('result')}")
                break

            print()

        # 4) Fetch final state for inspection
        print(">>> Fetching final game state...")
        resp = await client.get(f"/api/game/state/{game_id}")
        assert resp.status_code == 200, resp.text
        state = resp.json()

        print(
            f"Final state: round={state['round']}, "
            f"phase={state['phase']}, "
            f"alive_agents={len(state['agents'])}"
        )
        print("Last few conversation messages:")
        for msg in state["conversation_history"][-10:]:
            print(
                f"  [ROUND {msg['round']}] {msg['agent_id']} "
                f"({msg['type']}): {msg['content']}"
            )

        # Basic assertions to ensure something non-trivial happened
        assert state["round"] >= 1
        assert len(state["conversation_history"]) > 0


