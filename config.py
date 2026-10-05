"""SDK 静态配置: 通过 TOML 文件载入。

约定:
- TOML 只存"不常改变的数值" (模式开关 / 时间范围 / 格式 / 并发等)
- 动态参数 (cookie / 用户名 / 保存路径 / 下载数量等) 在构造 class 或调用功能时注册
"""

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from .exceptions import ConfigError

# ---- Python 版本门禁 ----
# 重复 __init__.py 的检查: 直接 `from twitter_sdk.config import ...` 会绕过 __init__
MIN_PYTHON = (3, 10)

if sys.version_info < MIN_PYTHON:
    _current = ".".join(map(str, sys.version_info[:3]))
    raise RuntimeError(
        f"twitter_sdk 需要 Python {'.'.join(map(str, MIN_PYTHON))}+, "
        f"当前 {_current}。请用 Python 3.10+ 重建虚拟环境。"
    )

# tomllib 是 Python 3.11+ 才进标准库, 3.10 需要 tomli 回退
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - 仅 3.10 环境走到这里
    import tomli as tomllib

# SDK 内置默认配置 (与 config.py 同目录的 config.toml)
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")


@dataclass
class SDKConfig:
    """静态配置对象 (字段对应 config.toml)。"""

    has_retweet: bool = False            # 是否包含转推
    high_lights: bool = False            # 亮点标签页
    likes: bool = False                  # likes 标签页
    time_range: str = ""                 # 时间范围限制, 空为不限
    down_log: bool = False               # 记录已下载内容避免重复
    auto_sync: bool = False              # 自动同步最新内容
    image_format: str = "jpg"            # orig / jpg / png
    has_video: bool = False              # 是否下载视频
    log_output: bool = False             # 下载过程日志
    max_concurrent_requests: int = 8     # 最大并发数
    md_output: bool = False              # 输出 Markdown
    media_count_limit: int = 350         # 单个 md 媒体链接上限 (0 不限)

    @classmethod
    def from_toml(cls, path: str) -> "SDKConfig":
        """从 TOML 文件载入 (缺省字段使用默认值, 未知字段宽容忽略)。"""
        if not os.path.exists(path):
            raise ConfigError(f"配置文件不存在: {path}")
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"TOML 解析失败: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"配置文件读取失败: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError("配置文件根节点必须是表 (table)")

        def get(*keys: str, default=None):
            for key in keys:
                if key in data:
                    return data[key]
            return default

        return cls(
            has_retweet=bool(get("has_retweet", default=False)),
            high_lights=bool(get("high_lights", default=False)),
            likes=bool(get("likes", default=False)),
            time_range=str(get("time_range", default="") or ""),
            down_log=bool(get("down_log", default=False)),
            auto_sync=bool(get("autoSync", "auto_sync", default=False)),
            image_format=str(get("image_format", default="jpg") or "jpg"),
            has_video=bool(get("has_video", default=False)),
            log_output=bool(get("log_output", default=False)),
            max_concurrent_requests=int(get("max_concurrent_requests", default=8) or 8),
            md_output=bool(get("md_output", default=False)),
            media_count_limit=int(get("media_count_limit", default=350) or 350),
        )


def extract_cookie_field(cookie: str, key: str) -> Optional[str]:
    """从 cookie 字符串中提取指定字段, 如 auth_token / ct0。"""
    match = re.search(rf"{key}=([^;]+)", cookie)
    return match.group(1).strip() if match else None


def load_config() -> SDKConfig:
    """加载 SDK 内置 config.toml (静态配置由 SDK 自行管理, 不支持外部覆盖)。"""
    return SDKConfig.from_toml(DEFAULT_CONFIG_PATH)