import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from app.config import PROVIDER_PRESETS, Settings
from app.model_gateway import ModelGateway


class TestProviderConfig(unittest.TestCase):
    def test_default_aliyun_endpoint_is_preserved(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_cloud_and_local_presets_are_available(self):
        for provider in ("qwen", "deepseek", "kimi", "ollama", "lmstudio"):
            self.assertIn(provider, PROVIDER_PRESETS)
            self.assertTrue(PROVIDER_PRESETS[provider]["models"])
            self.assertTrue(PROVIDER_PRESETS[provider]["base_url"])

    def test_provider_payload_uses_default_model_and_endpoint(self):
        settings = Settings.from_payload({"provider": "kimi"}, Settings(provider="kimi", api_key="old-key"))
        self.assertEqual(settings.provider, "kimi")
        self.assertEqual(settings.model, "kimi-k2-turbo-preview")
        self.assertEqual(settings.base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(settings.api_key, "old-key")

    def test_local_provider_is_live_without_api_key(self):
        settings = Settings.from_payload({"provider": "ollama"}, Settings(api_key="cloud-key", mode="live"))
        self.assertEqual(settings.mode, "live")
        self.assertEqual(settings.api_key, "")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode()

        with patch("urllib.request.urlopen", return_value=Response()) as opener:
            result = ModelGateway(settings).complete([{"role": "user", "content": "ping"}])
        self.assertTrue(result["ok"])
        request = opener.call_args.args[0]
        self.assertNotIn("Authorization", request.headers)

    def test_switching_cloud_provider_does_not_reuse_old_key(self):
        settings = Settings.from_payload(
            {"provider": "qwen", "api_key": ""},
            Settings(provider="deepseek", api_key="deepseek-key", mode="live"),
        )
        self.assertEqual(settings.api_key, "")
        self.assertEqual(settings.mode, "mock")

    def test_quick_setup_buttons_cover_cloud_and_local_choices(self):
        html = (pathlib.Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        for provider in ("qwen", "deepseek", "kimi", "ollama", "lmstudio"):
            self.assertIn(f'data-quick-provider="{provider}"', html)

    def test_avatar_assets_are_uniform_when_present(self):
        avatar_dir = pathlib.Path(__file__).parents[1] / "static" / "assets" / "avatars"
        paths = [avatar_dir / f"seat-{seat}.png" for seat in range(7)]
        self.assertTrue(all(path.is_file() for path in paths))
        import struct

        def png_shape(path):
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
            return width, height, bit_depth, color_type

        expected = png_shape(paths[0])
        for path in paths[1:]:
            self.assertEqual(png_shape(path), expected)
        self.assertEqual(expected, (512, 512, 8, 6))


if __name__ == "__main__":
    unittest.main()
