"""Tests for UIState and model label helper — pure logic, no NiceGUI dependency."""
import pytest

from ui_state import UIState, build_model_label
from llama_client import ModelInfo


def test_vision_models_have_badge():
    model = ModelInfo(id="qwen3-vl-8b", is_vision=True)
    label = build_model_label(model)
    assert "👁" in label
    assert "qwen3-vl-8b" in label


def test_non_vision_models_no_badge():
    model = ModelInfo(id="qwen3.5-9b", is_vision=False)
    label = build_model_label(model)
    assert "👁" not in label
    assert "qwen3.5-9b" in label


def test_model_dropdown_populated_from_client():
    models = [
        ModelInfo(id="qwen3-vl-8b", is_vision=True),
        ModelInfo(id="qwen3.5-9b", is_vision=False),
    ]
    labels = [build_model_label(m) for m in models]
    assert any("qwen3-vl-8b" in l for l in labels)
    assert any("qwen3.5-9b" in l for l in labels)


def test_move_button_disabled_before_run():
    state = UIState()
    assert not state.move_button_enabled


def test_move_button_enabled_after_successful_run():
    state = UIState(rename_count=3, output_folder="/tmp/out")
    assert state.move_button_enabled


def test_run_button_disabled_during_run():
    state = UIState(is_running=True)
    assert not state.run_buttons_enabled


def test_progress_callback_appends_to_log():
    state = UIState()
    state.on_progress("success", "renamed: sunset.jpg")
    assert len(state.log_lines) == 1
    assert "success" in state.log_lines[0]
    assert "sunset.jpg" in state.log_lines[0]
