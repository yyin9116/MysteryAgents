import json
from pathlib import Path

from services.werewolf_report_service import werewolf_report_service


def _load_replay() -> dict:
    replay_path = Path("/Users/yinyin/test/killer/game_states/werewolf_replays/glm45_long9_20260323.json")
    return json.loads(replay_path.read_text(encoding="utf-8"))


def test_markdown_report_reads_like_battle_report():
    replay_data = _load_replay()

    markdown = werewolf_report_service.build_markdown(replay_data)

    assert "# 狼人杀战报" in markdown
    assert "## 关键转折" in markdown
    assert "## 回合战况" in markdown
    assert "## 完整事件流" in markdown
    assert "## 角色卡" in markdown


def test_pdf_report_generation_returns_nonempty_bytes():
    replay_data = _load_replay()

    pdf_bytes = werewolf_report_service.build_pdf(replay_data)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
