"""Tests for LlamaClient — OpenAI-compatible inference client."""
import json

import pytest
import responses as responses_lib

from llama_client import (
    LlamaClient,
    LlamaConnectionError,
    LlamaResponseError,
    ModelInfo,
    _is_vision_model,
)

BASE_URL = "http://localhost:8080"

MODELS_PAYLOAD = {
    "data": [
        {"id": "qwen3-vl-8b"},
        {"id": "gemma4-e4b"},
        {"id": "qwen3.5-9b"},
        {"id": "deepseek-r1-14b"},
    ]
}

ANALYZE_RESPONSE = {
    "choices": [
        {"message": {"content": "CATEGORY: animal\nDESCRIPTION: brown dog running in park"}}
    ]
}


def test_vision_flag_set_for_vl_in_name():
    assert _is_vision_model("qwen3-vl-8b") is True


def test_vision_flag_set_for_gemma4():
    assert _is_vision_model("gemma4-e4b") is True


def test_vision_flag_false_for_text_model():
    assert _is_vision_model("qwen3.5-9b") is False


@responses_lib.activate
def test_list_models_returns_model_ids():
    responses_lib.add(responses_lib.GET, f"{BASE_URL}/v1/models", json=MODELS_PAYLOAD)
    client = LlamaClient(base_url=BASE_URL)
    models = client.list_models()
    ids = [m.id for m in models]
    assert "qwen3-vl-8b" in ids
    assert "qwen3.5-9b" in ids
    assert all(isinstance(m, ModelInfo) for m in models)


@responses_lib.activate
def test_vision_models_sorted_first():
    responses_lib.add(responses_lib.GET, f"{BASE_URL}/v1/models", json=MODELS_PAYLOAD)
    client = LlamaClient(base_url=BASE_URL)
    models = client.list_models()
    vision_indices = [i for i, m in enumerate(models) if m.is_vision]
    non_vision_indices = [i for i, m in enumerate(models) if not m.is_vision]
    assert vision_indices  # at least one vision model
    assert non_vision_indices  # at least one non-vision model
    assert max(vision_indices) < min(non_vision_indices)


@responses_lib.activate
def test_analyze_image_sends_base64(tmp_image_dir):
    responses_lib.add(
        responses_lib.POST, f"{BASE_URL}/v1/chat/completions", json=ANALYZE_RESPONSE
    )
    client = LlamaClient(base_url=BASE_URL, model="qwen3-vl-8b")
    image = list(tmp_image_dir.glob("*.jpg"))[0]
    client.analyze_image(image)

    request_body = json.loads(responses_lib.calls[0].request.body)
    content = request_body["messages"][0]["content"]
    image_part = next(p for p in content if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


@responses_lib.activate
def test_analyze_image_returns_category_description(tmp_image_dir):
    responses_lib.add(
        responses_lib.POST,
        f"{BASE_URL}/v1/chat/completions",
        json={
            "choices": [
                {"message": {"content": "CATEGORY: landscape\nDESCRIPTION: sunset over mountains"}}
            ]
        },
    )
    client = LlamaClient(base_url=BASE_URL, model="qwen3-vl-8b")
    image = list(tmp_image_dir.glob("*.jpg"))[0]
    category, description = client.analyze_image(image)
    assert category == "landscape"
    assert description == "sunset_over_mountains"


@responses_lib.activate
def test_analyze_image_raises_on_bad_response(tmp_image_dir):
    responses_lib.add(
        responses_lib.POST,
        f"{BASE_URL}/v1/chat/completions",
        json={"choices": [{"message": {"content": "This image shows a dog."}}]},
    )
    client = LlamaClient(base_url=BASE_URL, model="qwen3-vl-8b")
    image = list(tmp_image_dir.glob("*.jpg"))[0]
    with pytest.raises(LlamaResponseError):
        client.analyze_image(image)


@responses_lib.activate
def test_validate_connection_true_on_200():
    responses_lib.add(
        responses_lib.GET, f"{BASE_URL}/health", json={"status": "ok"}, status=200
    )
    client = LlamaClient(base_url=BASE_URL)
    assert client.validate_connection() is True


@responses_lib.activate
def test_validate_connection_falls_back_to_models_on_404():
    responses_lib.add(responses_lib.GET, f"{BASE_URL}/health", status=404)
    responses_lib.add(responses_lib.GET, f"{BASE_URL}/v1/models", json=MODELS_PAYLOAD, status=200)
    client = LlamaClient(base_url=BASE_URL)
    assert client.validate_connection() is True


@responses_lib.activate
def test_validate_connection_raises_on_failure():
    responses_lib.add(
        responses_lib.GET,
        f"{BASE_URL}/health",
        body=ConnectionError("Connection refused"),
    )
    client = LlamaClient(base_url=BASE_URL)
    with pytest.raises(LlamaConnectionError):
        client.validate_connection()
