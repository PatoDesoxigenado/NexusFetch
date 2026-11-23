"""Motor de compressão inteligente por tamanho alvo (Discord & WhatsApp) para Vídeos e Áudios via FFmpeg."""
import os
import re
import sys
import time
import shutil
import tempfile
import threading
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from src.core.converter import (
    MediaFileInfo,
    get_ffmpeg_executable,
    probe_media_file,
    is_encoder_available,
    ALL_SUPPORTED_EXTS,
)
from src.utils.helpers import format_bytes
from src.utils.logger import log_info, log_error, log_warning

# Presets de limite de tamanho por aplicativo (chave -> (label, limit_mb, target_mb))
COMPRESS_PRESETS: List[Tuple[str, str, float, float]] = [
    ("discord_10", "🎮 Discord Grátis (Limite 10 MB)", 10.0, 9.4),
    ("whatsapp_16", "💬 WhatsApp Vídeo (Limite 16 MB)", 16.0, 15.2),
    ("discord_50", "🚀 Discord Nitro Basic (Limite 50 MB)", 50.0, 48.0),
    ("whatsapp_64", "📱 WhatsApp HD / Estendido (Limite 64 MB)", 64.0, 61.5),
]

PRESET_BY_KEY: Dict[str, Tuple[str, float, float]] = {
    k: (label, limit_mb, target_mb) for k, label, limit_mb, target_mb in COMPRESS_PRESETS
}


@dataclass
class CompressionPlan:
    already_within_limit: bool
    is_video: bool
    target_bytes: int
    limit_bytes: int
    video_kbps: int
    audio_kbps: int
    scale_height: Optional[int]
    output_ext: str
    target_fps: Optional[int] = None
    low_quality_warning: bool = False


def calculate_compression_plan(file_info: MediaFileInfo, limit_mb: float, target_mb: float) -> CompressionPlan:
    """
    Calcula o plano ótimo de bitrate, resolução e FPS adaptativos para atingir o tamanho alvo
    preservando a máxima qualidade visual/sonora sem macroblocos.
    """
    limit_bytes = int(limit_mb * 1024 * 1024)
    target_bytes = int(target_mb * 1024 * 1024)

    if file_info.size_bytes <= limit_bytes:
        return CompressionPlan(
            already_within_limit=True,
            is_video=file_info.is_video,
            target_bytes=target_bytes,
            limit_bytes=limit_bytes,
            video_kbps=0,
            audio_kbps=0,
            scale_height=None,
            output_ext=file_info.ext or (".mp4" if file_info.is_video else ".mp3"),
        )

    duration = max(1.0, float(file_info.duration_sec or 1.0))
    # Margem de 6% para overhead de container MP4/MP3
    total_kbps = int((target_bytes * 8.0) / duration / 1000.0 * 0.94)

    if not file_info.is_video:
        audio_kbps = max(48, min(320, total_kbps))
        return CompressionPlan(
            already_within_limit=False,
            is_video=False,
            target_bytes=target_bytes,
            limit_bytes=limit_bytes,
            video_kbps=0,
            audio_kbps=audio_kbps,
            scale_height=None,
            output_ext=".mp3",
        )

    # Vídeo: reserva áudio equilibrado e destina o restante ao vídeo
    if total_kbps >= 900:
        audio_kbps = 128
    elif total_kbps >= 450:
        audio_kbps = 96
    else:
        audio_kbps = 64

    video_kbps = max(120, total_kbps - audio_kbps)
    low_quality_warning = video_kbps < 280

    # Downscale adaptativo + redução para 30fps em bitrates apertados (dobra bits por frame!)
    scale_height: Optional[int] = None
    target_fps: Optional[int] = None
    if video_kbps < 550:
        scale_height = 480
        target_fps = 30
    elif video_kbps < 1400:
        scale_height = 720
        target_fps = 30
    elif video_kbps < 3500:
        scale_height = 1080

    if scale_height and file_info.height and file_info.height <= scale_height:
        scale_height = None

    return CompressionPlan(
        already_within_limit=False,
        is_video=True,
        target_bytes=target_bytes,
        limit_bytes=limit_bytes,
        video_kbps=video_kbps,
        audio_kbps=audio_kbps,
        scale_height=scale_height,
        output_ext=".mp4",
        target_fps=target_fps,
        low_quality_warning=low_quality_warning,
    )


def _run_ffmpeg_with_progress(
    cmd: List[str],
    duration_sec: float,
    on_pct: Optional[Callable[[float], None]],
    is_cancelled_fn: Callable[[], bool],
    proc_holder: List[Optional[subprocess.Popen]],
) -> int:
    """Executa um processo FFmpeg reportando progresso via stderr time=HH:MM:SS.xx."""
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo,
    )
    proc_holder[0] = proc
    time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

    try:
        if proc.stderr:
            for line in proc.stderr:
                if is_cancelled_fn():
                    proc.terminate()
                    return -1
                if on_pct and duration_sec > 0:
                    m = time_re.search(line)
                    if m:
                        secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        on_pct(min(99.0, max(0.0, (secs / duration_sec) * 100.0)))
        proc.wait()
        return proc.returncode
    finally:
        proc_holder[0] = None


class MediaCompressor:
    """Gerencia compressão em lote assíncrona com 2-pass H.264 para vídeo e MP3 otimizado para áudio."""

    def __init__(self):
        self._is_cancelled = False
        self._proc_holder: List[Optional[subprocess.Popen]] = [None]
        self._thread: Optional[threading.Thread] = None

    def cancel(self):
        self._is_cancelled = True
        proc = self._proc_holder[0]
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def compress_batch_async(
        self,
        files: List[MediaFileInfo],
        preset_key: str,
        output_dir: str,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_complete: Optional[Callable[[bool, str, str], None]] = None,
    ):
        self._is_cancelled = False
        self._thread = threading.Thread(
            target=self._run_batch,
            args=(files, preset_key, output_dir, on_progress, on_complete),
            daemon=True,
        )
        self._thread.start()

    def _run_batch(
        self,
        files: List[MediaFileInfo],
        preset_key: str,
        output_dir: str,
        on_progress: Optional[Callable[[float, str], None]],
        on_complete: Optional[Callable[[bool, str, str], None]],
    ):
        if not files:
            if on_complete:
                on_complete(False, "Nenhum arquivo na fila para comprimir.", "")
            return

        os.makedirs(output_dir, exist_ok=True)
        label, limit_mb, target_mb = PRESET_BY_KEY.get(preset_key, PRESET_BY_KEY["discord_10"])
        ffmpeg_exe = get_ffmpeg_executable()
        total = len(files)
        success_count = 0
        skipped_count = 0

        for idx, finfo in enumerate(files, 1):
            if self._is_cancelled:
                if on_complete:
                    on_complete(False, f"Compressão cancelada ({success_count}/{total} concluídos).", output_dir)
                return

            plan = calculate_compression_plan(finfo, limit_mb, target_mb)
            base_name = os.path.splitext(finfo.name)[0]
            tag = preset_key.replace("_", "-")
            dest_path = os.path.join(output_dir, f"{base_name}_{tag}{plan.output_ext}")
            tmp_path = os.path.join(output_dir, f".tmp_{os.getpid()}_{idx}_{base_name}{plan.output_ext}")

            if plan.already_within_limit:
                skipped_count += 1
                success_count += 1
                if on_progress:
                    on_progress((idx / total) * 100.0, f"[{idx}/{total}] {finfo.name} já cabe no limite ({finfo.size_str})!")
                continue

            try:
                if plan.is_video:
                    ok = self._compress_video_two_pass(
                        ffmpeg_exe, finfo, plan, tmp_path, idx, total, on_progress
                    )
                else:
                    ok = self._compress_audio(
                        ffmpeg_exe, finfo, plan, tmp_path, idx, total, on_progress
                    )

                if self._is_cancelled:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    if on_complete:
                        on_complete(False, f"Compressão cancelada ({success_count}/{total} concluídos).", output_dir)
                    return

                if ok and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    os.replace(tmp_path, dest_path)
                    new_size = format_bytes(os.path.getsize(dest_path))
                    log_info(f"Compressão concluída: {finfo.name} ({finfo.size_str} -> {new_size})")
                    success_count += 1
                else:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    log_error(f"Falha ao comprimir {finfo.name}")

            except Exception as e:
                log_error(f"Erro na compressão de {finfo.name}: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        if on_complete:
            if success_count == total:
                extra = f" ({skipped_count} já cabiam no limite)" if skipped_count else ""
                on_complete(True, f"{success_count} de {total} arquivo(s) prontos para envio!{extra}", output_dir)
            elif success_count > 0:
                on_complete(True, f"{success_count} de {total} arquivo(s) comprimidos com sucesso.", output_dir)
            else:
                on_complete(False, "Não foi possível comprimir os arquivos selecionados.", "")

    def _compress_video_two_pass(
        self,
        ffmpeg_exe: str,
        finfo: MediaFileInfo,
        plan: CompressionPlan,
        tmp_path: str,
        idx: int,
        total: int,
        on_progress: Optional[Callable[[float, str], None]],
    ) -> bool:
        vf_parts = []
        if plan.scale_height:
            vf_parts.append(f"scale=-2:{plan.scale_height}")
        if plan.target_fps:
            vf_parts.append(f"fps={plan.target_fps}")
        vf_args = ["-vf", ",".join(vf_parts)] if vf_parts else []

        # 1. Aceleração por GPU (5x–10x mais rápido que CPU 2-Pass!)
        hw_args: Optional[List[str]] = None
        hw_label = ""
        if is_encoder_available("h264_nvenc"):
            hw_args = [
                "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-multipass", "fullres",
                "-b:v", f"{plan.video_kbps}k",
                "-maxrate", f"{int(plan.video_kbps * 1.2)}k",
                "-bufsize", f"{int(plan.video_kbps * 2)}k",
                "-pix_fmt", "yuv420p",
            ]
            hw_label = "GPU NVIDIA"
        elif is_encoder_available("h264_qsv"):
            hw_args = [
                "-c:v", "h264_qsv", "-preset", "medium",
                "-b:v", f"{plan.video_kbps}k",
                "-maxrate", f"{int(plan.video_kbps * 1.2)}k",
                "-bufsize", f"{int(plan.video_kbps * 2)}k",
                "-pix_fmt", "nv12",
            ]
            hw_label = "GPU Intel"
        elif is_encoder_available("h264_amf"):
            hw_args = [
                "-c:v", "h264_amf", "-rc", "vbr_peak",
                "-b:v", f"{plan.video_kbps}k",
                "-maxrate", f"{int(plan.video_kbps * 1.2)}k",
                "-bufsize", f"{int(plan.video_kbps * 2)}k",
                "-pix_fmt", "yuv420p",
            ]
            hw_label = "GPU AMD"

        if hw_args:
            cmd_gpu = [
                ffmpeg_exe, "-y", "-i", finfo.path,
                *hw_args, *vf_args,
                "-c:a", "aac", "-b:a", f"{plan.audio_kbps}k",
                "-movflags", "+faststart",
                "-f", "mp4", tmp_path,
            ]

            def on_gpu(pct: float):
                if on_progress:
                    overall = ((idx - 1) / total + (pct / 100.0) / total) * 100.0
                    on_progress(overall, f"[{idx}/{total}] Comprimindo ({hw_label}): {finfo.name[:32]} ({pct:.0f}%)")

            rc_gpu = _run_ffmpeg_with_progress(cmd_gpu, finfo.duration_sec, on_gpu, lambda: self._is_cancelled, self._proc_holder)
            if rc_gpu == 0 or self._is_cancelled:
                return rc_gpu == 0
            log_warning(f"Compressão via {hw_label} falhou (rc={rc_gpu}); usando fallback CPU 2-Pass...")

        # 2. Fallback CPU multi-thread otimizado (2-Pass H.264)
        passlog_dir = tempfile.mkdtemp(prefix="nexus_2pass_")
        passlog_prefix = os.path.join(passlog_dir, "ffmpeg2pass")
        null_out = "NUL" if sys.platform == "win32" else "/dev/null"

        common_v = [
            "-c:v", "libx264",
            "-b:v", f"{plan.video_kbps}k",
            "-maxrate", f"{int(plan.video_kbps * 1.25)}k",
            "-bufsize", f"{int(plan.video_kbps * 2)}k",
            "-preset", "fast",
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            *vf_args,
        ]

        try:
            cmd_p1 = [
                ffmpeg_exe, "-y", "-i", finfo.path,
                *common_v,
                "-pass", "1", "-passlogfile", passlog_prefix,
                "-an", "-f", "mp4", null_out,
            ]

            def on_p1(pct: float):
                if on_progress:
                    overall = ((idx - 1) / total + (pct * 0.4 / 100.0) / total) * 100.0
                    on_progress(overall, f"[{idx}/{total}] Passo 1/2 (Analisando): {finfo.name[:35]} ({pct:.0f}%)")

            rc1 = _run_ffmpeg_with_progress(cmd_p1, finfo.duration_sec, on_p1, lambda: self._is_cancelled, self._proc_holder)
            if rc1 != 0 or self._is_cancelled:
                return False

            cmd_p2 = [
                ffmpeg_exe, "-y", "-i", finfo.path,
                *common_v,
                "-pass", "2", "-passlogfile", passlog_prefix,
                "-c:a", "aac", "-b:a", f"{plan.audio_kbps}k",
                "-movflags", "+faststart",
                "-f", "mp4", tmp_path,
            ]

            def on_p2(pct: float):
                if on_progress:
                    overall = ((idx - 1) / total + ((40.0 + pct * 0.6) / 100.0) / total) * 100.0
                    on_progress(overall, f"[{idx}/{total}] Passo 2/2 (Comprimindo): {finfo.name[:35]} ({pct:.0f}%)")

            rc2 = _run_ffmpeg_with_progress(cmd_p2, finfo.duration_sec, on_p2, lambda: self._is_cancelled, self._proc_holder)
            return rc2 == 0
        finally:
            shutil.rmtree(passlog_dir, ignore_errors=True)

    def _compress_audio(
        self,
        ffmpeg_exe: str,
        finfo: MediaFileInfo,
        plan: CompressionPlan,
        tmp_path: str,
        idx: int,
        total: int,
        on_progress: Optional[Callable[[float, str], None]],
    ) -> bool:
        cmd = [
            ffmpeg_exe, "-y", "-i", finfo.path,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", f"{plan.audio_kbps}k",
            "-f", "mp3", tmp_path,
        ]

        def on_a(pct: float):
            if on_progress:
                overall = ((idx - 1) / total + (pct / 100.0) / total) * 100.0
                on_progress(overall, f"[{idx}/{total}] Comprimindo áudio ({plan.audio_kbps} kbps): {finfo.name[:32]} ({pct:.0f}%)")

        rc = _run_ffmpeg_with_progress(cmd, finfo.duration_sec, on_a, lambda: self._is_cancelled, self._proc_holder)
        return rc == 0
