"""Окно «Птицезор». Запуск: python -m app из папки pticezor."""

from __future__ import annotations

import base64
import socket
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
import webview

from app.main import SESSION, app


class Desk:
    def save_pdf(self, payload: str, name: str) -> str:
        raw = base64.b64decode(payload)
        window = webview.active_window() or webview.windows[0]
        choice = window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=name,
            file_types=("PDF (*.pdf)",),
        )
        if not choice:
            return ""
        target = Path(choice if isinstance(choice, str) else choice[0])
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        target.write_bytes(raw)
        return str(target)


def _free_port() -> int:
    for port in range(8766, 8780):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Нет свободного порта для окна")


def main() -> None:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    ready = False
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.2)
            ready = True
            break
        except Exception:
            time.sleep(0.1)
    if not ready:
        server.should_exit = True
        raise SystemExit("Окно не открылось: локальный движок не ответил.")
    webview.create_window(
        "Птицезор",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        min_size=(1024, 680),
        background_color="#E6EBE7",
        js_api=Desk(),
    )
    webview.start()
    SESSION.stop()
    server.should_exit = True


if __name__ == "__main__":
    main()
