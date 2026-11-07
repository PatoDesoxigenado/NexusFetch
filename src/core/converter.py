"""Módulo de conversão de mídia de alta performance e segurança atômica via FFmpeg."""
import os
import re
import sys
import json
import time
import shutil
import threading
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Callable

from src.utils.logger import log_info, log_error, log_warning
from src.utils.helpers import format_bytes, format_duration
from src.utils.diagnostics import find_ffmpeg

# Extensões suportadas para entrada
SUPPORTED_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".wmv", ".m4v"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
ALL_SUPPORTED_EXTS = SUPPORTED_VIDEO_EXTS | SUPPORTED_AUDIO_EXTS

# Formatos de destino disponíveis
TARGET_VIDEO_FORMATS = ["MP4", "MKV", "AVI", "MOV", "WEBM"]
TARGET_AUDIO_FORMATS = ["MP3", "WAV", "FLAC", "M4A", "OGG", "OPUS"]

# Presets de resolução
RESOLUTION_PRESETS = [
    ("original", "Manter Resolução Original"),
    ("2160p", "4K UHD (2160p)"),
    ("1440p", "2K QHD (1440p)"),
    ("1080p", "1080p (FHD)"),
    ("720p", "720p (HD)"),
    ("480p", "480p (SD)"),
]

# Codecs específicos para MP4 -> MP4
MP4_CODECS = [
    ("h264", "H.264 / AVC (Padrão - Alta Compatibilidade)"),
    ("hevc", "H.265 / HEVC (Alta Eficiência / Menor Tamanho)"),
    ("av1", "AV1 (Nova Geração / Ultra Eficiente)"),
    ("vp9", "VP9 (Aberto / Web)"),
]

@dataclass
class MediaFileInfo:
    path: str
    name: str
    size_bytes: int
    size_str: str
    is_video: bool
    is_audio: bool
    ext: str
    duration_sec: float
    duration_str: str
    width: Optional[int] = None
    height: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None

    @property
    def resolution_str(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "N/A"

def get_ffmpeg_executable() -> str:
    """Retorna o caminho do executável do FFmpeg."""
    ok, path, _ = find_ffmpeg()
    if ok and path:
        return path
    return "ffmpeg"

def get_ffprobe_executable() -> str:
    """Retorna o caminho do executável do FFprobe se existir próximo ao ffmpeg."""
    ok, path, _ = find_ffmpeg()
    if ok and path:
        bin_dir = os.path.dirname(path)
        is_win = (os.name == "nt")
        ffprobe_name = "ffprobe.exe" if is_win else "ffprobe"
        cand = os.path.join(bin_dir, ffprobe_name)
        if os.path.isfile(cand):
            return cand
    return "ffprobe"

def probe_media_file(file_path: str) -> Optional[MediaFileInfo]:
    """Obtém metadados do arquivo via FFprobe ou FFmpeg de forma ultrarrápida."""
    if not os.path.isfile(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()
    is_video = ext in SUPPORTED_VIDEO_EXTS
    is_audio = ext in SUPPORTED_AUDIO_EXTS
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    duration = 0.0
    width = None
    height = None
    vcodec = None
    acodec = None

    # Tenta usar ffprobe para inspeção JSON
    ffprobe_cmd = get_ffprobe_executable()
    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        cmd = [
            ffprobe_cmd,
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,codec_type,width,height",
            "-of", "json",
            file_path
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            timeout=6
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            try:
                duration = float(format_info.get("duration", 0.0))
            except (ValueError, TypeError):
                duration = 0.0

            streams = data.get("streams", [])
            for st in streams:
                c_type = st.get("codec_type")
                if c_type == "video" and not width:
                    width = st.get("width")
                    height = st.get("height")
                    vcodec = st.get("codec_name")
                    is_video = True
                elif c_type == "audio" and not acodec:
                    acodec = st.get("codec_name")
                    if not is_video:
                        is_audio = True

    except Exception as e:
        log_warning(f"ffprobe falhou para {file_name}: {e}. Tentando fallback ffmpeg...")
        # Fallback rápido usando ffmpeg -i
        try:
            ffmpeg_cmd = get_ffmpeg_executable()
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            proc = subprocess.run(
                [ffmpeg_cmd, "-i", file_path],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                timeout=6
            )
            err_out = proc.stderr or ""
            # Procura Duration: 00:01:23.45
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err_out)
            if dur_match:
                h, m, s = dur_match.groups()
                duration = int(h) * 3600 + int(m) * 60 + float(s)

            # Procura resolução: 1920x1080
            res_match = re.search(r",\s*(\d{2,5})x(\d{2,5})", err_out)
            if res_match:
                width = int(res_match.group(1))
                height = int(res_match.group(2))
                is_video = True
        except Exception as e2:
            log_warning(f"Fallback ffmpeg também falhou: {e2}")

    return MediaFileInfo(
        path=file_path,
        name=file_name,
        size_bytes=file_size,
        size_str=format_bytes(file_size),
        is_video=is_video,
        is_audio=is_audio,
        ext=ext,
        duration_sec=duration,
        duration_str=format_duration(int(duration)) if duration > 0 else "--:--",
        width=width,
        height=height,
        vcodec=vcodec,
        acodec=acodec
    )

_HW_ACCEL_CACHE: Dict[str, bool] = {}

def is_encoder_available(encoder_name: str) -> bool:
    """Verifica se um encoder de aceleração por hardware específico está funcional na máquina."""
    if encoder_name in _HW_ACCEL_CACHE:
        return _HW_ACCEL_CACHE[encoder_name]

    ffmpeg_cmd = get_ffmpeg_executable()
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        cmd = [
            ffmpeg_cmd,
            "-v", "error",
            "-f", "lavfi",
            "-i", "nullsrc=s=256x256:d=0.04",
            "-c:v", encoder_name,
            "-f", "null",
            "-"
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            timeout=2
        )
        avail = (res.returncode == 0)
    except Exception:
        avail = False

    _HW_ACCEL_CACHE[encoder_name] = avail
    return avail

def get_optimized_video_encoder_args(codec_key: str) -> List[str]:
    """
    Retorna os melhores argumentos de codificação:
    1º GPU NVIDIA (NVENC) — aceleração máxima por hardware
    2º GPU Intel (QSV)
    3º GPU AMD (AMF)
    4º CPU com preset rápido otimizado ('fast') mantendo qualidade excelente
    """
    if codec_key == "hevc":
        if is_encoder_available("hevc_nvenc"):
            return ["-c:v", "hevc_nvenc", "-preset", "p4", "-cq", "24", "-pix_fmt", "yuv420p"]
        elif is_encoder_available("hevc_qsv"):
            return ["-c:v", "hevc_qsv", "-global_quality", "24", "-pix_fmt", "nv12"]
        elif is_encoder_available("hevc_amf"):
            return ["-c:v", "hevc_amf", "-rc", "cqp", "-qp_p", "24", "-pix_fmt", "yuv420p"]
        else:
            return ["-c:v", "libx265", "-preset", "fast", "-crf", "24", "-pix_fmt", "yuv420p"]

    elif codec_key == "av1":
        if is_encoder_available("av1_nvenc"):
            return ["-c:v", "av1_nvenc", "-preset", "p4", "-cq", "28", "-pix_fmt", "yuv420p"]
        elif is_encoder_available("av1_qsv"):
            return ["-c:v", "av1_qsv", "-global_quality", "28", "-pix_fmt", "nv12"]
        elif is_encoder_available("av1_amf"):
            return ["-c:v", "av1_amf", "-rc", "cqp", "-qp_p", "28", "-pix_fmt", "yuv420p"]
        else:
            return ["-c:v", "libaom-av1", "-crf", "28", "-b:v", "0", "-cpu-used", "6", "-pix_fmt", "yuv420p"]

    elif codec_key == "vp9":
        return ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-row-mt", "1", "-speed", "3", "-pix_fmt", "yuv420p"]

    else: # Default H.264
        if is_encoder_available("h264_nvenc"):
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p"]
        elif is_encoder_available("h264_qsv"):
            return ["-c:v", "h264_qsv", "-global_quality", "22", "-pix_fmt", "nv12"]
        elif is_encoder_available("h264_amf"):
            return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_p", "22", "-pix_fmt", "yuv420p"]
        else:
            return ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p"]

def build_conversion_args(
    input_path: str,
    output_path: str,
    target_format: str,
    resolution_key: str = "original",
    codec_key: str = "h264"
) -> List[str]:
    """
    Constrói a lista de argumentos de comando do FFmpeg com máxima otimização e qualidade.
    Garante dimensões pares (-2) e saída atômica segura.
    """
    ffmpeg_cmd = get_ffmpeg_executable()
    fmt_lower = target_format.lower().replace(" (extrair áudio 320k)", "").replace(" (extrair áudio)", "").strip()
    # Limpa labels como 'MP3 (320 kbps)' -> 'mp3'
    fmt_clean = fmt_lower.split()[0].replace(".", "").lower()

    in_ext = os.path.splitext(input_path)[1].lower().replace(".", "")
    is_mp4_to_mp4 = (in_ext == "mp4" and fmt_clean == "mp4")

    # Início do comando com leitura de progresso em tempo real
    args = [
        ffmpeg_cmd,
        "-y",
        "-nostdin",
        "-progress", "pipe:1",
    ]
    is_target_audio = fmt_clean in {"mp3", "wav", "flac", "m4a", "ogg", "opus"}
    if not is_target_audio:
        # Acelera a decodificação do vídeo fonte diretamente pela GPU quando compatível
        args.extend(["-hwaccel", "auto"])

    args.extend(["-i", input_path])

    # Resolução / Filtro de escala (se for formato de vídeo)
    scale_filter = None
    target_heights = {
        "2160p": 2160,
        "1440p": 1440,
        "1080p": 1080,
        "720p": 720,
        "480p": 480,
    }
    if resolution_key in target_heights:
        target_h = target_heights[resolution_key]
        # Garante que a largura calculada seja sempre múltiplo de 2 (obrigatório para h264/h265)
        scale_filter = f"scale=-2:{target_h}"

    # 1. Destino de ÁUDIO (Extração de vídeo ou conversão de áudio para áudio)
    if is_target_audio:
        args.append("-vn") # Sem stream de vídeo
        if fmt_clean == "mp3":
            args.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
        elif fmt_clean == "wav":
            args.extend(["-c:a", "pcm_s16le"])
        elif fmt_clean == "flac":
            args.extend(["-c:a", "flac"])
        elif fmt_clean == "m4a":
            args.extend(["-c:a", "aac", "-b:a", "320k"])
        elif fmt_clean == "ogg":
            args.extend(["-c:a", "libvorbis", "-b:a", "320k"])
        elif fmt_clean == "opus":
            args.extend(["-c:a", "libopus", "-b:a", "320k"])

    # 2. Destino de VÍDEO (Com aceleração por hardware e codecs otimizados)
    else:
        # Se for MP4 para MP4, permite customizar o CODEC selecionado
        if is_mp4_to_mp4:
            args.extend(get_optimized_video_encoder_args(codec_key))
            args.extend(["-c:a", "aac", "-b:a", "192k"])
            args.extend(["-movflags", "+faststart"])

        # Outros formatos de vídeo famosos
        else:
            if fmt_clean == "mp4":
                args.extend(get_optimized_video_encoder_args("h264"))
                args.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"])
            elif fmt_clean == "mkv":
                args.extend(get_optimized_video_encoder_args("h264"))
                args.extend(["-c:a", "aac", "-b:a", "192k"])
            elif fmt_clean == "mov":
                args.extend(get_optimized_video_encoder_args("h264"))
                args.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"])
            elif fmt_clean == "avi":
                args.extend(["-c:v", "mpeg4", "-q:v", "3", "-c:a", "libmp3lame", "-b:a", "192k"])
            elif fmt_clean == "webm":
                args.extend(["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-row-mt", "1", "-speed", "3", "-c:a", "libopus", "-b:a", "128k"])
            else:
                args.extend(get_optimized_video_encoder_args("h264"))
                args.extend(["-c:a", "aac", "-b:a", "192k"])

        # Aplica redimensionamento se selecionado
        if scale_filter:
            args.extend(["-vf", scale_filter])

    # Uso multi-thread e arquivo de saída
    args.extend(["-threads", "0", output_path])
    return args

class MediaConverter:
    """Gerenciador de conversão em lote com segurança atômica e cancelamento limpo."""
    def __init__(self):
        self._cancel_requested = threading.Event()
        self._current_process: Optional[subprocess.Popen] = None

    def cancel(self):
        """Solicita o cancelamento imediato da conversão em andamento."""
        self._cancel_requested.set()
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass

    def convert_batch(
        self,
        files: List[MediaFileInfo],
        output_dir: str,
        target_format: str,
        resolution_key: str = "original",
        codec_key: str = "h264",
        on_progress: Optional[Callable[[int, int, float, float, str, str], None]] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Executa a conversão sequencial de todos os arquivos.
        Retorna (convertidos_com_sucesso, total_arquivos, lista_de_erros).
        
        on_progress recebe:
            (item_idx, total_items, item_pct, total_pct, speed_str, status_msg)
        """
        self._cancel_requested.clear()
        os.makedirs(output_dir, exist_ok=True)

        total_files = len(files)
        success_count = 0
        errors: List[str] = []

        fmt_lower = target_format.lower().replace(" (extrair áudio 320k)", "").replace(" (extrair áudio)", "").strip()
        target_ext = "." + fmt_lower.split()[0].replace(".", "").lower()

        for idx, file_info in enumerate(files):
            if self._cancel_requested.is_set():
                break

            base_name = os.path.splitext(file_info.name)[0]
            # Se o arquivo de saída teria o mesmo nome e extensão na mesma pasta, adiciona sufixo
            dest_filename = f"{base_name}{target_ext}"
            dest_path = os.path.join(output_dir, dest_filename)
            if os.path.abspath(dest_path) == os.path.abspath(file_info.path):
                dest_filename = f"{base_name}_converted{target_ext}"
                dest_path = os.path.join(output_dir, dest_filename)

            # Arquivo temporário para garantir atomicidade
            tmp_path = dest_path + ".tmp" + target_ext
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            cmd = build_conversion_args(
                input_path=file_info.path,
                output_path=tmp_path,
                target_format=target_format,
                resolution_key=resolution_key,
                codec_key=codec_key
            )

            log_info(f"Iniciando conversao [{idx+1}/{total_files}]: {file_info.name} -> {dest_filename}")

            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    universal_newlines=True,
                    startupinfo=startupinfo
                )
                self._current_process = proc

                duration_us = int(file_info.duration_sec * 1_000_000) if file_info.duration_sec > 0 else 0
                current_speed = "--"

                # Loop de leitura do progresso oficial do FFmpeg (-progress pipe:1)
                for line in proc.stdout:
                    if self._cancel_requested.is_set():
                        proc.terminate()
                        break

                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("speed="):
                        current_speed = line.split("=", 1)[1].strip()

                    elif line.startswith("out_time_us="):
                        try:
                            out_us = int(line.split("=", 1)[1].strip())
                            if duration_us > 0:
                                item_pct = min(99.0, max(0.0, (out_us / duration_us) * 100.0))
                            else:
                                item_pct = 50.0

                            total_pct = ((idx + (item_pct / 100.0)) / total_files) * 100.0
                            if on_progress:
                                status_msg = f"Convertendo: {file_info.name}"
                                on_progress(idx + 1, total_files, item_pct, total_pct, current_speed, status_msg)
                        except (ValueError, TypeError):
                            pass

                    elif line == "progress=end":
                        if on_progress:
                            total_pct = ((idx + 1) / total_files) * 100.0
                            on_progress(idx + 1, total_files, 100.0, total_pct, current_speed, f"Finalizado: {file_info.name}")

                proc.wait()

                if self._cancel_requested.is_set():
                    log_warning(f"Conversão cancelada pelo usuário: {file_info.name}")
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                    break

                # Valida integridade do arquivo gerado
                if proc.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    if os.path.exists(dest_path):
                        try:
                            os.remove(dest_path)
                        except Exception:
                            pass
                    os.rename(tmp_path, dest_path)
                    success_count += 1
                    log_info(f"Conversao concluida com sucesso: {dest_path}")
                else:
                    err_msg = f"Falha ao converter '{file_info.name}' (Código de saída: {proc.returncode})"
                    errors.append(err_msg)
                    log_error(err_msg)
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

            except Exception as e:
                err_msg = f"Erro inesperado ao converter '{file_info.name}': {str(e)[:120]}"
                errors.append(err_msg)
                log_error(err_msg)
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            finally:
                self._current_process = None

        return success_count, total_files, errors
