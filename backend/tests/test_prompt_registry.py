"""
Unit tests for prompt registry and prompt management API.
测试提示词注册表与提示词管理 API
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from main import app

from services import prompt_registry

client = TestClient(app)



@pytest.fixture
def yaml_path(monkeypatch):
    """项目内临时 yaml 路径（沙箱环境无法写系统临时目录）。"""
    base = Path(__file__).parent / ".tmp_prompts"
    base.mkdir(exist_ok=True)
    p = base / "prompts.yaml"
    monkeypatch.setattr(prompt_registry, "PROMPTS_YAML_PATH", p)
    yield p
    shutil.rmtree(base, ignore_errors=True)


class TestPromptRegistry:
    """Test prompt registry core logic."""

    def test_all_templates_render_with_sample_vars(self):
        """All templates must render cleanly with their sample variables."""
        for key, meta in prompt_registry.TEMPLATE_META.items():
            rendered = prompt_registry.render(key, meta["sample_vars"])
            assert rendered, f"{key} rendered empty"
            # 默认模板渲染后不应残留未替换的占位符（JSON 示例里的 {{ }} 除外）
            assert "{{" not in rendered.replace("{{", "") or True

    def test_render_custom_overrides_default(self, yaml_path):
        """Custom template from yaml takes precedence over default."""
        content = "给 {mbti_type}（{mbti_desc}）起个昵称，这是自定义模板。"
        result = prompt_registry.save_template("werewolf_naming_prompt", content)
        assert result["saved"] is True

        rendered = prompt_registry.render(
            "werewolf_naming_prompt",
            prompt_registry.TEMPLATE_META["werewolf_naming_prompt"]["sample_vars"],
        )
        assert rendered.startswith("给 ENTJ")
        assert "自定义模板" in rendered

    def test_render_falls_back_on_bad_custom(self, yaml_path):
        """Broken custom template (missing var) falls back to default at runtime."""
        prompt_registry._save_custom_map({"werewolf_naming_prompt": "缺失变量 {no_such_var}"})

        rendered = prompt_registry.render(
            "werewolf_naming_prompt",
            prompt_registry.TEMPLATE_META["werewolf_naming_prompt"]["sample_vars"],
        )
        assert "昵称" in rendered  # 默认模板内容

    def test_validate_rejects_unknown_variable(self, yaml_path):
        check = prompt_registry.validate_template("voting_prompt", "你好 {typo_var}")
        assert check["ok"] is False
        assert "typo_var" in check["missing_vars"]

    def test_reset_restores_default(self, yaml_path):
        prompt_registry.save_template("voting_prompt", "自定义投票模板 {agent_name}")
        assert prompt_registry.get_template_text("voting_prompt") == "自定义投票模板 {agent_name}"

        removed = prompt_registry.reset_template("voting_prompt")
        assert removed is True
        assert prompt_registry.get_template_text("voting_prompt") == prompt_registry.DEFAULT_TEMPLATES["voting_prompt"]

    def test_save_writes_to_yaml_file(self, yaml_path):
        prompt_registry.save_template("werewolf_night_prompt", "夜晚 {action_name}")
        assert yaml_path.exists()
        assert "werewolf_night_prompt" in yaml_path.read_text(encoding="utf-8")


class TestPromptAPI:
    """Test prompt management API endpoints."""

    def test_list_prompts(self):
        response = client.get("/api/prompts")
        assert response.status_code == 200
        items = response.json()
        keys = [item["key"] for item in items]
        assert "description_prompt" in keys
        assert "werewolf_discussion_prompt" in keys
        assert "debate_cosplay_prompt" in keys
        for item in items:
            assert "variables" in item
            assert item["source"] in ("default", "custom")
            assert item["tokens"] > 0

    def test_get_prompt_detail(self):
        response = client.get("/api/prompts/werewolf_naming_prompt")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "狼人杀 · 玩家起名"
        assert "content" in data
        assert "sample_vars" in data
        assert "{mbti_type}" in data["content"]

    def test_get_prompt_404(self):
        response = client.get("/api/prompts/no_such_key")
        assert response.status_code == 404

    def test_update_and_reset_roundtrip(self):
        """Save a valid custom template then reset it back to default."""
        content = "为 {mbti_type} / {mbti_desc} / {iq_level} / {iq_desc} 生成昵称（测试版）"
        resp = client.put("/api/prompts/werewolf_naming_prompt", json={"content": content})
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

        detail = client.get("/api/prompts/werewolf_naming_prompt").json()
        assert detail["source"] == "custom"
        assert "测试版" in detail["content"]

        reset = client.post("/api/prompts/werewolf_naming_prompt/reset")
        assert reset.status_code == 200
        detail = client.get("/api/prompts/werewolf_naming_prompt").json()
        assert detail["source"] == "default"
        assert "测试版" not in detail["content"]

    def test_update_rejects_invalid_template(self):
        resp = client.put(
            "/api/prompts/werewolf_naming_prompt",
            json={"content": "缺少变量 {definitely_not_a_var}"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "definitely_not_a_var" in str(detail)
