"""Motor de Recorte Rápido (Trim / Clip) para Links Remotos (YouTube/X/Instagram) e Arquivos Locais via FFmpeg."""
import os
import re
import sys
import time
import threading
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from src.core.converter import (
    MediaFileInfo,
    get_ffmpeg_executable,
    probe_media_file,
    is_encoder_available,
)
from src.utils.helpers import format_duration, sanitize_filename, ensure_directory
from src.utils.logger import log_info, log_error, log_warning
from src.utils.validators import detect_platform, clean_url


# Modos de corte suportados
TRIM_MODE_FAST = "fast"        # Stream copy (-c copy) — instantâneo, sem perda
TRIM_MODE_PRECISE = "precise"  # Re-encode (GPU/CPU) — precisão exata de quadro

# Qualidades disponíveis para links remotos
REMOTE_QUALITY_OPTIONS: List[Tuple[str, Optional[int]]] = [
    ("Melhor Disponível", None),
    ("4K (2160p)", 2160),
    ("2K (1440p)", 1440),
    ("1080p (Full HD)", 1080),
    ("720p (HD)", 720),
    ("480p (SD)", 480),
]


@dataclass
class TrimSourceInfo:
    """Metadados normalizados da fonte a recortar (link remoto ou arquivo local)."""
    source_type: str  # "url" ou "file"
    source: str       # URL limpa ou caminho absoluto do arquivo
    title: str
    duration_sec: float
    is_video: bool = True
    uploader: str = ""
    platform: str = ""
    file_ext: str = ".mp4"
    error: Optional[str] = None


def parse_timestamp(value: str) -> Optional[float]:
    """
    Converte strings de tempo em segundos (float).
    Aceita formatos: 'HH:MM:SS', 'MM:SS', 'SS' (com ou sem decimais '.5').
    Retorna None se inválido ou negativo.
    """
    if value is None:
        return None
    raw = str(value).strip().replace(",", ".")
    if not raw:
        return None

    parts = raw.split(":")
    if len(parts) > 3:
        return None

    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None

    if any(n < 0 for n in nums):
        return None

    if len(parts) == 1:
        return nums[0]
    if len(parts) == 2:
        mins, secs = nums
        if secs >= 60.0:
            return None
        return mins * 60.0 + secs
    hours, mins, secs = nums
    if mins >= 60.0 or secs >= 60.0:
        return None
    return hours * 3600.0 + mins * 60.0 + secs


def format_timestamp_hms(seconds: float) -> str:
    """Formata segundos em 'HH:MM:SS'."""
    total = max(0, int(round(seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_timestamp_slug(seconds: float) -> str:
    """Formata segundos em slug seguro para nome de arquivo (ex.: '01h02m05s' ou '02m00s')."""
    total = max(0, int(round(seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h:02d}h{m:02d}m{s:02d}s"
    return f"{m:02d}m{s:02d}s"


def validate_trim_range(
    start_sec: Optional[float],
    end_sec: Optional[float],
    total_duration: float = 0.0,
) -> Tuple[bool, str]:
    """Valida o intervalo [start_sec, end_sec] antes de disparar qualquer processo."""
    if start_sec is None:
        return False, "Tempo inicial inválido. Use HH:MM:SS ou MM:SS (ex.: 00:00:00)."
    if end_sec is None:
        return False, "Tempo final inválido. Use HH:MM:SS ou MM:SS (ex.: 00:02:00)."
    if start_sec < 0:
        return False, "O tempo inicial não pode ser negativo."
    if end_sec <= start_sec:
        return False, "O tempo final deve ser maior que o tempo inicial."
    if total_duration > 0 and start_sec >= total_duration:
        return False, f"O tempo inicial ultrapassa a duração total ({format_timestamp_hms(total_duration)})."
    if total_duration > 0 and end_sec > total_duration + 1.0:
        return False, f"O tempo final ({format_timestamp_hms(end_sec)}) ultrapassa a duração total ({format_timestamp_hms(total_duration)})."
    return True, ""


def _pick_hardware_or_cpu_video_args(ffmpeg_exe: str) -> Tuple[List[str], str]:
    """Retorna argumentos de encoder de vídeo (GPU prioritária ou CPU fast) para fallback."""
    if is_encoder_available("h264_nvenc"):
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p"], "GPU NVIDIA"
    if is_encoder_available("h264_qsv"):
        return ["-c:v", "h264_qsv", "-preset", "fast", "-global_quality", "22", "-pix_fmt", "yuv420p"], "GPU Intel"
    if is_encoder_available("h264_amf"):
        return ["-c:v", "h264_amf", "-quality", "balanced", "-pix_fmt", "yuv420p"], "GPU AMD"
    return ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p"], "CPU"


def _format_ffmpeg_headers(headers: Optional[Dict[str, str]]) -> Optional[str]:
    """Serializa cabeçalhos HTTP do yt-dlp no formato CRLF esperado por `-headers` do FFmpeg."""
    if not headers:
        return None
    lines = []
    for key, val in headers.items():
        k = str(key).replace("\r", "").replace("\n", "").strip()
        v = str(val).replace("\r", "").replace("\n", "").strip()
        if k and v:
            lines.append(f"{k}: {v}")
    if not lines:
        return None
    return "\r\n".join(lines) + "\r\n"


def _resolve_remote_streams(
    url: str,
    audio_only: bool = False,
    max_height: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, str]], Dict]:
    """
    Usa yt-dlp (sem baixar nada!) para resolver as URLs diretas de stream de vídeo e áudio.
    Prioriza streams compatíveis com MP4 (H.264/AAC) para permitir stream copy (-c copy) instantâneo.
    Retorna: (video_url, audio_url, http_headers, raw_info)
    """
    import yt_dlp

    if audio_only:
        fmt = "bestaudio[ext=m4a]/bestaudio/best"
    elif max_height is None:
        # Melhor Disponível real (permite 4K/2K VP9/AV1 sem travar em 1080p H.264)
        fmt = "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    elif max_height > 1080:
        # 2K / 4K no YouTube usam VP9/AV1, não restringir a avc1
        fmt = (
            f"bestvideo[height<={max_height}]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        )
    else:
        fmt = (
            f"bestvideo[vcodec^=avc1][height<={max_height}]+bestaudio[ext=m4a]/"
            f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": fmt,
        "socket_timeout": 15,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("Não foi possível obter informações do link.")

        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        requested = info.get("requested_formats")
        headers = info.get("http_headers")

        if audio_only:
            if requested:
                # Escolhe o stream de áudio
                audio_fmt = next((f for f in requested if f.get("acodec") != "none"), requested[-1])
                return None, audio_fmt.get("url"), audio_fmt.get("http_headers") or headers, info
            return None, info.get("url"), headers, info

        if requested and len(requested) >= 2:
            v_fmt = next((f for f in requested if f.get("vcodec") not in (None, "none")), requested[0])
            a_fmt = next((f for f in requested if f.get("acodec") not in (None, "none") and f is not v_fmt), requested[1])
            return (
                v_fmt.get("url"),
                a_fmt.get("url"),
                v_fmt.get("http_headers") or headers,
                info,
            )

        # Stream único (muxed — vídeo + áudio juntos)
        return info.get("url"), None, headers, info


def analyze_trim_source(source: str) -> TrimSourceInfo:
    """Analisa rapidamente um link remoto ou arquivo local para preencher título e duração."""
    cleaned = (source or "").strip()
    if not cleaned:
        return TrimSourceInfo("file", "", "", 0.0, error="Informe um link ou selecione um arquivo.")

    # Arquivo local
    if os.path.isfile(cleaned):
        info: Optional[MediaFileInfo] = probe_media_file(cleaned)
        if not info:
            return TrimSourceInfo("file", cleaned, os.path.basename(cleaned), 0.0, error="Arquivo de mídia inválido ou não suportado.")
        return TrimSourceInfo(
            source_type="file",
            source=cleaned,
            title=os.path.splitext(info.name)[0],
            duration_sec=float(info.duration_sec or 0.0),
            is_video=info.is_video,
            uploader="Arquivo Local",
            platform="local",
            file_ext=info.ext or (".mp4" if info.is_video else ".mp3"),
        )

    # Link remoto
    cleaned_url = clean_url(cleaned)
    platform = detect_platform(cleaned_url)
    if not platform:
        return TrimSourceInfo(
            "url",
            cleaned_url,
            "",
            0.0,
            error="Link inválido ou plataforma não suportada (use YouTube, Twitter/X ou Instagram).",
        )

    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
            if not info:
                return TrimSourceInfo("url", cleaned_url, "", 0.0, error="Não foi possível ler metadados do link.")
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            duration = float(info.get("duration") or 0.0)
            title = str(info.get("title") or "Video")
            uploader = str(info.get("uploader") or info.get("channel") or "")
            return TrimSourceInfo(
                source_type="url",
                source=cleaned_url,
                title=title,
                duration_sec=duration,
                is_video=True,
                uploader=uploader,
                platform=platform,
                file_ext=".mp4",
            )
    except Exception as e:
        log_error(f"[Trimmer] Falha ao analisar link {cleaned}", e)
        return TrimSourceInfo("url", cleaned, "", 0.0, error=f"Falha ao analisar link: {str(e)[:120]}")


def build_local_trim_command(
    ffmpeg_exe: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    audio_only: bool = False,
    mode: str = TRIM_MODE_FAST,
) -> Tuple[List[str], str]:
    """
    Constrói o comando FFmpeg otimizado para corte de arquivo local.
    Usa `-ss` ANTES de `-i` (input seeking) para pular instantaneamente para o trecho.
    """
    cmd: List[str] = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-ss", f"{start_sec:.3f}",
        "-i", input_path,
        "-t", f"{duration_sec:.3f}",
    ]

    engine_label = "Instantâneo"
    if audio_only:
        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".mp3":
            cmd += ["-vn", "-c:a", "libmp3lame", "-b:a", "320k"]
        else:
            cmd += ["-vn", "-c:a", "copy"]
        engine_label = "Áudio"
    elif mode == TRIM_MODE_FAST:
        cmd += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
        if output_path.lower().endswith(".mp4"):
            cmd += ["-movflags", "+faststart"]
    else:
        v_args, hw_label = _pick_hardware_or_cpu_video_args(ffmpeg_exe)
        cmd += v_args + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
        engine_label = f"Preciso ({hw_label})"

    cmd.append(output_path)
    return cmd, engine_label


def build_remote_trim_command(
    ffmpeg_exe: str,
    video_url: Optional[str],
    audio_url: Optional[str],
    output_path: str,
    start_sec: float,
    duration_sec: float,
    headers: Optional[Dict[str, str]] = None,
    audio_only: bool = False,
    mode: str = TRIM_MODE_FAST,
) -> Tuple[List[str], str]:
    """
    Constrói o comando FFmpeg com HTTP Range Seeking (`-ss` ANTES de cada `-i`).
    Baixa EXCLUSIVAMENTE o trecho [start_sec, start_sec + duration_sec], nunca o vídeo completo.
    """
    cmd: List[str] = [ffmpeg_exe, "-y", "-hide_banner"]
    hdr_str = _format_ffmpeg_headers(headers)

    def _add_remote_input(stream_url: str):
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ])
        if hdr_str:
            cmd.extend(["-headers", hdr_str])
        cmd.extend([
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-i", stream_url,
        ])

    engine_label = "Stream Copy"
    if audio_only:
        target_url = audio_url or video_url
        if not target_url:
            raise ValueError("Nenhuma URL de stream de áudio disponível.")
        _add_remote_input(target_url)
        cmd += ["-vn", "-c:a", "libmp3lame", "-b:a", "320k"]
        engine_label = "Áudio Direto"
    else:
        if not video_url:
            raise ValueError("Nenhuma URL de stream de vídeo disponível.")
        _add_remote_input(video_url)
        if audio_url:
            _add_remote_input(audio_url)
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]

        if mode == TRIM_MODE_FAST:
            cmd += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
            if output_path.lower().endswith(".mp4"):
                cmd += ["-movflags", "+faststart"]
        else:
            v_args, hw_label = _pick_hardware_or_cpu_video_args(ffmpeg_exe)
            cmd += v_args + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
            engine_label = f"Preciso ({hw_label})"

    cmd.append(output_path)
    return cmd, engine_label


class MediaTrimmer:
    """Executa recortes rápidos de links remotos e arquivos locais com progresso em tempo real e cancelamento."""

    def __init__(self):
        self._cancel_event = threading.Event()
        self._active_process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def cancel(self):
        self._cancel_event.set()
        with self._lock:
            proc = self._active_process
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _run_ffmpeg(
        self,
        cmd: List[str],
        clip_duration: float,
        on_progress: Optional[Callable[[float, str], None]] = None,
        status_prefix: str = "Recortando...",
    ) -> Tuple[bool, str]:
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        with self._lock:
            self._active_process = proc

        time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
        stderr_tail: List[str] = []

        try:
            if proc.stderr:
                for line in proc.stderr:
                    if self._cancel_event.is_set():
                        proc.terminate()
                        return False, "Recorte cancelado pelo usuário."
                    stripped = line.strip()
                    if stripped:
                        stderr_tail.append(stripped)
                        if len(stderr_tail) > 12:
                            stderr_tail.pop(0)
                    m = time_re.search(line)
                    if m and clip_duration > 0 and on_progress:
                        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                        cur = h * 3600 + mi * 60 + s
                        pct = min(0.99, max(0.01, cur / clip_duration))
                        on_progress(pct, f"{status_prefix} ({int(pct * 100)}%)")
            proc.wait()
            if self._cancel_event.is_set():
                return False, "Recorte cancelado pelo usuário."
            if proc.returncode != 0:
                err_msg = stderr_tail[-1] if stderr_tail else f"FFmpeg retornou código {proc.returncode}"
                return False, err_msg
            return True, ""
        finally:
            with self._lock:
                self._active_process = None

    def _trim_remote_via_ytdlp(
        self,
        url: str,
        start_sec: float,
        end_sec: float,
        output_path: str,
        ffmpeg_exe: str,
        audio_only: bool = False,
        max_height: Optional[int] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Recorta links remotos (YouTube/X/Instagram) via yt-dlp `download_ranges`,
        baixando EXCLUSIVAMENTE o trecho [start_sec, end_sec] com suporte total a 4K/2K (AV1/VP9)
        e sem bloqueios HTTP 403.
        """
        import yt_dlp

        if audio_only:
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
        elif max_height is None:
            fmt = "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        elif max_height > 1080:
            fmt = (
                f"bestvideo[height<={max_height}]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_height}]+bestaudio/"
                f"best[height<={max_height}]/best"
            )
        else:
            fmt = (
                f"bestvideo[vcodec^=avc1][height<={max_height}]+bestaudio[ext=m4a]/"
                f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_height}]+bestaudio/"
                f"best[height<={max_height}]/best"
            )

        base_no_ext = os.path.splitext(output_path)[0]
        target_ext = ".mp3" if audio_only else ".mp4"
        expected_out = base_no_ext + target_ext
        outtmpl = base_no_ext + ".%(ext)s"

        class _CancelTrimError(Exception):
            pass

        def progress_hook(d: Dict):
            if self._cancel_event.is_set():
                raise _CancelTrimError("Recorte cancelado pelo usuário.")
            status = d.get("status")
            if status == "downloading" and on_progress:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0
                if total > 0:
                    pct = min(0.95, max(0.08, downloaded / total))
                    spd_str = f" • {speed / 1048576:.1f} MB/s" if speed > 0 else ""
                    on_progress(pct, f"Baixando trecho ({int(pct * 100)}%){spd_str}")
                else:
                    on_progress(0.35, "Baixando apenas o trecho selecionado...")
            elif status == "finished" and on_progress:
                on_progress(0.96, "Finalizando recorte...")

        ydl_opts: Dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": fmt,
            "outtmpl": outtmpl,
            "ffmpeg_location": os.path.dirname(ffmpeg_exe),
            "download_ranges": yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
            "force_keyframes_at_cuts": False,
            "progress_hooks": [progress_hook],
            "socket_timeout": 20,
        }

        if audio_only:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]
        else:
            ydl_opts["merge_output_format"] = "mp4"

        if on_progress:
            on_progress(0.06, "Conectando e recortando apenas o trecho...")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except _CancelTrimError:
            return False, "Recorte cancelado pelo usuário.", None
        except Exception as e:
            return False, str(e), None

        if os.path.exists(expected_out) and os.path.getsize(expected_out) > 0:
            return True, "", expected_out

        # Procura arquivo gerado com mesmo prefixo caso o container final difira
        parent_dir = os.path.dirname(output_path)
        prefix = os.path.basename(base_no_ext)
        for fname in os.listdir(parent_dir):
            if fname.startswith(prefix) and not fname.endswith(".part"):
                full = os.path.join(parent_dir, fname)
                if os.path.getsize(full) > 0:
                    return True, "", full

        return False, "Arquivo recortado não foi gerado.", None

    def trim(
        self,
        source_info: TrimSourceInfo,
        start_sec: float,
        end_sec: float,
        output_dir: str,
        audio_only: bool = False,
        mode: str = TRIM_MODE_FAST,
        max_height: Optional[int] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Executa o recorte de `source_info` no intervalo [start_sec, end_sec].
        Retorna: (sucesso, mensagem, caminho_do_arquivo_gerado)
        """
        self._cancel_event.clear()

        ok_range, err_range = validate_trim_range(start_sec, end_sec, source_info.duration_sec)
        if not ok_range:
            return False, err_range, None

        ffmpeg_exe = get_ffmpeg_executable()
        if not ffmpeg_exe:
            return False, "FFmpeg não encontrado no sistema.", None

        ensure_directory(output_dir)
        clip_duration = end_sec - start_sec

        base_name = sanitize_filename(source_info.title or "clip")[:80]
        slug = f"{format_timestamp_slug(start_sec)}-{format_timestamp_slug(end_sec)}"
        if audio_only:
            out_ext = ".mp3"
        elif source_info.source_type == "file" and mode == TRIM_MODE_FAST and source_info.file_ext:
            out_ext = source_info.file_ext
        else:
            out_ext = ".mp4"

        candidate = os.path.join(output_dir, f"{base_name}_clip_{slug}{out_ext}")
        counter = 2
        while os.path.exists(candidate):
            candidate = os.path.join(output_dir, f"{base_name}_clip_{slug}_{counter}{out_ext}")
            counter += 1
        output_path = candidate

        t0 = time.monotonic()

        try:
            if source_info.source_type == "file":
                cmd, engine_label = build_local_trim_command(
                    ffmpeg_exe=ffmpeg_exe,
                    input_path=source_info.source,
                    output_path=output_path,
                    start_sec=start_sec,
                    duration_sec=clip_duration,
                    audio_only=audio_only,
                    mode=mode,
                )
                if on_progress:
                    on_progress(0.05, f"Recortando ({engine_label})...")
                ok, err = self._run_ffmpeg(cmd, clip_duration, on_progress, f"Recortando ({engine_label})")
                final_path = output_path
            else:
                ok, err, final_path = self._trim_remote_via_ytdlp(
                    url=source_info.source,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    output_path=output_path,
                    ffmpeg_exe=ffmpeg_exe,
                    audio_only=audio_only,
                    max_height=max_height,
                    on_progress=on_progress,
                )
                if not ok and not self._cancel_event.is_set():
                    log_warning(f"[Trimmer] yt-dlp download_ranges falhou ({err[:120]}). Tentando seek direto FFmpeg...")
                    video_url, audio_url, headers, _ = _resolve_remote_streams(
                        url=source_info.source,
                        audio_only=audio_only,
                        max_height=max_height,
                    )
                    cmd, engine_label = build_remote_trim_command(
                        ffmpeg_exe=ffmpeg_exe,
                        video_url=video_url,
                        audio_url=audio_url,
                        output_path=output_path,
                        start_sec=start_sec,
                        duration_sec=clip_duration,
                        headers=headers,
                        audio_only=audio_only,
                        mode=mode,
                    )
                    ok, err = self._run_ffmpeg(cmd, clip_duration, on_progress, f"Recortando trecho ({engine_label})")
                    final_path = output_path

            if not ok or not final_path:
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                return False, err or "Falha ao recortar mídia.", None

            if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
                return False, "Arquivo recortado ficou vazio ou não foi gerado.", None

            elapsed = time.monotonic() - t0
            if on_progress:
                on_progress(1.0, f"✓ Recorte concluído em {elapsed:.1f}s!")
            log_info(
                f"[Trimmer] Recorte concluído em {elapsed:.1f}s: {os.path.basename(final_path)} "
                f"({format_duration(int(clip_duration))})"
            )
            return True, f"✓ Recorte salvo em {elapsed:.1f}s: {os.path.basename(final_path)}", final_path

        except Exception as e:
            log_error("[Trimmer] Erro inesperado durante recorte", e)
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return False, f"Erro no recorte: {str(e)[:140]}", None
