"""Unit tests for PersonaConfig, loader, and dynamic prompt integration."""

import json
from pathlib import Path
import pytest
from app.models.persona import (
    AvoidInteractionsConfig,
    PersonalityConfig,
    PersonaConfig,
    TargetInteractionsConfig,
)
from app.planner.prompts import PromptBuilder


class TestPersonaConfig:
    """Test suite for persona configuration models and loaders."""

    def test_default_persona_structure(self):
        persona = PersonaConfig.default()
        assert persona.personality.name == "Aviral"
        assert len(persona.personality.style_rules) > 0
        assert len(persona.personality.example_comments) > 0
        assert len(persona.what_to_interact_with.topics) > 0
        assert len(persona.what_to_interact_with.keywords) > 0
        assert len(persona.what_to_not_interact_with.topics) > 0
        assert "crypto" in persona.what_to_not_interact_with.negative_keywords
        assert "airdrop" in persona.what_to_not_interact_with.negative_keywords

    def test_load_from_valid_file(self, tmp_path):
        custom_data = {
            "personality": {
                "name": "Alex",
                "role": "Python Backend Engineer",
                "bio": "Open-source contributor building distributed systems.",
                "tone": "Direct, technical, witty",
                "style_rules": ["Be concise", "No buzzwords"],
                "example_comments": ["Clean architecture! Did you benchmark this?"],
            },
            "what_to_interact_with": {
                "topics": ["Distributed systems", "Rust", "Python performance"],
                "keywords": ["rust", "python", "benchmark", "fastapi"],
                "preferred_actions": {"benchmarks": "comment"},
            },
            "what_to_not_interact_with": {
                "topics": ["Crypto pumps", "Politics"],
                "negative_keywords": ["memecoin", "presale", "airdrop"],
                "blocked_accounts": ["@spammer123"],
                "content_restrictions": ["No offensive words"],
            },
        }
        file_path = tmp_path / "custom_persona.json"
        file_path.write_text(json.dumps(custom_data), encoding="utf-8")

        loaded = PersonaConfig.load_from_file(str(file_path))
        assert loaded.personality.name == "Alex"
        assert loaded.personality.role == "Python Backend Engineer"
        assert "rust" in loaded.what_to_interact_with.keywords
        assert "@spammer123" in loaded.what_to_not_interact_with.blocked_accounts

    def test_load_from_file_with_comments(self, tmp_path):
        content_with_comments = """
        // Top-level persona config
        {
          "personality": {
            "name": "DevG", /* in-line comment */
            "role": "Engineer",
            "bio": "Building in public",
            "tone": "Chill",
            "style_rules": ["Rule 1"],
            "example_comments": ["Nice work!"]
          },
          "what_to_interact_with": {
            "topics": ["AI agents"],
            "keywords": ["agent"],
            "preferred_actions": {}
          },
          "what_to_not_interact_with": {
            "topics": ["Spam"],
            "negative_keywords": ["giveaway"],
            "blocked_accounts": [],
            "content_restrictions": []
          }
        }
        """
        file_path = tmp_path / "commented_persona.json"
        file_path.write_text(content_with_comments, encoding="utf-8")

        loaded = PersonaConfig.load_from_file(str(file_path))
        assert loaded.personality.name == "DevG"
        assert "agent" in loaded.what_to_interact_with.keywords

    def test_load_non_existent_file_falls_back_to_default(self, tmp_path):
        missing_file = tmp_path / "non_existent.json"
        loaded = PersonaConfig.load_from_file(str(missing_file))
        assert isinstance(loaded, PersonaConfig)
        assert loaded.personality.name == "Aviral"

    def test_load_corrupted_file_falls_back_to_default(self, tmp_path):
        bad_file = tmp_path / "corrupt.json"
        bad_file.write_text("{ this is not valid json : [[", encoding="utf-8")
        loaded = PersonaConfig.load_from_file(str(bad_file))
        assert isinstance(loaded, PersonaConfig)
        assert loaded.personality.name == "Aviral"

    def test_save_and_reload(self, tmp_path):
        persona = PersonaConfig.default()
        persona.personality.name = "TestUser"
        target_path = tmp_path / "sub" / "saved_persona.json"
        persona.save_to_file(str(target_path))

        assert target_path.exists()
        reloaded = PersonaConfig.load_from_file(str(target_path))
        assert reloaded.personality.name == "TestUser"

    def test_build_system_prompt_incorporates_persona_fields(self):
        persona = PersonaConfig.default()
        persona.personality.name = "CustomPersona"
        persona.personality.role = "Security Researcher"
        persona.personality.tone = "Ultra-analytical and calm"
        persona.what_to_interact_with.keywords.append("zero-day")
        persona.what_to_not_interact_with.negative_keywords.append("nft_drop")

        prompt = PromptBuilder.build_system_prompt(persona)

        assert "CustomPersona" in prompt
        assert "Security Researcher" in prompt
        assert "Ultra-analytical and calm" in prompt
        assert "zero-day" in prompt
        assert "nft_drop" in prompt
        assert "BIO & IDENTITY:" in prompt
        assert "WHAT TO INTERACT WITH" in prompt
        assert "WHAT TO STRICTLY AVOID / SKIP" in prompt

