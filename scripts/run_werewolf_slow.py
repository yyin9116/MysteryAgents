#!/usr/bin/env python3
"""
Run a full werewolf game with deliberate pacing to avoid model rate limits.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from services.werewolf_report_service import werewolf_report_service
from services.werewolf_service import WerewolfService


def phase_value(phase: Any) -> str:
    return phase.value if hasattr(phase, "value") else str(phase)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a slow-paced werewolf game.")
    parser.add_argument("--game-id", default="", help="Optional explicit game id")
    parser.add_argument("--player-count", type=int, default=9)
    parser.add_argument("--discussion-turn-limit", type=int, default=5)
    parser.add_argument("--call-delay", type=float, default=8.0)
    parser.add_argument("--round-delay", type=float, default=12.0)
    parser.add_argument("--initial-delay", type=float, default=0.0)
    parser.add_argument("--max-round-loops", type=int, default=20)
    parser.add_argument("--llm-timeout", type=int, default=60)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--base-url", default="http://127.0.0.1:15721/v1")
    parser.add_argument("--report-dir", default="/Users/yinyin/test/killer/game_states/werewolf_reports")
    parser.add_argument("--replay-dir", default="/Users/yinyin/test/killer/game_states/werewolf_replays")
    return parser


async def paced_sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


async def main() -> None:
    args = build_parser().parse_args()
    api_key = os.environ.get("WEREWOLF_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("WEREWOLF_API_KEY is required")

    settings.LLM_MAX_RETRIES = 1
    settings.LLM_TIMEOUT = args.llm_timeout

    game_id = args.game_id or f"glm45_slow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    report_dir = Path(args.report_dir)
    replay_dir = Path(args.replay_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    replay_dir.mkdir(parents=True, exist_ok=True)
    log_path = report_dir / f"{game_id}.log"

    def log(*parts: Any) -> None:
        line = " ".join(str(part) for part in parts)
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

    model_config = {
        "provider": args.provider,
        "model": args.model,
        "api_key": api_key,
        "base_url": args.base_url,
    }

    service = WerewolfService(
        game_id=game_id,
        player_count=args.player_count,
        model_config=model_config,
        game_config={
            "fast_mode": False,
            "discussion_turn_limit": args.discussion_turn_limit,
        },
    )

    log("GAME_ID", game_id)
    log("CONFIG", json.dumps(
        {
            "player_count": args.player_count,
            "discussion_turn_limit": args.discussion_turn_limit,
            "call_delay": args.call_delay,
            "round_delay": args.round_delay,
            "model": args.model,
            "provider": args.provider,
            "llm_max_retries": settings.LLM_MAX_RETRIES,
            "llm_timeout": settings.LLM_TIMEOUT,
        },
        ensure_ascii=False,
    ))
    for agent_id, agent in service.state.agents.items():
        log("AGENT", agent_id, agent.name, agent.role.value, agent.mbti_type, agent.iq_level)

    if args.initial_delay > 0:
        log("INITIAL_DELAY", args.initial_delay)
        await paced_sleep(args.initial_delay)

    loop_count = 0
    while phase_value(service.state.phase) != "game_over" and loop_count < args.max_round_loops:
        loop_count += 1
        log("LOOP", loop_count, "ROUND", service.state.current_round, "PHASE", phase_value(service.state.phase))

        if phase_value(service.state.phase) == "night":
            wolf = await service.decide_werewolf_kill()
            log("NIGHT_WOLF", wolf)
            await paced_sleep(args.call_delay)

            seer = await service.decide_seer_check()
            log("NIGHT_SEER", seer)
            await paced_sleep(args.call_delay)

            witch = await service.decide_witch_action()
            log("NIGHT_WITCH", witch)
            await paced_sleep(args.call_delay)

            guard = await service.decide_guard_protect()
            log("NIGHT_GUARD", guard)
            await paced_sleep(args.call_delay)

            night_result = service.resolve_night()
            log("NIGHT_RESOLVE", night_result)
            service.state.phase = "dawn"
            await paced_sleep(args.round_delay)

        if phase_value(service.state.phase) == "dawn":
            day = service.start_day_phase()
            log("DAWN", day)
            win = service.check_win_condition()
            if win:
                log("WIN_AFTER_DAWN", win)
                break
            service.start_discussion_phase()
            await paced_sleep(args.round_delay)

        if phase_value(service.state.phase) == "day_discussion":
            for agent in service.get_discussion_agents_for_round():
                msg = await service.run_discussion_turn(agent.agent_id)
                log("DISCUSSION", agent.name, msg.get("content"))
                if msg.get("thought"):
                    log("THOUGHT", agent.name, msg.get("thought"))
                await paced_sleep(args.call_delay)
            service.start_voting_phase()
            await paced_sleep(args.round_delay)

        if phase_value(service.state.phase) == "day_voting":
            for agent in service.get_alive_agents():
                vote = await service.run_voting_turn(agent.agent_id)
                log("VOTE", agent.name, "->", vote.get("target_name"), "THOUGHT", vote.get("thought"))
                await paced_sleep(args.call_delay)
            elimination = service.resolve_voting()
            log("ELIMINATION", elimination)
            win = service.check_win_condition()
            if win:
                log("WIN_AFTER_VOTE", win)
                break
            service.advance_to_next_round()
            await paced_sleep(args.round_delay)

    replay = service.to_replay_dict()
    markdown = werewolf_report_service.build_markdown(replay)
    pdf = werewolf_report_service.build_pdf(replay)

    report_md_path = report_dir / f"{game_id}-report.md"
    report_pdf_path = report_dir / f"{game_id}-report.pdf"
    replay_path = replay_dir / f"{game_id}.json"
    report_md_path.write_text(markdown, encoding="utf-8")
    report_pdf_path.write_bytes(pdf)
    replay_path.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")

    fallback_count = sum(
        1 for event in replay.get("events", [])
        if "系统错误" in json.dumps(event.get("data", {}), ensure_ascii=False)
    )
    log("FINAL_WINNER", replay.get("winner"))
    log("FINAL_REASON", replay.get("game_over_reason"))
    log("FINAL_ROUND", replay.get("current_round"))
    log("TOTAL_EVENTS", replay.get("total_events"))
    log("FALLBACK_EVENTS", fallback_count)
    log("REPLAY_PATH", replay_path)
    log("MD_PATH", report_md_path)
    log("PDF_PATH", report_pdf_path)


if __name__ == "__main__":
    asyncio.run(main())
