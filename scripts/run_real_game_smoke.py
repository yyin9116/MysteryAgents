#!/usr/bin/env python3
"""
Run real smoke tests against a live backend using the local OpenAI-compatible model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8011"
DEFAULT_LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-5.5",
    "api_key": "test-key",
    "base_url": "http://127.0.0.1:15721/v1",
}


def _compact_event(event: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: event.get(key) for key in keys if key in event}


async def _collect_sse_events(
    client: httpx.AsyncClient,
    url: str,
    *,
    stop_after_speeches: int | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            events.append(payload)
            if stop_after_speeches is not None:
                speech_count = sum(1 for event in events if event.get("type") == "agent_speaking")
                if speech_count >= stop_after_speeches:
                    break
    return events


async def run_undercover_round(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    llm_config: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{base_url}/api/game/create",
        json={
            "agent_count": 6,
            "civilian_word": "苹果",
            "undercover_word": "香蕉",
            "use_balanced_team": True,
            "llm_config": llm_config,
        },
    )
    response.raise_for_status()
    game_id = response.json()["game_id"]
    events = await _collect_sse_events(client, f"{base_url}/api/game/{game_id}/next-round-stream")
    speeches = [event for event in events if event.get("type") == "agent_speaking"]
    votes = [event for event in events if event.get("type") == "agent_voting"]
    errors = [event for event in events if "error" in str(event.get("type", "")).lower()]
    elimination = next((event for event in events if event.get("type") == "elimination"), None)
    return {
        "case": label,
        "game_id": game_id,
        "speech_count": len(speeches),
        "vote_count": len(votes),
        "speech_samples": [event.get("speech", "") for event in speeches[:3]],
        "votes": [
            _compact_event(
                event,
                ["agent_name", "voted_for_name", "confidence", "thought"],
            )
            for event in votes
        ],
        "elimination": elimination,
        "errors": errors,
    }


async def run_discussion_round(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    llm_config: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{base_url}/api/discussion/create",
        json={
            "topic": "人工智能是否应该优先追求能力还是安全",
            "agent_count": 4,
            "use_balanced_team": True,
            "use_characters": True,
            "llm_config": llm_config,
        },
    )
    response.raise_for_status()
    discussion_id = response.json()["discussion_id"]
    start = await client.post(
        f"{base_url}/api/discussion/start",
        json={"discussion_id": discussion_id},
    )
    start.raise_for_status()
    events = await _collect_sse_events(
        client,
        f"{base_url}/api/discussion/stream/{discussion_id}",
        stop_after_speeches=4,
    )
    speeches = [event for event in events if event.get("type") == "agent_speaking"]
    errors = [event for event in events if "error" in str(event.get("type", "")).lower()]
    return {
        "case": label,
        "discussion_id": discussion_id,
        "speech_count": len(speeches),
        "speech_samples": [event.get("speech", "") for event in speeches],
        "errors": errors,
    }


async def run_werewolf_round(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    llm_config: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{base_url}/api/werewolf/create",
        json={
            "player_count": 6,
            "fast_mode": True,
            "discussion_turn_limit": 3,
            "model_config_data": llm_config,
        },
    )
    response.raise_for_status()
    game_id = response.json()["game_id"]

    from services.werewolf_service import WerewolfService

    service = WerewolfService(
        game_id=game_id,
        player_count=6,
        model_config=llm_config,
        game_config={
            "fast_mode": True,
            "discussion_turn_limit": 3,
        },
    )

    rounds: list[dict[str, Any]] = []
    loop_count = 0
    while loop_count < 3:
        loop_count += 1
        if getattr(service.state.phase, "value", service.state.phase) == "night":
            night = {
                "werewolf": await service.decide_werewolf_kill(),
                "seer": await service.decide_seer_check(),
                "witch": await service.decide_witch_action(),
                "guard": await service.decide_guard_protect(),
                "resolve": service.resolve_night(),
            }
            service.state.phase = "dawn"
        else:
            night = None

        dawn = service.start_day_phase()
        win_after_dawn = service.check_win_condition()
        if win_after_dawn:
            rounds.append({"night": night, "dawn": dawn, "win": win_after_dawn})
            break

        service.start_discussion_phase()
        discussion = []
        for agent in service.get_discussion_agents_for_round():
            discussion.append(await service.run_discussion_turn(agent.agent_id))

        service.start_voting_phase()
        voting = []
        for agent in service.get_alive_agents():
            voting.append(await service.run_voting_turn(agent.agent_id))
        elimination = service.resolve_voting()
        win_after_vote = service.check_win_condition()

        rounds.append(
            {
                "night": night,
                "dawn": dawn,
                "discussion_count": len(discussion),
                "discussion_samples": [item.get("content", "") for item in discussion[:3]],
                "vote_count": len(voting),
                "votes": [
                    _compact_event(item, ["voter_name", "target_name", "confidence", "thought"])
                    for item in voting
                ],
                "elimination": elimination,
                "win": win_after_vote,
            }
        )

        if win_after_vote:
            break
        service.advance_to_next_round()

    return {
        "case": label,
        "game_id": game_id,
        "final_phase": getattr(service.state.phase, "value", service.state.phase),
        "winner": getattr(getattr(service.state, "winner", None), "value", getattr(service.state, "winner", None)),
        "current_round": service.state.current_round,
        "rounds": rounds,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--undercover-rounds", type=int, default=3)
    parser.add_argument("--discussion-rounds", type=int, default=1)
    parser.add_argument("--werewolf-rounds", type=int, default=1)
    args = parser.parse_args()

    timeout = httpx.Timeout(300.0, read=300.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        results: list[dict[str, Any]] = []
        for index in range(1, args.undercover_rounds + 1):
            results.append(
                await run_undercover_round(
                    client,
                    base_url=args.base_url,
                    llm_config=DEFAULT_LLM_CONFIG,
                    label=f"undercover_{index}",
                )
            )
        for index in range(1, args.discussion_rounds + 1):
            results.append(
                await run_discussion_round(
                    client,
                    base_url=args.base_url,
                    llm_config=DEFAULT_LLM_CONFIG,
                    label=f"discussion_{index}",
                )
            )
        for index in range(1, args.werewolf_rounds + 1):
            results.append(
                await run_werewolf_round(
                    client,
                    base_url=args.base_url,
                    llm_config=DEFAULT_LLM_CONFIG,
                    label=f"werewolf_{index}",
                )
            )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
