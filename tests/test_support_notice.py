import copy
import datetime as dt
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support_notice as support
from openhelper.core import windows_update


class SupportNoticeTests(unittest.TestCase):
    def test_only_older_known_versions_warn(self):
        for current in ["3.0.2", "3.0.2-build-999", "4.0.0", "garbage", None]:
            self.assertIsNone(support.notice("OpenCore-Helper", current))
        self.assertIsNone(support.notice("Unknown-private-app", "0.0.1"))
        self.assertIsNone(support.notice("ChimpiConstrucoes", "1.0.0"))
        self.assertIsNotNone(support.notice("OpenCore-Helper", "3.0.0"))

    def test_cutoff_is_exact_and_has_a_year(self):
        before = dt.datetime(2026, 11, 3, 23, 59, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(seconds=1)
        self.assertEqual(support.notice("OpenCore-Helper", "2.0.0", now=before)["phase"], "before")
        self.assertEqual(support.notice("OpenCore-Helper", "2.0.0", now=after)["phase"], "after")
        self.assertIn("2026", support.notice("OpenCore-Helper", "2.0.0", now=before)["body"])

    def test_numeric_comparison_not_lexical(self):
        self.assertGreater(support.version("1.10.0"), support.version("1.9.9"))
        self.assertLess(support.version("v1.1.0-preview.2"), support.version("v1.1.0-preview.3"))
        for value in ["1.0", "prefix1.0.0", "1.0.0<script>", "9" * 101, None]:
            self.assertIsNone(support.version(value))

    def test_language_detection_and_fallback(self):
        self.assertEqual(support.language("pt_BR.UTF-8"), "pt")
        self.assertEqual(support.language("en-US"), "en")
        self.assertEqual(support.language("xx-ZZ"), "en")
        for lang in support.MESSAGES:
            for phase, date in [("before", dt.datetime(2026, 11, 1)), ("after", dt.datetime(2026, 11, 4))]:
                item = support.notice("OpenCore-Helper", "2.0.0", now=date, lang=lang)
                self.assertNotIn("{", item["body"])
                self.assertEqual(item["title"], support.MESSAGES[lang][phase])

    def test_untrusted_links_and_downgrades_are_ignored(self):
        for url in ["http://github.com/Chimpi-hackintosh/OpenCore-Helper", "https://evil.test/", "https://github.com/Other/OpenCore-Helper", "https://github.com/Chimpi-hackintosh/Other", "https://github.com@evil.test/Chimpi-hackintosh/OpenCore-Helper"]:
            candidate = copy.deepcopy(support.POLICY)
            candidate["apps"]["OpenCore-Helper"].update(minimum="99.0.0", url=url)
            self.assertEqual(support.checked_policy(candidate), support.POLICY)
        candidate = copy.deepcopy(support.POLICY)
        candidate["apps"]["OpenCore-Helper"]["minimum"] = "1.0.0"
        self.assertEqual(support.checked_policy(candidate), support.POLICY)

    def test_network_failure_uses_bundled_policy(self):
        with patch.object(support, "read_json", side_effect=OSError("offline")):
            self.assertIsNotNone(support.check("OpenCore-Helper", "2.0.0"))
            self.assertIsNone(support.check("OpenCore-Helper", "3.0.2"))
        with patch.object(support, "read_json") as read:
            self.assertIsNone(support.check("Unknown-private-app", "1.0.0"))
            read.assert_not_called()

    def test_release_channels_and_assets(self):
        url = "https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases/tag/v4.0.0"
        candidate = dict(tag_name="v4.0.0", html_url=url, assets=[{}], draft=False, prerelease=False)
        for invalid in [dict(candidate, draft=True), dict(candidate, assets=[]), dict(candidate, prerelease=True), dict(candidate, html_url="https://evil.test/")]:
            self.assertEqual(support.with_releases(support.POLICY, "OpenCore-Helper", [invalid]), support.POLICY)
        result = support.with_releases(support.POLICY, "OpenCore-Helper", [candidate])
        self.assertIsNotNone(support.notice("OpenCore-Helper", "3.0.2", result))
        self.assertEqual(support.release_version("v0.1-lite.3", "lite"), "0.1.3")
        self.assertIsNone(support.release_version("v0.2-games.1", "lite"))

    def test_smoke_flags_never_start_network(self):
        with patch.object(support.sys, "argv", ["app", "--gui-smoke", "report.json"]):
            self.assertFalse(support.enabled())
        with patch.dict(support.os.environ, {"CHIMPI_SUPPORT_CHECK": "0"}):
            self.assertFalse(support.enabled())


class WindowsUpdateTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"test installer bytes"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.catalog = dict(windows_update.SETUP_302, digest="sha256:" + self.digest)
        self.entry = support.POLICY["apps"]["OpenCore-Helper"]
        self.asset = {
            "name": "OpenCoreHelper-3.0.2-Setup-x64.exe",
            "digest": self.catalog["digest"],
            "size": len(self.payload),
            "browser_download_url": (
                "https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases/download/"
                "v3.0.2/OpenCoreHelper-3.0.2-Setup-x64.exe"
            ),
        }
        self.release = {
            "tag_name": "v3.0.2",
            "html_url": self.entry["url"],
            "draft": False,
            "prerelease": False,
            "published_at": "2026-11-02T13:41:00Z",
            "assets": [self.asset],
        }
        self.setup = windows_update.select_setup(self.entry, self.catalog, [self.release])

    def test_only_exact_approved_published_setup_is_eligible(self):
        self.assertEqual(self.setup.digest, self.digest)
        for changed in (
            {"draft": True}, {"prerelease": True}, {"published_at": None},
            {"assets": [dict(self.asset, digest=None)]},
            {"assets": [dict(self.asset, browser_download_url="https://example.com/setup.exe")]},
        ):
            self.assertIsNone(windows_update.select_setup(self.entry, self.catalog, [dict(self.release, **changed)]))
        self.assertIsNone(windows_update.select_setup(self.entry, dict(self.catalog, digest="sha256:" + "0" * 64),
                                                     [self.release]))
        self.assertIsNone(windows_update.select_setup(self.entry, dict(self.catalog, min_build=True), [self.release]))

    def test_only_verified_local_package_enables_reinstall_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            target = staging / self.setup.name
            with patch.object(windows_update.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = lambda *args, **kwargs: io.BytesIO(self.payload)
                self.assertEqual(windows_update.stage(self.setup, staging), target)
                self.assertEqual(target.read_bytes(), self.payload)
            self.assertFalse(windows_update.attempted(self.setup, staging))
            with patch.object(windows_update, "compatible", return_value=True), patch.object(
                windows_update.os, "startfile", create=True
            ) as start:
                windows_update.launch(self.setup, staging)
                start.assert_called_once_with(str(target))
                self.assertTrue(windows_update.attempted(self.setup, staging))
                target.write_bytes(b"tampered")
                self.assertFalse(windows_update.attempted(self.setup, staging))
                with self.assertRaises(ValueError):
                    windows_update.launch(self.setup, staging)
                start.assert_called_once()

    def test_incorrect_bytes_are_never_staged(self):
        for payload in (b"X" * self.setup.size, self.payload + b"X", b"short"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory, patch.object(
                windows_update.urllib.request, "build_opener"
            ) as opener:
                opener.return_value.open.return_value = io.BytesIO(payload)
                with self.assertRaises(ValueError):
                    windows_update.stage(self.setup, Path(directory))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_release_redirects_reject_external_hosts_and_http(self):
        for url in ("http://github.com/", "https://github.com.example.org/", "https://user@github.com/"):
            self.assertFalse(windows_update.trusted_asset_host(url))
        self.assertTrue(windows_update.trusted_asset_host("https://release-assets.githubusercontent.com/asset"))

    def test_mandatory_flow_requires_post_cutoff_windows_and_an_older_version(self):
        before = dt.datetime(2026, 11, 3, 23, 59, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(seconds=1)
        notice = support.notice
        with patch.object(support, "read_json", side_effect=[{}, [self.release]] * 3), patch.object(
            support.sys, "platform", "win32"
        ), patch.object(windows_update, "find_update", return_value=(self.setup, Path("updates"), False)) as find:
            with patch.object(support, "notice", side_effect=lambda app, current, policy: notice(
                app, current, policy, now=before, lang="en"
            )):
                self.assertNotIn("windows_update", support.check("OpenCore-Helper", "3.0.1"))
            find.assert_not_called()
            with patch.object(support, "notice", side_effect=lambda app, current, policy: notice(
                app, current, policy, now=after, lang="en"
            )):
                self.assertIsNone(support.check("OpenCore-Helper", "3.0.2"))
                self.assertIn("windows_update", support.check("OpenCore-Helper", "3.0.1"))
            find.assert_called_once()


class PrereleaseVersionTests(unittest.TestCase):
    def test_semver_precedence_and_existing_build_labels(self):
        self.assertLess(support.version("1.1.0-preview.2"), support.version("1.1.0-preview.3"))
        self.assertLess(support.version("1.1.0-preview.9"), support.version("1.1.0-preview.10"))
        self.assertLess(support.version("1.1.0-alpha"), support.version("1.1.0-beta"))
        self.assertLess(support.version("1.1.0-preview.3"), support.version("1.1.0"))
        self.assertEqual(support.version("3.0.2-build-999"), support.version("3.0.2"))
        self.assertEqual(support.version("1.1.0+build.1"), support.version("1.1.0+build.2"))
        self.assertIsNone(support.version("1.1.0-preview..3"))
        self.assertIsNone(support.version("1.1.0-01"))

    def test_chimpicode_preview_floor_and_next_release(self):
        self.assertEqual(support.POLICY["apps"]["ChimpiCode"]["minimum"], "1.1.0-preview.3")
        self.assertIsNotNone(support.notice("ChimpiCode", "1.1.0-preview.2"))
        self.assertIsNone(support.notice("ChimpiCode", "1.1.0-preview.3"))
        self.assertIsNone(support.notice("ChimpiCode", "1.1.0"))
        release = {
            "tag_name": "v1.1.0-preview.4",
            "html_url": "https://github.com/Chimpi-hackintosh/ChimpiCode/releases/tag/v1.1.0-preview.4",
            "assets": [{}],
            "draft": False,
            "prerelease": True,
        }
        updated = support.with_releases(support.POLICY, "ChimpiCode", [release])
        self.assertEqual(updated["apps"]["ChimpiCode"]["minimum"], "1.1.0-preview.4")
        self.assertEqual(updated["apps"]["ChimpiCode"]["tag"], "v1.1.0-preview.4")


if __name__ == "__main__":
    unittest.main()
