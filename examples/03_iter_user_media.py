"""示例 03: 流式遍历某用户的媒体 (不下载, 自己处理)。

教学目标:
    教 SDK 的 async 迭代接口 iter_user_media, 演示 MediaItem 的字段含义与
    "只产出含媒体推文"的过滤语义。

SDK 入口:
    twitter_sdk.MediaClient.iter_user_media(...) -> AsyncIterator[MediaItem]

参数说明:
    - screen_name    用户名 (@ 后字符)
    - time_range     "1990-01-01:2030-01-01" 或 None
    - videos         False (默认) 只产图片与动图; True 时视频也产出

返回值 MediaItem 字段含义:
    - media_url           直链 (图片 / 动图 / 视频)。download_file 直接用这个地址
    - media_type          'photo' / 'gif' / 'video'
    - expanded_url        媒体页链接 (例如 https://twitter.com/xxx/photo/1)
    - tweet_msecs         推文发布时间, 毫秒时间戳
    - full_text           推文正文
    - favorite_count      点赞数
    - retweet_count       转推数
    - reply_count         回复数
    - is_retweet          是否为转推内容 (此时 author_* 为原作者)
    - time_str (property) 形如 "2026-09-30 12-00", 文件名前缀

注意 (与 iter_user_tweets 的差别):
    iter_user_media 仅在推文"含媒体"时产出 MediaItem, 纯文字推文会被服务端过滤掉;
    如果想拿纯文本, 用示例 04 的 iter_user_tweets。

注意 (vs download_user_media):
    iter_user_media 只负责"取数据", 文件落盘 / 动图转 gif / 并发 / 缓存都跳过。
    适合需要自定义处理 (例如写入数据库 / 转推打标 / 自定义重命名) 的场景。

预期输出 (成功运行):
    [2026-09-30 12-00] photo  https://pbs.twimg.com/media/xxx.jpg
    [2026-09-30 11-30] gif    https://video.twimg.com/xxx.mp4
    ...
    done, 共遍历 5 条, 请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/03.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # ===== 2. 调用: 异步流式遍历 =====
        # 关键写法: async for 直接消费, 不需要预先建 list 再统一处理
        # 这里限制只取前 5 条作演示, 实际使用直接 for 即可
        count = 0
        async for item in client.iter_user_media("Aurorallast", videos=False):
            count += 1
            if count > 5:
                break  # 演示用, 只看 5 条

            # ===== 3. 处理结果: 每条 MediaItem 打印一行摘要 =====
            # media_type / media_url / time_str 都在 MediaItem 上, 见上面字段说明
            print(
                f"[{item.time_str}] "
                f"{item.media_type:<6}  "  # 左对齐填充, 排版对齐
                f"{item.media_url}")

            # 提示: 如果要下载这条, 直接拿 media_url 即可, 或者用示例 06 的 download_tweet

        # ===== 4. 清理 =====
        print(f"done, 共遍历 {count} 条, 请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())