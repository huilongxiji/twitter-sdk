"""示例 04: 流式遍历某用户的全部推文 (含纯文本, 与示例 03 互补)。

教学目标:
    教 SDK 的 iter_user_tweets, 演示 TweetItem 字段含义, 并演示 retweets=False
    vs retweets=True 的切换, 看是否包含转推。

SDK 入口:
    twitter_sdk.MediaClient.iter_user_tweets(...) -> AsyncIterator[TweetItem]

参数说明:
    - screen_name    用户名 (@ 后字符)
    - time_range     "1990-01-01:2030-01-01" 或 None
    - retweets       False (默认) 不含转推; True 时切换到含转推的 UserTweets 接口
    - like           True 时改抓该用户的点赞页 (与 retweets 互斥)
    - videos         False 时 video 类型媒体不产出 (动图始终产出)

返回值 TweetItem 字段含义:
    - tweet_id              推文数字 ID, 拼 URL 用
    - url                   推文链接 (https://twitter.com/xxx/status/...)
    - author_name           作者昵称 (转推模式下为原作者)
    - author_screen_name    作者用户名 (转推模式下为原作者)
    - tweet_msecs           推文发布时间, 毫秒时间戳
    - full_text             推文正文
    - favorite_count        点赞数
    - retweet_count         转推数
    - reply_count           回复数
    - is_retweet            是否为转推内容
    - media                 推文内的 MediaItem 列表, 纯文本推文为空 []
    - is_quote              是否引用了其他推文
    - quoted_url            被引用推文的链接 (is_quote=True 时才有值)
    - has_media (property)  是否含媒体

注意 (与 iter_user_media 的差别):
    iter_user_tweets 对每条推文都产出 (含纯文本), 与 iter_user_media 互补;
    iter_user_media 只产出含媒体的推文, 纯文本会被服务端过滤掉。

注意 (转推模式下):
    author_name / author_screen_name 会变成原作者, 而不是发起转推的用户;
    is_retweet=True, media 是被转推内容的媒体 (壳推文自己通常没媒体)。

预期输出 (成功运行):
    不含转推段
        [含媒体] [Aurorallast 2026-09-30 12:00] 1234567890  '...'
        [纯文本] [Aurorallast 2026-09-30 11:00] 1234567891  '...'
    注意: 切到含转推模式
    含转推段
        (原创) [Aurorallast ...]  ...  '...'
        (转推) [OriginalUser ...]  ...  '...'
    done, 共遍历 10 条, 请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/04.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")


async def show(client, retweets: bool, limit: int = 5) -> int:
    """取前 limit 条打印摘要, 返回实际遍历数。"""
    shown = 0
    async for tweet in client.iter_user_tweets("Aurorallast", retweets=retweets):
        shown += 1
        if shown > limit:
            break
        # has_media 区分纯文本与带媒体推文; is_quote 另起一行打印被引用 URL
        mark = "[含媒体]" if tweet.has_media else "[纯文本]"
        tag = "(转推)" if tweet.is_retweet else "(原创)"
        print(f"{mark} {tag} [{tweet.author_screen_name} {tweet.time_str}] "
              f"{tweet.tweet_id}  {tweet.full_text[:50]!r}")
        if tweet.is_quote and tweet.quoted_url:
            print(f"    引用 -> {tweet.quoted_url}")
    return shown


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # ===== 2. 第一段: retweets=False (默认), 不含转推 =====
        print("不含转推段")
        n1 = await show(client, retweets=False)

        # ===== 3. 第二段: 注意: 切到含转推模式 =====
        # 转推模式下 author_* 是原作者, is_retweet=True; 接口从 UserMedia 切到 UserTweets
        print("\n注意: 切到含转推模式\n含转推段")
        n2 = await show(client, retweets=True)

        # ===== 4. 清理 =====
        # request_count 是 SDK 计数器, 每次 get_json 自增; 不受 retweets 参数影响
        print(f"done, 共遍历 {n1 + n2} 条, 请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())