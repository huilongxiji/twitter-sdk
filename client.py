"""TwitterClient —— SDK 基类: 鉴权 + 异步 HTTP 复用。"""

import asyncio
import json
from typing import Any, Dict, Optional

import httpx

from .config import extract_cookie_field, load_config
from .exceptions import AuthError, FetchError, RateLimitError

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
BEARER_TOKEN = ("Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
                "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")
GRAPHQL_BASE = "https://twitter.com/i/api/graphql"

USER_BY_SCREEN_NAME_ENDPOINT = "xc8f1g7BYqr6VTzTbvNlGw"
USER_BY_SCREEN_NAME_FEATURES = (
    '{"hidden_profile_likes_enabled":false,"hidden_profile_subscriptions_enabled":false,'
    '"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,'
    '"subscriptions_verification_info_verified_since_enabled":true,"highlights_tweets_tab_ui_enabled":true,'
    '"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"responsive_web_graphql_timeline_navigation_enabled":true}'
)
USER_BY_SCREEN_NAME_FIELD_TOGGLES = '{"withAuxiliaryUserLabels":false}'

USER_MEDIA_ENDPOINT = "Le6KlbilFmSu-5VltFND-Q"   # UserMedia: 仅含媒体, 单页 500
USER_TWEETS_ENDPOINT = "2GIWTr7XwadIixZDtyXd4A"  # UserTweets: 含转推, 单页 20
LIKES_ENDPOINT = "-fbTO1rKPa3nO6-XIRgEFQ"        # Likes 标签页, 单页 200
SEARCH_ENDPOINT = "AIdc203rPpK_k_2KWSdm7g"        # 搜索, 支持 since/until
TWEET_DETAIL_ENDPOINT = "_8aYOgEDz35BrBcBal1-_w"  # TweetDetail: 单条推文 + 回复

USER_MEDIA_FEATURES = (
    '{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,'
    '"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_timeline_navigation_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,'
    '"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
    '"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,'
    '"responsive_web_twitter_article_tweet_consumption_enabled":false,'
    '"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,'
    '"standardized_nudges_misinfo":true,'
    '"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
    '"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,'
    '"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}'
)
USER_TWEETS_FEATURES = (
    '{"rweb_lists_timeline_redesign_enabled":true,'
    '"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,'
    '"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_timeline_navigation_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,'
    '"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
    '"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,'
    '"responsive_web_twitter_article_tweet_consumption_enabled":false,'
    '"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,'
    '"standardized_nudges_misinfo":true,'
    '"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
    '"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,'
    '"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}'
)
USER_TWEETS_FIELD_TOGGLES = '{"withAuxiliaryUserLabels":false,"withArticleRichContentState":false}'

SEARCH_FEATURES = (
    '{"rweb_video_screen_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,'
    '"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,'
    '"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_timeline_navigation_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"premium_content_api_read_enabled":false,'
    '"communities_web_enable_tweet_community_results_fetch":true,'
    '"c9s_tweet_anatomy_moderator_badge_enabled":true,'
    '"responsive_web_grok_analyze_button_fetch_trends_enabled":false,'
    '"responsive_web_grok_analyze_post_followups_enabled":true,'
    '"responsive_web_jetfuel_frame":false,"responsive_web_grok_share_attachment_enabled":true,'
    '"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,'
    '"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
    '"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,'
    '"responsive_web_twitter_article_tweet_consumption_enabled":true,'
    '"tweet_awards_web_tipping_enabled":false,'
    '"responsive_web_grok_show_grok_translated_post":false,'
    '"responsive_web_grok_analysis_button_from_backend":false,'
    '"creator_subscriptions_quote_tweet_preview_enabled":false,'
    '"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,'
    '"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
    '"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,'
    '"responsive_web_grok_image_annotation_enabled":true,"responsive_web_enhance_cards_enabled":false}'
)

TWEET_DETAIL_FEATURES = (
    '{"rweb_video_screen_enabled":false,"profile_label_improvements_pcf_label_in_post_enabled":true,'
    '"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,'
    '"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_timeline_navigation_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"premium_content_api_read_enabled":false,'
    '"communities_web_enable_tweet_community_results_fetch":true,'
    '"c9s_tweet_anatomy_moderator_badge_enabled":true,'
    '"responsive_web_grok_analyze_button_fetch_trends_enabled":false,'
    '"responsive_web_grok_analyze_post_followups_enabled":true,'
    '"responsive_web_jetfuel_frame":false,"responsive_web_grok_share_attachment_enabled":true,'
    '"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,'
    '"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
    '"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,'
    '"responsive_web_twitter_article_tweet_consumption_enabled":true,'
    '"tweet_awards_web_tipping_enabled":false,'
    '"responsive_web_grok_show_grok_translated_post":false,'
    '"responsive_web_grok_analysis_button_from_backend":false,'
    '"creator_subscriptions_quote_tweet_preview_enabled":false,'
    '"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,'
    '"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
    '"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,'
    '"responsive_web_grok_image_annotation_enabled":true,"responsive_web_enhance_cards_enabled":false}'
)
TWEET_DETAIL_FIELD_TOGGLES = (
    '{"withArticleRichContentState":true,"withArticlePlainText":false,'
    '"withGrokAnalyze":false,"withDisallowedReplyControls":false}'
)

# 下载后缀白名单 (orig 模式用于校验原图扩展名)
VALID_SUFFIX = {"jpg", "jpeg", "png", "webp", "gif"}


class TwitterClient:
    """鉴权 + 异步 HTTP 核心基类。"""

    def __init__(
        self,
        cookie: str,
        save_path: Optional[str] = None,
    ):
        """cookie 为鉴权 cookie (含 auth_token + ct0); save_path 为下载根目录。"""
        self.config = load_config()
        self.save_path = save_path

        cookie = (cookie or "").strip()
        self.auth_token = extract_cookie_field(cookie, "auth_token")
        self.ct0 = extract_cookie_field(cookie, "ct0")
        if not self.auth_token or not self.ct0:
            raise AuthError("cookie 中缺少 auth_token 或 ct0 字段")

        self._headers = {
            "user-agent": USER_AGENT,
            "authorization": BEARER_TOKEN,
            "cookie": cookie,
            "x-csrf-token": self.ct0,
        }
        # _session 在末尾才赋值, 中间任意一步抛 AuthError 都不会泄漏半成品连接
        self._session: Optional[httpx.AsyncClient] = None
        self._session = httpx.AsyncClient(headers=self._headers, trust_env=True)

        self.request_count = 0   # API 请求计数
        self.download_count = 0  # 文件下载计数
        self._rest_id_cache: Dict[str, str] = {}
        # transaction 头生成器懒加载, 用锁保护并发首次构建
        self._transaction = None
        self._transaction_lock: Optional[asyncio.Lock] = None

    # ---- 工具 ----

    @staticmethod
    def quote_url(url: str) -> str:
        """转义 URL 中的花括号 (GraphQL 路径里出现 {x} 时需要)。"""
        return url.replace("{", "%7B").replace("}", "%7D")

    # ---- 请求核心 ----

    async def get_json(
        self,
        url: str,
        referer: Optional[str] = None,
        transaction: bool = False,
    ) -> Any:
        """统一 GET 请求入口: 计数 + 异常检测 + JSON 解析。

        - referer: 可选 referer 头
        - transaction: SearchTimeline 等接口需要 x-client-transaction-id 校验头
        """
        headers = {}
        if referer:
            headers["referer"] = referer
        if transaction:
            # _transaction_lock 在第一次用到时才建, 避免在 __init__ 里绑 event loop
            if self._transaction_lock is None:
                self._transaction_lock = asyncio.Lock()
            if self._transaction is None:
                from .transaction import TransactionGenerator
                self._transaction = TransactionGenerator(self._headers["cookie"])
            # 锁保护懒构建的并发安全: 多协程同时首次调 transaction 头时只算一次
            async with self._transaction_lock:
                # 锁里再 await 一次构建, 已经在跑的构建会阻塞等结果, 不重复抓首页
                headers["x-client-transaction-id"] = await self._transaction.generate(url)
        try:
            # 正常路径下 _session 一定存在; 仅在被手动置 None 后才会为 None, 防御性判断
            if self._session is None:
                raise FetchError("客户端已关闭, 无法再发请求")
            response = await self._session.get(
                self.quote_url(url), headers=headers or None)
        except httpx.HTTPError as exc:
            raise FetchError(f"请求失败: {exc}") from exc
        self.request_count += 1

        text = response.text
        # 限流判定: 仅 HTTP 429 抛 RateLimitError; 子串匹配只作为兜底,
        # 避免在正常错误页里含 "Rate limit exceeded" 字样时被误判
        if response.status_code == 429:
            raise RateLimitError("API 请求次数已耗尽 (429 Rate limit exceeded)")
        if response.status_code == 401:
            raise AuthError(
                "认证失败 (401): 请检查 cookie 是否仍有效 "
                "(auth_token 与 ct0 可能已过期, 也可能是账号/IP 被风控)")
        if response.status_code != 200:
            # 非 200 但含限流提示: 当作 FetchError, 给出更明确的提示
            if "Rate limit exceeded" in text:
                raise RateLimitError(
                    f"响应提示 Rate limit 但状态码为 {response.status_code}: {text[:200]}")
            raise FetchError(f"HTTP {response.status_code}: {text[:200]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FetchError(f"响应不是有效 JSON: {text[:200]}") from exc

    # ---- 用户信息原始查询 ----

    async def get_user_raw(self, screen_name: str) -> Dict:
        """UserByScreenName 接口的原始 result 字典。"""
        variables = json.dumps(
            {"screen_name": screen_name, "withSafetyModeUserFields": False},
            separators=(",", ":"),
        )
        url = (
            f"{GRAPHQL_BASE}/{USER_BY_SCREEN_NAME_ENDPOINT}/UserByScreenName"
            f"?variables={variables}"
            f"&features={USER_BY_SCREEN_NAME_FEATURES}"
            f"&fieldToggles={USER_BY_SCREEN_NAME_FIELD_TOGGLES}"
        )
        data = await self.get_json(url, referer=f"https://twitter.com/{screen_name}")
        try:
            return data["data"]["user"]["result"]
        except (KeyError, TypeError) as exc:
            raise FetchError(f"无法解析用户 {screen_name} 的信息") from exc

    async def get_user_rest_id(self, screen_name: str) -> str:
        """用户名 -> 数字 ID, 带内存缓存。"""
        if screen_name in self._rest_id_cache:
            return self._rest_id_cache[screen_name]
        result = await self.get_user_raw(screen_name)
        try:
            rest_id = str(result["rest_id"])
        except KeyError as exc:
            raise FetchError(f"用户 {screen_name} 响应中缺少 rest_id") from exc
        self._rest_id_cache[screen_name] = rest_id
        return rest_id

    # ---- 生命周期 ----

    async def aclose(self) -> None:
        """关闭底层 HTTP 连接 (幂等, 重复调用安全)。"""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def __aenter__(self) -> "TwitterClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()