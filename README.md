# IDM Naya

PC + Android ke liye free video/audio downloader. Python + [Flet](https://flet.dev) + [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Kya naya hai
- **Smart offline queue:** net na ho to link save ho jata hai, net aate hi khud download shuru. App band ho to bhi queue bachi rehti hai.
- **Clipboard detect:** link copy karein, app khud pooch legi.
- **Roman Urdu / English:** ek tap se badlein.
- **Ek-tap Video ya MP3.**
- **Ek hi code:** PC aur Android dono.
- aria2c install ho to **16 connections** se tez download (IDM jaisa).

## Chalane ka tareeqa (PC)
```bash
pip install -r requirements.txt
python main.py
```
MP3 ke liye [ffmpeg](https://ffmpeg.org) install hona chahiye. Files `Downloads/IDM-Naya` mein jati hain.

## Android APK
```bash
flet build apk
```
(Flutter SDK aur Android SDK chahiye. Detail: https://flet.dev/docs/publish/android)

## Note
DRM wali cheezein (Netflix, paid courses) download nahi hoti. Sirf apni ya allowed cheezein download karein.
