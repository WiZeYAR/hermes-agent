"""Tests for TTS speed configuration across providers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("OPENAI_API_KEY", "MINIMAX_API_KEY", "HERMES_SESSION_PLATFORM"):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Edge TTS speed
# ---------------------------------------------------------------------------

class TestEdgeTtsSpeed:
    def _run(self, tts_config, tmp_path):
        mock_comm = MagicMock()
        mock_comm.save = AsyncMock()
        mock_edge = MagicMock()
        mock_edge.Communicate = MagicMock(return_value=mock_comm)

        with patch("tools.tts_tool._import_edge_tts", return_value=mock_edge):
            from tools.tts_tool import _generate_edge_tts
            asyncio.run(_generate_edge_tts("Hello", str(tmp_path / "out.mp3"), tts_config))
        return mock_edge.Communicate

    def test_default_no_rate_kwarg(self, tmp_path):
        """No speed config => no rate kwarg passed to Communicate."""
        comm_cls = self._run({}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert "rate" not in kwargs

    def test_global_speed_applied(self, tmp_path):
        """Global tts.speed used as fallback."""
        comm_cls = self._run({"speed": 1.5}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert kwargs["rate"] == "+50%"

    def test_provider_speed_overrides_global(self, tmp_path):
        """tts.edge.speed takes precedence over tts.speed."""
        comm_cls = self._run({"speed": 1.5, "edge": {"speed": 2.0}}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert kwargs["rate"] == "+100%"

    def test_speed_below_one(self, tmp_path):
        """Speed < 1.0 produces a negative rate string."""
        comm_cls = self._run({"speed": 0.5}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert kwargs["rate"] == "-50%"

    def test_speed_exactly_one_no_rate(self, tmp_path):
        """Explicit speed=1.0 should not pass rate kwarg."""
        comm_cls = self._run({"speed": 1.0}, tmp_path)
        kwargs = comm_cls.call_args[1]
        assert "rate" not in kwargs


# ---------------------------------------------------------------------------
# OpenAI TTS speed
# ---------------------------------------------------------------------------

class TestOpenaiTtsSpeed:
    def _run(self, tts_config, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls = MagicMock(return_value=mock_client)

        with patch("tools.tts_tool._import_openai_client", return_value=mock_cls), \
             patch("tools.tts_tool._resolve_openai_audio_client_config",
                   return_value=("test-key", None)):
            from tools.tts_tool import _generate_openai_tts
            _generate_openai_tts("Hello", str(tmp_path / "out.mp3"), tts_config)
        return mock_client.audio.speech.create

    def test_default_no_speed_kwarg(self, tmp_path, monkeypatch):
        """No speed config => no speed kwarg in create call."""
        create = self._run({}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert "speed" not in kwargs

    def test_global_speed_applied(self, tmp_path, monkeypatch):
        """Global tts.speed used as fallback."""
        create = self._run({"speed": 1.5}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["speed"] == 1.5

    def test_provider_speed_overrides_global(self, tmp_path, monkeypatch):
        """tts.openai.speed takes precedence over tts.speed."""
        create = self._run({"speed": 1.5, "openai": {"speed": 2.0}}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["speed"] == 2.0

    def test_speed_clamped_low(self, tmp_path, monkeypatch):
        """Speed below 0.25 is clamped to 0.25."""
        create = self._run({"speed": 0.1}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["speed"] == 0.25

    def test_speed_clamped_high(self, tmp_path, monkeypatch):
        """Speed above 4.0 is clamped to 4.0."""
        create = self._run({"speed": 10.0}, tmp_path, monkeypatch)
        kwargs = create.call_args[1]
        assert kwargs["speed"] == 4.0


# ---------------------------------------------------------------------------
# MiniMax TTS (new API: raw audio, no speed/voice_setting)
# ---------------------------------------------------------------------------

class TestMinimaxTtsSpeed:
    def _run(self, tts_config, tmp_path, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "audio/mpeg"}
        mock_response.content = b"\x00\x01\x02\x03"

        # requests is imported locally inside _generate_minimax_tts
        with patch("requests.post", return_value=mock_response) as mock_post:
            from tools.tts_tool import _generate_minimax_tts
            output = _generate_minimax_tts("Hello", str(tmp_path / "out.mp3"), tts_config)
        return mock_post, output

    def test_simple_payload(self, tmp_path, monkeypatch):
        """v1 API uses flat payload with model, text, voice_id."""
        mock_post, _ = self._run({"minimax": {"api_version": "v1"}}, tmp_path, monkeypatch)
        payload = mock_post.call_args[1]["json"]
        assert "model" in payload
        assert "text" in payload
        assert "voice_id" in payload
        assert "voice_setting" not in payload
        assert "audio_setting" not in payload
        assert "stream" not in payload

    def test_writes_raw_audio(self, tmp_path, monkeypatch):
        """v1 API returns raw bytes written directly to file."""
        _, output = self._run({"minimax": {"api_version": "v1"}}, tmp_path, monkeypatch)
        assert output == str(tmp_path / "out.mp3")
        with open(output, "rb") as f:
            assert f.read() == b"\x00\x01\x02\x03"


# ---------------------------------------------------------------------------
# MiniMax TTS v2
# ---------------------------------------------------------------------------

class TestMinimaxTtsV2:
    """Tests for MiniMax TTS v2 (t2a_v2) API support."""

    def _make_v2_response(self, hex_audio="", audio_url="", status_code=0, status_msg=""):
        """Build a mock response mimicking t2a_v2 JSON output."""
        mock = MagicMock()
        mock.headers = {"Content-Type": "application/json"}
        data = {}
        if hex_audio:
            data["audio"] = hex_audio
        if audio_url:
            data["audio_url"] = audio_url
        body = {"base_resp": {"status_code": status_code, "status_msg": status_msg}, "data": data}
        mock.json.return_value = body
        mock.content = b'{"base_resp": ...}'
        return mock

    def _run_v2(self, tts_config, tmp_path, monkeypatch, **response_kw):
        """Run _generate_minimax_tts with v2 config and mocked response."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        config = {"minimax": {"api_version": "v2"}}
        config["minimax"].update(tts_config.get("minimax", {}))
        config.update({k: v for k, v in tts_config.items() if k != "minimax"})

        mock_response = self._make_v2_response(**response_kw)
        with patch("requests.post", return_value=mock_response) as mock_post:
            from tools.tts_tool import _generate_minimax_tts
            output = _generate_minimax_tts("Hello", str(tmp_path / "out.mp3"), config)
        return mock_post, output

    def test_dispatcher_routes_to_v2(self, tmp_path, monkeypatch):
        """Default api_version='v2' routes to v2 endpoint."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_response = self._make_v2_response(hex_audio="48454c4c4f")
        with patch("requests.post", return_value=mock_response) as mock_post:
            from tools.tts_tool import _generate_minimax_tts
            _generate_minimax_tts("Hello", str(tmp_path / "out.mp3"), {})
        # v2 endpoint URL should be used (api.minimax.io)
        called_url = mock_post.call_args[0][0]
        assert "minimax.io" in called_url
        assert "t2a_v2" in called_url

    def test_dispatcher_routes_to_v1(self, tmp_path, monkeypatch):
        """api_version='v1' routes to v1 endpoint."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "audio/mpeg"}
        mock_response.content = b"\x00\x01"
        with patch("requests.post", return_value=mock_response) as mock_post:
            from tools.tts_tool import _generate_minimax_tts
            _generate_minimax_tts(
                "Hello", str(tmp_path / "out.mp3"),
                {"minimax": {"api_version": "v1"}},
            )
        called_url = mock_post.call_args[0][0]
        assert "minimax.chat" in called_url

    def test_v2_payload_structure(self, tmp_path, monkeypatch):
        """v2 payload has voice_setting and audio_setting sub-objects."""
        mock_post, _ = self._run_v2({}, tmp_path, monkeypatch, hex_audio="48454c4c4f")
        payload = mock_post.call_args[1]["json"]
        assert "voice_setting" in payload
        assert "audio_setting" in payload
        assert payload["stream"] is False
        assert "model" in payload

    def test_v2_writes_hex_audio(self, tmp_path, monkeypatch):
        """v2 response with hex-encoded audio writes decoded bytes to file."""
        audio_hex = "deadbeef01020304"
        _, output = self._run_v2({}, tmp_path, monkeypatch, hex_audio=audio_hex)
        with open(output, "rb") as f:
            assert f.read() == bytes.fromhex(audio_hex)

    def test_v2_downloads_audio_url(self, tmp_path, monkeypatch):
        """v2 response with audio_url downloads and writes the file."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        config = {"minimax": {"api_version": "v2"}}
        mock_v2_response = self._make_v2_response(audio_url="https://cdn.example.com/audio.mp3")
        mock_download = MagicMock()
        mock_download.content = b"\xaa\xbb\xcc"
        mock_download.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_v2_response), \
             patch("requests.get", return_value=mock_download) as mock_get:
            from tools.tts_tool import _generate_minimax_tts
            output = _generate_minimax_tts("Hello", str(tmp_path / "out.mp3"), config)

        mock_get.assert_called_once_with("https://cdn.example.com/audio.mp3", timeout=60)
        with open(output, "rb") as f:
            assert f.read() == b"\xaa\xbb\xcc"

    def test_v2_error_response(self, tmp_path, monkeypatch):
        """v2 API error raises RuntimeError with status code and message."""
        with pytest.raises(RuntimeError, match="code 1001"):
            self._run_v2({}, tmp_path, monkeypatch, status_code=1001, status_msg="quota exceeded")

    def test_v2_no_audio_nor_url_raises(self, tmp_path, monkeypatch):
        """v2 response with neither audio nor audio_url raises RuntimeError."""
        with pytest.raises(RuntimeError, match="neither audio nor audio_url"):
            self._run_v2({}, tmp_path, monkeypatch)

    def test_v2_config_voice_setting_overrides(self, tmp_path, monkeypatch):
        """voice_setting values from config override defaults in payload."""
        config = {"minimax": {
            "api_version": "v2",
            "voice_setting": {"speed": 1.5, "pitch": 3},
        }}
        mock_post, _ = self._run_v2(config, tmp_path, monkeypatch, hex_audio="48454c4c4f")
        payload = mock_post.call_args[1]["json"]
        assert payload["voice_setting"]["speed"] == 1.5
        assert payload["voice_setting"]["pitch"] == 3

    def test_v2_config_audio_setting_overrides(self, tmp_path, monkeypatch):
        """audio_setting values from config override defaults in payload."""
        config = {"minimax": {
            "api_version": "v2",
            "audio_setting": {"sample_rate": 48000, "format": "wav"},
        }}
        mock_post, _ = self._run_v2(config, tmp_path, monkeypatch, hex_audio="48454c4c4f")
        payload = mock_post.call_args[1]["json"]
        assert payload["audio_setting"]["sample_rate"] == 48000
        assert payload["audio_setting"]["format"] == "wav"

    def test_v2_voice_id_inherits_from_top_level(self, tmp_path, monkeypatch):
        """voice_setting.voice_id falls back to minimax.voice_id when not set in voice_setting."""
        config = {"minimax": {
            "api_version": "v2",
            "voice_id": "my-custom-voice",
        }}
        mock_post, _ = self._run_v2(config, tmp_path, monkeypatch, hex_audio="48454c4c4f")
        payload = mock_post.call_args[1]["json"]
        assert payload["voice_setting"]["voice_id"] == "my-custom-voice"

    def test_v2_voice_setting_voice_id_overrides_top_level(self, tmp_path, monkeypatch):
        """voice_setting.voice_id takes precedence over minimax.voice_id."""
        config = {"minimax": {
            "api_version": "v2",
            "voice_id": "top-level-voice",
            "voice_setting": {"voice_id": "nested-voice"},
        }}
        mock_post, _ = self._run_v2(config, tmp_path, monkeypatch, hex_audio="48454c4c4f")
        payload = mock_post.call_args[1]["json"]
        assert payload["voice_setting"]["voice_id"] == "nested-voice"

    def test_v2_unknown_api_version_warns(self, tmp_path, monkeypatch):
        """Unknown api_version logs a warning and falls back to v1."""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "audio/mpeg"}
        mock_response.content = b"\x00\x01"
        with patch("requests.post", return_value=mock_response), \
             patch("tools.tts_tool.logger") as mock_logger:
            from tools.tts_tool import _generate_minimax_tts
            _generate_minimax_tts(
                "Hello", str(tmp_path / "out.mp3"),
                {"minimax": {"api_version": "v3"}},
            )
        mock_logger.warning.assert_called_once()
        assert "v3" in mock_logger.warning.call_args[0][1]
