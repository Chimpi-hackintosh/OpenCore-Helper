"""Regression tests for release asset redirect trust boundaries."""

import io

import pytest

from openhelper.core import downloads
from openhelper.core.downloads import Asset, download_asset
from openhelper.errors import AppError


class FakeResponse(io.BytesIO):
    def __init__(self, content: bytes, url: str):
        super().__init__(content)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.mark.parametrize("redirect", [
    "https://evil.example/asset.zip",
    "http://release-assets.githubusercontent.com/asset.zip",
    "https://release-assets.githubusercontent.com.evil.example/asset.zip",
    "https://release-assets.githubusercontent.com:8443/asset.zip",
    "https://user@release-assets.githubusercontent.com/asset.zip",
])
def test_rejects_untrusted_redirect_before_following(tmp_path, monkeypatch, redirect):
    followed = []

    def fake_build_opener(handler):
        class FakeOpener:
            def open(self, request, timeout):
                # Simulate urllib receiving a 302. The handler must reject the
                # Location before the opener can issue a request to that host.
                next_request = handler.redirect_request(
                    request, None, 302, "Found", {"Location": redirect}, redirect
                )
                followed.append(next_request.full_url)
                raise AssertionError("untrusted redirect must not be followed")

        return FakeOpener()

    monkeypatch.setattr(downloads.urllib.request, "build_opener", fake_build_opener)
    asset = Asset(
        "OpenCore.zip",
        "https://github.com/acidanthera/OpenCorePkg/releases/download/test/OpenCore.zip",
        7,
        None,
    )
    target = tmp_path / "OpenCore.zip"

    with pytest.raises(AppError, match="untrusted_download"):
        download_asset(asset, target)

    assert followed == []
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))


def test_accepts_official_release_asset_redirect(tmp_path, monkeypatch):
    content = b"official release payload"
    followed = []

    def fake_build_opener(handler):
        class FakeOpener:
            def open(self, request, timeout):
                next_request = handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {"Location": "https://release-assets.githubusercontent.com/official.zip"},
                    "https://release-assets.githubusercontent.com/official.zip",
                )
                followed.append(next_request.full_url)
                return FakeResponse(content, next_request.full_url)

        return FakeOpener()

    monkeypatch.setattr(downloads.urllib.request, "build_opener", fake_build_opener)
    asset = Asset(
        "OpenCore.zip",
        "https://github.com/acidanthera/OpenCorePkg/releases/download/test/OpenCore.zip",
        len(content),
        None,
    )
    target = tmp_path / "OpenCore.zip"

    path, _, verified = download_asset(asset, target)

    assert followed == ["https://release-assets.githubusercontent.com/official.zip"]
    assert path == target
    assert path.read_bytes() == content
    assert verified is False
    assert not list(tmp_path.glob("*.part"))


def test_rejects_untrusted_final_response_url(tmp_path, monkeypatch):
    def fake_build_opener(handler):
        class FakeOpener:
            def open(self, request, timeout):
                return FakeResponse(b"payload", "https://evil.example/asset.zip")

        return FakeOpener()

    monkeypatch.setattr(downloads.urllib.request, "build_opener", fake_build_opener)
    asset = Asset(
        "OpenCore.zip",
        "https://github.com/acidanthera/OpenCorePkg/releases/download/test/OpenCore.zip",
        7,
        None,
    )
    target = tmp_path / "OpenCore.zip"

    with pytest.raises(AppError, match="untrusted_download"):
        download_asset(asset, target)

    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))
