"""SnipText application controller: tray, hotkey, snip pipeline."""

from __future__ import annotations

import logging
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from sniptext import __app_name__, __version__
from sniptext.capture.grabber import capture_region
from sniptext.capture.overlay import select_region
from sniptext.services import clipboard
from sniptext.services.config import load_config, log_path, save_config
from sniptext.services.history import clear_history, load_history, push_history
from sniptext.services.hotkey import HotkeyService
from sniptext.services.providers import provider_status_line
from sniptext.services.readiness import any_local_ready, full_status_report, readiness_summary
from sniptext.services.shutter import play_shutter
from sniptext.services.secrets import has_any_vision_key
from sniptext.transcribe.router import EngineRouter
from sniptext.ui.clip_desk import ClipDesk
from sniptext.ui.onboarding import show_onboarding
from sniptext.ui.preview_card import PreviewCard
from sniptext.ui.settings_window import SettingsWindow
from sniptext.ui.toast import notify, show_busy_pill

log = logging.getLogger("sniptext")


def _setup_logging() -> None:
    path = log_path()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: assets next to exe; onefile: _MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass)
            if (p / "assets").is_dir():
                return p
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _make_icon_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (15, 23, 42, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, size - 5, size - 5), radius=12, outline=(91, 219, 255, 255), width=3)
    cx, cy = size // 2, size // 2
    d.line((cx, 14, cx, size - 14), fill=(91, 219, 255, 255), width=3)
    d.line((14, cy, size - 14, cy), fill=(91, 219, 255, 255), width=3)
    d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=(248, 250, 252, 255), width=2)
    return img


def _load_tray_icon() -> Image.Image:
    assets = _resource_root() / "assets"
    for name in ("icon.png", "icon.ico"):
        p = assets / name
        if p.is_file():
            try:
                return Image.open(p).convert("RGBA")
            except Exception:
                pass
    return _make_icon_image()


def _wake_path() -> Path:
    from sniptext.services.config import config_dir

    return config_dir() / "wake.request"


def _acquire_single_instance() -> bool:
    """True if this process owns the instance. False if another is already running."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        handle = kernel32.CreateMutexW(None, False, "Local\\SnipText_SingleInstance_v1")
        # Keep handle alive for process lifetime so the mutex stays held
        _acquire_single_instance._mutex_handle = handle  # type: ignore[attr-defined]
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            try:
                _wake_path().write_text("open_settings", encoding="utf-8")
            except OSError as exc:
                log = logging.getLogger("sniptext")
                log.warning("Could not signal running instance: %s", exc)
            return False
        return True
    except Exception as exc:
        logging.getLogger("sniptext").warning("Single-instance check failed: %s", exc)
        return True


class SnipTextApp:
    def __init__(self) -> None:
        _setup_logging()
        self.config = load_config()
        self.router = EngineRouter(self.config)
        self.hotkeys = HotkeyService()
        self._snip_lock = threading.Lock()
        self._busy = False
        self._icon = None
        self._last_image: Optional[Image.Image] = None
        self._countdown_win: Optional[tk.Toplevel] = None
        self._startup_banner: Optional[tk.Toplevel] = None
        self._clip_desk: Optional[ClipDesk] = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(__app_name__)
        try:
            self.root.attributes("-topmost", True)
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass

        self.root.after(400, self._tick)

    def _tick(self) -> None:
        self._poll_wake_request()
        self.root.after(400, self._tick)

    def _poll_wake_request(self) -> None:
        path = _wake_path()
        if not path.is_file():
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            try:
                path.unlink()
            except OSError:
                return
        self.open_settings()

    def _show_running_banner(self) -> None:
        """Visible proof of life - tray apps feel dead without this."""
        hotkey = self.config.get("hotkey") or "ctrl+shift+t"
        text = f"SnipText is running  ·  tray icon  ·  {hotkey}"
        try:
            win, close = show_busy_pill(self.root, text)
            self._startup_banner = win
            self.root.after(4500, close)
        except Exception as exc:
            log.debug("Startup banner failed: %s", exc)
        notify(
            __app_name__,
            f"In the system tray. Hotkey: {hotkey}. Right-click the tray icon for snip/settings.",
            self.config.get("notifications", True),
        )

    def start(self) -> None:
        log.info("Starting %s v%s (frozen=%s)", __app_name__, __version__, getattr(sys, "frozen", False))
        self._start_hotkey()
        self._start_tray()

        if not self.config.get("first_run_complete"):
            self.root.after(400, self._first_run)
        else:
            self.root.after(500, self._show_running_banner)
            self.root.after(900, self._maybe_ocr_nudge)

        try:
            self.root.mainloop()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        log.info("Shutting down")
        self.hotkeys.stop()
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _first_run(self) -> None:
        def on_done(cfg: dict) -> None:
            self.config = cfg
            self.router.update_config(cfg)
            self._rebuild_tray_menu()
            self.root.after(300, self._maybe_ocr_nudge)

        def open_settings() -> None:
            self.open_settings(focus_connect=True)

        show_onboarding(
            self.root,
            config=self.config,
            on_done=on_done,
            on_open_settings=open_settings,
        )

    def _maybe_ocr_nudge(self) -> None:
        if self.config.get("dismissed_ocr_nudge"):
            return
        if has_any_vision_key():
            return
        if any_local_ready():
            return
        self.config["dismissed_ocr_nudge"] = True
        save_config(self.config)
        notify(
            __app_name__,
            "No local OCR found. Connect an AI key (tray -> Connect AI) to transcribe.",
            True,
        )

    def _start_hotkey(self) -> None:
        spec = self.config.get("hotkey") or "ctrl+shift+t"
        ok = self.hotkeys.start(spec, self._on_hotkey)
        if ok:
            log.info("Hotkey registered: %s", spec)
        else:
            log.warning("Hotkey failed; use tray menu New snip")
            notify(
                __app_name__,
                f"Hotkey failed. Use tray menu. Tried: {spec}",
                enabled=True,
            )

    def _on_hotkey(self) -> None:
        try:
            self.root.after(0, lambda: self.begin_snip(delay_sec=None))
        except Exception:
            self.begin_snip(delay_sec=None)

    def begin_snip(self, delay_sec: Optional[int] = None) -> None:
        """Start a snip. delay_sec=None uses config; pass 0 for instant, 3 for forced delay."""
        if self._busy:
            log.info("Snip ignored (busy)")
            return
        if not self._snip_lock.acquire(blocking=False):
            return

        if delay_sec is None:
            try:
                delay_sec = int(self.config.get("snip_delay_sec") or 0)
            except (TypeError, ValueError):
                delay_sec = 0
        delay_sec = max(0, min(10, int(delay_sec)))

        self._busy = True

        def after_delay() -> None:
            try:
                self._run_selection_capture()
            finally:
                self._busy = False
                try:
                    self._snip_lock.release()
                except RuntimeError:
                    pass

        if delay_sec > 0:
            log.info("Snip delay %ss", delay_sec)
            self._countdown_then(delay_sec, after_delay)
        else:
            after_delay()

    def _countdown_then(self, seconds: int, callback) -> None:
        """Non-blocking countdown pill, then callback on Tk thread."""
        win = tk.Toplevel(self.root)
        self._countdown_win = win
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        win.configure(bg="#111827")
        lbl = tk.Label(
            win,
            text=f"Snip in {seconds}...",
            fg="#E5E7EB",
            bg="#111827",
            font=("Segoe UI", 14, "bold"),
            padx=20,
            pady=14,
        )
        lbl.pack()
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        remaining = {"n": seconds}

        def tick() -> None:
            n = remaining["n"]
            if n <= 0:
                try:
                    win.destroy()
                except tk.TclError:
                    pass
                self._countdown_win = None
                callback()
                return
            lbl.configure(text=f"Snip in {n}...")
            remaining["n"] = n - 1
            win.after(1000, tick)

        tick()

    def _run_selection_capture(self) -> None:
        log.info("Opening region overlay")
        rect = select_region(parent=self.root)
        if rect is None:
            log.info("Selection cancelled")
            return
        left, top, width, height = rect
        log.info("Selected %sx%s at (%s,%s)", width, height, left, top)
        try:
            image = capture_region(rect)
        except Exception as exc:
            log.exception("Capture failed")
            notify(__app_name__, f"Capture failed: {exc}", self.config.get("notifications", True))
            return
        play_shutter(bool(self.config.get("shutter_sound", True)))
        self._last_image = image
        self._transcribe_async(image)

    def _transcribe_async(self, image: Image.Image) -> None:
        close_pill = None
        started = time.perf_counter()

        def show_pill_later() -> None:
            nonlocal close_pill
            if close_pill is None and (time.perf_counter() - started) >= 0.3:
                _, close_pill = show_busy_pill(self.root, "Transcribing...")

        self.root.after(320, show_pill_later)

        def worker() -> None:
            try:
                result = self.router.transcribe(image)
            except Exception as exc:
                log.exception("Transcribe crashed")
                result_err = str(exc)

                def fail() -> None:
                    if close_pill:
                        close_pill()
                    notify(
                        __app_name__,
                        f"Transcription error: {result_err}",
                        self.config.get("notifications", True),
                    )

                self.root.after(0, fail)
                return

            def done() -> None:
                if close_pill:
                    close_pill()
                self._handle_result(result, image)

            self.root.after(0, done)

        threading.Thread(target=worker, name="sniptext-ocr", daemon=True).start()

    def _handle_result(self, result, image: Image.Image) -> None:
        text = (result.text or "").strip()
        if not text:
            msg = result.error or "No text detected"
            log.info("Empty result: %s", msg)
            notify(__app_name__, msg, self.config.get("notifications", True))
            return

        clipboard.set_text(text)
        if self.config.get("copy_image_too"):
            clipboard.set_image(image)

        push_history(
            text,
            engine=result.engine,
            limit=int(self.config.get("history_limit") or 50),
        )
        self._rebuild_tray_menu()
        self._refresh_clip_desk()

        notify(
            __app_name__,
            "Text copied to clipboard",
            self.config.get("notifications", True),
        )
        log.info("OK via %s (%s chars)", result.engine, len(text))

        if (
            result.engine in ("rapid", "paddle", "easyocr", "tesseract", "local")
            and not has_any_vision_key()
            and not self.config.get("dismissed_ai_nudge")
        ):
            self.config["dismissed_ai_nudge"] = True
            save_config(self.config)
            notify(
                __app_name__,
                "Tip: Connect an AI key in tray -> Connect AI for higher accuracy",
                self.config.get("notifications", True),
            )

        if self.config.get("show_preview", True):
            def reprocess() -> None:
                r2 = self.router.transcribe_local_only(image)
                if r2.ok:
                    clipboard.set_text(r2.text)
                    notify(__app_name__, f"Re-processed via {r2.engine}", True)
                    PreviewCard(
                        self.root,
                        r2.text,
                        r2.engine,
                        image=image,
                        auto_dismiss_sec=int(self.config.get("preview_auto_dismiss_sec") or 8),
                        on_reprocess_local=None,
                    )
                else:
                    notify(__app_name__, r2.error or "Local re-process failed", True)

            PreviewCard(
                self.root,
                text,
                result.engine,
                image=image,
                auto_dismiss_sec=int(self.config.get("preview_auto_dismiss_sec") or 8),
                on_reprocess_local=reprocess,
            )

    def open_settings(self, focus_connect: bool = False) -> None:
        def on_save(cfg: dict) -> None:
            self.config = cfg
            self.router.update_config(cfg)
            self._start_hotkey()
            self._rebuild_tray_menu()

        SettingsWindow(
            self.root,
            self.config,
            on_save=on_save,
            focus_connect=focus_connect,
        )

    def open_connect_ai(self) -> None:
        self.open_settings(focus_connect=True)

    def open_clip_desk(self) -> None:
        try:
            if self._clip_desk is not None and self._clip_desk.win.winfo_exists():
                self._clip_desk.win.deiconify()
                self._clip_desk.win.lift()
                self._clip_desk.refresh()
                return
        except tk.TclError:
            self._clip_desk = None
        self._clip_desk = ClipDesk(self.root, on_change=self._rebuild_tray_menu)

    def _refresh_clip_desk(self) -> None:
        desk = self._clip_desk
        if desk is None:
            return
        try:
            if desk.win.winfo_exists():
                desk.refresh()
        except tk.TclError:
            self._clip_desk = None

    def _start_tray(self) -> None:
        try:
            import pystray
            from pystray import MenuItem as Item
        except ImportError:
            log.error("pystray not installed - tray unavailable")
            return

        self._pystray = pystray
        self._Item = Item
        icon_img = _load_tray_icon()

        def run_icon() -> None:
            self._icon = pystray.Icon(
                __app_name__,
                icon_img,
                __app_name__,
                menu=self._build_menu(),
            )
            self._icon.run()

        t = threading.Thread(target=run_icon, name="sniptext-tray", daemon=True)
        t.start()

    def _build_menu(self):
        Item = self._Item
        pystray = self._pystray

        def snip(icon=None, item=None) -> None:
            self.root.after(0, lambda: self.begin_snip(delay_sec=0))

        def snip_delay(icon=None, item=None) -> None:
            self.root.after(0, lambda: self.begin_snip(delay_sec=3))

        def settings(icon=None, item=None) -> None:
            self.root.after(0, self.open_settings)

        def connect_ai(icon=None, item=None) -> None:
            self.root.after(0, self.open_connect_ai)

        def quit_app(icon=None, item=None) -> None:
            def _q() -> None:
                if self._icon:
                    try:
                        self._icon.stop()
                    except Exception:
                        pass
                self.root.after(0, self.root.destroy)

            threading.Thread(target=_q, daemon=True).start()

        def about(icon=None, item=None) -> None:
            def _a() -> None:
                from tkinter import messagebox

                available = self.router.list_available()
                delay = self.config.get("snip_delay_sec") or 0
                messagebox.showinfo(
                    __app_name__,
                    f"{__app_name__} v{__version__}\n"
                    f"Snip. Read. Clipboard.\n\n"
                    f"Hotkey: {self.config.get('hotkey')}\n"
                    f"Snip delay: {delay}s\n"
                    f"{provider_status_line()}\n"
                    f"{readiness_summary()}\n"
                    f"Vision: {', '.join(available['vision']) or 'none'}\n"
                    f"Local: {', '.join(available['local']) or 'none'}\n",
                    parent=self.root,
                )

            self.root.after(0, _a)

        def open_desk(icon=None, item=None) -> None:
            self.root.after(0, self.open_clip_desk)

        history_items = []
        for item in load_history(limit=int(self.config.get("history_limit") or 50))[:12]:
            def make_copy(txt: str):
                def _c(icon=None, it=None, t=txt) -> None:
                    clipboard.set_text(t)
                    notify(__app_name__, "Copied from history", self.config.get("notifications", True))

                return _c

            preview = (item.preview or item.text[:60]).replace("\n", " ")[:60]
            history_items.append(Item(preview, make_copy(item.text)))

        if not history_items:
            history_items = [Item("(empty)", None, enabled=False)]

        def clear_h(icon=None, item=None) -> None:
            clear_history()
            self._rebuild_tray_menu()

        connect_text = (
            "Manage AI keys..."
            if has_any_vision_key()
            else "Connect AI (max accuracy)..."
        )

        return pystray.Menu(
            Item("New snip", snip, default=True),
            Item("New snip (3s delay)", snip_delay),
            Item(connect_text, connect_ai),
            Item("Clip Desk...", open_desk),
            Item("Recent", pystray.Menu(*history_items)),
            Item("Clear history", clear_h),
            Item("Settings", settings),
            Item("About", about),
            Item("Quit", quit_app),
        )

    def _rebuild_tray_menu(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
        except Exception as exc:
            log.debug("Tray menu rebuild: %s", exc)


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes

                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    if not _acquire_single_instance():
        # Another instance is already in the tray; wake it (opens Settings)
        time.sleep(0.25)
        return

    app = SnipTextApp()
    app.start()


if __name__ == "__main__":
    main()
