"""示例 06: 下载单条推文内的媒体。

教学目标:
    教 download_tweet, 演示如何下载单条推文里所有媒体 (图片 / 动图 / 视频)。

SDK 入口:
    twitter_sdk.MediaClient.download_tweet(url) -> int (成功下载数)

参数说明:
    - url            推文链接 或 数字 ID
    - save_path      保存目录, 默认 {save_path}/tweet/{tweet_id}
    - image_format   jpg / png / orig; 默认取 config.toml 的 image_format
    - videos         是否下载视频 (动图始终下载并转成 gif)
    - concurrency    同时进行的下载数量, 默认 8

注意 (与 download_user_media 的重要差别):
    download_tweet 单条推文**不写入去重缓存** (cache_data.log),
    避免污染用户目录的断点续传记录; 重跑示例会重新下载。
    如果要跳过已下载, 用示例 08 的 DownloadCache 自己包一层。

注意 (文件命名):
    单条推文的命名规则: {time_str}-{img/gif/vid}_{tweet_id}_{index}.{suffix}
    - 时间格式 "2026-09-30 12-00" (来自 MediaItem.time_str)
    - 类型前缀 -img / -gif / -vid (由 MediaItem.media_type 决定)
    - {tweet_id} 用于去重不同推文里的同序号媒体
    - 后缀: video 是 mp4, gif 是 gif (原 mp4 自动转), 原图走 image_format
    转推内容会加 -retweet 后缀

返回值:
    成功下载的文件数。

预期输出 (成功运行):
    2026-09-30 12-00-img_1234567890_1.jpg 下载完成
    done, 下载 1 个, 共请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/06.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")

# 改成你的推文链接或数字 ID
TWEET_URL = "https://x.com/Aurorallast/status/1234567890"


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # ===== 2. 调用: 下载单条推文的媒体 =====
        # save_path 不传时默认落到 {save_path}/tweet/{tweet_id}/
        # image_format="jpg" 强制转 jpg, 想要原图就传 "orig"
        # videos=True 时视频也下载, 视频始终保持 mp4 后缀
        count = await client.download_tweet(
            url=TWEET_URL,                 # 链接或数字 ID 都行
            image_format="jpg",            # jpg / png / orig, 默认取配置
            videos=True,                    # 视频 / 动图都下; 动图始终下并转成 gif
            # concurrency=8 默认值, 这里省略
        )

        # ===== 3. 处理结果 =====
        if count == 0:
            print("这条推文不含媒体 (纯文本)")
        else:
            print(f"下载成功: {count} 个")

        # ===== 4. 清理 =====
        print(f"done, 下载 {count} 个, 共请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())