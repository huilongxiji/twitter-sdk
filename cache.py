"""DownloadCache —— 已下载媒体去重缓存 (JSON 持久化)。

每个账户的缓存独立存放在该账户的下载文件夹:
    {save_path}/cache_data.log
用 JSON 而非 pickle: key 全是字符串; 文本格式便于 cat / jq 排错; 不识别
的数据格式 (历史 pickle 残留等) 读不出来按空集合处理, 让其自然重建。
"""

import json
import os
from typing import Set


class DownloadCache:
    """记录已下载的媒体 key, 实现断点续传。"""

    def __init__(self, save_path: str):
        self.cache_path = os.path.join(save_path, "cache_data.log")
        self.cache_data: Set[str] = self._load(self.cache_path)

    @staticmethod
    def _load(path: str) -> Set[str]:
        """加载缓存, 任何异常 (文件不存在 / JSON 解析失败 / 数据类型不对) 都按空集合处理。"""
        if not os.path.exists(path):
            return set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return set()
        if not isinstance(raw, list):
            return set()
        # 防御性: 只保留字符串 key
        return {item for item in raw if isinstance(item, str)}

    def contains(self, key: str) -> bool:
        """该 key 是否已下载过。"""
        return key in self.cache_data

    def add(self, key: str) -> None:
        """记录该 key 已下载。"""
        self.cache_data.add(key)

    def close(self) -> None:
        """持久化到磁盘 (JSON 格式)。"""
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(sorted(self.cache_data), f, ensure_ascii=False)

    def __enter__(self) -> "DownloadCache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()