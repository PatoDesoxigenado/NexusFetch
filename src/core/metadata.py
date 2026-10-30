"""Extração ultra-rápida de metadados de mídias (YouTube, Twitter/X, Instagram)."""
import os
import re
import ssl
import json
import html
import time
import urllib.request
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import yt_dlp
from src.utils.helpers import format_bytes, format_duration, sanitize_filename
from src.utils.diagnostics import find_ffmpeg
from src.utils.logger import log_info, log_error, log_warning
from src.utils.validators import is_playlist_url

@dataclass
class VideoQualityOption:
    label: str
    height: Optional[int]
    format_id: str
    filesize_bytes: Optional[int] = None

@dataclass
class PlaylistItem:
    index: int  # 1, 2, 3...
    video_id: str
    title: str
    duration: Optional[int]
    duration_str: str
    url: str
    thumbnail_url: Optional[str]
    uploader: Optional[str] = None
    is_selected: bool = True

@dataclass
class MediaMetadata:
    url: str
    title: str
    uploader: str
    duration: Optional[int]
    duration_str: str
    thumbnail_url: Optional[str]
    qualities: List[VideoQualityOption] = field(default_factory=list)
    raw_info: Dict = field(default_factory=dict)
    media_type: str = "video"  # "video", "audio", "image", "gif", "playlist"
    image_urls: List[str] = field(default_factory=list)
    video_stream_url: Optional[str] = None
    thumbnail_local_path: Optional[str] = None
    estimated_audio_size: Optional[int] = None
    error: Optional[str] = None
    is_playlist: bool = False
    playlist_items: List[PlaylistItem] = field(default_factory=list)
    playlist_count: int = 0

def clear_thumbnail_cache():
    """Remove com segurança arquivos residuais de thumbnails temporárias."""
    temp_dir = tempfile.gettempdir()
    try:
        for fname in os.listdir(temp_dir):
            if fname.startswith("nexus_thumb_") and fname.endswith(".jpg"):
                try:
                    p = os.path.join(temp_dir, fname)
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass

def extract_tweet_id(url: str) -> Optional[str]:
    match = re.search(r'status/(\d+)', url)
    return match.group(1) if match else None

def get_ssl_context():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None

def fetch_twitter_syndication(tweet_id: str) -> Optional[Dict]:
    """Consulta a API oficial de sindicação do Twitter/X (resposta em ~0.4s)."""
    try:
        api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=x"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4, context=get_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log_warning(f"Syndication API falhou para tweet {tweet_id}: {e}")
        return None

def extract_frame_with_ffmpeg(video_url_or_path: str, output_jpg_path: str) -> bool:
    """Extrai o primeiro frame de um vídeo remoto ou local via FFmpeg."""
    ffmpeg_ok, ffmpeg_path, _ = find_ffmpeg()
    if not ffmpeg_ok or not ffmpeg_path:
        return False

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", video_url_or_path,
            "-ss", "00:00:00.1",
            "-vframes", "1",
            "-q:v", "2",
            output_jpg_path
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, startupinfo=startupinfo)
        return proc.returncode == 0 and os.path.exists(output_jpg_path) and os.path.getsize(output_jpg_path) > 0
    except Exception as e:
        log_error(f"Erro no FFmpeg ao extrair frame: {e}")
        return False

def fetch_uncropped_instagram_images(url: str) -> List[str]:
    """Obtém as URLs das imagens originais completas sem o recorte quadrado de thumbnail."""
    try:
        import urllib.parse
        from curl_cffi import requests as cffi_requests
        s = cffi_requests.Session(impersonate='chrome')
        r = s.get('https://indown.io/', timeout=4, verify=False)
        m = re.search(r'name="_token"\s+value="([^"]+)"', r.text) or re.search(r'value="([^"]+)"\s+name="_token"', r.text)
        if not m:
            return []
        data = {
            'referer': 'https://indown.io/en5',
            'locale': 'en',
            '_token': m.group(1),
            'link': url
        }
        resp = s.post('https://indown.io/download', data=data, timeout=6, verify=False)
        matches = re.findall(r'fetch\?url=([^"\'\s&]+)', resp.text)
        urls = []
        for m_url in matches:
            decoded = urllib.parse.unquote(m_url)
            if decoded.startswith('http') and decoded not in urls:
                urls.append(decoded)
        return urls
    except Exception as e:
        log_warning(f"Falha ao obter imagem uncropped via indown: {e}")
        return []

def fetch_instagram_media(url: str) -> Optional[MediaMetadata]:
    """Extrai fotos e mídias do Instagram contornando proteções e restrições de login."""
    shortcode_match = re.search(r'instagram\.com/(?:p|reel|reels|tv)/([a-zA-Z0-9_-]+)', url)
    if not shortcode_match:
        return None
    shortcode = shortcode_match.group(1)
    post_url = f"https://www.instagram.com/p/{shortcode}/"

    html_text = ""
    # 1. Tenta curl_cffi para emulação de TLS/JA4 de navegador real
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(post_url, impersonate="chrome", timeout=8, verify=False)
        if resp.status_code == 200 and resp.text:
            html_text = resp.text
    except Exception as e:
        log_warning(f"curl_cffi falhou para Instagram ({shortcode}): {e}")

    # 2. Fallback urllib padrão
    if not html_text:
        try:
            req = urllib.request.Request(
                post_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
            )
            with urllib.request.urlopen(req, timeout=6, context=get_ssl_context()) as resp:
                html_text = resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            log_warning(f"urllib fallback falhou para Instagram ({shortcode}): {e}")

    if not html_text:
        return None

    # Extrai imagem (og:image / twitter:image)
    img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_text)
    if not img_match:
        img_match = re.search(r'<meta name="twitter:image" content="([^"]+)"', html_text)
    img_url = html.unescape(img_match.group(1)) if img_match else None

    # Extrai vídeo se houver (og:video)
    vid_match = re.search(r'<meta property="og:video" content="([^"]+)"', html_text)
    if not vid_match:
        vid_match = re.search(r'<meta property="og:video:secure_url" content="([^"]+)"', html_text)
    vid_url = html.unescape(vid_match.group(1)) if vid_match else None

    if not img_url and not vid_url:
        return None

    # Extrai título e autor do post
    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
    raw_title = html.unescape(title_match.group(1)) if title_match else f"Instagram Post {shortcode}"

    author = "Instagram"
    clean_title = raw_title
    if " on Instagram: " in raw_title:
        parts = raw_title.split(" on Instagram: ", 1)
        author = parts[0].strip()
        clean_title = parts[1].strip().strip('"')
    elif " no Instagram: " in raw_title:
        parts = raw_title.split(" no Instagram: ", 1)
        author = parts[0].strip()
        clean_title = parts[1].strip().strip('"')
    elif " (@" in raw_title:
        author = raw_title.split(" (@")[0].strip()

    if not clean_title or clean_title == raw_title:
        desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html_text)
        if desc_match:
            clean_title = html.unescape(desc_match.group(1)).strip()

    clean_title = clean_title.replace("\n", " ").strip()
    if len(clean_title) > 90:
        clean_title = clean_title[:90] + "..."

    # Caso 1: É um vídeo / Reel
    if vid_url:
        return MediaMetadata(
            url=url,
            title=clean_title or f"Instagram Reel ({shortcode})",
            uploader=author,
            duration=None,
            duration_str="Vídeo / Reel",
            thumbnail_url=img_url,
            qualities=[
                VideoQualityOption(
                    label="🌟 Vídeo Original (Instagram MP4)",
                    height=None,
                    format_id="best"
                )
            ],
            media_type="video",
            video_stream_url=vid_url,
            raw_info={"shortcode": shortcode, "video_url": vid_url, "image_url": img_url}
        )

    # Caso 2: É uma Foto / Imagem
    # og:image costuma vir com corte quadrado (ex: ?stp=c216.0.648.648a...).
    # Busca a imagem completa sem recorte
    uncropped_urls = fetch_uncropped_instagram_images(post_url)
    main_image = uncropped_urls[0] if uncropped_urls else img_url
    image_list = uncropped_urls if uncropped_urls else ([img_url] if img_url else [])

    return MediaMetadata(
        url=url,
        title=clean_title or f"Instagram Foto ({shortcode})",
        uploader=author,
        duration=0,
        duration_str="Foto / Imagem",
        thumbnail_url=main_image,
        qualities=[
            VideoQualityOption(
                label="🖼️ Imagem Original Completa (Sem Recorte)",
                height=None,
                format_id="photo_orig"
            )
        ],
        media_type="image",
        image_urls=image_list,
        raw_info={"shortcode": shortcode, "image_url": main_image, "uncropped": bool(uncropped_urls)}
    )

def _process_playlist_info(url: str, info: Dict, start_t: float) -> MediaMetadata:
    """Processa e estrutura metadados de uma playlist completa do YouTube."""
    title = info.get("title") or "Playlist do YouTube"
    uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "YouTube"
    raw_entries = info.get("entries") or []
    
    playlist_items: List[PlaylistItem] = []
    item_idx = 1
    total_duration = 0
    
    for entry in raw_entries:
        if not entry:
            continue
        v_title = entry.get("title")
        if not v_title or v_title in ("[Private video]", "[Deleted video]"):
            continue
        v_id = entry.get("id") or ""
        v_url = entry.get("url")
        if not v_url or not str(v_url).startswith("http"):
            v_url = f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
        v_dur = entry.get("duration")
        if v_dur:
            total_duration += v_dur
        v_dur_str = format_duration(v_dur) if v_dur else "--:--"
        
        # Thumbnail
        v_thumb = None
        thumbs = entry.get("thumbnails") or []
        if thumbs:
            v_thumb = thumbs[-1].get("url")
        if not v_thumb and v_id:
            v_thumb = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"

        playlist_items.append(PlaylistItem(
            index=item_idx,
            video_id=v_id,
            title=v_title,
            duration=v_dur,
            duration_str=v_dur_str,
            url=v_url,
            thumbnail_url=v_thumb,
            uploader=entry.get("uploader") or uploader,
            is_selected=True
        ))
        item_idx += 1

    p_thumb = info.get("thumbnail")
    if not p_thumb and playlist_items:
        p_thumb = playlist_items[0].thumbnail_url

    qualities = [
        VideoQualityOption(label="🌟 Máxima Resolução (Melhor Qualidade)", height=None, format_id="bestvideo+bestaudio/best"),
        VideoQualityOption(label="2160p (4K UHD)", height=2160, format_id="bestvideo[height<=2160]+bestaudio/best[height<=2160]"),
        VideoQualityOption(label="1440p (2K QHD)", height=1440, format_id="bestvideo[height<=1440]+bestaudio/best[height<=1440]"),
        VideoQualityOption(label="1080p (FHD)", height=1080, format_id="bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
        VideoQualityOption(label="720p (HD)", height=720, format_id="bestvideo[height<=720]+bestaudio/best[height<=720]"),
        VideoQualityOption(label="480p", height=480, format_id="bestvideo[height<=480]+bestaudio/best[height<=480]"),
        VideoQualityOption(label="360p", height=360, format_id="bestvideo[height<=360]+bestaudio/best[height<=360]"),
    ]

    elapsed = time.time() - start_t
    log_info(f"Playlist extraida em {elapsed:.2f}s: {title} ({len(playlist_items)} itens)")

    return MediaMetadata(
        url=url,
        title=title,
        uploader=uploader,
        duration=total_duration,
        duration_str=f"{len(playlist_items)} vídeos",
        thumbnail_url=p_thumb,
        qualities=qualities,
        media_type="playlist",
        is_playlist=True,
        playlist_items=playlist_items,
        playlist_count=len(playlist_items),
        raw_info=info
    )

def extract_media_info(url: str) -> MediaMetadata:
    """Extrai metadados completos de forma otimizada para máxima velocidade."""
    start_t = time.time()
    log_info(f"Iniciando analise de URL: {url}")
    clear_thumbnail_cache()

    # 1. Rota otimizada para Twitter / X via Syndication API
    is_twitter = bool(re.search(r'(?:twitter\.com|x\.com)', url, re.IGNORECASE))
    if is_twitter:
        tweet_id = extract_tweet_id(url)
        if tweet_id:
            tweet_data = fetch_twitter_syndication(tweet_id)
            if tweet_data:
                user_info = tweet_data.get("user", {})
                author_name = user_info.get("name", "Usuário do X")
                screen_name = user_info.get("screen_name", "")
                author_str = f"{author_name} (@{screen_name})" if screen_name else author_name
                tweet_text = tweet_data.get("text", "Post do X").replace("\n", " ")
                clean_title = (tweet_text[:85] + "...") if len(tweet_text) > 85 else tweet_text

                media_details = tweet_data.get("mediaDetails", [])
                photos = tweet_data.get("photos", [])

                # 1.1 Fotos / Imagens
                if photos or (media_details and media_details[0].get("type") == "photo"):
                    img_urls = []
                    p_info = (photos or media_details)[0]
                    w = p_info.get("original_info", {}).get("width") or p_info.get("width")
                    h = p_info.get("original_info", {}).get("height") or p_info.get("height")
                    dim_tag = f" ({w}x{h})" if w and h else " (Alta Resolução)"

                    for p in (photos or media_details):
                        p_url = p.get("url") or p.get("media_url_https")
                        if p_url:
                            img_urls.append(p_url)

                    main_img = img_urls[0] if img_urls else None
                    qualities = [
                        VideoQualityOption(
                            label=f"🖼️ Imagem Original{dim_tag}",
                            height=h,
                            format_id="photo_orig"
                        )
                    ]

                    elapsed = time.time() - start_t
                    log_info(f"Twitter Foto extraida em {elapsed:.2f}s: {clean_title}")
                    return MediaMetadata(
                        url=url,
                        title=clean_title,
                        uploader=author_str,
                        duration=0,
                        duration_str="Foto / Imagem",
                        thumbnail_url=main_img,
                        qualities=qualities,
                        media_type="image",
                        image_urls=img_urls,
                        raw_info=tweet_data
                    )

                # 1.2 GIFs Animados
                is_animated_gif = any(m.get("type") == "animated_gif" for m in media_details)
                if is_animated_gif:
                    gif_video_url = None
                    thumb_url = None
                    for m in media_details:
                        if m.get("type") == "animated_gif":
                            thumb_url = m.get("media_url_https")
                            variants = m.get("video_info", {}).get("variants", [])
                            for v in sorted(variants, key=lambda x: x.get("bitrate", 0), reverse=True):
                                if v.get("content_type") == "video/mp4":
                                    gif_video_url = v.get("url")
                                    break

                    qualities = [
                        VideoQualityOption(label="🎞️ Salvar como Animação (.GIF)", height=None, format_id="gif_convert"),
                        VideoQualityOption(label="🎬 Salvar como Vídeo (.MP4)", height=None, format_id="gif_mp4"),
                    ]

                    elapsed = time.time() - start_t
                    log_info(f"Twitter GIF extraido em {elapsed:.2f}s: {clean_title}")
                    return MediaMetadata(
                        url=url,
                        title=f"[GIF] {clean_title}",
                        uploader=author_str,
                        duration=0,
                        duration_str="Animação GIF",
                        thumbnail_url=thumb_url,
                        qualities=qualities,
                        media_type="gif",
                        video_stream_url=gif_video_url,
                        raw_info=tweet_data
                    )

                # 1.3 Vídeo do Twitter via Syndication (SUPER RÁPIDO, < 1s)
                has_video = any(m.get("type") == "video" for m in media_details)
                if has_video:
                    v_thumb = None
                    v_variants = []
                    v_duration_ms = 0
                    for m in media_details:
                        if m.get("type") == "video":
                            v_thumb = m.get("media_url_https")
                            v_info = m.get("video_info", {})
                            v_duration_ms = v_info.get("duration_millis") or 0
                            for var in v_info.get("variants", []):
                                if var.get("content_type") == "video/mp4":
                                    v_variants.append(var)

                    v_variants.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
                    duration_sec = int(v_duration_ms / 1000) if v_duration_ms else None
                    dur_str = format_duration(duration_sec) if duration_sec else "--:--"

                    qualities = [
                        VideoQualityOption(label="🌟 Máxima Resolução (HD)", height=None, format_id="bestvideo+bestaudio/best")
                    ]
                    for var in v_variants:
                        # Extrai a resolução da url se presente (ex: /vid/avc1/720x1280/...)
                        res_match = re.search(r'/vid/(?:[a-zA-Z0-9]+/)?(\d+)x(\d+)/', var.get("url", ""))
                        if res_match:
                            h = int(res_match.group(2))
                            qualities.append(VideoQualityOption(
                                label=f"{h}p (HD)" if h >= 720 else f"{h}p",
                                height=h,
                                format_id=f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                            ))

                    elapsed = time.time() - start_t
                    log_info(f"Twitter Video syndication extraido em {elapsed:.2f}s: {clean_title}")
                    return MediaMetadata(
                        url=url,
                        title=clean_title,
                        uploader=author_str,
                        duration=duration_sec,
                        duration_str=dur_str,
                        thumbnail_url=v_thumb,
                        qualities=qualities,
                        media_type="video",
                        video_stream_url=v_variants[0].get("url") if v_variants else None,
                        raw_info=tweet_data
                    )

    # 2. Rota otimizada para Instagram (Fotos e Vídeos/Reels)
    is_instagram = bool(re.search(r'instagram\.com', url, re.IGNORECASE))
    if is_instagram:
        insta_meta = fetch_instagram_media(url)
        if insta_meta:
            elapsed = time.time() - start_t
            log_info(f"Instagram extraido com sucesso em {elapsed:.2f}s: {insta_meta.title}")
            return insta_meta

    # 3. Extração via yt-dlp para YouTube (incluindo Playlists) e fallback geral
    is_playlist = is_playlist_url(url)
    ydl_opts = {
        'extract_flat': 'in_playlist' if is_playlist else False,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True if is_playlist else False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return MediaMetadata(
                    url=url,
                    title="Não encontrado",
                    uploader="Desconhecido",
                    duration=0,
                    duration_str="--:--",
                    thumbnail_url=None,
                    error="Não foi possível obter dados para este link."
                )

            # Caso detecte que o retorno é uma playlist de múltiplos vídeos
            if info.get("_type") == "playlist" or ("entries" in info and len(list(info.get("entries") or [])) > 0):
                return _process_playlist_info(url, info, start_t)

            title = info.get("title") or "Sem título"
            uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "Autor Desconhecido"
            duration = info.get("duration")
            duration_str = format_duration(duration) if duration else "Ao vivo / N/A"
            thumbnail_url = info.get("thumbnail")

            formats = info.get("formats", [])
            best_audio_format = None
            for f in formats:
                if f.get("vcodec") == "none" and f.get("acodec") != "none":
                    fsize = f.get("filesize") or f.get("filesize_approx") or 0
                    if not best_audio_format or fsize > (best_audio_format.get("filesize") or 0):
                        best_audio_format = f

            best_audio_bytes = 0
            if best_audio_format:
                best_audio_bytes = best_audio_format.get("filesize") or best_audio_format.get("filesize_approx") or 0
            elif duration:
                best_audio_bytes = int(duration * 40 * 1024)

            height_data: Dict[int, Dict] = {}
            for f in formats:
                h = f.get("height")
                vcodec = f.get("vcodec", "none")
                if h and vcodec != "none" and h >= 144:
                    vsize = f.get("filesize") or f.get("filesize_approx") or 0
                    total_size = (vsize + best_audio_bytes) if vsize > 0 else 0
                    if h not in height_data or total_size > height_data[h]["size"]:
                        height_data[h] = {
                            "size": total_size,
                            "format_id": f.get("format_id")
                        }

            sorted_heights = sorted(list(height_data.keys()), reverse=True)
            qualities: List[VideoQualityOption] = []

            max_size = height_data[sorted_heights[0]]["size"] if sorted_heights else 0
            max_size_tag = f" ~ {format_bytes(max_size)}" if max_size > 0 else ""
            qualities.append(VideoQualityOption(
                label=f"🌟 Máxima Resolução{max_size_tag}",
                height=None,
                format_id="bestvideo+bestaudio/best",
                filesize_bytes=max_size
            ))

            for h in sorted_heights:
                tag = ""
                if h >= 2160:
                    tag = " (4K UHD)"
                elif h >= 1440:
                    tag = " (2K QHD)"
                elif h >= 1080:
                    tag = " (FHD)"
                elif h >= 720:
                    tag = " (HD)"

                h_size = height_data[h]["size"]
                h_size_tag = f" ~ {format_bytes(h_size)}" if h_size > 0 else ""

                qualities.append(VideoQualityOption(
                    label=f"{h}p{tag}{h_size_tag}",
                    height=h,
                    format_id=f"bestvideo[height<={h}]+bestaudio/best[height<={h}]",
                    filesize_bytes=h_size
                ))

            is_gif = info.get("is_gif") or (info.get("extractor_key") == "Twitter" and not best_audio_format and duration and duration <= 15)
            media_type = "gif" if is_gif else "video"

            if is_gif:
                qualities.insert(0, VideoQualityOption(
                    label="🎞️ Salvar como Animação (.GIF)",
                    height=None,
                    format_id="gif_convert"
                ))

            elapsed = time.time() - start_t
            log_info(f"yt-dlp extraido em {elapsed:.2f}s: {title}")
            return MediaMetadata(
                url=url,
                title=title,
                uploader=uploader,
                duration=duration,
                duration_str=duration_str,
                thumbnail_url=thumbnail_url,
                qualities=qualities,
                media_type=media_type,
                video_stream_url=info.get("url"),
                estimated_audio_size=best_audio_bytes,
                raw_info=info
            )

    except Exception as e:
        err_msg = str(e)
        log_error(f"Erro ao extrair via yt-dlp: {err_msg}")

        # Se falhou no yt-dlp e for Instagram, tenta a rota direta caso ainda não tenha rodado
        if is_instagram:
            try:
                insta_fallback = fetch_instagram_media(url)
                if insta_fallback:
                    return insta_fallback
            except Exception:
                pass

        friendly_err = f"Erro ao obter informações: {err_msg[:100]}"
        return MediaMetadata(
            url=url,
            title="Erro ao carregar",
            uploader="",
            duration=0,
            duration_str="",
            thumbnail_url=None,
            error=friendly_err
        )

def download_thumbnail_image(thumbnail_url: str, output_path: str) -> bool:
    """Baixa imagem em alta resolução com headers completos e fallback SSL/TLS."""
    # 1. Tenta curl_cffi para contornar proteções de CDN (Instagram/Meta)
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(thumbnail_url, impersonate="chrome", timeout=8, verify=False)
        if resp.status_code == 200 and len(resp.content) > 0:
            with open(output_path, "wb") as out_file:
                out_file.write(resp.content)
            return True
    except Exception:
        pass

    # 2. Fallback urllib padrão
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        }
        req = urllib.request.Request(thumbnail_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6, context=get_ssl_context()) as response:
            with open(output_path, 'wb') as out_file:
                out_file.write(response.read())
        return True
    except Exception as e:
        log_error(f"Falha ao salvar thumbnail: {e}")
        return False
