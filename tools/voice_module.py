"""
JARVIS Tool — Voice Module
Speech-to-text (microphone input) + Text-to-speech (JARVIS speaking back).
Works offline via pyttsx3 + SpeechRecognition, with optional Whisper upgrade.
"""

import logging
import queue
import threading
import time

log = logging.getLogger("JARVIS.voice")


class VoiceModule:
    """
    Unified voice I/O for JARVIS.
    Usage:
        vm = VoiceModule()
        vm.say("Hello, I am JARVIS.")
        text = vm.listen()          # blocks until speech detected
    """

    def __init__(self, wake_word: str = "hey jarvis"):
        self._wake_word   = wake_word.lower()
        self._tts_engine  = None
        self._recognizer  = None
        self._microphone  = None
        self._cmd_queue: queue.Queue = queue.Queue()
        self._listening   = False
        self._wake_active = False

    # ── TTS ───────────────────────────────────────────────────────────────────
    def _get_tts(self):
        if self._tts_engine:
            return self._tts_engine
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # JARVIS voice — prefer a male voice, slow it slightly
            voices = engine.getProperty("voices")
            for v in voices:
                if any(k in v.name.lower() for k in ("david", "mark", "alex", "daniel", "george")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate",  165)    # words per minute (default ~200)
            engine.setProperty("volume", 0.92)
            self._tts_engine = engine
            return engine
        except ImportError:
            log.warning("pyttsx3 not installed — TTS disabled. pip install pyttsx3")
            return None
        except Exception as e:
            log.warning("TTS init failed: %s", e)
            return None

    def say(self, text: str, blocking: bool = True) -> bool:
        """Speak text aloud. Returns True if successful."""
        engine = self._get_tts()
        if not engine:
            print(f"[JARVIS]: {text}")
            return False
        try:
            engine.say(text)
            if blocking:
                engine.runAndWait()
            else:
                threading.Thread(target=engine.runAndWait, daemon=True).start()
            return True
        except Exception as e:
            log.warning("TTS speak error: %s", e)
            print(f"[JARVIS]: {text}")
            return False

    def set_voice_rate(self, wpm: int):
        engine = self._get_tts()
        if engine:
            engine.setProperty("rate", wpm)

    def set_volume(self, vol: float):
        """vol: 0.0 – 1.0"""
        engine = self._get_tts()
        if engine:
            engine.setProperty("volume", max(0.0, min(1.0, vol)))

    # ── STT ───────────────────────────────────────────────────────────────────
    def _get_recognizer(self):
        if self._recognizer:
            return self._recognizer, self._microphone
        try:
            import speech_recognition as sr
            self._recognizer  = sr.Recognizer()
            self._microphone  = sr.Microphone()
            # calibrate for ambient noise on first use
            with self._microphone as source:
                log.info("Calibrating microphone for ambient noise…")
                self._recognizer.adjust_for_ambient_noise(source, duration=1.0)
            log.info("Microphone ready")
            return self._recognizer, self._microphone
        except ImportError:
            log.error("SpeechRecognition not installed. pip install SpeechRecognition pyaudio")
            return None, None
        except Exception as e:
            log.error("Microphone init failed: %s", e)
            return None, None

    def listen(self, timeout: float = 8.0, phrase_limit: float = 15.0,
               engine: str = "google") -> str | None:
        """
        Listen for one utterance and return transcribed text.
        engine: 'google' (requires internet) | 'whisper' (offline, pip install openai-whisper)
        Returns None on failure.
        """
        recognizer, mic = self._get_recognizer()
        if not recognizer:
            return None

        import speech_recognition as sr
        try:
            with mic as source:
                log.info("Listening…")
                audio = recognizer.listen(source, timeout=timeout,
                                          phrase_time_limit=phrase_limit)

            if engine == "whisper":
                return self._transcribe_whisper(audio)
            elif engine == "sphinx":
                return recognizer.recognize_sphinx(audio)
            else:
                return recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            log.warning("STT request error: %s", e)
            return None

    def _transcribe_whisper(self, audio) -> str | None:
        """Local Whisper transcription (pip install openai-whisper)."""
        try:
            import tempfile, os
            import whisper
            import numpy as np

            # save to temp wav
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio.get_wav_data())
                tmp = f.name

            model = whisper.load_model("base")
            result = model.transcribe(tmp, language="en")
            os.unlink(tmp)
            return result.get("text", "").strip()
        except ImportError:
            log.warning("Whisper not installed. pip install openai-whisper")
            return None
        except Exception as e:
            log.warning("Whisper transcription error: %s", e)
            return None

    # ── WAKE WORD LOOP ────────────────────────────────────────────────────────
    def start_wake_word_loop(self, on_command_cb, stt_engine: str = "google"):
        """
        Continuously listen in background. When wake word is detected,
        listen for a command and call on_command_cb(text).
        """
        if self._wake_active:
            return
        self._wake_active = True

        def _loop():
            self.say("JARVIS online. Listening for wake word.", blocking=False)
            while self._wake_active:
                raw = self.listen(timeout=20, stt_engine=stt_engine)
                if raw and self._wake_word in raw.lower():
                    self.say("Yes?", blocking=False)
                    time.sleep(0.4)
                    command = self.listen(timeout=10, stt_engine=stt_engine)
                    if command:
                        log.info("Voice command: %s", command)
                        try:
                            on_command_cb(command)
                        except Exception as e:
                            log.error("Command callback error: %s", e)
                time.sleep(0.05)

        t = threading.Thread(target=_loop, daemon=True, name="jarvis-wake")
        t.start()
        log.info("Wake word loop started (trigger: '%s')", self._wake_word)

    def stop_wake_word_loop(self):
        self._wake_active = False
        log.info("Wake word loop stopped")

    # ── VOICE COMMAND SERVER INTEGRATION ─────────────────────────────────────
    @staticmethod
    def list_microphones() -> list[str]:
        try:
            import speech_recognition as sr
            return sr.Microphone.list_microphone_names()
        except ImportError:
            return ["SpeechRecognition not installed"]

    def test(self):
        """Quick test — say hello and listen for response."""
        print("Testing TTS…")
        self.say("JARVIS voice module online. Please say something for the microphone test.")
        print("Testing STT — speak now…")
        text = self.listen(timeout=6)
        if text:
            print(f"Heard: {text}")
            self.say(f"I heard: {text}")
        else:
            print("Nothing heard or STT unavailable.")


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    vm = VoiceModule()
    vm.test()
