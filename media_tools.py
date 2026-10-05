"""MediaToolsMixin —— 媒体判定 / 命名 / 下载的共用实现。

抽成独立 mixin 的原因:
- TweetClient 需要 _make_media_item (给推文填充媒体) 与 _download_file /
  _type_prefix / _resolve_suffix (下载单条推文的媒体)
- MediaClient 需要同样这些方法
若两者互相 import 会形成循环依赖, 故把共用部分下沉到本模块。

继承关系: MediaToolsMixin -> 被 TweetClient 混入 -> MediaClient 继承 TweetClient
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from .client import VALID_SUFFIX
from .exceptions import FetchError
from .models import MediaItem


class MediaToolsMixin:
    """媒体判定 / 命名 / 下载的共用实现。"""

    @staticmethod
    def _make_media_item(media: dict, tweet_msecs: int, full_text: str, frr: list,
                         videos: bool, is_retweet: bool,
                         author_name: str, author_screen_name: str) -> Optional[MediaItem]:
        """将单条 media 数据转换为 MediaItem; 不符合条件返回 None。

        图片与动图默认产出 (动图取 video_info 里的 mp4, 再转成 gif);
        视频仅 videos=True 时产出。
        """
        media_type = media.get("type")
        if media_type == "photo" and "media_url_https" in media:
            url, item_type = media["media_url_https"], "photo"
        elif media_type == "animated_gif":
            # media_url_https 只是 jpg 预览; 会动的是 variants 里那条 mp4
            if "video_info" in media:
                url = MediaToolsMixin._get_highest_video_quality(
                    media["video_info"].get("variants", []))
                if not url:
                    return None
            elif "media_url_https" in media:
                url = media["media_url_https"]
            else:
                return None
            item_type = "gif"
        elif videos and media_type == "video" and "video_info" in media:
            url = MediaToolsMixin._get_highest_video_quality(
                media["video_info"].get("variants", []))
            if not url:
                return None
            item_type = "video"
        else:
            return None
        return MediaItem(
            media_url=url,
            media_type=item_type,
            expanded_url=media.get("expanded_url", ""),
            tweet_msecs=tweet_msecs,
            full_text=full_text,
            favorite_count=frr[0],
            retweet_count=frr[1],
            reply_count=frr[2],
            is_retweet=is_retweet,
            author_name=author_name,
            author_screen_name=author_screen_name,
        )

    @staticmethod
    def _get_highest_video_quality(variants: list) -> Optional[str]:
        """选最高码率; 只有一个 variant 时直接返回。"""
        if len(variants) == 1:
            return variants[0].get("url")
        max_bitrate = 0
        highest_url = None
        for v in variants:
            if "bitrate" in v:
                bitrate = int(v["bitrate"])
                if bitrate > max_bitrate:
                    max_bitrate = bitrate
                    highest_url = v["url"]
        return highest_url

    # ---- 命名规则 ----

    @staticmethod
    def _type_prefix(media_type: str) -> str:
        return {"photo": "-img", "gif": "-gif", "video": "-vid"}[media_type]

    @staticmethod
    def _resolve_suffix(image_format: str, media_item: MediaItem) -> str:
        if media_item.media_type == "video":
            return "mp4"
        if media_item.media_type == "gif":
            return "gif"  # 原片是 mp4, 下载后转成 gif
        if image_format == "orig":
            suffix = media_item.media_url.rsplit(".", 1)[-1].split("?")[0].lower()
            return suffix if suffix in VALID_SUFFIX else "jpg"
        return image_format  # jpg / png

    @staticmethod
    def _cache_key(media_item: MediaItem, image_format: str) -> str:
        """去重缓存 key: 图片带格式维度 (换格式自动重下); 动图/视频固定前缀。"""
        if media_item.media_type == "gif":
            return f"gif-file|{media_item.media_url}"  # 单独命名空间, 永远会重新转码
        if media_item.media_type == "video":
            return f"video|{media_item.media_url}"
        return f"{image_format}|{media_item.media_url}"

    # ---- 动图转 gif ----

    @staticmethod
    def _ffmpeg_exe() -> str:
        """优先系统 ffmpeg, 否则用 imageio-ffmpeg 自带二进制。"""
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise FetchError("把动图转成 gif 需要 ffmpeg 或 imageio-ffmpeg") from exc

    @staticmethod
    def _mp4_to_gif(mp4_bytes: bytes) -> bytes:
        """动图原片 (mp4) -> 循环播放的 gif 图片。"""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.mp4")
            dst = os.path.join(tmp, "out.gif")
            with open(src, "wb") as f:
                f.write(mp4_bytes)
            cmd = [
                MediaToolsMixin._ffmpeg_exe(), "-y", "-i", src,
                "-filter_complex",
                "[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
                "-loop", "0", dst,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if proc.returncode != 0 or not os.path.exists(dst):
                raise FetchError("动图转 gif 失败")
            with open(dst, "rb") as f:
                gif_bytes = f.read()
        if not gif_bytes.startswith(b"GIF"):
            raise FetchError("动图转 gif 失败")
        return gif_bytes

    # ---- 下载 ----

    async def _download_file(
        self, media_item: MediaItem, file_path: str,
        image_format: str, semaphore: asyncio.Semaphore,
    ) -> bool:
        """下载单个文件: 图片按 4K 最高规格, 动图转 gif, 视频原样, 带 404 回退与重试。

        依赖基类提供的 self._session / self.quote_url / self.download_count /
        self.config.log_output。
        """
        if media_item.media_type == "video" or media_item.media_type == "gif":
            download_url = media_item.media_url  # 原样下载, 不加格式参数
        elif image_format == "orig":
            download_url = media_item.media_url + "?name=orig"
        else:
            download_url = media_item.media_url + f"?format={image_format}&name=4096x4096"

        fallback_used = False
        attempt = 0
        while True:
            try:
                async with semaphore:
                    response = await self._session.get(
                        self.quote_url(download_url), timeout=(3.05, 16))
                if response.status_code == 404:
                    # 高分辨率尺寸不可用 -> 回退原图 (仅普通图片)
                    if (not fallback_used and media_item.media_type == "photo"
                            and image_format != "orig"):
                        fallback_used = True
                        download_url = media_item.media_url + "?name=orig"
                        attempt = 0
                        continue
                    raise FetchError("404")
                if response.status_code != 200:
                    raise FetchError(f"HTTP {response.status_code}")
                payload = response.content
                if media_item.media_type == "gif" and not payload.startswith(b"GIF"):
                    try:
                        payload = await asyncio.to_thread(self._mp4_to_gif, payload)
                    except Exception:
                        print(f"{os.path.basename(file_path)} 转成 gif 失败, 已跳过")
                        return False
                with open(file_path, "wb") as f:
                    f.write(payload)
                self.download_count += 1
                if self.config.log_output:
                    print(f"{os.path.basename(file_path)} 下载完成")
                return True
            except Exception:
                attempt += 1
                if attempt >= 10:
                    print(f"{os.path.basename(file_path)} 下载失败, 已跳过")
                    return False
                await asyncio.sleep(0.5)