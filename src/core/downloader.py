"""Gerenciador de download assíncrono para Vídeos, Áudios, GIFs e Imagens."""
import os
import sys
import time
import shutil
import subprocess
import threading
import urllib.request
from typing import Callable, Optional
import yt_dlp
from src.utils.helpers import format_bytes, format_duration, sanitize_filename
from src.utils.diagnostics import find_ffmpeg

class SpeedSmoother:
    """Calcula velocidade real suave e filtra picos de buffers e caches."""
    def __init__(self, alpha: float = 0.25):
        self.alpha = alpha
        self.smoothed_speed: float = 0.0
        self.last_bytes: int = 0
        self.last_time: float = 0.0

    def update(self, current_bytes: int, yt_speed: Optional[float] = None) -> float:
        now = time.time()
        if self.last_time == 0.0:
            self.last_time = now
            self.last_bytes = current_bytes
            self.smoothed_speed = yt_speed or 0.0
            return self.smoothed_speed

        delta_time = now - self.last_time
        if delta_time >= 0.25:
            delta_bytes = max(0, current_bytes - self.last_bytes)
            inst_speed = delta_bytes / delta_time
            if self.smoothed_speed <= 0.0:
                self.smoothed_speed = inst_speed
            else:
                self.smoothed_speed = self.alpha * inst_speed + (1.0 - self.alpha) * self.smoothed_speed
            self.last_time = now
            self.last_bytes = current_bytes

        if self.smoothed_speed <= 0.0 and yt_speed:
            return yt_speed
        return self.smoothed_speed

class MediaDownloader:
    def __init__(self):
        self._is_cancelled = False
        self._current_thread: Optional[threading.Thread] = None

    def cancel(self):
        """Sinaliza para cancelar o download em andamento."""
        self._is_cancelled = True

    def download_async(
        self,
        url: str,
        output_dir: str,
        mode: str,  # "video", "audio", "image", "gif"
        format_id: Optional[str] = None,
        media_type: str = "video",
        image_urls: Optional[list] = None,
        title: str = "download",
        playlist_items: Optional[list] = None,
        on_progress: Optional[Callable[[float, str, str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, str, str], None]] = None,
    ):
        """Inicia o download em uma thread separada para não travar a interface."""
        self._is_cancelled = False
        self._current_thread = threading.Thread(
            target=self._run_download,
            args=(url, output_dir, mode, format_id, media_type, image_urls, title, playlist_items, on_progress, on_status, on_complete),
            daemon=True
        )
        self._current_thread.start()

    def _run_download(
        self,
        url: str,
        output_dir: str,
        mode: str,
        format_id: Optional[str],
        media_type: str,
        image_urls: Optional[list],
        title: str,
        playlist_items: Optional[list],
        on_progress: Optional[Callable[[float, str, str, str], None]],
        on_status: Optional[Callable[[str], None]],
        on_complete: Optional[Callable[[bool, str, str], None]],
    ):
        os.makedirs(output_dir, exist_ok=True)
        safe_title = sanitize_filename(title) or "download"

        # Localiza FFmpeg se disponível
        ffmpeg_ok, ffmpeg_path, _ = find_ffmpeg()
        ffmpeg_location = os.path.dirname(ffmpeg_path) if (ffmpeg_ok and ffmpeg_path) else None

        # -------------------------------------------------------------
        # CASO 0: Download de PLAYLIST DO YOUTUBE
        # -------------------------------------------------------------
        if media_type == "playlist" or (playlist_items and len(playlist_items) > 0):
            selected_items = [it for it in (playlist_items or []) if getattr(it, "is_selected", True)]
            if not selected_items:
                if on_complete:
                    on_complete(False, "Nenhum vídeo foi selecionado na playlist.", "")
                return

            total_sel = len(selected_items)
            playlist_dir = os.path.join(output_dir, safe_title)
            os.makedirs(playlist_dir, exist_ok=True)

            playlist_start_time = time.time()
            success_count = 0
            for idx, item in enumerate(selected_items, 1):
                if self._is_cancelled:
                    if on_complete:
                        on_complete(False, f"Download cancelado pelo usuário ({success_count}/{total_sel} baixados).", playlist_dir)
                    return

                if on_status:
                    on_status(f"[{idx}/{total_sel}] Conectando: {item.title[:40]}...")

                item_smoother = SpeedSmoother()

                def make_progress_hook(item_idx, total_items, item_title, smoother):
                    def hook(d):
                        if self._is_cancelled:
                            raise Exception("Download cancelado pelo usuário.")
                        status = d.get("status")
                        if status == "downloading":
                            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                            dl = d.get("downloaded_bytes") or 0
                            video_pct = (dl / tot * 100.0) if tot > 0 else 0.0
                            overall_pct = ((item_idx - 1) / total_items * 100.0) + (video_pct / total_items)
                            overall_pct = min(99.9, max(0.0, overall_pct))

                            speed = smoother.update(dl, d.get("speed"))
                            speed_str = f"{format_bytes(speed)}/s" if speed > 0 else "-- KB/s"

                            elapsed = time.time() - playlist_start_time
                            if overall_pct >= 2.0 and elapsed >= 1.5:
                                total_est_sec = elapsed / (overall_pct / 100.0)
                                remaining_sec = max(0, int(total_est_sec - elapsed))
                                eta_str = f"ETA: {format_duration(remaining_sec)}"
                            else:
                                remaining_bytes = max(0, tot - dl)
                                if speed > 0 and remaining_bytes > 0:
                                    calc_video_eta = int(remaining_bytes / speed)
                                    eta_str = f"ETA: {format_duration(calc_video_eta)}"
                                else:
                                    yt_eta = d.get("eta")
                                    if yt_eta and yt_eta > 0:
                                        eta_str = f"ETA: {format_duration(yt_eta)}"
                                    else:
                                        eta_str = "ETA: --:--"

                            title_snippet = (item_title[:32] + "...") if len(item_title) > 32 else item_title
                            if on_progress:
                                on_progress(overall_pct, speed_str, eta_str, f"[{item_idx}/{total_items}] {title_snippet}")

                        elif status == "finished":
                            if on_status:
                                on_status(f"[{item_idx}/{total_items}] Mesclando e finalizando com FFmpeg...")
                    return hook

                item_outtmpl = os.path.join(playlist_dir, f"{item.index:02d} - %(title)s.%(ext)s")

                ydl_opts_item = {
                    "outtmpl": item_outtmpl,
                    "progress_hooks": [make_progress_hook(idx, total_sel, item.title, item_smoother)],
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "windowsfilenames": True,
                }
                if ffmpeg_location:
                    ydl_opts_item["ffmpeg_location"] = ffmpeg_location

                if mode == "audio":
                    ydl_opts_item.update({
                        "format": "bestaudio/best",
                        "postprocessors": [
                            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                            {"key": "FFmpegMetadata", "add_metadata": True}
                        ] if ffmpeg_ok else [],
                    })
                else:
                    sel_fmt = format_id or "bestvideo+bestaudio/best"
                    ydl_opts_item.update({
                        "format": sel_fmt,
                        "merge_output_format": "mp4",
                        "postprocessors": [
                            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                        ] if ffmpeg_ok else [],
                    })

                try:
                    with yt_dlp.YoutubeDL(ydl_opts_item) as ydl:
                        ydl.download([item.url])
                    success_count += 1
                except Exception as ex:
                    if "cancelado pelo usuário" in str(ex):
                        if on_complete:
                            on_complete(False, f"Download cancelado ({success_count}/{total_sel} baixados).", playlist_dir)
                        return
                    # Registra erro no log mas continua com os outros vídeos
                    try:
                        from src.utils.logger import log_error
                        log_error(f"Erro ao baixar vídeo da playlist ({item.url}): {ex}")
                    except Exception:
                        pass

            if on_complete:
                if self._is_cancelled:
                    on_complete(False, f"Download cancelado ({success_count}/{total_sel} baixados).", playlist_dir)
                else:
                    on_complete(True, f"Playlist concluída! {success_count} de {total_sel} vídeos salvos com sucesso.", playlist_dir)
            return

        # -------------------------------------------------------------
        # CASO 1: Download de IMAGEM (Fotos Twitter / X e Instagram)
        # -------------------------------------------------------------
        if mode == "image" or media_type == "image":
            try:
                if on_status:
                    on_status("Baixando imagem em alta resolução...")

                target_urls = image_urls or [url]
                final_path = ""

                for idx, img_url in enumerate(target_urls):
                    if self._is_cancelled:
                        raise Exception("Download cancelado pelo usuário.")

                    ext = ".png" if ".png" in img_url.lower() else ".jpg"
                    suffix = f"_{idx+1}" if len(target_urls) > 1 else ""
                    dest_file = os.path.join(output_dir, f"{safe_title}{suffix}{ext}")

                    data = None
                    # 1. Tenta curl_cffi para CDN do Instagram / Meta
                    try:
                        from curl_cffi import requests as cffi_requests
                        resp = cffi_requests.get(img_url, impersonate="chrome", timeout=15, verify=False)
                        if resp.status_code == 200 and len(resp.content) > 0:
                            data = resp.content
                    except Exception:
                        pass

                    # 2. Fallback urllib padrão
                    if data is None:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                        }
                        req = urllib.request.Request(img_url, headers=headers)
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            data = resp.read()

                    with open(dest_file, "wb") as f:
                        f.write(data)

                    final_path = dest_file
                    if on_progress:
                        pct = ((idx + 1) / len(target_urls)) * 100.0
                        on_progress(pct, "Concluído", "00:00", os.path.basename(dest_file))

                if on_complete:
                    on_complete(True, "Imagem baixada com sucesso!", final_path)
                return

            except Exception as e:
                err = str(e)
                if on_complete:
                    on_complete(False, f"Falha ao baixar imagem: {err[:100]}", "")
                return

        # -------------------------------------------------------------
        # CASO 2: Download e Conversão de GIF ANIMADO
        # -------------------------------------------------------------
        if mode == "gif" or format_id == "gif_convert":
            try:
                if on_status:
                    on_status("Baixando mídia e gerando GIF animado...")

                temp_mp4 = os.path.join(output_dir, f"_temp_{safe_title}.mp4")
                final_gif = os.path.join(output_dir, f"{safe_title}.gif")

                # Baixa o MP4 base
                ydl_opts_gif = {
                    "outtmpl": temp_mp4,
                    "quiet": True,
                    "no_warnings": True,
                    "format": "best",
                }
                if ffmpeg_location:
                    ydl_opts_gif["ffmpeg_location"] = ffmpeg_location

                with yt_dlp.YoutubeDL(ydl_opts_gif) as ydl:
                    ydl.download([url])

                # Se temos FFmpeg, converte para GIF de alta qualidade com paleta de 256 cores
                if ffmpeg_ok and os.path.exists(temp_mp4):
                    if on_status:
                        on_status("Otimizando animação GIF com FFmpeg...")

                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE

                    cmd = [
                        ffmpeg_path,
                        "-y",
                        "-i", temp_mp4,
                        "-vf", "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                        final_gif
                    ]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, startupinfo=startupinfo)
                    
                    # Remove o temporário
                    if os.path.exists(temp_mp4):
                        os.remove(temp_mp4)

                    if os.path.exists(final_gif):
                        if on_complete:
                            on_complete(True, "Animação GIF criada com sucesso!", final_gif)
                        return

                # Se falhar a conversão ou não houver ffmpeg, mantém o mp4
                if os.path.exists(temp_mp4):
                    final_mp4 = os.path.join(output_dir, f"{safe_title}.mp4")
                    os.rename(temp_mp4, final_mp4)
                    if on_complete:
                        on_complete(True, "GIF salvo como vídeo MP4 com sucesso!", final_mp4)
                    return

            except Exception as e:
                err = str(e)
                if on_complete:
                    on_complete(False, f"Falha ao gerar GIF: {err[:100]}", "")
                return

        # -------------------------------------------------------------
        # CASO 3: Download de VÍDEO (MP4) ou ÁUDIO (MP3) padrão
        # -------------------------------------------------------------
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        downloaded_file_path = ""
        single_smoother = SpeedSmoother()

        def progress_hook(d):
            if self._is_cancelled:
                raise Exception("Download cancelado pelo usuário.")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100.0) if total > 0 else 0.0
                percent = min(99.9, max(0.0, percent))
                
                speed = single_smoother.update(downloaded, d.get("speed"))
                speed_str = f"{format_bytes(speed)}/s" if speed > 0 else "-- KB/s"
                
                remaining = max(0, total - downloaded)
                if speed > 0 and remaining > 0:
                    calc_eta = int(remaining / speed)
                    eta_str = f"ETA: {format_duration(calc_eta)}"
                else:
                    yt_eta = d.get("eta")
                    if yt_eta and yt_eta > 0:
                        eta_str = f"ETA: {format_duration(yt_eta)}"
                    else:
                        eta_str = "ETA: --:--"
                
                filename = os.path.basename(d.get("filename", ""))
                if on_progress:
                    on_progress(percent, speed_str, eta_str, filename)

            elif status == "finished":
                if on_status:
                    on_status("Processando e finalizando com FFmpeg...")

        ydl_opts = {
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "windowsfilenames": True,
        }

        if ffmpeg_location:
            ydl_opts["ffmpeg_location"] = ffmpeg_location

        if mode == "audio":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    },
                    {
                        "key": "FFmpegMetadata",
                        "add_metadata": True,
                    }
                ],
            })
        else:
            selected_format = format_id or "bestvideo+bestaudio/best"
            ydl_opts.update({
                "format": selected_format,
                "merge_output_format": "mp4",
                "postprocessors": [
                    {
                        "key": "FFmpegVideoRemuxer",
                        "preferedformat": "mp4",
                    }
                ] if ffmpeg_ok else []
            })

        try:
            if on_status:
                on_status("Conectando e iniciando download...")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    title = info.get("title", "download")
                    ext = "mp3" if mode == "audio" else "mp4"
                    safe_title = sanitize_filename(title)
                    expected_path = os.path.join(output_dir, f"{safe_title}.{ext}")
                    
                    if os.path.exists(expected_path):
                        downloaded_file_path = expected_path
                    else:
                        downloaded_file_path = output_dir

            if on_complete:
                on_complete(True, "Download concluído com sucesso!", downloaded_file_path)

        except Exception as e:
            err_msg = str(e)
            if "cancelado pelo usuário" in err_msg:
                if on_complete:
                    on_complete(False, "Download cancelado.", "")
            else:
                if on_complete:
                    on_complete(False, f"Falha no download: {err_msg[:120]}", "")
