"""UserInfoClient —— 用户基本信息查询。"""

from .client import TwitterClient
from .exceptions import FetchError
from .models import UserInfo


class UserInfoClient(TwitterClient):
    """继承 TwitterClient, 提供用户信息查询能力。"""

    async def get_user_info(self, screen_name: str) -> UserInfo:
        """查询用户基本信息。

        返回 UserInfo: screen_name / rest_id / name / statuses_count / media_count
        """
        result = await self.get_user_raw(screen_name)
        try:
            legacy = result["legacy"]
            return UserInfo(
                screen_name=screen_name,
                rest_id=str(result["rest_id"]),
                name=legacy.get("name", ""),
                statuses_count=int(legacy.get("statuses_count") or 0),
                media_count=int(legacy.get("media_count") or 0),
            )
        except (KeyError, TypeError) as exc:
            raise FetchError(f"解析用户 {screen_name} 信息失败") from exc