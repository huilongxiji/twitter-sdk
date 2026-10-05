"""MdGen —— 推文 Markdown 记录。

按用户输出 Markdown 文件, 记录下载的每条推文:
- 年月标题、作者与时间、推文正文、媒体标签 (图片/视频)
- 同一推文的多张媒体合并显示
- 媒体数量超过 media_count_limit 时自动分文件
"""

import os
import re
from datetime import datetime
from typing import List, Optional

from .models import MediaItem
from .utils import stamp2time


class MdGen:
    """单个用户的推文 Markdown 记录器。"""

    def __init__(
        self,
        save_path: str,
        user_name: str,
        screen_name: str,
        tweet_range: str,
        media_count_limit: int = 0,
    ):
        file_name = f'{screen_name}-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}_1.md'
        self.f = open(os.path.join(save_path, file_name), "w", encoding="utf-8-sig", newline="")
        self.f.write(f"{user_name} {screen_name}\n")
        self.f.write(f"Tweet Range: {tweet_range}\n")
        self.f.write(f"Save Path: {save_path}\n")

        self.save_path = save_path
        self.user_name = user_name
        self.screen_name = screen_name
        self.tweet_range = tweet_range
        self.media_count_limit = media_count_limit  # 单个 md 最大媒体数 (0 不限)

        self.current_tweet_id = ""   # 当前推文 id, 用于合并同推文的多媒体
        self.current_footer = ""     # 当前推文互动数据 (输出于下一条推文之前)
        self.current_month = ""      # 当前年月标题
        self.file_media_count = 0    # 当前文件中的媒体数量
        self.file_count = 1          # 已输出的文件数量

    def close(self) -> None:
        """结束写入 (输出最后一条推文的互动数据)。"""
        self.f.write("\n" + self.current_footer + "\n")
        self.f.close()

    def record_media(self, media_item: MediaItem, file_name: str) -> None:
        """记录一条媒体 (下载任务创建时调用, 保证推文顺序)。"""
        fixed_filename = file_name.replace(" ", "%20")
        fixed_timestr = media_item.time_str
        current_month = fixed_timestr[:7]

        tweet_id = ""
        match = re.findall(r"status/(\d+)", media_item.expanded_url)
        if match:
            tweet_id = match[0]

        display_name = media_item.author_name or self.user_name
        screen_name = media_item.author_screen_name or self.screen_name

        if self.current_tweet_id != tweet_id or not tweet_id:
            # 切换到下一条推文, 先输出上一条的互动数据
            self.f.write(f"\n{self.current_footer}\n\n" if self.current_footer else "")

            # 媒体数量超限 -> 分文件; 续写后必须重置月份标题, 否则第一条推文若
            # 和上一文件同月, 就不会再写 "## {month}" 标题, 排版错乱
            if self.media_count_limit > 0 and self.file_media_count >= self.media_count_limit:
                self.f.close()
                self.file_media_count = 0
                self.file_count += 1
                new_name = (f'{self.screen_name}-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}'
                            f'_{self.file_count}_{current_month}.md')
                self.f = open(os.path.join(self.save_path, new_name), "w", encoding="utf-8-sig", newline="")
                self.f.write(f"{self.user_name} {self.screen_name}\n")
                self.f.write(f"Tweet Range: {self.tweet_range}\n")
                self.f.write(f"Save Path: {self.save_path}\n\n")
                self.current_month = ""

            # 年月标题
            if not media_item.is_retweet and current_month != self.current_month:
                self.f.write(f"## {current_month}\n")
                self.current_month = current_month

            # 推文头: 转推标注 + 作者 + 时间 + 链接 + 正文
            retweet_mark = f"*{self.user_name} retweeted*\n" if media_item.is_retweet else ""
            self.f.write(
                f"{retweet_mark}{display_name} @{screen_name} · {fixed_timestr}"
                f" [src]({media_item.expanded_url})\n")
            self.f.write(media_item.full_text + "\n")

            self.current_tweet_id = tweet_id
            self.current_footer = (f'{media_item.favorite_count} Likes, '
                                   f'{media_item.retweet_count} Retweets, '
                                   f'{media_item.reply_count} Replies')

        # 媒体标签
        if media_item.media_type == "video":
            self.f.write(f'<video src="{fixed_filename}" controls></video>\n')
        else:
            self.f.write(f'[![]({fixed_filename})]({media_item.media_url})\n')
        self.file_media_count += 1