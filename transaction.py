"""TransactionGenerator —— x-client-transaction-id 异步生成器。

SearchTimeline 等接口要求请求携带 x-client-transaction-id 校验头, 该 id 需
从 X 登录态首页引用的 on-demand JS 文件动态计算 (抓首页 -> 解析 ondemand.s
-> 生成 id)。懒构建, 首次 await generate() 时才下载。
"""

import asyncio
import re
from typing import Optional

import bs4
import httpx
from x_client_transaction import ClientTransaction
from x_client_transaction.utils import generate_headers, get_ondemand_file_url


class TransactionGenerator:
    """为每个请求生成有效的 x-client-transaction-id, 异步不阻塞 event loop。"""

    def __init__(self, cookie: str):
        self.cookie = cookie
        self._ct: Optional[ClientTransaction] = None
        # 保护懒构建的并发安全: 多个 await generate 同时触发时只跑一次首页抓取
        self._lock = asyncio.Lock()

    async def _build(self) -> ClientTransaction:
        # 快速路径: 已构建过直接返回, 避免每次都抢锁
        if self._ct is not None:
            return self._ct
        async with self._lock:
            # 抢到锁后再判一次, 防止并发下重复构建
            if self._ct is not None:
                return self._ct
            # 登录态首页才有 on-demand 引用, 因此必须带 cookie
            async with httpx.AsyncClient(
                    headers=generate_headers(), follow_redirects=True) as session:
                session.headers["cookie"] = self.cookie
                home_resp = await session.get("https://x.com")
                home_soup = bs4.BeautifulSoup(home_resp.content, "html.parser")
                ondemand_url = get_ondemand_file_url(home_soup)
                ondemand_resp = await session.get(ondemand_url)
                ondemand_soup = bs4.BeautifulSoup(ondemand_resp.content, "html.parser")
            self._ct = ClientTransaction(home_soup, ondemand_soup)
            return self._ct

    async def generate(self, url: str) -> str:
        """根据请求 URL 生成 x-client-transaction-id (异步)。"""
        ct = await self._build()
        path = re.findall(r"https?://(?:twitter|x)\.com(.*?)\?", url)[0]
        return ct.generate_transaction_id(method="GET", path=path)