"""MediaClient —— 用户媒体爬取与下载。

继承 TweetClient (进而继承 UserInfoClient 与 TwitterClient), 同时具备
本类的媒体能力 (iter_user_media / download_user_media) 与 TweetClient 的
全部推文 / 单条推文能力。

附加项 (默认 False, 调用时传 True 才生效):
- videos=True:   同时下载视频 (动图始终下载)
- retweets=True: 切换到含转推的 UserTweets 接口
- deep=True:     直接走 SearchTimeline (与 retweets 互斥)
- auto_complete: 默认模式 (非 deep) 拉到接口深度上限后, 自动衔接 SearchTimeline
  补全更老内容 —— 默认开启
- md_output:     输出 Markdown 推文记录

去重缓存: use_cache=True 时按 "格式|URL" 记录已下载内容, 实现断点续传。
"""

import asyncio
import json
import os
from typing import AsyncIterator, List, Optional, Tuple

from .cache import DownloadCache
from .client import (
    GRAPHQL_BASE,
    SEARCH_ENDPOINT,
    SEARCH_FEATURES,
    USER_MEDIA_ENDPOINT,
    USER_MEDIA_FEATURES,
    USER_TWEETS_ENDPOINT,
    USER_TWEETS_FEATURES,
    USER_TWEETS_FIELD_TOGGLES,
)
from .exceptions import FetchError
from .md_gen import MdGen
from .models import MediaItem
from .tweet import TweetClient
from .utils import parse_time_range, stamp2date, twitter_time_to_stamp


class MediaClient(TweetClient):
    """用户媒体爬取与图片下载 (同时具备 TweetClient 的全部推文能力)。"""

    # ---- 拉取 ----

    async def iter_user_media(
        self,
        screen_name: str,
        time_range: Optional[str] = None,
        videos: bool = False,
        retweets: bool = False,
        deep: bool = False,
        auto_complete: bool = True,
    ) -> AsyncIterator[MediaItem]:
        """逐条产出用户的媒体 (自动分页)。

        - time_range: "1990-01-01:2030-01-01" 或 None (默认取 config.toml)
        - videos: 附加项, True 时同时产出视频 (动图始终随图片产出)
        - retweets: 附加项, True 时切换到含转推的 UserTweets 接口
        - deep: 附加项, True 时直接走 SearchTimeline 搜索接口 (适合指定时间区间补档)
        - auto_complete: 默认模式下 UserMedia 拉到接口深度上限后,
          自动衔接 SearchTimeline 补全更老内容 (默认开启, 一次跑完即全部)
        推文由新到旧返回, 一旦早于起始时间立即终止翻页。
        """
        if retweets and deep:
            raise ValueError("retweets 与 deep 互斥, 只能开启一个")
        mode = "tweets" if retweets else ("deep" if deep else "media")
        start_stamp, end_stamp = parse_time_range(time_range)
        rest_id = await self.get_user_rest_id(screen_name)

        if mode == "deep":
            async for item in self._iter_search_pages(screen_name, start_stamp, end_stamp, videos):
                yield item
            return
        if mode == "tweets":
            async for item in self._iter_tweets_pages(screen_name, rest_id, start_stamp, end_stamp, videos):
                yield item
            return

        # 默认 UserMedia 模式
        cursor: Optional[str] = None
        first_page = True
        last_msecs: Optional[int] = None
        stopped_by_time = False
        while True:
            variables = {
                "userId": rest_id,
                "count": 500,
                "includePromotedContent": False,
                "withClientEventToken": False,
                "withBirdwatchNotes": False,
                "withVoice": True,
                "withV2Timeline": True,
            }
            if cursor:
                variables["cursor"] = cursor
            url = (
                f"{GRAPHQL_BASE}/{USER_MEDIA_ENDPOINT}/UserMedia"
                f"?variables={json.dumps(variables, separators=(',', ':'))}"
                f"&features={USER_MEDIA_FEATURES}"
            )
            data = await self.get_json(url, referer=f"https://twitter.com/{screen_name}")
            try:
                instructions = data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
            except (KeyError, TypeError) as exc:
                raise FetchError(f"无法解析用户 {screen_name} 的媒体时间线") from exc

            for entry in instructions[-1]["entries"]:
                if "bottom" in entry.get("entryId", ""):
                    cursor = entry["content"]["value"]
            if first_page:
                content_items = instructions[-1]["entries"][0]["content"]["items"]
                first_page = False
            else:
                if "moduleItems" not in instructions[0]:
                    break  # 接口深度到顶
                content_items = instructions[0]["moduleItems"]

            for entry in content_items:
                media_items, stop = self._extract_media_items(
                    entry, start_stamp, end_stamp, "media", videos, screen_name)
                for media_item in media_items:
                    if last_msecs is None or media_item.tweet_msecs < last_msecs:
                        last_msecs = media_item.tweet_msecs
                    yield media_item
                if stop:
                    stopped_by_time = True
                    break
            if stopped_by_time:
                break

        # 接口深度到顶 -> 自动衔接搜索, 补更老内容
        if auto_complete and not stopped_by_time and last_msecs is not None:
            if start_stamp is None or last_msecs > start_stamp:
                async for item in self._iter_search_pages(
                        screen_name, start_stamp, last_msecs, videos):
                    yield item

    async def _iter_search_pages(
        self,
        screen_name: str,
        start_stamp: Optional[int],
        end_stamp: Optional[int],
        videos: bool,
    ) -> AsyncIterator[MediaItem]:
        """SearchTimeline 搜索接口分页 (需要 x-client-transaction-id 校验头)。"""
        query = f"from:{screen_name}"
        if end_stamp:
            query += f" until:{stamp2date(end_stamp + 86400000)}"  # until 不含当日, +1 天
        if start_stamp:
            query += f" since:{stamp2date(start_stamp)}"
        cursor = ""
        while True:
            variables = {
                "rawQuery": query,
                "count": 50,
                "cursor": cursor,
                "querySource": "typed_query",
                "product": "Media",
            }
            url = (
                f"{GRAPHQL_BASE}/{SEARCH_ENDPOINT}/SearchTimeline"
                f"?variables={json.dumps(variables, separators=(',', ':'))}"
                f"&features={SEARCH_FEATURES}"
            )
            data = await self.get_json(
                url,
                referer=f"https://twitter.com/search?q={query}&src=typed_query&f=media",
                transaction=True,
            )
            try:
                instructions = (data["data"]["search_by_raw_query"]["search_timeline"]
                               ["timeline"]["instructions"])
            except (KeyError, TypeError) as exc:
                raise FetchError(f"无法解析用户 {screen_name} 的搜索时间线") from exc
            entries = None
            for ins in reversed(instructions):
                if "entries" in ins:
                    entries = ins["entries"]
                    break
            if entries is None:
                return  # 无更多结果
            grid = next((e for e in entries if "search-grid" in e.get("entryId", "")), None)
            if grid is None or "items" not in grid.get("content", {}):
                return  # 无更多结果
            content_items = grid["content"]["items"]
            for e in entries:
                if "cursor-bottom" in e.get("entryId", ""):
                    cursor = e["content"]["value"]
            for entry in content_items:
                media_items, _ = self._extract_media_items(
                    entry, None, None, "deep", videos, screen_name)
                for media_item in media_items:
                    yield media_item

    async def _iter_tweets_pages(
        self,
        screen_name: str,
        rest_id: str,
        start_stamp: Optional[int],
        end_stamp: Optional[int],
        videos: bool,
    ) -> AsyncIterator[MediaItem]:
        """UserTweets 含转推接口分页。"""
        cursor: Optional[str] = None
        while True:
            variables = {
                "userId": rest_id,
                "count": 20,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True,
            }
            if cursor:
                variables["cursor"] = cursor
            url = (
                f"{GRAPHQL_BASE}/{USER_TWEETS_ENDPOINT}/UserTweets"
                f"?variables={json.dumps(variables, separators=(',', ':'))}"
                f"&features={USER_TWEETS_FEATURES}"
                f"&fieldToggles={USER_TWEETS_FIELD_TOGGLES}"
            )
            data = await self.get_json(url, referer=f"https://twitter.com/{screen_name}")
            try:
                instructions = data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
            except (KeyError, TypeError) as exc:
                raise FetchError(f"无法解析用户 {screen_name} 的媒体时间线") from exc
            entries = instructions[-1]["entries"]
            if "cursor-top" in entries[0].get("entryId", ""):
                return  # 全部拉取完毕
            stop = False
            for entry in entries:
                media_items, stop = self._extract_media_items(
                    entry, start_stamp, end_stamp, "tweets", videos, screen_name)
                if "cursor-bottom" in entry.get("entryId", ""):
                    cursor = entry["content"]["value"]  # 更新下一页游标
                for media_item in media_items:
                    yield media_item
                if stop:
                    break
            if stop:
                return

    def _extract_media_items(
        self,
        entry: dict,
        start_stamp: Optional[int],
        end_stamp: Optional[int],
        mode: str,
        videos: bool,
        screen_name: str,
    ) -> Tuple[List[MediaItem], bool]:
        """解析单条时间线 entry, 返回 (媒体列表, 是否超出时间范围应终止翻页)。"""
        items: List[MediaItem] = []
        try:
            entry_id = entry.get("entryId", "")
            if "promoted-tweet" in entry_id:
                return [], False  # 排除广告
            x_label = "content" if mode == "tweets" else "item"
            if "tweet" in entry_id:
                result_obj = entry[x_label]["itemContent"]["tweet_results"]["result"]
            elif "profile-conversation" in entry_id:
                result_obj = entry[x_label]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
            else:
                return [], False

            if "tweet" in result_obj:  # 受限回复账号
                legacy = result_obj["tweet"]["legacy"]
                edit_msecs = result_obj["tweet"].get("edit_control", {}).get("editable_until_msecs")
            else:
                legacy = result_obj["legacy"]
                edit_msecs = result_obj.get("edit_control", {}).get("editable_until_msecs")
            if edit_msecs:
                tweet_msecs = int(edit_msecs) - 3600000
            else:
                # 搜索结果类接口没有 edit_control, 用 created_at 获取时间
                tweet_msecs = twitter_time_to_stamp(legacy.get("created_at", ""))

            # 时间范围过滤 (推文由新到旧)
            if start_stamp is not None and tweet_msecs < start_stamp:
                return [], True
            if end_stamp is not None and tweet_msecs > end_stamp:
                return [], False

            frr = [
                int(legacy.get("favorite_count") or 0),
                int(legacy.get("retweet_count") or 0),
                int(legacy.get("reply_count") or 0),
            ]

            # 转推模式下的转推内容
            if "retweeted_status_result" in legacy:
                if mode != "tweets":
                    return [], False  # 非转推模式跳过转推
                rt_result = legacy["retweeted_status_result"]["result"]
                rt_legacy = rt_result.get("legacy") or {}
                rt_core = (rt_result.get("core", {}).get("user_results", {})
                           .get("result", {}).get("legacy", {}))
                author_screen = rt_core.get("screen_name", "")
                if author_screen == screen_name:
                    return [], False  # 排除用户转推自己
                if "extended_entities" not in rt_legacy:
                    return [], False
                full_text = rt_legacy.get("full_text", "")
                for media in rt_legacy["extended_entities"]["media"]:
                    item = self._make_media_item(
                        media, tweet_msecs, full_text, frr, videos,
                        is_retweet=True, author_name=rt_core.get("name", ""),
                        author_screen_name=author_screen)
                    if item:
                        items.append(item)
                return items, False

            # 正常推文
            if "extended_entities" not in legacy:
                return [], False
            full_text = legacy.get("full_text", "")
            for media in legacy["extended_entities"]["media"]:
                item = self._make_media_item(
                    media, tweet_msecs, full_text, frr, videos,
                    is_retweet=False, author_name="", author_screen_name="")
                if item:
                    items.append(item)
        except Exception:
            return [], False  # 单条解析失败不中断整体
        return items, False

    # ---- 下载 ----

    async def download_user_media(
        self,
        screen_name: str,
        save_path: Optional[str] = None,
        time_range: Optional[str] = None,
        videos: bool = False,
        retweets: bool = False,
        deep: bool = False,
        auto_complete: bool = True,
        concurrency: Optional[int] = None,
        max_download: Optional[int] = None,
        image_format: Optional[str] = None,
        use_cache: Optional[bool] = None,
        md_output: Optional[bool] = None,
    ) -> int:
        """下载指定用户的媒体, 返回成功下载数量。

        附加项 (默认 False, 携带 True 才生效):
        - videos: 同时下载视频 (动图始终随图片下载)
        - retweets: 含转推模式 (与 deep 互斥)
        - deep: 直接走 SearchTimeline 搜索接口 (适合指定时间区间补档)
        - auto_complete: 默认模式 (非 deep) 下拉到接口深度上限后,
          自动衔接搜索接口补全更老内容 —— 默认开启, 一次跑完即全部历史
        - md_output: 输出 Markdown 推文记录, 默认 config.toml 的 md_output
        动态参数:
        - concurrency: 同时进行的下载数量 (并发数), 默认 config.toml 的 max_concurrent_requests
        - max_download: 本次总下载数量上限 (None 不限)
        - use_cache: 是否启用去重缓存, 默认 config.toml 的 down_log
        文件命名: {时间}-img/-gif/-vid_{序号}.{格式}, 转推内容追加 -retweet。
        """
        if save_path is None:
            base = self.save_path or os.getcwd()
            save_path = os.path.join(base, screen_name)
        if time_range is None:
            time_range = self.config.time_range
        concurrency = concurrency or self.config.max_concurrent_requests or 8
        image_format = (image_format or self.config.image_format or "jpg").lower()
        if use_cache is None:
            use_cache = self.config.down_log
        if md_output is None:
            md_output = self.config.md_output
        os.makedirs(save_path, exist_ok=True)

        cache = DownloadCache(save_path) if use_cache else None
        md = None
        if md_output:
            info = await self.get_user_info(screen_name)  # md 头部需要昵称
            md = MdGen(save_path, info.name, screen_name, time_range or "",
                       self.config.media_count_limit)
        semaphore = asyncio.Semaphore(concurrency)
        downloads = []  # (cache_key, task)
        index = 0
        try:
            async for media_item in self.iter_user_media(
                    screen_name, time_range, videos, retweets, deep, auto_complete):
                cache_key = self._cache_key(media_item, image_format)
                if cache is not None and cache.contains(cache_key):
                    continue  # 已下载过, 跳过
                if max_download is not None and index >= max_download:
                    break
                index += 1
                prefix = media_item.time_str + self._type_prefix(media_item.media_type)
                if media_item.is_retweet:
                    prefix += "-retweet"
                suffix = self._resolve_suffix(image_format, media_item)
                file_name = f"{prefix}_{index}.{suffix}"
                file_path = os.path.join(save_path, file_name)
                if md is not None:
                    md.record_media(media_item, file_name)  # 创建任务时记录, 保证推文顺序
                task = asyncio.create_task(
                    self._download_file(media_item, file_path, image_format, semaphore))
                downloads.append((cache_key, task))

            results = await asyncio.gather(*[t for _, t in downloads], return_exceptions=True)
            success = 0
            for (key, _), result in zip(downloads, results):
                if result is True:
                    success += 1
                    if cache is not None:
                        cache.add(key)   # 下载成功才记录, 失败下次重试
                        cache.close()    # 立即落盘, 保证断点续传
            return success
        finally:
            if cache is not None:
                cache.close()
            if md is not None:
                md.close()

    async def download_user_images(self, screen_name: str, **kwargs) -> int:
        """download_user_media 的图片专用别名 (videos 固定 False)。"""
        return await self.download_user_media(screen_name, videos=False, **kwargs)