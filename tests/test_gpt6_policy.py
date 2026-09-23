import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import advisor, config


class GPT6PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_default_is_luna_medium_with_sol_then_astra_escalation(self):
        settings = config.load(self.root)
        self.assertEqual(settings["model"], "gpt-6-luna")
        self.assertEqual(settings["reasoning"], "medium")
        self.assertEqual(settings["diagnostic_models"], [
            {"model": "gpt-6-sol", "reasoning": "high"},
            {"model": "gpt-6-astra", "reasoning": "high"},
        ])

    def test_legacy_defaults_migrate_without_rewriting_global_codex_config(self):
        private = config.private_dir(self.root)
        (private / "config.json").write_text(json.dumps({
            "model": "gpt-5.6-luna", "reasoning": "medium", "fast": False,
            "port": 8765, "idle_seconds": 3600, "step_timeout_seconds": 1800,
            "verify_timeout_seconds": 600, "retry_base_seconds": 15,
            "retry_max_seconds": 3600, "github_progress_seconds": 60,
        }))
        (private / "features.json").write_text(json.dumps({
            "github_followups": True, "github_operators": [],
            "diagnostic_escalation": True,
            "diagnostic_models": [{"model": "gpt-5.6-terra", "reasoning": "high"}],
            "diagnostic_min_attempts": 3, "diagnostic_cooldown_seconds": 3600,
            "diagnostic_timeout_seconds": 180, "framework_check_seconds": 86400,
        }))
        settings = config.load(self.root)
        self.assertEqual(settings["model"], "gpt-6-luna")
        self.assertEqual(settings["diagnostic_models"], config.GPT6_ESCALATION)

    def test_non_gpt6_models_are_rejected_at_configuration_and_advisor_boundaries(self):
        for model in ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.5", "gpt-reserve", "custom-model"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                config.save(self.root, {"model": model})
        with self.assertRaises(ValueError):
            config.save(self.root, {"diagnostic_models": [{"model": "gpt-5.6-sol", "reasoning": "high"}]})
        settings = dict(config.load(self.root), diagnostic_models=[{"model": "gpt-5.6-sol", "reasoning": "high"}])
        models = [{"id": "gpt-5.6-sol", "reasoning": ["high"]}]
        self.assertEqual(advisor.candidates(settings, models), [])

    def test_catalog_exposes_only_gpt6_family_for_automatic_selection(self):
        cache = self.root / "models_cache.json"
        cache.write_text(json.dumps({"models": [
            {"slug": "gpt-5.6-luna", "supported_reasoning_levels": ["medium", "high"]},
            {"slug": "gpt-6-luna", "supported_reasoning_levels": ["medium", "high"]},
            {"slug": "gpt-6-sol", "supported_reasoning_levels": ["medium", "high"]},
            {"slug": "gpt-6-astra", "supported_reasoning_levels": ["medium", "high"]},
            {"slug": "gpt-5.6-terra", "supported_reasoning_levels": ["high"]},
        ]}))
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root)}):
            self.assertEqual([m["id"] for m in config.available_models()],
                             ["gpt-6-luna", "gpt-6-sol", "gpt-6-astra"])

    def test_advisor_progresses_luna_high_then_sol_high_then_astra_high(self):
        settings = config.load(self.root)
        catalog = [
            {"id": "gpt-6-luna", "reasoning": ["medium", "high"]},
            {"id": "gpt-6-sol", "reasoning": ["medium", "high"]},
            {"id": "gpt-6-astra", "reasoning": ["medium", "high"]},
        ]
        luna = {"kind": "advisor_started", "data": {"model": "gpt-6-luna", "reasoning": "high"}}
        sol = {"kind": "advisor_started", "data": {"model": "gpt-6-sol", "reasoning": "high"}}
        sol_delegation = {"kind": "delegation_started", "data": {"model": "gpt-6-sol", "reasoning": "high"}}
        with patch("agent_os.advisor.config.available_models", return_value=catalog):
            self.assertEqual(advisor.selection(settings, "consult_reasoning"),
                             {"model": "gpt-6-luna", "reasoning": "high"})
            self.assertIsNone(advisor.selection(settings, "consult_reasoning", [luna]))
            self.assertEqual(advisor.selection(settings, "consult_model", [luna]),
                             {"model": "gpt-6-sol", "reasoning": "high"})
            self.assertEqual(advisor.selection(settings, "consult_model", [luna, sol]),
                             {"model": "gpt-6-astra", "reasoning": "high"})
            self.assertEqual(advisor.selection(settings, "delegate", [sol]),
                             {"model": "gpt-6-sol", "reasoning": "high"})
            self.assertEqual(advisor.selection(settings, "delegate", [sol, sol_delegation]),
                             {"model": "gpt-6-astra", "reasoning": "high"})


if __name__ == "__main__":
    unittest.main()
