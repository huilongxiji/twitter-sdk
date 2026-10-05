"""TweetClient —— 单条推文与用户全部推文的爬取/下载。

继承 MediaToolsMixin 与 UserInfoClient (进而继承 TwitterClient), 复用鉴权、请求
与媒体下载能力。

与 MediaClient 的分工:
- MediaClient.iter_user_media 只在推文"含媒体"时产出 MediaItem, 纯文字推文会被丢弃;
- 本模块的 iter_user_tweets 对每条推文都产出 TweetItem, 因此能拿到全部推文
  (含视频 / 图片 / 动图 / 纯文本), 转推与点赞可分别开关。
- MediaClient 继承本类, 因此一个 MediaClient 实例即拥有全部推文 + 媒体能力。

接口选择说明:
- 抓"全部推文"走 UserTweets (而非 UserMedia) —— UserMedia 由服务端只返回含媒体的
  推文, 客户端无法补回纯文本推文;
- 点赞页走 Likes 接口 (单页上限 200 条, 远多于 UserTweets 的 20 条)。
"""
import asyncio
import json
import os
from typing import AsyncIterator, List, Optional

from .client import (
    GRAPHQL_BASE,
    LIKES_ENDPOINT,
    TWEET_DETAIL_ENDPOINT,
    TWEET_DETAIL_FEATURES,
    TWEET_DETAIL_FIELD_TOGGLES,
    USER_TWEETS_ENDPOINT,
    USER_TWEETS_FEATURES,
    USER_TWEETS_FIELD_TOGGLES,
)
from .exceptions import FetchError
from .media_tools import MediaToolsMixin
from .models import MediaItem, TweetItem
from .user_info import UserInfoClient
from .utils import parse_time_range, parse_tweet_id, twitter_time_to_stamp

LIKES_FEATURES = USER_TWEETS_FEATURES  # 点赞页与 UserTweets 共用 features


class TweetClient(MediaToolsMixin, UserInfoClient):
    """单条推文与用户全部推文的爬取与下载。"""

    # ---- 全部推文 ----

    async def iter_user_tweets(
        self,
        screen_name: str,
        time_range: Optional[str] = None,
        retweets: bool = False,
        like: bool = False,
        videos: bool = True,
    ) -> AsyncIterator[TweetItem]:
        """逐条产出用户的全部推文 (自动分页), 含纯文本推文。

        - time_range: "1990-01-01:2030-01-01" 或 None
        - retweets: True 时包含转推 (author_* 为原作者)
        - like:     True 时改抓该用户的点赞 (与 retweets 互斥)
        - videos:   False 时 video 类型媒体不产出 (动图始终产出)
        推文由新到旧返回, 一旦早于起始时间立即终止翻页。
        """
        if retweets and like:
            raise ValueError("retweets 与 like 互斥, 只能开启一个")
        start_stamp, end_stamp = parse_time_range(time_range)
        rest_id = await self.get_user_rest_id(screen_name)
        if like:
            async for item in self._iter_timeline_pages(
                    screen_name, rest_id, start_stamp, end_stamp, videos,
                    LIKES_ENDPOINT, "Likes", 200, allow_retweets=False):
                yield item
            return
        async for item in self._iter_timeline_pages(
                screen_name, rest_id, start_stamp, end_stamp, videos,
                USER_TWEETS_ENDPOINT, "UserTweets", 20, allow_retweets=retweets):
            yield item

    async def _iter_timeline_pages(
        self,
        screen_name: str,
        rest_id: str,
        start_stamp: Optional[int],
        end_stamp: Optional[int],
        videos: bool,
        endpoint: str,
        op_name: str,
        count: int,
        allow_retweets: bool,
    ) -> AsyncIterator[TweetItem]:
        """UserTweets / Likes 共用的分页逻辑。"""
        cursor: Optional[str] = None
        # seen_cursors 防死循环: 接口偶尔会回"全是 cursor 没推文"的空页,
        # 此时 cursor-top 判定失效, 必须用历史 cursor 集合兜底
        seen_cursors: set = set()
        while True:
            variables = {
                "userId": rest_id,
                "count": count,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True,
                "withClientEventToken": False,
                "withBirdwatchNotes": False,
            }
            if cursor:
                variables["cursor"] = cursor
            url = (
                f"{GRAPHQL_BASE}/{endpoint}/{op_name}"
                f"?variables={json.dumps(variables, separators=(',', ':'))}"
                f"&features={LIKES_FEATURES}"
                f"&fieldToggles={USER_TWEETS_FIELD_TOGGLES}"
            )
            data = await self.get_json(url, referer=f"https://twitter.com/{screen_name}")
            try:
                instructions = data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
            except (KeyError, TypeError) as exc:
                raise FetchError(f"无法解析用户 {screen_name} 的推文时间线") from exc
            entries = instructions[-1]["entries"]
            if "cursor-top" in entries[0].get("entryId", ""):
                return  # 全部拉取完毕

            stop = False
            new_cursor: Optional[str] = None
            for entry in entries:
                if "cursor-bottom" in entry.get("entryId", ""):
                    new_cursor = entry["content"]["value"]  # 下一页游标
                    continue
                item = self._parse_timeline_entry(
                    entry, start_stamp, end_stamp, videos, screen_name, allow_retweets)
                if item is not None:
                    yield item
                elif self._is_older_than(entry, start_stamp):
                    stop = True
                    break
            if stop:
                return
            if not new_cursor:  # 接口未给下一页游标, 视为到底
                return
            # cursor 不再变化 -> 服务端不再返回新内容, 安全退出避免死循环
            if new_cursor == cursor or new_cursor in seen_cursors:
                return
            seen_cursors.add(new_cursor)
            cursor = new_cursor

    @staticmethod
    def _is_older_than(entry: dict, start_stamp: Optional[int]) -> bool:
        """判断该 entry 是否早于起始时间 (用于终止翻页)。"""
        if start_stamp is None:
            return False
        msecs = TweetClient._entry_msecs(entry)
        return msecs is not None and msecs < start_stamp

    @staticmethod
    def _entry_msecs(entry: dict) -> Optional[int]:
        """从时间线 entry 提取发布时间 (毫秒); 失败返回 None。"""
        try:
            if "tweet" in entry.get("entryId", ""):
                result = entry["content"]["itemContent"]["tweet_results"]["result"]
            elif "profile-conversation" in entry.get("entryId", ""):
                result = entry["content"]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
            else:
                return None
            if "tweet" in result:  # 受限回复账号
                result = result["tweet"]
            return TweetClient._result_msecs(result, result.get("legacy") or {})
        except Exception:
            return None

    def _parse_timeline_entry(
        self,
        entry: dict,
        start_stamp: Optional[int],
        end_stamp: Optional[int],
        videos: bool,
        screen_name: str,
        allow_retweets: bool,
    ) -> Optional[TweetItem]:
        """解析单条时间线 entry 为 TweetItem; 不是推文或解析失败返回 None。"""
        try:
            entry_id = entry.get("entryId", "")
            if "promoted-tweet" in entry_id:
                return None  # 排除广告
            if "tweet" in entry_id:
                result = entry["content"]["itemContent"]["tweet_results"]["result"]
            elif "profile-conversation" in entry_id:
                result = entry["content"]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
            else:
                return None
            if "tweet" in result:  # 受限回复账号
                result = result["tweet"]
            legacy = result.get("legacy") or {}
            tweet_msecs = self._result_msecs(result, legacy)
            if tweet_msecs is None:
                return None

            # 时间范围过滤 (推文由新到旧)
            if start_stamp is not None and tweet_msecs < start_stamp:
                return None
            if end_stamp is not None and tweet_msecs > end_stamp:
                return None

            frr = [
                int(legacy.get("favorite_count") or 0),
                int(legacy.get("retweet_count") or 0),
                int(legacy.get("reply_count") or 0),
            ]

            # 转推: 壳推文无媒体, 内容在 retweeted_status_result 里
            if "retweeted_status_result" in legacy:
                if not allow_retweets:
                    return None
                rt_result = legacy["retweeted_status_result"].get("result") or {}
                rt_legacy = rt_result.get("legacy") or {}
                rt_core = (rt_result.get("core", {}).get("user_results", {})
                           .get("result", {}).get("legacy", {}))
                author_screen = rt_core.get("screen_name", "")
                if not rt_legacy:
                    return None
                return self._build_tweet(
                    legacy=rt_legacy,
                    tweet_id=legacy.get("id_str", ""),
                    tweet_msecs=tweet_msecs,
                    full_text=rt_legacy.get("full_text", ""),
                    frr=frr,
                    author_name=rt_core.get("name", ""),
                    author_screen_name=author_screen,
                    is_retweet=True,
                    videos=videos,
                )

            # 原创推文 (含纯文本)
            core = (result.get("core", {}).get("user_results", {})
                    .get("result", {}).get("legacy", {}))
            return self._build_tweet(
                legacy=legacy,
                tweet_id=legacy.get("id_str", ""),
                tweet_msecs=tweet_msecs,
                full_text=legacy.get("full_text", ""),
                frr=frr,
                author_name=core.get("name", ""),
                author_screen_name=core.get("screen_name", "") or screen_name,
                is_retweet=False,
                videos=videos,
            )
        except Exception:
            return None  # 单条解析失败不中断整体

    def _build_tweet(
        self,
        legacy: dict,
        tweet_id: str,
        tweet_msecs: int,
        full_text: str,
        frr: list,
        author_name: str,
        author_screen_name: str,
        is_retweet: bool,
        videos: bool,
    ) -> Optional[TweetItem]:
        """由 legacy 字典组装 TweetItem。"""
        if not tweet_id:
            return None
        media: List[MediaItem] = []
        for media_dict in (legacy.get("extended_entities") or {}).get("media", []):
            item = self._make_media_item(
                media_dict, tweet_msecs, full_text, frr, videos,
                is_retweet, author_name, author_screen_name)
            if item:
                media.append(item)
        quoted = legacy.get("quoted_status_permalink") or {}
        return TweetItem(
            tweet_id=tweet_id,
            url=f"https://twitter.com/{author_screen_name}/status/{tweet_id}",
            author_name=author_name,
            author_screen_name=author_screen_name,
            tweet_msecs=tweet_msecs,
            full_text=full_text,
            favorite_count=frr[0],
            retweet_count=frr[1],
            reply_count=frr[2],
            is_retweet=is_retweet,
            media=media,
            is_quote=bool(quoted.get("expanded")),
            quoted_url=quoted.get("expanded", ""),
        )

    # ---- 单条推文 (分享链接) ----

    async def fetch_tweet_by_url(self, url: str, videos: bool = True) -> TweetItem:
        """根据分享链接抓取单条推文。

        支持三种链接形态: twitter.com/xxx/status/...、x.com/xxx/status/...、
        twitter.com/i/web/status/...。
        """
        tweet_id = parse_tweet_id(url)
        if not tweet_id:
            raise ValueError(f"不是合法的推文链接: {url}")
        return await self.get_tweet_by_id(tweet_id, videos)

    async def get_tweet_by_id(self, tweet_id: str, videos: bool = True) -> TweetItem:
        """根据推文数字 ID 抓取单条推文 (走 TweetDetail 接口)。"""
        tweet_id = str(tweet_id).strip()
        if not tweet_id.isdigit():
            raise ValueError(f"推文 ID 必须是数字: {tweet_id}")
        data = await self._fetch_tweet_detail(tweet_id, cursor="")
        item = self._parse_detail_tweet(data, tweet_id, videos)
        if item is None:
            raise FetchError(f"无法解析推文 {tweet_id}, 可能已删除或需要登录")
        return item

    async def _fetch_tweet_detail(self, tweet_id: str, cursor: str) -> dict:
        """请求 TweetDetail 接口, 返回 data 字典。"""
        variables = {
            "focalTweetId": tweet_id,
            "cursor": cursor,
            "referrer": "tweet",
            "with_rux_injections": False,
            "rankingMode": "Relevance",
            "includePromotedContent": False,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True,
        }
        url = (
            f"https://x.com/i/api/graphql/{TWEET_DETAIL_ENDPOINT}/TweetDetail"
            f"?variables={json.dumps(variables, separators=(',', ':'))}"
            f"&features={TWEET_DETAIL_FEATURES}"
            f"&fieldToggles={TWEET_DETAIL_FIELD_TOGGLES}"
        )
        data = await self.get_json(
            url, referer=f"https://x.com/i/web/status/{tweet_id}", transaction=True)
        if not isinstance(data, dict) or "data" not in data:
            raise FetchError(f"推文 {tweet_id} 详情响应异常")
        return data["data"]

    def _parse_detail_tweet(self, data: dict, tweet_id: str,
                            videos: bool = True) -> Optional[TweetItem]:
        """从 TweetDetail 响应的 instructions 中取出目标推文。"""
        for entry in self._collect_detail_entries(data):
            result = self._extract_detail_result(entry)
            if result is None:
                continue
            if str((result.get("legacy") or {}).get("id_str", "")) != str(tweet_id):
                continue
            return self._result_to_tweet_item(result, videos)
        return None

    @staticmethod
    def _collect_detail_entries(data: dict) -> List[dict]:
        """把 TweetDetail 的 instructions 摊平成统一的 entry 列表。

        首页目标推文在顶层条目 (含 entryId), 回复在 instructions[].entries
        里; 翻页时全部位于 instructions[0].entries, 故两种形态一并收集。
        """
        entries: List[dict] = []
        try:
            instructions = data["threaded_conversation_with_injections_v2"]["instructions"]
        except (KeyError, TypeError):
            return entries
        for ins in instructions:
            if not isinstance(ins, dict):
                continue
            if "entryId" in ins:  # 顶层条目 (首页)
                entries.append(ins)
            elif isinstance(ins.get("entries"), list):
                entries.extend(ins["entries"])
        return entries

    @staticmethod
    def _extract_detail_result(entry: dict) -> Optional[dict]:
        """从 TweetDetail 的 entry 中取出 tweet result 字典。

        需兼容三类 entry: tweet-xxx (content.itemContent),
        conversationthread-xxx (content.items[i].item.itemContent),
        受限回复账号 (result 外面多包一层 tweet)。
        """
        try:
            entry_id = entry.get("entryId", "")
            if "tweet" not in entry_id and "conversationthread" not in entry_id:
                return None
            content = entry.get("content") or {}
            result = None
            if "itemContent" in content:
                result = content["itemContent"]["tweet_results"]["result"]
            elif "items" in content:  # conversationthread 嵌套
                for sub in content.get("items") or []:
                    item = sub.get("item") or sub
                    if "itemContent" in item:
                        result = item["itemContent"]["tweet_results"]["result"]
                        break
                    if "items" in item:  # 再嵌一层
                        for inner in item.get("items") or []:
                            if "itemContent" in inner:
                                result = inner["itemContent"]["tweet_results"]["result"]
                                break
                        if result is not None:
                            break
            if not isinstance(result, dict):
                return None
            if "tweet" in result:
                result = result["tweet"]  # 受限回复账号
            return result
        except Exception:
            return None

    async def iter_thread_replies(
        self,
        url: str,
        videos: bool = True,
    ) -> AsyncIterator[TweetItem]:
        """逐条产出某条推文下方的回复 (分享链接或数字 ID 均可)。"""
        tweet_id = parse_tweet_id(url)
        if tweet_id is None:
            tweet_id = str(url).strip()  # 允许直接传数字 ID
        if not tweet_id.isdigit():
            raise ValueError(f"不是合法的推文链接或 ID: {url}")
        cursor = ""
        while True:
            data = await self._fetch_tweet_detail(tweet_id, cursor)
            instructions = data.get("threaded_conversation_with_injections_v2", {}).get(
                "instructions", [])
            bottom = instructions[-1] if instructions else {}
            if isinstance(bottom, dict) and bottom.get("direction") == "Bottom":
                return  # 已到末尾
            new_cursor = ""
            for entry in self._collect_detail_entries(data):
                if "conversationthread" in entry.get("entryId", ""):
                    result = self._extract_detail_result(entry)
                    if result is not None:
                        item = self._result_to_tweet_item(result, videos)
                        if item is not None:
                            yield item
                elif "cursor-bottom" in entry.get("entryId", ""):
                    new_cursor = entry["content"]["value"]
            if not new_cursor or new_cursor == cursor:
                return
            cursor = new_cursor

    @staticmethod
    def _result_msecs(result: dict, legacy: dict) -> Optional[int]:
        """从推文 result 取发布时间 (毫秒)。

        优先 edit_control.editable_until_msecs (比真实时间晚 1 小时, 需减);
        缺失时回退 edit_control_initial; 仍缺失则用 legacy.created_at。
        """
        edit_control = result.get("edit_control") or {}
        msecs = edit_control.get("editable_until_msecs")
        if not msecs:
            msecs = (edit_control.get("edit_control_initial") or {}).get(
                "editable_until_msecs")
        if msecs:
            return int(msecs) - 3600000
        created_at = legacy.get("created_at")
        return twitter_time_to_stamp(created_at) if created_at else None

    def _result_to_tweet_item(self, result: dict, videos: bool) -> Optional[TweetItem]:
        """把推文的 result 字典 (时间线或详情接口) 转成 TweetItem。"""
        try:
            legacy = result.get("legacy") or {}
            core = (result.get("core", {}).get("user_results", {})
                    .get("result", {}).get("legacy", {}))
            tweet_msecs = self._result_msecs(result, legacy)
            if tweet_msecs is None:
                return None
            return self._build_tweet(
                legacy=legacy,
                tweet_id=str(legacy.get("id_str", "")),
                tweet_msecs=tweet_msecs,
                full_text=legacy.get("full_text", ""),
                frr=[
                    int(legacy.get("favorite_count") or 0),
                    int(legacy.get("retweet_count") or 0),
                    int(legacy.get("reply_count") or 0),
                ],
                author_name=core.get("name", ""),
                author_screen_name=core.get("screen_name", ""),
                is_retweet="retweeted_status_result" in legacy,
                videos=videos,
            )
        except Exception:
            return None

    # ---- 下载 ----

    async def download_tweet(
        self,
        url: str,
        save_path: Optional[str] = None,
        image_format: Optional[str] = None,
        videos: bool = True,
        concurrency: Optional[int] = None,
    ) -> int:
        """下载单条推文内的媒体, 返回成功下载数量。

        - url: 推文分享链接或数字 ID
        - save_path: 保存目录, 默认 save_path/tweet_id
        - image_format: jpg / png / orig, 默认 config.toml 的 image_format
        - videos: 是否下载视频 (动图始终下载并转成 gif)
        单条推文不写入去重缓存, 避免污染用户目录的断点续传记录。
        """
        if "://" in str(url):
            tweet = await self.fetch_tweet_by_url(str(url), videos)
        else:
            tweet = await self.get_tweet_by_id(str(url).strip(), videos)
        if save_path is None:
            base = self.save_path or os.getcwd()
            save_path = os.path.join(base, "tweet", tweet.tweet_id)
        if image_format is None:
            image_format = self.config.image_format or "jpg"
        image_format = image_format.lower()
        concurrency = concurrency or self.config.max_concurrent_requests or 8
        if not tweet.media:
            return 0
        os.makedirs(save_path, exist_ok=True)
        semaphore = asyncio.Semaphore(concurrency)

        tasks = []
        for index, media_item in enumerate(tweet.media, start=1):
            prefix = media_item.time_str + self._type_prefix(media_item.media_type)
            if tweet.is_retweet:
                prefix += "-retweet"
            suffix = self._resolve_suffix(image_format, media_item)
            file_name = f"{prefix}_{tweet.tweet_id}_{index}.{suffix}"
            tasks.append(self._download_file(
                media_item, os.path.join(save_path, file_name), image_format, semaphore))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)