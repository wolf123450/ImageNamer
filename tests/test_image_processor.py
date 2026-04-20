"""Tests for ImageProcessor v2 additions: input folder, move_to_output, progress_callback."""
from pathlib import Path

import pytest

from image_processor import ImageProcessor, MoveResult
from config import Config


def test_rename_in_place(tmp_image_dir, mocker):
    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("animal", "brown_dog_running")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir

    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    original_name = image.name

    success, new_filename, error = processor.process_image(image)

    assert success
    assert error is None
    assert (tmp_image_dir / new_filename).exists()
    assert not (tmp_image_dir / original_name).exists()


def test_rename_dry_run_no_change(tmp_image_dir, mocker):
    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("animal", "brown_dog_running")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir

    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    original_name = image.name

    success, new_filename, error = processor.process_image(image, dry_run=True)

    assert success
    assert (tmp_image_dir / original_name).exists()  # File NOT renamed


def test_separate_input_folder_scanned(tmp_image_dir, mocker, monkeypatch):
    monkeypatch.setattr(Config, "INPUT_FOLDER", str(tmp_image_dir))

    mock_client = mocker.MagicMock()
    processor = ImageProcessor(mock_client)

    images = processor.discover_images()
    assert len(images) == 3


def test_move_to_output_moves_renamed_files(tmp_image_dir, tmp_path, mocker):
    output_dir = tmp_path / "output"

    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("landscape", "sunset_over_ocean")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir
    processor.output_folder = str(output_dir)

    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    success, new_filename, _ = processor.process_image(image)
    assert success

    result = processor.move_to_output()

    assert result.moved == 1
    assert result.errors == []
    assert (output_dir / new_filename).exists()


def test_move_to_output_dry_run_no_move(tmp_image_dir, tmp_path, mocker):
    output_dir = tmp_path / "output"

    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("landscape", "sunset_over_ocean")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir
    processor.output_folder = str(output_dir)

    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    processor.process_image(image)

    result = processor.move_to_output(dry_run=True)

    assert result.moved == 0
    assert not output_dir.exists() or not any(output_dir.iterdir())


def test_move_to_output_noop_when_no_output_folder(tmp_image_dir, mocker):
    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("landscape", "sunset_over_ocean")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir
    processor.output_folder = ""

    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    processor.process_image(image)

    result = processor.move_to_output()

    assert result.moved == 0
    assert result.skipped == 1


def test_move_resolves_filename_conflict(tmp_image_dir, tmp_path, mocker):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    mock_client = mocker.MagicMock()
    mock_client.analyze_image.return_value = ("landscape", "sunset_over_ocean")

    processor = ImageProcessor(mock_client)
    processor.image_folder = tmp_image_dir
    processor.output_folder = str(output_dir)

    # Rename one image
    image = sorted(tmp_image_dir.glob("*.jpg"))[0]
    success, new_filename, _ = processor.process_image(image)
    assert success

    # Pre-create a conflicting file in the output directory
    conflicting = output_dir / new_filename
    conflicting.touch()

    result = processor.move_to_output()

    assert result.moved == 1
    assert result.errors == []
    # File moved with -2 suffix
    stem = Path(new_filename).stem
    ext = Path(new_filename).suffix
    assert (output_dir / f"{stem}-2{ext}").exists()
