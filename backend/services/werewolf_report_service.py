"""
Werewolf replay report export service.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class WerewolfReportService:
    """Build markdown and PDF exports from persisted werewolf replays."""

    def __init__(self) -> None:
        registerFont(UnicodeCIDFont("STSong-Light"))

    @staticmethod
    def _format_dt(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    @staticmethod
    def _winner_label(value: str | None) -> str:
        mapping = {
            "good": "好人阵营",
            "werewolf": "狼人阵营",
        }
        return mapping.get(value or "", value or "未结束")

    @staticmethod
    def _faction_label(value: str | None) -> str:
        mapping = {
            "good": "好人",
            "werewolf": "狼人",
        }
        return mapping.get(value or "", value or "-")

    @staticmethod
    def _role_priority(role_cn: str) -> int:
        return {
            "狼人": 0,
            "预言家": 1,
            "女巫": 2,
            "守卫": 3,
            "猎人": 4,
            "村民": 5,
        }.get(role_cn, 99)

    @staticmethod
    def _agent_rows(replay_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        agents = replay_data.get("agents", {}) or {}
        rows = []
        for agent_id, agent in agents.items():
            rows.append(
                {
                    "agent_id": agent_id,
                    "name": agent.get("name", agent_id),
                    "role_cn": agent.get("role_cn", agent.get("role", "-")),
                    "faction": agent.get("faction", "-"),
                    "mbti_type": agent.get("mbti_type", "-"),
                    "iq_level": agent.get("iq_level", "-"),
                }
            )
        if rows:
            return sorted(
                rows,
                key=lambda item: (
                    WerewolfReportService._role_priority(item["role_cn"]),
                    item["agent_id"],
                ),
            )

        inferred: Dict[str, Dict[str, Any]] = {}
        for event in replay_data.get("events", []):
            data = event.get("data", {}) or {}
            for prefix in ("actor", "target", "voter", "eliminated", "agent"):
                agent_id = data.get(f"{prefix}_id")
                agent_name = data.get(f"{prefix}_name")
                if agent_id:
                    inferred.setdefault(
                        agent_id,
                        {
                            "agent_id": agent_id,
                            "name": agent_name or agent_id,
                            "role_cn": "-",
                            "faction": "-",
                            "mbti_type": "-",
                            "iq_level": "-",
                        },
                    )
                    if agent_name:
                        inferred[agent_id]["name"] = agent_name
            if event.get("event_type") == "elimination" and data.get("eliminated_id"):
                inferred.setdefault(
                    data["eliminated_id"],
                    {
                        "agent_id": data["eliminated_id"],
                        "name": data.get("eliminated_name", data["eliminated_id"]),
                        "role_cn": "-",
                        "faction": "-",
                        "mbti_type": "-",
                        "iq_level": "-",
                    },
                )
                inferred[data["eliminated_id"]]["role_cn"] = data.get("eliminated_role_cn", "-")

            snapshot = event.get("game_state_snapshot") or {}
            for alive_agent in snapshot.get("alive_agents", []) or []:
                agent_id = alive_agent.get("agent_id")
                if agent_id:
                    inferred.setdefault(
                        agent_id,
                        {
                            "agent_id": agent_id,
                            "name": alive_agent.get("name", agent_id),
                            "role_cn": "-",
                            "faction": "-",
                            "mbti_type": "-",
                            "iq_level": "-",
                        },
                    )
                    inferred[agent_id]["name"] = alive_agent.get("name", inferred[agent_id]["name"])
        return sorted(inferred.values(), key=lambda item: item["agent_id"])

    @staticmethod
    def _group_events_by_round(replay_data: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
        grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for event in replay_data.get("events", []):
            grouped[int(event.get("round", 0))].append(event)
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    @staticmethod
    def _event_to_markdown(event: Dict[str, Any]) -> str:
        event_type = event.get("event_type")
        data = event.get("data", {}) or {}
        timestamp = WerewolfReportService._format_dt(event.get("timestamp"))

        if event_type == "night_action":
            action_type = data.get("action_type")
            if action_type == "werewolf_kill":
                return f"- [{timestamp}] 夜晚行动：{data.get('actor_name')} 锁定 {data.get('target_name')}。"
            if action_type == "seer_check":
                result = "狼人" if data.get("result") == "werewolf" else "好人"
                return f"- [{timestamp}] 夜晚行动：{data.get('actor_name')} 查验 {data.get('target_name')}，结果为 {result}。"
            if action_type == "witch_save":
                return f"- [{timestamp}] 夜晚行动：{data.get('actor_name')} 使用解药救下 {data.get('target_name')}。"
            if action_type == "witch_poison":
                return f"- [{timestamp}] 夜晚行动：{data.get('actor_name')} 毒杀 {data.get('target_name')}。"
            if action_type == "guard_protect":
                return f"- [{timestamp}] 夜晚行动：{data.get('actor_name')} 守护 {data.get('target_name')}。"
        if event_type == "death_announcement":
            return f"- [{timestamp}] 天亮公告：{data.get('message')}"
        if event_type == "phase_change":
            return f"- [{timestamp}] 阶段切换：{data.get('from_phase')} -> {data.get('to_phase')}。"
        if event_type == "discussion":
            thought = data.get("thought")
            suspicion = data.get("suspicion") or {}
            line = f"- [{timestamp}] {data.get('agent_name')} 发言：{data.get('speech')}"
            if thought:
                line += f"\n  - 内心分析：{thought}"
            if suspicion:
                line += f"\n  - 怀疑分：{suspicion}"
            return line
        if event_type == "vote":
            return f"- [{timestamp}] 投票：{data.get('voter_name')} -> {data.get('target_name')}。"
        if event_type == "elimination":
            return (
                f"- [{timestamp}] 淘汰：{data.get('eliminated_name')} 出局，"
                f"身份为 {data.get('eliminated_role_cn')}，得票 {data.get('vote_count')}。"
            )
        if event_type == "game_over":
            return (
                f"- [{timestamp}] 游戏结束：{WerewolfReportService._winner_label(data.get('winner'))}"
                f" 获胜，原因：{data.get('reason')}。"
            )
        return f"- [{timestamp}] {event_type}: {data}"

    @staticmethod
    def _glossary_lines() -> List[str]:
        return [
            "狼人：夜晚可以选择击杀目标的阵营。",
            "预言家：夜晚可以查验一名玩家是狼人还是好人。",
            "女巫：通常有一次解药和一次毒药，能救人或毒人。",
            "守卫：夜晚可以守护一名玩家，防止其被狼人击杀。",
            "平安夜：这一晚没有玩家死亡，通常意味着被救下、被守住或狼人未成功击杀。",
            "悍跳：某人主动跳出关键身份，但真实性可疑。",
            "带队：通过发言和逻辑推动大家集中票型或怀疑方向。",
        ]

    @staticmethod
    def _safe_text(value: Any) -> str:
        text = str(value or "").strip()
        return text or "-"

    @staticmethod
    def _player_palette() -> List[str]:
        return [
            "#b91c1c",
            "#1d4ed8",
            "#047857",
            "#7c3aed",
            "#c2410c",
            "#0f766e",
            "#be185d",
            "#1f2937",
            "#0369a1",
            "#4338ca",
            "#65a30d",
            "#92400e",
        ]

    def _player_color_map(self, replay_data: Dict[str, Any]) -> Dict[str, str]:
        palette = self._player_palette()
        color_map: Dict[str, str] = {}
        for index, agent in enumerate(self._agent_rows(replay_data)):
            color_map[agent["name"]] = palette[index % len(palette)]
        return color_map

    @staticmethod
    def _paragraph_text(text: Any) -> str:
        return escape(str(text or "")).replace("\n", "<br/>")

    def _name_span(self, name: str, color_map: Dict[str, str]) -> str:
        color = color_map.get(name, "#111827")
        return f'<font color="{color}"><b>{escape(name)}</b></font>'

    def _replace_names_with_color(self, text: str, color_map: Dict[str, str]) -> str:
        rendered = escape(text or "")
        for name in sorted(color_map.keys(), key=len, reverse=True):
            rendered = rendered.replace(
                escape(name),
                self._name_span(name, color_map),
            )
        return rendered

    def _build_scoreboard(self, replay_data: Dict[str, Any]) -> List[str]:
        rows = self._agent_rows(replay_data)
        wolves = [row["name"] for row in rows if row["faction"] == "werewolf"]
        good = [row["name"] for row in rows if row["faction"] == "good"]
        powers = [f"{row['name']}（{row['role_cn']}）" for row in rows if row["role_cn"] not in {"狼人", "村民"}]
        villagers = [row["name"] for row in rows if row["role_cn"] == "村民"]
        return [
            f"- 狼人阵营：{'、'.join(wolves) or '无'}",
            f"- 好人阵营：{'、'.join(good) or '无'}",
            f"- 神职配置：{'、'.join(powers) or '无'}",
            f"- 村民位：{'、'.join(villagers) or '无'}",
        ]

    def _build_opening_line(self, replay_data: Dict[str, Any]) -> str:
        winner = self._winner_label(replay_data.get("winner"))
        reason = replay_data.get("game_over_reason") or "对局仍在进行"
        rounds = replay_data.get("current_round", "-")
        player_count = replay_data.get("player_count", "-")
        return f"{winner}在 {player_count} 人局中鏖战至第 {rounds} 回合，最终以“{reason}”收官。"

    def _collect_round_story(self, round_num: int, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        story: Dict[str, Any] = {
            "round": round_num,
            "night_actions": [],
            "deaths": [],
            "death_message": "",
            "discussions": [],
            "votes": [],
            "elimination": None,
            "game_over": None,
        }

        for event in events:
            data = event.get("data", {}) or {}
            event_type = event.get("event_type")
            if event_type == "night_action":
                action_type = data.get("action_type")
                if action_type == "werewolf_kill":
                    story["night_actions"].append(f"狼人将刀口指向 {data.get('target_name')}。")
                elif action_type == "seer_check":
                    result = "狼人" if data.get("result") == "werewolf" else "好人"
                    story["night_actions"].append(
                        f"{data.get('actor_name')} 夜验 {data.get('target_name')}，结果为 {result}。"
                    )
                elif action_type == "witch_save":
                    story["night_actions"].append(f"{data.get('actor_name')} 用解药救下 {data.get('target_name')}。")
                elif action_type == "witch_poison":
                    story["night_actions"].append(f"{data.get('actor_name')} 用毒药带走 {data.get('target_name')}。")
                elif action_type == "guard_protect":
                    story["night_actions"].append(f"{data.get('actor_name')} 守护了 {data.get('target_name')}。")
            elif event_type == "death_announcement":
                story["death_message"] = data.get("message") or ""
                for death in data.get("deaths", []) or []:
                    story["deaths"].append(f"{death.get('name')}（{death.get('role_cn')}）")
            elif event_type == "discussion":
                story["discussions"].append(
                    {
                        "name": data.get("agent_name", "-"),
                        "speech": self._safe_text(data.get("speech")),
                        "thought": self._safe_text(data.get("thought")),
                    }
                )
            elif event_type == "vote":
                story["votes"].append(
                    f"{data.get('voter_name')} 投给 {data.get('target_name')}"
                )
            elif event_type == "elimination":
                story["elimination"] = {
                    "name": data.get("eliminated_name"),
                    "role_cn": data.get("eliminated_role_cn"),
                    "vote_count": data.get("vote_count"),
                }
            elif event_type == "game_over":
                story["game_over"] = {
                    "winner": self._winner_label(data.get("winner")),
                    "reason": data.get("reason"),
                }
        return story

    def _build_round_digest(self, round_story: Dict[str, Any]) -> List[str]:
        lines = []
        if round_story["night_actions"]:
            lines.append(f"- 夜间博弈：{' '.join(round_story['night_actions'])}")
        if round_story["death_message"]:
            lines.append(f"- 天亮结果：{round_story['death_message']}")
        if round_story["elimination"]:
            elimination = round_story["elimination"]
            lines.append(
                f"- 白天出局：{elimination['name']} 被票出，翻牌 {elimination['role_cn']}，累计 {elimination['vote_count']} 票。"
            )
        if round_story["votes"]:
            vote_counter = Counter(vote.split(" 投给 ")[1] for vote in round_story["votes"] if " 投给 " in vote)
            if vote_counter:
                focus = "，".join(f"{name} {count}票" for name, count in vote_counter.most_common(3))
                lines.append(f"- 票型焦点：{focus}")
        if round_story["discussions"]:
            highlights = []
            for item in round_story["discussions"][:3]:
                excerpt = item["speech"][:52]
                if len(item["speech"]) > 52:
                    excerpt += "…"
                highlights.append(f"{item['name']}：「{excerpt}」")
            lines.append(f"- 发言切片：{'；'.join(highlights)}")
        if round_story["game_over"]:
            lines.append(
                f"- 终局判定：{round_story['game_over']['winner']} 获胜，原因是 {round_story['game_over']['reason']}。"
            )
        return lines

    def _build_turning_points(self, replay_data: Dict[str, Any]) -> List[str]:
        points: List[str] = []
        for round_num, events in self._group_events_by_round(replay_data).items():
            round_story = self._collect_round_story(round_num, events)

            if round_story["death_message"] and "平安夜" in round_story["death_message"]:
                points.append(f"第 {round_num} 回合出现平安夜，狼刀没有兑现，场上信息节奏被明显拉长。")

            for action in round_story["night_actions"]:
                if "结果为 狼人" in action:
                    points.append(f"第 {round_num} 回合预言家命中狼人：{action}")
                    break

            elimination = round_story["elimination"]
            if elimination and elimination["role_cn"] == "狼人":
                points.append(
                    f"第 {round_num} 回合白天票出狼人 {elimination['name']}，好人阵营完成一次关键正票。"
                )
            elif elimination and elimination["role_cn"] in {"预言家", "女巫", "守卫", "猎人"}:
                points.append(
                    f"第 {round_num} 回合损失神职 {elimination['name']}（{elimination['role_cn']}），局面一度变得危险。"
                )

            for death in round_story["deaths"]:
                if "（预言家）" in death or "（女巫）" in death or "（守卫）" in death or "（猎人）" in death:
                    points.append(f"第 {round_num} 回合夜里倒下关键身份：{death}。")

            if round_story["game_over"]:
                points.append(
                    f"终局在第 {round_num} 回合锁定，{round_story['game_over']['winner']}以“{round_story['game_over']['reason']}”结束对局。"
                )

        deduped: List[str] = []
        seen = set()
        for point in points:
            if point not in seen:
                deduped.append(point)
                seen.add(point)
        return deduped[:8]

    def build_markdown(self, replay_data: Dict[str, Any]) -> str:
        """Render replay data as a battle-report style markdown export."""
        lines = [
            f"# 狼人杀战报：{replay_data.get('game_id', '-')}",
            "",
            f"> {self._build_opening_line(replay_data)}",
            "",
            "## 胜负概览",
            f"- 游戏 ID：`{replay_data.get('game_id', '-')}`",
            f"- 开始时间：{self._format_dt(replay_data.get('started_at'))}",
            f"- 结束时间：{self._format_dt(replay_data.get('updated_at'))}",
            f"- 玩家人数：{replay_data.get('player_count', '-')}",
            f"- 总回合数：{replay_data.get('current_round', '-')}",
            f"- 获胜阵营：{self._winner_label(replay_data.get('winner'))}",
            f"- 收官原因：{replay_data.get('game_over_reason') or '未结束'}",
            "",
            "## 阵营名单",
            *self._build_scoreboard(replay_data),
            "",
            "## 关键转折",
        ]
        for point in self._build_turning_points(replay_data):
            lines.append(f"- {point}")

        lines.extend([
            "",
            "## 角色卡",
            "",
            "| 名字 | 身份 | 阵营 | MBTI | IQ | 玩家ID |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for agent in self._agent_rows(replay_data):
            lines.append(
                f"| {agent['name']} | {agent['role_cn']} | {self._faction_label(agent['faction'])} | "
                f"{agent['mbti_type']} | {agent['iq_level']} | `{agent['agent_id']}` |"
            )

        lines.extend(["", "## 回合战况", ""])
        for round_num, events in self._group_events_by_round(replay_data).items():
            story = self._collect_round_story(round_num, events)
            lines.append(f"### 第 {round_num} 回合")
            lines.append("")
            for line in self._build_round_digest(story):
                lines.append(line)
            if story["discussions"]:
                lines.append("")
                lines.append("#### 发言摘录")
                lines.append("")
                for item in story["discussions"]:
                    lines.append(f"- **{item['name']}**：{item['speech']}")
                    if item["thought"] and item["thought"] != "-":
                        lines.append(f"  - 内心线索：{item['thought']}")
                lines.append("")

        lines.extend(["## 完整事件流", ""])
        for round_num, events in self._group_events_by_round(replay_data).items():
            lines.append(f"### 第 {round_num} 回合原始纪要")
            lines.append("")
            for event in events:
                lines.append(self._event_to_markdown(event))
            lines.append("")

        lines.extend(["## 新手术语", ""])
        for line in self._glossary_lines():
            lines.append(f"- {line}")

        return "\n".join(lines).strip() + "\n"

    def build_pdf(self, replay_data: Dict[str, Any]) -> bytes:
        """Render replay data as a readable PDF battle report."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleCN",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=4,
        )
        strap_style = ParagraphStyle(
            "StrapCN",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=11.5,
            leading=18,
            textColor=colors.HexColor("#475569"),
            spaceAfter=8,
        )
        section_style = ParagraphStyle(
            "Heading2CN",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=15,
            leading=22,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=7,
        )
        subsection_style = ParagraphStyle(
            "Heading3CN",
            parent=styles["Heading3"],
            fontName="STSong-Light",
            fontSize=12.5,
            leading=18,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=8,
            spaceAfter=5,
        )
        body_style = ParagraphStyle(
            "BodyCN",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.8,
            leading=17,
            textColor=colors.HexColor("#111827"),
            spaceAfter=3,
            wordWrap="CJK",
        )
        bullet_style = ParagraphStyle(
            "BulletCN",
            parent=body_style,
            leftIndent=10,
            bulletIndent=0,
            spaceAfter=3,
            wordWrap="CJK",
        )
        small_style = ParagraphStyle(
            "SmallCN",
            parent=body_style,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#475569"),
            wordWrap="CJK",
        )
        name_style = ParagraphStyle(
            "NameCN",
            parent=body_style,
            fontSize=11.2,
            leading=15,
            spaceAfter=0,
        )
        callout_style = ParagraphStyle(
            "CalloutCN",
            parent=body_style,
            fontSize=10.2,
            leading=16,
            textColor=colors.HexColor("#334155"),
            backColor=colors.HexColor("#f8fafc"),
            borderColor=colors.HexColor("#e2e8f0"),
            borderWidth=0.6,
            borderPadding=7,
            borderRadius=4,
            spaceAfter=5,
        )

        color_map = self._player_color_map(replay_data)
        story: List[Any] = []
        story.append(Paragraph(escape(f"狼人杀战报：{replay_data.get('game_id', '-')}"), title_style))
        story.append(Paragraph(escape(self._build_opening_line(replay_data)), strap_style))

        summary_rows = [
            [
                Paragraph("玩家人数", small_style),
                Paragraph(str(replay_data.get("player_count", "-")), body_style),
                Paragraph("总回合", small_style),
                Paragraph(str(replay_data.get("current_round", "-")), body_style),
            ],
            [
                Paragraph("开始时间", small_style),
                Paragraph(self._paragraph_text(self._format_dt(replay_data.get("started_at"))), body_style),
                Paragraph("结束时间", small_style),
                Paragraph(self._paragraph_text(self._format_dt(replay_data.get("updated_at"))), body_style),
            ],
            [
                Paragraph("获胜阵营", small_style),
                Paragraph(self._paragraph_text(self._winner_label(replay_data.get("winner"))), body_style),
                Paragraph("收官原因", small_style),
                Paragraph(self._paragraph_text(self._safe_text(replay_data.get("game_over_reason") or "未结束")), body_style),
            ],
        ]
        summary_table = Table(summary_rows, colWidths=[23 * mm, 56 * mm, 23 * mm, 66 * mm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                    ("LEADING", (0, 0), (-1, -1), 14),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph("阵营名单", section_style))
        for line in self._build_scoreboard(replay_data):
            story.append(
                Paragraph(
                    self._replace_names_with_color(line.lstrip("- ").strip(), color_map),
                    bullet_style,
                    bulletText="•",
                )
            )

        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("关键转折", section_style))
        for point in self._build_turning_points(replay_data):
            story.append(
                Paragraph(
                    self._replace_names_with_color(point, color_map),
                    bullet_style,
                    bulletText="•",
                )
            )

        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("角色卡", section_style))
        roster_rows = [[Paragraph("玩家", small_style), Paragraph("身份画像", small_style)]]
        for agent in self._agent_rows(replay_data):
            roster_rows.append(
                [
                    Paragraph(self._name_span(agent["name"], color_map), name_style),
                    Paragraph(
                        self._paragraph_text(
                            f"{agent['role_cn']} / {self._faction_label(agent['faction'])} / "
                            f"{agent['mbti_type']} / IQ {agent['iq_level']}"
                        ),
                        body_style,
                    ),
                ]
            )
        roster_table = Table(roster_rows, colWidths=[34 * mm, 134 * mm], repeatRows=1)
        roster_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e5e7eb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEADING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(roster_table)

        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("回合战况", section_style))
        for round_num, events in self._group_events_by_round(replay_data).items():
            round_story = self._collect_round_story(round_num, events)
            block: List[Any] = [Paragraph(escape(f"第 {round_num} 回合"), subsection_style)]
            for line in self._build_round_digest(round_story):
                block.append(
                    Paragraph(
                        self._replace_names_with_color(line.lstrip("- ").strip(), color_map),
                        bullet_style,
                        bulletText="•",
                    )
                )
            if round_story["discussions"]:
                block.append(Paragraph("发言摘录", small_style))
                for item in round_story["discussions"]:
                    block.append(
                        Paragraph(
                            f"{self._name_span(item['name'], color_map)}：{self._replace_names_with_color(item['speech'], color_map)}",
                            callout_style,
                        )
                    )
            block.append(Spacer(1, 2 * mm))
            story.append(KeepTogether(block))

        story.append(Paragraph("附录：完整事件流", section_style))
        for round_num, events in self._group_events_by_round(replay_data).items():
            story.append(Paragraph(escape(f"第 {round_num} 回合原始纪要"), subsection_style))
            for event in events:
                for line in self._event_to_markdown(event).split("\n"):
                    clean_line = line.lstrip("- ").strip()
                    story.append(
                        Paragraph(
                            self._replace_names_with_color(clean_line, color_map),
                            small_style,
                        )
                    )
            story.append(Spacer(1, 1.5 * mm))

        story.append(Paragraph("新手术语", section_style))
        for line in self._glossary_lines():
            story.append(Paragraph(escape(line), bullet_style, bulletText="•"))

        doc.build(story)
        return buffer.getvalue()


werewolf_report_service = WerewolfReportService()
