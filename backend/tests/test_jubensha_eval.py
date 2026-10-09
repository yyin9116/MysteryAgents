"""Jubensha evaluation statistics + MIRAGE converted packs smoke tests."""
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from models.jubensha import validate_script_pack  # noqa: E402
from services.jubensha_eval import compute_statistics  # noqa: E402


class _FakeAgent:
    def __init__(self, model_config):
        self.model_config = model_config


class _FakeRuntime:
    def __init__(self, char_id, name, camp, clues):
        self.char_id = char_id
        self.name = name
        self.char = type("C", (), {"camp": camp})()
        self.received_clues = clues
        self.agent = _FakeAgent({"model": "test-model"})


class _FakeService:
    """Minimal duck-typed service for compute_statistics."""

    def __init__(self):
        from models.jubensha import CharacterCamp

        self.script_pack = type("P", (), {"truth": type("T", (), {"murderer": "c02"})})()
        self.votes = {
            "c01": {"target": "c02"},
            "c03": {"target": "c02"},
            "c04": {"target": "c01"},
        }
        self.reveal_result = None
        self.game_events = [
            {
                "event_type": "discussion",
                "data": {
                    "agent_id": "c01",
                    "speech": "我觉得 c02 很可疑，那把刀呢？",
                    "suspicion": {"c02": 8, "c03": 2},
                },
            },
            {
                "event_type": "discussion",
                "data": {
                    "agent_id": "c03",
                    "speech": "同意 c02 嫌疑最大",
                    "suspicion": {"c02": 9, "c01": 1},
                },
            },
        ]
        clue = type("L", (), {"title": "染血匕首", "content": "一把染血的匕首"})()
        self.agents = {
            "c01": _FakeRuntime("c01", "甲", CharacterCamp.CIVILIAN, [clue]),
            "c02": _FakeRuntime("c02", "乙", CharacterCamp.MURDERER, []),
            "c03": _FakeRuntime("c03", "丙", CharacterCamp.CIVILIAN, []),
        }


def test_compute_statistics_mrr_tii():
    stats = compute_statistics(_FakeService())
    # murderer c02 ranked 1st in votes -> MRR 1.0
    assert stats["victory_mrr"] == 1.0
    # suspicion toward murderer (8, 9) >> overall -> high TII
    assert stats["tii"] is not None and stats["tii"] > 100
    assert stats["tii_details"]["suspicion_records"] == 4
    # c01 mentioned clue keyword 染血匕首? speech does not; ratio 0
    assert stats["cic_details"]["c01"]["clues_received"] == 1
    assert stats["cic_details"]["c01"]["clue_usage_ratio"] == 0.0
    # ICI present
    assert stats["ici"] is not None


def test_statistics_without_murderer_or_votes():
    svc = _FakeService()
    svc.script_pack.truth.murderer = None
    svc.votes = {}
    stats = compute_statistics(svc)
    assert stats["victory_mrr"] is None
    assert stats["tii"] is None


@pytest.mark.parametrize("pack_file", sorted((BACKEND / "scripts").glob("mirage_*.json")))
def test_mirage_packs_valid(pack_file):
    raw = json.loads(pack_file.read_text(encoding="utf-8"))
    report = validate_script_pack(raw)
    assert report["ok"], f"{pack_file.name}: {report['errors']}"
    characters = raw["characters"]
    assert len(characters) >= 4
    assert any(c["camp"] == "murderer" for c in characters)
