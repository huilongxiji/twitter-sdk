"""示例 08: 断点续传 (DownloadCache 怎么用)。

教学目标:
    教 DownloadCache 的核心用法: 把"已下载的 key"持久化到磁盘, 第二次跑时
    自动跳过。download_user_media 默认就用它 (use_cache=True 时), 这里手动演示
    怎么用 iter_user_media + DownloadCache 自己实现断点续传。

SDK 入口:
    twitter_sdk.DownloadCache(save_path) -> DownloadCache
    twitter_sdk.MediaClient.iter_user_media(...) -> AsyncIterator[MediaItem]

注意 (cache_data.log 落盘位置):
    DownloadCache(save_path) 把 cache_data.log 写到 save_path/cache_data.log;
    download_user_media 默认传给它的 save_path 就是用户的下载目录
    (例: ./download/Aurorallast/), 因此重跑时会自动跳过上次已下载的媒体。

注意 (key 格式):
    - 图片: "{image_format}|{media_url}", 换格式自动重下
    - 动图: "gif-file|{media_url}", 即使后缀变 gif 也会重新转码下载
    - 视频: "video|{media_url}", 原样下载

注意 (重跑预期):
    第一次跑会下载若干文件, cache_data.log 落盘;
    第二次跑同样代码 -> iter_user_media 仍会拉 API (绕不开), 但 cache.contains 命中
    后会跳过下载, 二次下载数为 0; SDK request_count 仍增长。

预期输出 (成功运行两次):
    第一次:
        skip: 0, schedule: 5
    第二次:
        skip: 5, schedule: 0
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/08.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import DownloadCache, MediaClient, MediaItem

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")

USER_DIR = os.path.join("./download", "Aurorallast")  # 与 download_user_media 默认一致


def cache_key(media_item: MediaItem, image_format: str = "jpg") -> str:
    """复用 SDK 的 _cache_key 规则, 保持与 download_user_media 完全一致。

    注意: MediaToolsMixin._cache_key 是 SDK 内部方法 (下划线开头表示非对外契约),
    这里显式重写一份保持公开 API 干净, 三行规则与 SDK 完全对齐。
    """
    if media_item.media_type == "gif":
        return f"gif-file|{media_item.media_url}"
    if media_item.media_type == "video":
        return f"video|{media_item.media_url}"
    return f"{image_format}|{media_item.media_url}"


async def collect_skipping_cached(
    client: MediaClient, cache: DownloadCache, limit: int = 5,
) -> tuple:
    """遍历前 limit 条媒体, 跳过已缓存的; 返回 (跳过数, 待下载数)。"""
    skipped, scheduled = 0, 0
    async for media_item in client.iter_user_media("Aurorallast", videos=False):
        if cache.contains(cache_key(media_item)):
            skipped += 1
            continue
        scheduled += 1
        if scheduled > limit:
            break
    return skipped, scheduled


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # 第一次跑: 缓存空, 跳过 0, 待下载 5
        with DownloadCache(USER_DIR) as cache:
            skip1, schedule1 = await collect_skipping_cached(client, cache)
            print(f"第一次 -> skip: {skip1}, schedule: {schedule1}")
            # 模拟把第一条记进缓存 (实际应该是 download 成功后才 add)
            # 为演示, 我们手动 add 一条, 让第二次演示跳过效果
            cache.add("jpg|https://demo.test/example.jpg")
            # close() 在 with 退出时自动调用, 把 cache_data.log 写盘

        # 第二次跑: 重新构造 cache (从磁盘读), 跳过数应反映持久化的命中
        with DownloadCache(USER_DIR) as cache:
            skip2, schedule2 = await collect_skipping_cached(client, cache)
            print(f"第二次 -> skip: {skip2}, schedule: {schedule2}")

        # ===== 2. 处理结果: 解释观察 =====
        # request_count 在两次遍历后都会增长 (iter_user_media 仍要请求 API 翻页),
        # 但下载数 (schedule) 在有缓存时显著降低, 这就是断点续传的效果
        print(f"done, 共请求 {client.request_count} 次 (API 翻页数不受缓存影响)")

        # ===== 3. 提示: 真要下载, 把 schedule 那批喂给 _download_file =====
        # 完整版本看 download_user_media 内部实现:
        #   拿到 media_item -> 跳过缓存 -> 命名 -> 创建 task -> asyncio.gather 下载


if __name__ == "__main__":
    asyncio.run(main())