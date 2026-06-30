from pathlib import Path


def test_file_uploader_css_only_targets_dropzone_browse_button() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'div[data-testid="stFileUploaderDropzone"] button {' in source
    assert 'div[data-testid="stFileUploaderDropzone"] button:hover {' in source
    assert 'div[data-testid="stFileUploader"] button,' not in source
    assert 'div[data-testid="stFileUploader"] button:hover,' not in source
    assert "uploaded-file pills also contain remove (x) buttons" in source


def test_file_uploader_uploaded_file_remove_controls_are_not_action_styled() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    upload_block_start = source.index('/* Upload controls have a built-in Browse button')
    upload_block_end = source.index('/* Labels for user input points', upload_block_start)
    upload_block = source[upload_block_start:upload_block_end]

    assert 'stFileUploaderDropzone' in upload_block
    assert 'stFileUploader"] button' not in upload_block
    assert 'stFileUploader"] button:hover' not in upload_block
