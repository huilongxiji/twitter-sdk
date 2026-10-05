"""SDK 数据模型。"""

from dataclasses import dataclass, field
from typing import List

from .utils import stamp2time


@dataclass
class UserInfo:
    """用户基本信息。"""

    screen_name: str      # @ 后面的字符
    rest_id: str          # 数字 ID
    name: str             # 昵称
    statuses_count: int   # 总推数 (含转推)
    media_count: int      # 含图片/视频推数 (不含转推)


@dataclass
class MediaItem:
    """一条推文中的一条媒体 (图片 / 动图 / 视频)。"""

    media_url: str         # 图片直链 (media_url_https) 或视频直链
    media_type: str        # 'photo' / 'gif' / 'video'
    expanded_url: str      # 媒体页链接
    tweet_msecs: int       # 推文发布时间 (毫秒时间戳)
    full_text: str         # 推文正文
    favorite_count: int
    retweet_count: int
    reply_count: int
    is_retweet: bool = False             # 是否为转推内容
    author_name: str = ""                # 原作者昵称 (转推模式)
    author_screen_name: str = ""         # 原作者用户名

    @property
    def time_str(self) -> str:
        """用于文件名前缀的日期字符串。"""
        return stamp2time(self.tweet_msecs)


@dataclass
class TweetItem:
    """一条推文 (含纯文本推文)。

    与 MediaItem 的区别: MediaItem 仅在推文带媒体时产出, TweetItem 对每条推文
    都产出, 因此能拿到纯文字推文。带媒体时 media 列表非空。
    """

    tweet_id: str          # 推文数字 ID
    url: str               # 推文链接
    author_name: str       # 作者昵称
    author_screen_name: str  # 作者用户名 (@ 后面的字符)
    tweet_msecs: int       # 推文发布时间 (毫秒时间戳)
    full_text: str         # 推文正文
    favorite_count: int
    retweet_count: int
    reply_count: int
    is_retweet: bool = False       # 是否为转推内容 (转推模式下原作者信息填在 author_*)
    media: List[MediaItem] = field(default_factory=list)  # 推文内媒体, 纯文本推文为空
    is_quote: bool = False         # 是否引用了其他推文
    quoted_url: str = ""           # 被引用推文的链接

    @property
    def time_str(self) -> str:
        """用于文件名前缀的日期字符串。"""
        return stamp2time(self.tweet_msecs)

    @property
    def has_media(self) -> bool:
        """该推文是否含图片 / 动图 / 视频。"""
        return bool(self.media)