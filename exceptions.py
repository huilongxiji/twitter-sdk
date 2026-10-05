"""twitter_sdk 异常体系。"""


class TwitterSDKError(Exception):
    """所有 SDK 异常的基类。"""


class ConfigError(TwitterSDKError):
    """配置文件加载或内容错误。"""


class AuthError(TwitterSDKError):
    """鉴权失败: cookie 缺失 auth_token / ct0 等。"""


class RateLimitError(TwitterSDKError):
    """API 调用次数已耗尽 (Rate limit exceeded)。"""


class FetchError(TwitterSDKError):
    """请求失败或响应解析失败。"""