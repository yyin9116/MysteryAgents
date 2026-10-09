"""
Jubensha agent evaluation — MIRAGE-style metrics.

将平台定位为「观测智能体」平台：对局结束后对回放事件流做统计 +
一次 LLM 评审调用，产出专业向评估报告：

- victory_mrr  : 指认排名中真凶的 MRR（排名质量）
- TII          : Trust Inclination Index —— 各智能体逐轮怀疑度对真凶的区分度
- CIC          : Clue Investigation Capability —— 线索引用率（发言中引用已获线索的比例）
- ICI          : Interactivity Capability Index —— 互动密度（气泡数/提问率）
- SCI          : Script Compliance Index —— LLM 评判的剧本贴合度（0-100）
- 五维能力分    : 角色扮演 rp / 推理 ra / 交流合作 cc / 细节观察 do / 思维创新 ct（0-20，LLM 评）

所有 LLM 评审合并为单次调用（成本可控）；统计指标纯本地计算。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from services.llm_service import LLMService

logger = logging.getLogger(__name__)

ABILITY_DIMS = [
    ("rp", "角色扮演（人设一致性、口吻与身份契合）"),
    ("ra", "推理分析（信息整合、逻辑链、指向真凶的有效推理）"),
    ("cc", "交流合作（回应他人、推动讨论、信息交换质量）"),
    ("do", "细节观察（对剧本与线索细节的捕捉与运用）"),
    ("ct", "思维创新（话术策略、出乎意料但合理的表达）"),
]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_statistics(service) -> Dict[str, Any]:
    """从 game_events / votes / received_clues 统计非 LLM 指标。"""
    murderer_id = service.script_pack.truth.murderer

    # ---- 发言与怀疑度事件 ----
    speeches: Dict[str, List[str]] = {}
    suspicion_by_round: List[Dict[str, Dict[str, float]]] = []   # [{observer: {target: score}}]
    clue_events = 0
    for e in service.game_events:
        et = e.get("event_type")
        data = e.get("data") or {}
        if et == "discussion":
            speeches.setdefault(data.get("agent_id", ""), []).append(str(data.get("speech") or ""))
            sus = data.get("suspicion") or {}
            if isinstance(sus, dict) and sus:
                snapshot: Dict[str, Dict[str, float]] = {}
                for target, score in sus.items():
                    try:
                        snapshot[str(target)] = float(score)
                    except (TypeError, ValueError):
                        continue
                if snapshot:
                    suspicion_by_round.append({str(data.get("agent_id", "")): snapshot})
        elif et == "clue_granted":
            clue_events += 1

    # ---- TII：对真凶的怀疑区分度 ----
    # discrimination = mean(suspicion toward murderer) / mean(suspicion toward all) × 100
    tii_details: Dict[str, float] = {}
    mur_scores: List[float] = []
    all_scores: List[float] = []
    for snapshot in suspicion_by_round:
        for _observer, scores in snapshot.items():
            for target, score in scores.items():
                all_scores.append(score)
                if murderer_id and target == murderer_id:
                    mur_scores.append(score)
    tii = None
    if murderer_id and all_scores:
        mean_all = sum(all_scores) / len(all_scores)
        mean_mur = sum(mur_scores) / len(mur_scores) if mur_scores else 0.0
        tii = round(_clamp(mean_mur / mean_all * 100, 0, 200) if mean_all > 0 else 0.0, 1)
        tii_details = {
            "mean_suspicion_toward_murderer": round(mean_mur, 2),
            "mean_suspicion_overall": round(mean_all, 2),
            "suspicion_records": len(all_scores),
        }

    # ---- CIC：线索引用率 ----
    received: Dict[str, List[str]] = {}
    for runtime in service.agents.values():
        received[runtime.char_id] = [
            f"{c.title or ''}{c.content}" for c in (runtime.received_clues or [])
        ]

    cic_details: Dict[str, Any] = {}
    for cid, clue_texts in received.items():
        my_speeches = speeches.get(cid, [])
        if not my_speeches:
            cic_details[cid] = {"clues_received": len(clue_texts), "clue_usage_ratio": None}
            continue
        if not clue_texts:
            cic_details[cid] = {"clues_received": 0, "clue_usage_ratio": 0.0}
            continue
        # 取每条线索中最具辨识度的 4 字片段做包含检测
        keys: List[str] = []
        for text in clue_texts:
            clean = re.sub(r"[《》【】\s，。：:；;！？?、\"']", "", text)
            if len(clean) >= 4:
                keys.append(clean[:4])
        hits = 0
        for sp in my_speeches:
            sp_clean = re.sub(r"\s", "", sp)
            if any(k and k in sp_clean for k in keys):
                hits += 1
        cic_details[cid] = {
            "clues_received": len(clue_texts),
            "clue_usage_ratio": round(hits / len(my_speeches), 3),
        }
    usage_values = [v["clue_usage_ratio"] for v in cic_details.values() if v["clue_usage_ratio"] is not None]
    cic = round(sum(usage_values) / len(usage_values) * 100, 1) if usage_values else None

    # ---- ICI：互动密度 ----
    ici_details: Dict[str, Any] = {}
    for cid, sps in speeches.items():
        bubble_total = sum(len(s.split(" / ")) for s in sps)
        questions = sum(1 for s in sps for ch in s if ch in "？?")
        ici_details[cid] = {
            "speeches": len(sps),
            "bubbles": bubble_total,
            "question_rate": round(questions / max(1, bubble_total), 3),
        }
    q_rates = [v["question_rate"] for v in ici_details.values()]
    # 归一化到 0-100：提问率 0.25+ 视为满互动
    ici = round(_clamp((sum(q_rates) / len(q_rates)) / 0.25 * 100, 0, 100), 1) if q_rates else None

    # ---- Victory MRR ----
    mrr = None
    tally = dict(getattr(service.reveal_result or {}, "get", lambda *_: None)("tally") or {}) \
        if service.reveal_result else {}
    if not tally:
        for v in (service.votes or {}).values():
            tally[v["target"]] = tally.get(v["target"], 0) + 1
    if murderer_id and tally:
        ranking = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
        for rank, (target, _n) in enumerate(ranking, start=1):
            if target == murderer_id:
                mrr = round(1.0 / rank, 3)
                break

    return {
        "victory_mrr": mrr,
        "tii": tii,
        "tii_details": tii_details,
        "cic": cic,
        "cic_details": cic_details,
        "ici": ici,
        "ici_details": ici_details,
        "speech_counts": {cid: len(sps) for cid, sps in speeches.items()},
        "clue_grant_events": clue_events,
    }


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "…"


async def run_evaluation(service) -> Dict[str, Any]:
    """完整评估：统计指标 + 单次 LLM 评审（五维能力 + SCI）。"""
    stats = compute_statistics(service)
    llm = LLMService()

    # ---- 组装 LLM 评审材料（公开可见 + 各自私密剧本仅用于评审） ----
    agent_blocks: List[str] = []
    for runtime in service.agents.values():
        cid = runtime.char_id
        speeches = [
            e["data"].get("speech") or "" for e in service.game_events
            if e.get("event_type") == "discussion" and (e.get("data") or {}).get("agent_id") == cid
        ]
        transcript = "\n".join(f"- {s}" for s in speeches) or "（未发言）"
        agent_blocks.append(
            f"### 角色：{runtime.name}（id={cid}，阵营={runtime.char.camp.value}）\n"
            f"角色任务：{_truncate(runtime.char.mission, 300)}\n"
            f"剧本要点：{_truncate(runtime.char.script, 1200)}\n"
            f"对局发言记录：\n{_truncate(transcript, 3000)}"
        )

    murderer_id = service.script_pack.truth.murderer
    murderer_name = service.agents[murderer_id].name if murderer_id in service.agents else "未指定"
    prompt = (
        "你是社会推理游戏（剧本杀）的智能体行为评估专家。以下是一局已完成对局中所有 AI 角色的"
        "剧本任务、发言记录与真凶信息。请对每个角色分别打分。\n\n"
        f"本局真凶：{murderer_name}\n\n" + "\n\n".join(agent_blocks) +
        "\n\n请严格输出 JSON（不要其他文字），结构如下：\n"
        "{\"agents\": [{\"char_id\": \"...\", \"rp\": 0-20, \"ra\": 0-20, \"cc\": 0-20, "
        "\"do\": 0-20, \"ct\": 0-20, \"sci\": 0-100, \"comment\": \"一句话点评\"}]}\n"
        "维度含义：" + "；".join(f"{k}={d}" for k, d in ABILITY_DIMS) +
        "；sci=剧本贴合度（是否按剧本与任务行动、合理隐瞒/披露信息）。"
    )

    llm_scores: Dict[str, Dict[str, Any]] = {}
    model_config = next(iter(service.agents.values())).agent.model_config if service.agents else None
    try:
        raw = await llm.generate(
            prompt,
            model_config=model_config,
            temperature=0.2,
            max_tokens=2000,
            session_id=f"eval_{service.game_id}",
        )
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        for item in (parsed or {}).get("agents", []):
            cid = str(item.get("char_id", ""))
            if cid in service.agents:
                llm_scores[cid] = item
    except Exception as exc:
        logger.warning("Jubensha evaluation LLM call failed: %s", exc)

    # ---- 合并输出 ----
    per_agent: List[Dict[str, Any]] = []
    for runtime in service.agents.values():
        cid = runtime.char_id
        ls = llm_scores.get(cid, {})
        abilities = {
            k: _clamp(float(ls.get(k) or 0), 0, 20) for k, _d in ABILITY_DIMS
        } if ls else None
        sci = _clamp(float(ls.get("sci") or 0), 0, 100) if ls and ls.get("sci") is not None else None
        cic_info = stats["cic_details"].get(cid, {})
        ici_info = stats["ici_details"].get(cid, {})
        per_agent.append({
            "char_id": cid,
            "name": runtime.name,
            "camp": runtime.char.camp.value,
            "model": runtime.agent.model_config.get("model") if runtime.agent.model_config else None,
            "abilities": abilities,
            "ability_avg": round(sum(abilities.values()) / len(abilities), 1) if abilities else None,
            "sci": round(sci, 1) if sci is not None else None,
            "comment": ls.get("comment", "") if isinstance(ls.get("comment"), str) else "",
            "cic_detail": cic_info,
            "ici_detail": ici_info,
        })

    ability_avgs = [a["ability_avg"] for a in per_agent if a["ability_avg"] is not None]
    scis = [a["sci"] for a in per_agent if a["sci"] is not None]
    evaluation = {
        "evaluated": True,
        "murderer_name": murderer_name,
        "victory_mrr": stats["victory_mrr"],
        "tii": stats["tii"],
        "tii_details": stats["tii_details"],
        "cic": stats["cic"],
        "ici": stats["ici"],
        "sci_avg": round(sum(scis) / len(scis), 1) if scis else None,
        "ability_avg_overall": round(sum(ability_avgs) / len(ability_avgs), 1) if ability_avgs else None,
        "agents": per_agent,
        "llm_scored": bool(llm_scores),
    }
    return evaluation
