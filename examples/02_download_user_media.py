"""示例 02: 一键下载某用户的全部媒体 (含参数详解与自动补档)。

教学目标:
    教 SDK 最核心的下载能力 download_user_media, 演示它如何组合 5 个常用参数
    完成"拉到 UserMedia 接口深度上限 -> 自动衔接 SearchTimeline 补更老内容"。

SDK 入口:
    twitter_sdk.MediaClient.download_user_media(...) -> int (成功下载数)

参数详解:
    - screen_name    用户名 (@ 后字符), 这里固定 Aurorallast 方便排错
    - concurrency    同时进行的下载数量, 默认 8, 这里降到 4 以免对单用户 IP 触发风控
    - max_download   本次最多下载多少个文件, None 不限, 这里限制 10 方便快速演示
    - videos         是否下载视频 (动图始终下载并转成 gif), 这里 True
    - retweets       是否下载该用户转推的媒体, False 只下原创
    - md_output      是否额外输出 Markdown 推文记录 (会写到 save_path 下)
    - time_range     时间范围, None 时取 config.toml 默认值
    - auto_complete  默认模式拉到接口深度上限后是否自动衔接搜索接口补更老内容

注意 (自动补档的内部流程):
    download_user_media 默认分两段:
    (1) 走 UserMedia 接口抓近期媒体 (速度快, 单页多)
    (2) 接口深度到顶后 (服务端限制), 自动衔接 SearchTimeline 接口用 since/until 补更老的
    默认 auto_complete=True 一次跑完即全部历史, 不需要手动加 deep=True。

返回值:
    成功下载的文件数 (去重 + 跳过 + 失败后剩余的)。这里预期 10。

预期输出 (成功运行):
    xxx-img_1.jpg 下载完成
    ...
    done, 下载 10 个, 共请求 N 次
"""

import asyncio
import os
import sys

# 推特脚本/ 目录位置: __file__ = examples/02.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    # save_path 会作为该用户的下载根目录, SDK 会在里面建 Aurorallast/ 子目录
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:
        # ===== 2. 调用: 下载 =====
        # 一行调通, SDK 内部完成: 拉 UserMedia -> 翻页 -> 动图转 gif ->
        # 接口深度到顶后自动转 SearchTimeline -> 断点续传 (cache_data.log 在子目录里)
        count = await client.download_user_media(
            screen_name="Aurorallast",  # 演示用户
            concurrency=4,              # 并发下载数, 默认 8, 演示场景降到 4 减少请求压力
            max_download=10,            # 本次只下 10 个用于快速验证, 正式跑传 None
            videos=True,                # 视频 / 动图都下载; 动图始终下载, 与 videos 无关
            retweets=False,             # 不要转推内容 (默认 False)
            md_output=True,             # 同时输出 Markdown 推文记录
            # auto_complete=True 是默认值, 这里省略; 关闭后只跑 UserMedia 一段
            # time_range=None 时用 config.toml 的 time_range 字段
        )

        # ===== 3. 处理结果: 简单打印成功数 =====
        print(f"下载成功: {count} 个")

        # ===== 4. 清理 =====
        # request_count / download_count 是 SDK 计数器, 可用来估算调用成本
        print(f"done, 下载 {count} 个, 共请求 {client.request_count} 次")


if __name__ == "__main__":
    asyncio.run(main())