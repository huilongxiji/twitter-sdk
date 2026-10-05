"""示例 07: 遍历某条推文下方的回复 (主帖 + 回复一并抓取)。

教学目标:
    教 iter_thread_replies, 演示如何拿到某条推文的回复 (主帖不含, 仅回复)。

SDK 入口:
    twitter_sdk.MediaClient.iter_thread_replies(url) -> AsyncIterator[TweetItem]

参数说明:
    - url            推文分享链接 或 数字 ID
    - videos         是否在 TweetItem.media 里产出视频

注意 (与 fetch_tweet_by_url 的差别):
    iter_thread_replies 只产出"回复", 不含主帖; 想拿主帖用示例 05 的 fetch_tweet_by_url。

注意 (接口要求):
    走 TweetDetail 接口, 需要 transaction 校验头; 内部首次调用会触发
    TransactionGenerator 懒构建 (下载 X 登录态首页 + on-demand 文件, 一次性)。

返回值:
    与 iter_user_tweets 一样的 TweetItem 流, 字段含义见示例 04 docstring。

预期输出 (成功运行):
    [userA 2026-09-30 13:00] 2222222222  '回复...'
    [userB 2026-09-30 13:05] 3333333333  '...'
    [userC 2026-09-30 13:10] 4444444444  '...'
    done, 共遍历 3 条回复, 请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/07.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")

# 改成你想看回复的推文链接或数字 ID
TWEET_URL = "https://x.com/Aurorallast/status/1234567890"


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # ===== 2. 调用: 流式遍历回复 =====
        # iter_thread_replies 支持推文链接或数字 ID (自动 parse_tweet_id)
        count = 0
        async for reply in client.iter_thread_replies(TWEET_URL):
            count += 1
            if count > 3:
                break  # 演示只取前 3 条, 实际不要这个 break 就拿全部

            # ===== 3. 处理结果: 每条回复一行 =====
            # author_screen_name / full_text / time_str 都是 TweetItem 字段
            print(
                f"[{reply.author_screen_name} {reply.time_str}] "
                f"{reply.tweet_id}  {reply.full_text[:50]!r}")

            # 提示: 想看 reply 下面还有没有二级回复, 把 reply.url 喂给
            # iter_thread_replies 自己, 可以递归遍历整条 thread

        # ===== 4. 清理 =====
        print(f"done, 共遍历 {count} 条回复, 请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())