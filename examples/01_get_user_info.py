"""示例 01: 查询用户基本信息。

教学目标:
    教如何使用 MediaClient.get_user_info (继承自 UserInfoClient) 拿一个用户的
    基础档案, 拿到 5 个关键字段 (用户名 / 数字 ID / 昵称 / 推文数 / 媒体数)。

SDK 入口:
    twitter_sdk.MediaClient.get_user_info(screen_name) -> UserInfo

参数说明:
    - screen_name: 用户的 @ 后字符串 (不带 @), 例如 "Aurorallast"。

返回值 UserInfo 字段含义:
    - screen_name    用户名 (@ 后面的字符, 例如 Aurorallast)
    - rest_id        用户的数字 ID (字符串, 例如 1585745778136739840), 用作 GraphQL 入参
    - name           用户的昵称 (例如 "Aurora"), 不带 @
    - statuses_count  总推数, 含转推
    - media_count    含图片/视频的推文数, 不含转推 (因此通常远小于 statuses_count)

注意:
    - 不传 cookie 会直接抛 AuthError; 这里改成 SystemExit, 提示用户先 export。
    - 该方法只发一次请求 (UserByScreenName 接口), 不会拉推文, 成本很低, 适合做冒烟测试。

预期输出 (成功运行 / 返回):
    screen_name        : Aurorallast
    rest_id            : 1585745778136739840
    name               : Aurora
    statuses_count     : 1234
    media_count        : 567
    done, 请求 1 次, 下载 0 个
"""

import asyncio
import os
import sys

# 把 twitter_sdk 加入 sys.path, 这样示例文件可以独立运行
# 推特脚本/ 目录位置: __file__ = examples/01.py -> 往上两层即到 twitter_sdk/ -> 再往上即推特脚本/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from twitter_sdk import MediaClient  # MediaClient 继承了 UserInfoClient 与 TweetClient

COOKIE = os.environ.get("TWITTER_COOKIE", "")
if not COOKIE:
    # 注意: 没设 cookie 直接跑会撞上 AuthError, 用更友好的 SystemExit 提示
    raise SystemExit("请先 export TWITTER_COOKIE='auth_token=...; ct0=...;'")


async def main() -> None:
    # ===== 1. 准备: 构造客户端 =====
    # MediaClient(cookie, save_path) 是 SDK 入口; save_path 给后续下载用, 本例用不到
    async with MediaClient(cookie=COOKIE, save_path="./download") as client:
        # ===== 2. 调用: 查用户信息 =====
        # get_user_info 会自动先拿 REST_ID, 再用 REST_ID 拉档案, 内部两次 HTTP
        info = await client.get_user_info("Aurorallast")

        # ===== 3. 处理结果: 逐字段打印, 每个字段的含义写在注释里 =====
        # 用户名 (@ 后面的字符, 例: Aurorallast)
        print(f"screen_name        : {info.screen_name}")
        # 数字 ID (字符串形式), GraphQL 接口都要用, 别拿 screen_name 当 ID 用
        print(f"rest_id            : {info.rest_id}")
        # 昵称 (展示名, 不带 @), 可含空格与 emoji
        print(f"name               : {info.name}")
        # 总推数, 含转推 + 纯文本; 用于预估该用户规模
        print(f"statuses_count     : {info.statuses_count}")
        # 含媒体推数, 不含转推; 因此一般远小于 statuses_count
        print(f"media_count        : {info.media_count}")

        # ===== 4. 清理: 关闭 (async with 已自动 close, 这里仅做计数提示) =====
        # request_count 是 SDK 计数器: 每调一次 get_json 计数 +1
        # download_count 是下载计数器, 本例没下载, 保持为 0
        print(f"done, 请求 {client.request_count} 次, 下载 {client.download_count} 个")


if __name__ == "__main__":
    asyncio.run(main())