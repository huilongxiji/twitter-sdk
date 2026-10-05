"""twitter_sdk —— 推特图片下载 SDK。

用法:
    import asyncio
    from twitter_sdk import MediaClient

    async def main():
        # 动态参数 (cookie / 保存路径) 在构造时注册;
        # 静态配置由 SDK 自行加载内置 config.toml, 不允许外部覆盖
        async with MediaClient(cookie="auth_token=...; ct0=...;",
                               save_path="./download") as client:
            info = await client.get_user_info("<screen_name>")
            print(info)
            count = await client.download_user_media(
                "<screen_name>", concurrency=4, videos=True, retweets=False)
            print(count)

    asyncio.run(main())
"""

# ---- Python 版本门禁 ----
# 必须是本文件第一条可执行语句: 早于所有 SDK 内部 import,
# 否则低版本用户会先撞上 tomllib 的 ModuleNotFoundError 而不是这条提示。
import sys as _sys

MIN_PYTHON = (3, 10)

if _sys.version_info < MIN_PYTHON:
    _current = ".".join(map(str, _sys.version_info[:3]))
    raise RuntimeError(
        f"twitter_sdk 需要 Python {'.'.join(map(str, MIN_PYTHON))}+, "
        f"当前 {_current}。请用 Python 3.10+ 重建虚拟环境。"
    )

# ---- 原有导入 ----

from .cache import DownloadCache
from .client import TwitterClient
from .config import SDKConfig, extract_cookie_field, load_config
from .exceptions import (
    AuthError,
    ConfigError,
    FetchError,
    RateLimitError,
    TwitterSDKError,
)
from .media import MediaClient
from .media_tools import MediaToolsMixin
from .md_gen import MdGen
from .models import MediaItem, TweetItem, UserInfo
from .tweet import TweetClient
from .user_info import UserInfoClient
from .utils import parse_screen_name, parse_tweet_id

__version__ = "0.2.0"

__all__ = [
    "TwitterClient",
    "SDKConfig",
    "load_config",
    "extract_cookie_field",
    "UserInfoClient",
    "MediaToolsMixin",
    "TweetClient",
    "MediaClient",
    "DownloadCache",
    "MdGen",
    "UserInfo",
    "MediaItem",
    "TweetItem",
    "parse_tweet_id",
    "parse_screen_name",
    "TwitterSDKError",
    "AuthError",
    "ConfigError",
    "RateLimitError",
    "FetchError",
    "MIN_PYTHON",
    "__version__",
]