"""Regression tests with simulated UIA controls and real transcript file I/O.

Run with: python -m unittest discover -s tests -v
These tests do not interact with Windows Live Captions or a real COM provider.
"""
import asyncio
import importlib
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class FakeCOMError(Exception):
    pass


# Keep tests usable without a Windows desktop, including on non-Windows CI.
with patch.dict(sys.modules, {
    "uiautomation": types.ModuleType("uiautomation"),
    "comtypes": types.SimpleNamespace(COMError=FakeCOMError),
}):
    texthook = importlib.import_module("function.texthook")
    main = importlib.import_module("main")

save = texthook.save
CAPTION = "The recording should save this sentence."
STAMP = 1720000000.0


class Viewer:
    def __init__(self, text):
        self.text = text
        self.resolved = False

    def Exists(self, timeout):
        assert timeout == 0, "Lookup must not block waiting for captions"
        self.resolved = True
        return self.text is not None

    @property
    def Name(self):
        assert self.resolved, "Resolve before reading Name"
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


def desktop_for(text, window_exists=True):
    viewer = Viewer(text)
    window = Mock()
    window.Exists.side_effect = lambda timeout: timeout == 0 and window_exists
    window.Control.return_value = viewer
    desktop = Mock()
    desktop.Control.return_value = window
    return desktop


class CaptureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.filename = Path(self.temp.name) / "captions.txt"
        self.event = asyncio.Event()
        self.statuses = []
        texthook.current_sentences = {}
        texthook.last_full_text = ""
        save.saved_captions.clear()

    async def asyncTearDown(self):
        await save.close_file()
        self.temp.cleanup()

    async def record(self, frames, after_poll=None):
        """One newly resolved desktop tree per poll, with a deterministic stop."""
        polls = 0

        async def advance(delay):
            nonlocal polls
            self.assertIn(delay, (0.25, 0.5))
            polls += 1
            if after_poll is not None:
                after_poll(polls)
            if polls == len(frames):
                self.event.set()

        api = Mock()
        api.GetRootControl.side_effect = frames
        with patch.object(texthook, "auto", api), \
                patch.object(texthook.asyncio, "sleep", side_effect=advance), \
                patch.object(texthook.time, "time", return_value=STAMP):
            await texthook.hook(str(self.filename), self.event, self.statuses.append)
        self.assertEqual(api.GetRootControl.call_count, len(frames))
        return api

    def assert_transcript(self, *sentences):
        timestamp = time.strftime("%H:%M:%S", time.localtime(STAMP))
        self.assertEqual(
            self.filename.read_text(encoding="utf-8"),
            "".join(f"[{timestamp}] {sentence}\n" for sentence in sentences),
        )

    async def test_viewer_appears_long_after_recording_starts(self):
        def check_live_write(polls):
            if polls == 6:
                self.assertFalse(self.filename.exists())
            if polls == 9:
                self.assertFalse(self.event.is_set())
                self.assert_transcript(CAPTION)

        await self.record(
            [desktop_for(None) for _ in range(6)] +
            [desktop_for(CAPTION) for _ in range(5)], check_live_write,
        )
        self.assert_transcript(CAPTION)
        self.assertEqual(self.statuses, ["Waiting for captions", "Recording"])

    async def test_existing_but_empty_viewer_later_has_captions(self):
        await self.record([desktop_for("   ") for _ in range(6)] +
                          [desktop_for(CAPTION) for _ in range(4)])
        self.assert_transcript(CAPTION)

    async def test_window_missing_at_recording_start(self):
        await self.record([desktop_for(None, window_exists=False)] * 3 +
                          [desktop_for(CAPTION) for _ in range(3)])
        self.assert_transcript(CAPTION)

    async def test_replaced_window_and_viewer_preserve_deduplication(self):
        other = "Fresh subtitles arrive after restarting Windows captions."
        await self.record(
            [desktop_for(CAPTION) for _ in range(3)] +
            [desktop_for(None, window_exists=False), desktop_for(None)] +
            [desktop_for(CAPTION) for _ in range(3)] +
            [desktop_for(other) for _ in range(3)],
        )
        self.assert_transcript(CAPTION, other)
        self.assertEqual(self.statuses, [
            "Recording", "Waiting for captions", "Recording",
        ])

    async def test_lookup_and_stale_com_errors_recover(self):
        broken_window = desktop_for(None)
        broken_window.Control.return_value.Exists.side_effect = FakeCOMError("stale window")
        await self.record([
            FakeCOMError("desktop unavailable"), broken_window,
            desktop_for(LookupError("viewer disappeared")),
            desktop_for(FakeCOMError("stale viewer")),
        ] + [desktop_for(CAPTION) for _ in range(3)])
        self.assert_transcript(CAPTION)
        self.assertEqual(self.statuses, ["Reconnecting", "Recording"])

    async def test_stop_while_waiting_does_not_create_empty_transcript(self):
        await self.record([desktop_for(None)] * 3)
        self.assertFalse(self.filename.exists())

    async def test_stop_during_uia_outage_flushes_pending_text(self):
        trailing = "An unfinished caption without punctuation"
        await self.record([desktop_for(trailing), desktop_for(FakeCOMError("gone"))])
        self.assert_transcript(trailing)

    async def test_stop_flushes_sentence_below_stability_threshold(self):
        await self.record([desktop_for(CAPTION), desktop_for(None)])
        self.assert_transcript(CAPTION)

    async def test_unexpected_read_error_is_not_retried(self):
        with self.assertRaisesRegex(ValueError, "unexpected"):
            await self.record([desktop_for(ValueError("unexpected"))])

    async def test_write_failure_is_not_retried_as_uia_failure(self):
        with patch.object(texthook, "save_txt", new_callable=AsyncMock) as write:
            write.side_effect = PermissionError("disk denied")
            with self.assertRaisesRegex(PermissionError, "disk denied"):
                await self.record([desktop_for(CAPTION) for _ in range(3)])
            self.assertEqual(write.await_count, 1)
        self.assertNotIn("Reconnecting", self.statuses)

    async def test_final_flush_failure_propagates(self):
        with patch.object(texthook, "save_txt", new_callable=AsyncMock) as write:
            write.side_effect = OSError("disk full")
            with self.assertRaisesRegex(OSError, "disk full"):
                await self.record([desktop_for(CAPTION)])

    async def test_cleanup_failure_propagates(self):
        with patch("builtins.open", side_effect=PermissionError("cleanup denied")):
            # Real cleanup must not swallow the error when its file exists.
            with patch.object(texthook.os.path, "exists", return_value=True):
                with self.assertRaisesRegex(PermissionError, "cleanup denied"):
                    await self.record([desktop_for(None)])

    async def test_new_session_does_not_flush_old_session_text(self):
        texthook.last_full_text = CAPTION
        texthook.current_sentences = {CAPTION: 2}
        save.saved_captions.append((STAMP, CAPTION))
        await self.record([desktop_for(None)])
        self.assertFalse(self.filename.exists())
        self.assertEqual(save.saved_captions, [])

    async def test_caption_replacement_preserves_original_timestamp(self):
        old = "The result was forty percent."
        new = "The result was 40 percent."
        # Exercise the existing replacement path deterministically; matching
        # heuristics themselves are outside the UIA lifecycle fix.
        original_match = texthook.find_and_replace_similar

        def match(sentence):
            if sentence == new and save.saved_captions:
                return 0, True
            return original_match(sentence)

        with patch.object(texthook, "find_and_replace_similar", side_effect=match):
            await self.record([desktop_for(old) for _ in range(3)] + [desktop_for(new)])
        self.assert_transcript(new)


class DashboardErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_errors_are_shown_and_file_is_closed(self):
        status = Mock()
        with patch.object(main, "hook", new_callable=AsyncMock) as hook, \
                patch.object(main, "close_file", new_callable=AsyncMock) as close, \
                patch.object(main.msgbox, "showerror") as showerror:
            hook.side_effect = OSError("disk full")
            await main.capture("captions.txt", status)
        close.assert_awaited_once()
        status.assert_called_once_with("Error")
        self.assertIn("disk full", showerror.call_args.args[1])
        self.assertIn("captions.txt", showerror.call_args.args[1])

    async def test_close_errors_are_shown(self):
        with patch.object(main, "hook", new_callable=AsyncMock), \
                patch.object(main, "close_file", new_callable=AsyncMock) as close, \
                patch.object(main.msgbox, "showerror") as showerror:
            close.side_effect = OSError("close failed")
            await main.capture("captions.txt", Mock())
        self.assertIn("close failed", showerror.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
