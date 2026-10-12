"""IDM Naya - PC + Android video/audio downloader (Python + Flet + yt-dlp).

Naye features:
  1. Smart offline queue: net na ho to link save, net aate hi khud download.
  2. Clipboard detect: link copy karein, app khud pooch legi.
  3. Roman Urdu / English interface (ek tap se badlein).
  4. Ek-tap: sirf "Video" ya "MP3" ka button.
"""
import json
import os
import shutil
import socket
import threading
import time
import uuid

import flet as ft
import yt_dlp

APP_DIR = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.expanduser("~/.idm_naya")
DL_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "IDM-Naya")
if not os.access(os.path.expanduser("~"), os.W_OK):
    DL_DIR = os.path.join(APP_DIR, "downloads")
os.makedirs(APP_DIR, exist_ok=True)
os.makedirs(DL_DIR, exist_ok=True)
QUEUE_FILE = os.path.join(APP_DIR, "queue.json")

T = {
    "ur": {
        "title": "IDM Naya", "hint": "Yahan link paste karein",
        "video": "Video", "mp3": "MP3", "paste": "Paste",
        "pending": "Net ka intezar...", "downloading": "Download ho raha hai",
        "done": "Mukammal", "error": "Masla aa gaya", "offline": "Net band hai, queue mein save",
        "online": "Net chal raha hai", "clip": "Link mila. Download karun?", "yes": "Haan",
        "empty": "Abhi koi download nahi", "lang": "English",
    },
    "en": {
        "title": "IDM Naya", "hint": "Paste link here",
        "video": "Video", "mp3": "MP3", "paste": "Paste",
        "pending": "Waiting for internet...", "downloading": "Downloading",
        "done": "Done", "error": "Failed", "offline": "Offline, saved to queue",
        "online": "Online", "clip": "Link found. Download?", "yes": "Yes",
        "empty": "No downloads yet", "lang": "Roman Urdu",
    },
}


def is_online() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        return True
    except OSError:
        return False


def load_queue():
    try:
        with open(QUEUE_FILE, encoding="utf-8") as f:
            items = json.load(f)
        for it in items:  # app band hui thi to adhoora kaam dobara pending
            if it["status"] == "downloading":
                it["status"] = "pending"
        return items
    except (OSError, ValueError):
        return []


def save_queue(items):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)


def looks_like_link(text: str) -> bool:
    text = (text or "").strip()
    return text.startswith(("http://", "https://")) and " " not in text


def main(page: ft.Page):
    page.title = "IDM Naya"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16
    state = {"lang": "ur", "items": load_queue(), "last_clip": ""}
    lock = threading.Lock()

    t = lambda k: T[state["lang"]][k]

    link = ft.TextField(expand=True)
    status = ft.Text(size=12)
    listing = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    title_txt = ft.Text(size=24, weight=ft.FontWeight.BOLD)
    banner = ft.Row(visible=False)

    def refresh():
        title_txt.value = t("title")
        link.hint_text = t("hint")
        paste_btn.text, video_btn.text, mp3_btn.text = t("paste"), t("video"), t("mp3")
        lang_btn.text = t("lang")
        status.value = t("online") if state.get("online") else t("offline")
        status.color = ft.Colors.GREEN if state.get("online") else ft.Colors.ORANGE
        listing.controls.clear()
        with lock:
            items = list(state["items"])
        if not items:
            listing.controls.append(ft.Text(t("empty"), italic=True))
        for it in reversed(items):
            bar = ft.ProgressBar(value=it["progress"] / 100, visible=it["status"] == "downloading")
            listing.controls.append(
                ft.Card(ft.Container(ft.Column([
                    ft.Text(it.get("title") or it["url"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f'{"MP3" if it["mode"] == "mp3" else "Video"} - {t(it["status"])}', size=12),
                    bar,
                ], spacing=4), padding=12))
            )
        page.update()

    def add(url: str, mode: str):
        url = url.strip()
        if not looks_like_link(url):
            return
        with lock:
            state["items"].append({"id": uuid.uuid4().hex, "url": url, "mode": mode,
                                   "status": "pending", "progress": 0, "title": ""})
            save_queue(state["items"])
        link.value = ""
        refresh()

    def paste(_=None):
        try:
            clip = page.get_clipboard()
            if clip:
                link.value = clip.strip()
                page.update()
        except Exception:
            pass

    def toggle_lang(_):
        state["lang"] = "en" if state["lang"] == "ur" else "ur"
        refresh()

    paste_btn = ft.OutlinedButton(on_click=paste)
    video_btn = ft.FilledButton(icon=ft.Icons.VIDEOCAM, height=56, expand=True,
                                on_click=lambda _: add(link.value, "video"))
    mp3_btn = ft.FilledTonalButton(icon=ft.Icons.AUDIOTRACK, height=56, expand=True,
                                   on_click=lambda _: add(link.value, "mp3"))
    lang_btn = ft.TextButton(on_click=toggle_lang)

    # ---- clipboard watcher (ek feature: link copy karo, app pooche) ----
    def clip_watcher():
        while True:
            time.sleep(2)
            try:
                clip = (page.get_clipboard() or "").strip()
            except Exception:
                continue
            if clip and clip != state["last_clip"] and looks_like_link(clip):
                state["last_clip"] = clip
                banner.controls = [
                    ft.Text(t("clip"), expand=True),
                    ft.TextButton(t("yes"), on_click=lambda _, c=clip: (
                        setattr(banner, "visible", False), add(c, "video"))),
                ]
                banner.visible = True
                page.update()

    # ---- download worker (offline queue ka dil) ----
    def run_one(it):
        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total:
                    it["progress"] = int(d["downloaded_bytes"] * 100 / total)
                    refresh()

        opts = {
            "outtmpl": os.path.join(DL_DIR, "%(title).80s.%(ext)s"),
            "progress_hooks": [hook], "quiet": True, "noplaylist": True,
            "continuedl": True, "retries": 10,
        }
        if it["mode"] == "mp3":
            opts["format"] = "bestaudio/best"
            if shutil.which("ffmpeg"):
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                           "preferredcodec": "mp3", "preferredquality": "192"}]
        else:
            opts["format"] = "bv*[height<=1080]+ba/b[height<=1080]/b"
        if shutil.which("aria2c"):  # IDM jaisi multi-connection speed
            opts["external_downloader"] = "aria2c"
            opts["external_downloader_args"] = {"aria2c": ["-x16", "-s16", "-k1M"]}

        it["status"] = "downloading"
        refresh()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(it["url"], download=True)
                it["title"] = info.get("title", "")
            it["status"], it["progress"] = "done", 100
        except Exception:
            # net gaya ho to dobara pending, warna error
            it["status"] = "pending" if not is_online() else "error"
        with lock:
            save_queue(state["items"])
        refresh()

    def worker():
        while True:
            online = is_online()
            if online != state.get("online"):
                state["online"] = online
                refresh()
            if online:
                with lock:
                    nxt = next((i for i in state["items"] if i["status"] == "pending"), None)
                if nxt:
                    run_one(nxt)
                    continue
            time.sleep(3)

    page.add(
        ft.Row([title_txt, lang_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        status, banner,
        ft.Row([link, paste_btn]),
        ft.Row([video_btn, mp3_btn]),
        ft.Divider(),
        listing,
    )
    refresh()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=clip_watcher, daemon=True).start()


ft.app(target=main)
