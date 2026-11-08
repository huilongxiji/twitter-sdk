# twitter_sdk

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

推特图片下载 SDK —— 提供异步 API 让你的项目直接拉取用户推文与媒体。

## ⚠️ 重要免责声明 (Disclaimer)

> **本项目仅为个人学习与技术研究用途。**
> 使用本 SDK 意味着你已阅读、理解并同意以下全部条款:

### 1. 内容来源与版权

**通过本 SDK 下载到本地的所有媒体内容 (图片 / 视频 / 动图 / 文本 / 元数据)**
**均为原作者及 X Corp. (下称"原作者") 的知识产权。**

- 下载的内容**不归本项目所有**,也**不归你所有**;
- 你必须在原作者规定的范围内使用,**不得**:
  - 用于任何**商业目的** (售卖、付费订阅、广告变现、付费下载等)
  - 冒充原作者发布、声称原创、用于 AI 训练集
  - 删除或修改原作者的水印 / 署名
  - 进行大规模爬取、二次分发、构建镜像
- 转载 / 引用请**注明原作者及出处链接**。

### 2. 服务条款合规

- 你**必须**同时遵守 **[X / Twitter 服务条款](https://twitter.com/tos)** 与你所在辖区的法律法规;
- 本项目采用官方 Guest API 接口,未绕过 X 的付费墙,但 X 保留随时变更接口或封禁账号的权利;
- 由此引发的账号封禁、数据丢失、IP 封禁等后果**由使用者自行承担**。

### 3. 无担保 (无担保)

- 本项目**按"原样"提供**,作者**明确否认**任何形式的明示或暗示担保;
- 作者**不承担**因使用本项目导致的任何直接、间接、偶然、特殊或惩罚性损害赔偿责任;
- 作者**不保证**项目能持续运行、不被 X 反爬措施影响、不出现中断或数据错误。

### 4. 衍生与署名义务

如果你修改、再分发本项目,或基于本项目开发应用,你**必须**在用户可见处保留:
- 原作者署名 (`huilongxiji`)
- 项目仓库链接 (`https://github.com/huilongxiji/twitter-sdk`)
- 协议标识 (`CC BY-NC-SA 4.0`)

完整声明请参见 [`LICENSE`](./LICENSE) 文件。

---

## 许可证与署名要求

本项目基于 **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** 协议发布。
使用、修改或再分发本项目时,你 **必须** 在用户可见的位置 (README / About / 启动画面) 保留
以下署名声明:

```
本项目使用了 huilongxiji 开发的软件
(https://github.com/huilongxiji/twitter-sdk),
遵循 CC BY-NC-SA 4.0 协议。
```

协议三项核心限制:
- **BY (署名)** — 必须保留原作者署名
- **NC (非商业)** — 不得用于商业目的
- **SA (同协议)** — 衍生作品必须以相同协议发布

## 特性

- **异步优先**：对外全部 `async` 方法，基于 `httpx.AsyncClient` 复用连接
- **TOML 静态配置**：`config.toml` 只存不经常变的数值（`SDKConfig.from_toml`）
- **动态参数注册**：cookie / 用户名 / 保存路径 / 并发数等一律在构造 class 或调用功能时传入
- **附加项注入**：视频、转推、likes 默认 `False`，调用时传 `True` 才生效
- **去重缓存**：按 `格式|URL` 记录已下载内容，只下新内容（断点续传），每账户独立缓存
- **继承式扩展**：`TwitterClient` 承接鉴权与请求，功能模块继承扩展
- 当前已实现：用户信息查询 + 图片/动图/视频下载 + 转推模式 + 去重缓存
  + **全部推文（含纯文本）** + **分享链接下载单条推文**

## 环境要求

**Python >= 3.10**。导入 SDK 时会做版本门禁校验，低于 3.10 直接抛 `RuntimeError`
（而不是等到 `import tomllib` 才报 `ModuleNotFoundError`）：

```text
RuntimeError: twitter_sdk 需要 Python 3.10+, 当前 3.9.6。请用 Python 3.10+ 重建虚拟环境。
```

`tomllib` 是 Python 3.11+ 才有的标准库，因此 3.10 环境下会自动回退到 `tomli`。

## 安装

```bash
pip install -r requirements.txt   # 需要 Python >= 3.10
```

## 快速开始

1. 调用 SDK（动态参数在构造时注册，静态配置默认用 SDK 内置 `config.toml`）：

```python
import asyncio
from twitter_sdk import MediaClient

async def main():
    # cookie 与保存路径属于动态参数, 直接在构造时注册
    async with MediaClient(
        cookie="auth_token=xxx; ct0=yyy;",
        save_path="./download",
    ) as client:
        # 用户信息查询
        info = await client.get_user_info("<screen_name>")
        print(info.name, info.rest_id, info.media_count)

        # 下载该用户媒体 (附加项默认 False, 需要时传 True)
        count = await client.download_user_media(
            "<screen_name>",
            concurrency=4,      # 同时进行的下载数量 (并发数)
            videos=True,        # 附加项: 同时下载视频
            retweets=False,     # 附加项: 含转推模式
            max_download=None,  # 本次总下载数量上限 (可选)
        )
        print(f"下载了 {count} 份")

asyncio.run(main())
```

## 分步测试

`../twitter_sdk_test.ipynb` 是全局变量驱动的分步测试文件：所有参数集中在第一个代码块，
**不读取任何配置文件**，按顺序执行即可逐项验证功能。

## 抓取全部推文（含纯文本）

`iter_user_media` 走 `UserMedia` 接口，服务端只返回含媒体的推文，纯文本推文会丢失。
`iter_user_tweets` 走 `UserTweets` 接口，**每条推文都产出** `TweetItem`，因此能拿到
视频 / 图片 / gif / 纯文本推文的全部内容：

```python
async with MediaClient(cookie="auth_token=...; ct0=...;") as client:
    async for t in client.iter_user_tweets("<screen_name>", retweets=False, like=False):
        print(t.time_str, t.author_screen_name, t.full_text[:40])
        for m in t.media:
            print("   ", m.media_type, m.media_url)
```

- `retweets=False`（默认）：只取原创推文，跳过转推
- `like=False`（默认）：不抓点赞；`like=True` 改走 `Likes` 接口（单页 200 条）
- `retweets` 与 `like` 互斥，同时开 `True` 抛 `ValueError`
- 含转推时 `author_name` / `author_screen_name` 为**原作者**，`is_retweet=True`

## 按分享链接下载单条推文

```python
# 只读取, 不下载
tweet = await client.fetch_tweet_by_url("https://x.com/xxx/status/1234567890?s=20")
print(tweet.full_text, [m.media_type for m in tweet.media])

# 直接下载该推文的视频 / 图片 / gif
count = await client.download_tweet("https://x.com/xxx/status/1234567890")

# 该推文下方的回复
async for reply in client.iter_thread_replies("https://x.com/xxx/status/1234567890"):
    print(reply.author_screen_name, reply.full_text[:40])
```

支持的链接形态：`twitter.com/xxx/status/123`、`x.com/xxx/status/123?s=20&t=xxx`、
`twitter.com/i/web/status/123`。单条推文下载**不写入去重缓存**，避免污染用户目录的断点续传记录。

1. 如需自定义静态配置，复制 `config.toml` 到你自己的路径并修改，然后构造时指定：

```python
client = MediaClient(cookie="...", config="我的config.toml")
```

静态配置的 `config` 参数兼容：`None`（用内置默认）/ TOML 路径字符串 / `SDKConfig` 对象 / dict。

## 配置说明

### 静态配置（`config.toml`，不经常变的数值）

| 字段 | 说明 | 默认 |
| --- | --- | --- |
| `time_range` | 时间范围 `"开始:结束"`，空为不限 | 不限 |
| `down_log` | 去重缓存开关（记录已下载内容） | `false` |
| `autoSync` | 自动同步最新内容 | `false` |
| `image_format` | `orig` / `jpg` / `png`（动图不受影响） | `jpg` |
| `log_output` | 下载过程日志 | `false` |
| `max_concurrent_requests` | 默认并发数（可调用时覆盖） | `8` |
| `md_output` | 输出 Markdown | `false` |
| `media_count_limit` | 单个 md 媒体链接上限（`0` 不限） | `350` |

### 动态参数（构造 / 调用时注册）

| 参数 | 位置 | 说明 |
| --- | --- | --- |
| `cookie` | 构造函数，必填 | 含 `auth_token` 与 `ct0` |
| `save_path` | 构造函数或方法参数 | 保存根目录（每账户自成一文件夹） |
| 用户名 | 方法参数 | 如 `get_user_info("<screen_name>")` |
| `videos` | 附加项，默认 `False` | `True` 时同时下载视频 |
| `retweets` | 附加项，默认 `False` | `True` 时含转推模式 |
| `deep` | 附加项，默认 `False` | `True` 时直接走搜索接口 (适合指定区间补档) |
| `auto_complete` | 附加项，默认 `True` | 默认模式下拉到接口深度上限后自动衔接搜索接口补全更老内容 (一次跑完即全部历史) |
| `concurrency` | 方法参数 | 同时进行的下载数量（并发数） |
| `max_download` | 方法参数 | 本次总下载数量上限（可选） |

### 去重与断点续传

- 缓存 key：图片为 `格式\|URL`，动图固定 `gif\|URL`，视频固定 `video\|URL`
- 每个账户独立缓存：`{save_path}/{用户名}/cache_data.log`
- 每次运行只下载新内容；下载成功立即记录，失败下次重试
- 换 `image_format` 后同图会以新格式重新下载（原文件保留）

## 异常

所有异常继承 `TwitterSDKError`：

- `ConfigError`：配置文件缺失 / TOML 解析失败
- `AuthError`：cookie 缺少 `auth_token` 或 `ct0`，或认证失败 (401)
- `RateLimitError`：当日 API 调用次数耗尽
- `FetchError`：请求或解析失败

## 扩展指南（后续功能模块）

所有功能模块都继承核心类接入，复用基类的鉴权与请求能力：

```python
from twitter_sdk import TwitterClient

class TagClient(TwitterClient):        # 未来的 Tag 搜索模块
    async def search(self, tag: str):
        data = await self.get_json(...)   # 复用统一请求入口
        ...
```

继承链：`TwitterClient`（鉴权+HTTP）→ `UserInfoClient`（用户信息）→
`MediaToolsMixin`（媒体判定与下载工具）→ `TweetClient`（全部推文 + 单条推文）→
`MediaClient`（用户媒体爬取与下载）。

因为 `MediaClient` 继承自 `TweetClient`，一个 `MediaClient` 实例即拥有全部能力。

## 路线图

- [x] 用户信息查询
- [x] 图片 / 动图 / 视频下载
- [x] 转推模式
- [x] 去重缓存（断点续传）
- [x] 全部推文（含纯文本）与 likes 模式
- [x] 分享链接下载单条推文
- [x] CSV / Markdown 输出
- [ ] 亮点模式、Tag 搜索、评论区、主页信息模块

## 免责声明

本项目仅供编程学习交流、学术研究及个人练习使用。所有媒体内容的知识产权归原作者及所属平台所有，请遵守当地法律法规及目标平台服务条款。

## 📄 关于 LICENSE 协议 (CC BY-NC-SA 4.0)

[`LICENSE`](./LICENSE) 文件包含本项目的**完整法律声明**, 核心是 [Creative Commons
署名-非商业性使用-相同方式共享 4.0 国际 (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) 协议。

### 简单来说这个协议允许你:

- ✅ **下载、学习、修改** 本项目源码
- ✅ **个人非商业使用** (例如备份你关注的画师 / 研究爬虫技术)
- ✅ **再分发** 本项目 (但必须**完全相同协议** + **保留署名**)

### 但你**不能**:

- 🚫 把本项目用于任何**商业目的** (集成到付费产品、收费 API、SaaS、付费课程等)
- 🚫 删除 / 隐匿原作者署名
- 🚫 用 MIT / Apache / 商业专有协议**重新打包**后再发布
- 🚫 单独使用本项目下载的内容用于商业变现 (这条与 X 服务条款一致)

### 它**不**包含:

- ⚠️ **你下载到的内容的版权** — 这些内容属于原作者及 X Corp.,`LICENSE` 文件只约束**源代码本身**。
  请参见上方"⚠️ 重要免责声明"第 1 条。
- ⚠️ **本 SDK 的稳定性保证** — 见上方第 3 条"无担保"。
- ⚠️ **运行本 SDK 需要的 cookie** — cookie 是你个人账号的凭证,不属于 SDK 的一部分,
  也**绝不能**随源码公开。

### 你 fork / 修改后必须保留的内容

```text
--------------------------------------------------------------------
本项目使用了 huilongxiji 开发的软件
(https://github.com/huilongxiji/twitter-sdk),
遵循 CC BY-NC-SA 4.0 协议。
Modifications: <describe what you changed>   ← 如果你改了源码,加这行
--------------------------------------------------------------------
```

> 一句话总结: **你可以白嫖这份代码做非商业的事, 但必须注明出处, 而且别拿这个去赚钱。**
