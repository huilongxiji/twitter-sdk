"""示例 05: 根据分享链接抓单条推文。

教学目标:
    教 fetch_tweet_by_url, 演示 SDK 支持的三种推文链接形态; 也演示
    如果只有数字 ID, 用 get_tweet_by_id。

SDK 入口:
    twitter_sdk.MediaClient.fetch_tweet_by_url(url)        -> TweetItem
    twitter_sdk.MediaClient.get_tweet_by_id(tweet_id)       -> TweetItem
    twitter_sdk.utils.parse_tweet_id(url)                   -> Optional[str]

支持的链接形态 (parse_tweet_id 内部正则兼容以下三种):
    1. https://twitter.com/xxx/status/1234567890
    2. https://x.com/xxx/status/1234567890?s=20&t=abcdef
    3. https://twitter.com/i/web/status/1234567890

注意:
    - fetch_tweet_by_url / get_tweet_by_id 走 TweetDetail 接口, 需要 transaction
      校验头, 内部会触发 TransactionGenerator 懒构建。
    - parse_tweet_id 是 SDK 暴露的纯函数, 返回推文数字 ID 或 None,
      适合先验证链接合法再用 fetch_tweet_by_url。

注意 (与示例 06 的区别):
    本例只"看"推文 (返回 TweetItem), 不下载任何媒体; 要下载媒体看示例 06。

预期输出 (成功运行):
    链接解析成功 -> tweet_id: 1234567890
    作者: Aurorallast
    时间: 2026-09-30 12:00
    正文: '今日份的 ...'
    媒体数: 1
    done, 请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/05.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient, parse_tweet_id

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")

# 演示用链接, 改成你自己的推文即可
TWEET_URL = "https://x.com/Aurorallast/status/1234567890"


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:

        # ===== 2. 链接预处理: 先用 parse_tweet_id 拿 ID (不发起网络请求) =====
        # parse_tweet_id 是同步函数, 只会做正则提取; 如果返回 None, 说明链接不合法,
        # 此时再调 fetch_tweet_by_url 会抛 ValueError
        tweet_id = parse_tweet_id(TWEET_URL)
        if tweet_id is None:
            raise ValueError(f"不是合法的推文链接: {TWEET_URL}")
        print(f"链接解析成功 -> tweet_id: {tweet_id}")

        # ===== 3. 调用: fetch_tweet_by_url 拿完整 TweetItem =====
        # 内部调用 parse_tweet_id 再 get_tweet_by_id; 走 TweetDetail 接口,
        # 触发 TransactionGenerator 懒构建 (首次会下载 X 登录态首页)
        tweet = await client.fetch_tweet_by_url(TWEET_URL)

        # ===== 4. 处理结果: 打印关键字段 =====
        # 作者 (is_retweet=True 时 author_* 是原作者)
        print(f"作者: {tweet.author_screen_name} ({tweet.author_name})")
        # 时间 (time_str 是 SDK 内置格式, 用于文件名前缀)
        print(f"时间: {tweet.time_str}")
        # 正文 (前 60 字避免太长)
        print(f"正文: {tweet.full_text[:60]!r}")
        # 媒体数 (has_media 是 property, True 时 media 列表非空)
        print(f"媒体数: {len(tweet.media)}")
        # 互动数据
        print(f"点赞 {tweet.favorite_count} / 转推 {tweet.retweet_count} / "
              f"回复 {tweet.reply_count}")

        # ===== 5. 提示: 只看纯 ID 用法 =====
        # 如果手上只有数字 ID 没有链接, 用 get_tweet_by_id (走同样的接口)
        # tweet2 = await client.get_tweet_by_id("1234567890")

        # ===== 6. 清理 =====
        print(f"done, 请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())