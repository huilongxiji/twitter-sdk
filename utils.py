"""通用工具函数。"""

import re
import time
from datetime import datetime
from typing import Optional, Tuple


def stamp2time(msecs_stamp: int) -> str:
    """毫秒时间戳 -> 日期字符串 (含横杠, 可直接作文件名)。"""
    time_array = time.localtime(msecs_stamp / 1000)
    return time.strftime("%Y-%m-%d %H-%M", time_array)


def time2stamp(timestr: str) -> int:
    """日期字符串 -> 毫秒时间戳。"""
    datetime_obj = datetime.strptime(timestr, "%Y-%m-%d")
    msecs_stamp = int(time.mktime(datetime_obj.timetuple()) * 1000.0 + datetime_obj.microsecond / 1000.0)
    return msecs_stamp


def time_comparison(now: int, start: int, end: int) -> list:
    """判断推文时间是否落在 [start, end] 内。

    返回 [start_down, start_label]:
      - start_down: 该推文是否应下载
      - start_label: 是否应继续翻页 (推文由新到旧, 一旦早于 start 即可终止)
    """
    start_label = True
    start_down = False
    if start <= now <= end:
        start_down = True
    elif now < start:
        start_label = False
    return [start_down, start_label]


def del_special_char(string: str) -> str:
    """只保留中英文数字 / 日文假名 / 点号, 防止生成非法文件名。"""
    return re.sub(r"[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\u3040-\u31FF\.]", "", string)


def twitter_time_to_stamp(created_at: str) -> int:
    """推文 created_at 字符串 -> 毫秒时间戳 (用于搜索结果类没有 edit_control 的接口)。"""
    dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
    return int(dt.timestamp() * 1000)


def stamp2date(stamp: int) -> str:
    """毫秒时间戳 -> 'YYYY-MM-DD' 日期字符串 (用于搜索的 since/until 参数)。"""
    return datetime.fromtimestamp(stamp / 1000).strftime("%Y-%m-%d")


def parse_time_range(time_range: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """解析时间范围字符串 -> (start_stamp, end_stamp); 空则返回 (None, None)。"""
    if not time_range:
        return None, None
    start, end = time_range.split(":")
    return time2stamp(start), time2stamp(end)


# 匹配 twitter.com / x.com 分享链接中的推文 ID, 兼容带查询参数与 /i/web/ 形态
_TWEET_ID_RE = re.compile(r"/(?:i/web/)?status(?:es)?/(\d+)")


def parse_tweet_id(url: str) -> Optional[str]:
    """从推文分享链接中提取数字 ID; 不是合法推文链接则返回 None。

    支持 twitter.com / x.com / i/web 三种链接形态。
    """
    if not url:
        return None
    match = _TWEET_ID_RE.search(url.strip())
    return match.group(1) if match else None


def parse_screen_name(url: str) -> Optional[str]:
    """从推文链接中提取用户名; 不是合法推文链接则返回 None。"""
    if not url:
        return None
    match = re.search(
        r"(?:twitter|x)\.com/(?:i/web/)?([A-Za-z0-9_]{1,15})/status(?:es)?/\d+",
        url.strip(),
    )
    return match.group(1) if match else None