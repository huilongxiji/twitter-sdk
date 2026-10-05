# twitter_sdk/examples

8 个单文件最小示例, 每个可独立运行, 覆盖 SDK 的一项对外能力。

## 共通准备

1. 激活 Python 3.11 虚拟环境 (本 SDK 要求 Python 3.10+):
   ```bash
   source ../../.venv311/bin/activate
   ```

2. 准备 cookie (从浏览器 DevTools 复制):
   ```bash
   export TWITTER_COOKIE='auth_token=...; ct0=...;'
   ```

3. 跑任意示例:
   ```bash
   .venv311/bin/python twitter_sdk/examples/01_get_user_info.py
   ```

未设 cookie 时示例会立即 `SystemExit("请先 export TWITTER_COOKIE=...")`, 不会真发请求。

## 文件清单

| 文件 | 教什么 | 先看哪里 |
| --- | --- | --- |
| `01_get_user_info.py` | 拿用户基础档案 | `# ===== 3. 打印结果` 注释 |
| `02_download_user_media.py` | 一键下载某用户全部媒体 | docstring 中"自动补档"段 |
| `03_iter_user_media.py` | 流式遍历媒体 | 顶部 docstring |
| `04_iter_user_tweets.py` | 流式遍历全部推文 (含转推切换) | `show()` 函数 |
| `05_fetch_tweet_by_url.py` | 根据分享链接抓单条推文 | 顶部 docstring |
| `06_download_tweet.py` | 下载单条推文的媒体 | 顶部 docstring |
| `07_iter_thread_replies.py` | 遍历某条推文下方的回复 | 顶部 docstring |
| `08_with_cache.py` | 断点续传 | `cache_key` 函数 |

## 调通任一文件后, 其余只要改 URL/用户名

- `01~04`: `"<screen_name>"` 改成你想看的用户名
- `05~07`: `TWEET_URL` 改成具体推文链接或数字 ID
- `02` 的 `save_path`: 改成你期望的下载根目录

## 出错怎么办

- `AuthError (401)`: cookie 已过期, 重新从浏览器复制
- `RateLimitError (429)`: IP 短时间请求过多, 隔天再试或换 cookie
- `FetchError (HTTP 4xx/5xx)`: GraphQL endpoint hash 可能失效, 看主 README
- `RuntimeError: twitter_sdk 需要 Python 3.10+`: 用 `.venv311` (Python 3.11), 不要用 Python 3.9 的 `.venv`