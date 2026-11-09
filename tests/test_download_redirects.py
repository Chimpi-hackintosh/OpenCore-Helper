"""Regression tests for release asset redirect trust boundaries."""

import io

import pytest

from openhelper.core import downloads
from openhelper.core.downloads import Asset, download_asset
from openhelper.errors import AppError


@pytest.mark.parametrize("redirect", [
    "https://evil.example/asset.zip",
    "http://release-assets.githubusercontent.com/asset.zip",
])
def test_rejects_untrusted_redirect(tmp_path, monkeypatch, redirect):
    class FakeResponse(io.BytesIO):
        url = redirect

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(downloads.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse(b"payload"))
    asset = Asset("OpenCore.zip", "https://github.com/acidanthera/OpenCorePkg/releases/download/test/OpenCore.zip", 7, None)
    target = tmp_path / "OpenCore.zip"
    with pytest.raises(AppError, match="untrusted_download"):
        download_asset(asset, target)
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))
