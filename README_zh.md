<div align="center">

```
  ┌─────────────────────────────────────────┐
  │   silent-browser-use                    │
  │   ─ 让 agent 用你登过的 Chrome 干活 ─   │
  └─────────────────────────────────────────┘
```

# silent-browser-use

**让 Claude / GPT 用你的真实浏览器干活,登过的网站永久有效。**
[agent-browser](https://github.com/vercel-labs/agent-browser) 的 Python 伴侣工具包 —— 持久化 Chrome、自动登录流程、Pythonic 封装。

[![PyPI version](https://img.shields.io/pypi/v/silent-browser-use.svg)](https://pypi.org/project/silent-browser-use/)
[![Python](https://img.shields.io/pypi/pyversions/silent-browser-use.svg)](https://pypi.org/project/silent-browser-use/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![agent-browser](https://img.shields.io/badge/built_on-agent--browser-black.svg)](https://github.com/vercel-labs/agent-browser)
[![GitHub stars](https://img.shields.io/github/stars/Jcxu97/silent-browser-use?style=social)](https://github.com/Jcxu97/silent-browser-use/stargazers)

[English](README.md) · [中文](README_zh.md)

</div>

---

## 这是什么

> **一句话:agent-browser 很牛,但它默认开一个"无痕 Chrome",你登过的 B 站、知乎、Nexus、GitHub 全失效。
> silent-browser-use 给它装上你的真实浏览器,登一次永久生效。**

[agent-browser](https://github.com/vercel-labs/agent-browser) 是 Vercel Labs 开源的 Rust 命令行工具,让 LLM agent 操作浏览器。它默认启动一个干净的 Chrome-for-Testing,做 CI 完美,做"打开我的小红书,登 Nexus 下载 mod,刷我的知乎"就很难受 —— 每次都要重新登录。

**silent-browser-use** 是个小巧的 Python 工具包,**和 agent-browser 并排站,不是替代品**,补两件事:

- **专属 Chrome 窗口**:启动一次,常驻在 `--remote-debugging-port=9222`,有自己独立的 profile 目录。Google、GitHub、Nexus、B 站、知乎、网银 —— 任何你登过的,**永久有效**。
- **自动登录编排**:agent 撞到登录墙时,silent-browser-use 自动把窗口呼到前台,等你输完密码,登成功的瞬间窗口隐去。**全程不用动鼠标,只动键盘。**
- **Pythonic API**(`open_url` / `click` / `fill` / `snapshot`),把 agent-browser CLI 包装成子进程调用。upstream 升级?我们自动跟随,不需要维护 fork。
- **垂直案例**:BG3 Nexus mod 抓取、BG3 mod 汉化流水线、B 站 / 知乎 / 小红书数据抓取、电商多页流程,都给现成代码。

我们**不 fork** agent-browser,**不竞争**,只让它在你真实生活里好用。

---

## 30 秒看 demo

<!-- TODO: 录 GIF/asciinema 替换 -->

```text
[GIF 占位] sbu install → sbu login nexusmods.com →
          python -c "from silent_browser_use import open_url; open_url('https://nexusmods.com')"
          → 自动是登录态,agent 直接干活
```

```python
from silent_browser_use import open_url, click, fill, snapshot

# 自动复用专属 Chrome (端口 9222)
# 之前在这个 profile 登过 Nexus,现在还是登录态
open_url("https://www.nexusmods.com/baldursgate3/mods/12345")

shot = snapshot()                     # ARIA 树 + 截图
click(role="link", name="Files")
print(snapshot().text)                # 把页面文本喂给 agent
```

整个心智模型就这么大。剩下的脏活我们藏起来。

---

## 为什么用 silent-browser-use?

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    你的代码 / agent (Python / Claude / GPT-4o / ...)     │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              silent-browser-use  (本仓,纯 Python)                       │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│   │  Pythonic 封装   │  │  Profile 管理    │  │  自动登录流程        │   │
│   │  open_url/click  │  │  9222 端口守护   │  │  呼出窗口 → 等密码  │   │
│   └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘   │
└────────────┼─────────────────────┼──────────────────────┼────────────────┘
             ▼ subprocess          ▼ 启动/重连            ▼ OS 信号
┌──────────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│ agent-browser (Rust) │    │  专属 Chrome         │    │  你的键盘       │
│  vercel-labs CLI     │◀──▶│  --user-data-dir     │◀──▶│  输密码,不点鼠标 │
│  (CDP 客户端)        │ CDP│  --remote-debugging  │    │                 │
└──────────────────────┘    └──────────────────────┘    └─────────────────┘
```

三件事值得注意:

1. **agent-browser 干所有重活** —— DOM 序列化、ARIA 快照、点击/填表、截图。我们一行都不重写。
2. **Chrome 是你的。** 独立 Chrome 实例,独立 profile 目录。有 cookie、有 IndexedDB、有扩展、能跨重启活。
3. **自动登录流程**就是核心黑魔法:脚本撞到登录页时,我们把窗口呼到前台,你输密码,我们隐窗口。Cookie 永久存活,后面 1000 次跑都是登录态。

---

## 安装

```bash
pip install silent-browser-use
sbu install        # 自动装 agent-browser,配好专属 Chrome profile
```

`sbu install` 是幂等的:

1. 没有 `agent-browser` 二进制就装一份(走上游官方 installer)。
2. 找到系统 Chrome(没有就下载 Chrome-for-Testing 兜底)。
3. 在 `~/.silent-browser-use/chrome-profile/` 建一个 profile 目录。
4. 9222 端口起 Chrome,写 PID 文件防重复启动。

支持 **Windows 10/11、macOS 13+、Ubuntu 22.04+**。Python 3.10+。

---

## 快速上手

### 1. 用真实登录态打开页面

```python
from silent_browser_use import open_url

open_url("https://www.bilibili.com")    # 之前登过就还是登录态
```

### 2. 登一次,永久有效

```bash
sbu login nexusmods.com
# 弹出窗口,你输密码 / 过 2FA,窗口自动收起
# 之后每次跑脚本都是登录态
```

```bash
sbu login zhihu.com
sbu login xiaohongshu.com
sbu login bilibili.com
```

### 3. 操作页面

```python
from silent_browser_use import open_url, click, fill, snapshot

open_url("https://github.com/login")
fill(role="textbox", name="Username", value="octocat")
fill(role="textbox", name="Password", value="…")
click(role="button", name="Sign in")
print(snapshot().text)
```

### 4. 跑 agent 任务

```bash
sbu run "在 Nexus 上找 ID 12345 的 BG3 mod,把简介翻译成中文打印出来"
```

底层:我们把 prompt 转给 agent-browser,它通过 CDP 连到你的专属 Chrome。你保持登录,agent 干活。

---

## 核心特性

- **持久化 profile** —— cookie / localStorage / 扩展全部跨重启活。
- **一次登录** —— `sbu login <域名>` 弹窗等你登,登完自动收。不用脚本去硬磕 2FA。
- **Pythonic 封装** —— `open_url` / `click` / `fill` / `snapshot` / `wait_for` / `screenshot` / `goto` / `eval_js`。看 [examples/](examples/)。
- **CLI 对齐** —— `sbu run "<prompt>"` 和 agent-browser 的 `run` 等价,但默认用你的 profile。
- **单窗口 / 单端口** —— 设计上不会乱开标签页到别的窗口。多 tab 编排是 opt-in 的。
- **快照优先** —— `snapshot()` 一次返回 ARIA 树 + ref + 截图。借鉴 browser-use 的 snapshot-first 范式。
- **垂直案例** —— `examples/bg3_nexus_scrape.py`、`examples/bg3_mod_translate.py`、`examples/bilibili_subtitles.py`、`examples/zhihu_question.py`、`examples/xiaohongshu_feed.py` 全部开箱即用。

---

## silent-browser-use vs 替代品

| 能力                                    | 单用 agent-browser | playwright | silent-browser-use |
| --------------------------------------- | :----------------: | :--------: | :----------------: |
| LLM prompt 驱动 Chrome                  |         ✅         |     —      |   ✅ *(走 agent-browser)* |
| 持久化 profile / 真实登录态             |         —          |     ⚠️[^1] |          ✅        |
| 自动启动 / 重连同一个 Chrome            |         —          |     —      |          ✅        |
| 自动登录流程(弹窗 → 等密码 → 隐窗口)|         —          |     —      |          ✅        |
| Python 封装                             |         —          |     ✅     |          ✅        |
| ARIA 快照 + 截图一次出                  |         ✅         |     ⚠️     |          ✅        |
| 反指纹 / stealth                        |         —          |     ⚠️     |          —[^2]     |
| 多浏览器 (Firefox / WebKit)             |         —          |     ✅     |          —         |
| 适合 CI / 无登录态自动化                |         ✅         |     ✅     |          —         |
| 适合"用我自己的账号"自动化              |         —          |     —      |          ✅        |

[^1]: Playwright 支持 persistent context,但 profile 管理、端口固定、登录交互都得你自己拼。
[^2]: 反指纹不在我们 scope。要 stealth 用 [rebrowser-patches](https://github.com/rebrowser/rebrowser-patches)。我们的目标是"你的浏览器",不是匿名爬虫。

> **直接用 agent-browser**:CI、无登录态、纯净环境。
> **用 silent-browser-use**:把你的真实账号、Cookie、登录态带进 agent 流程。

---

## 高频食谱

所有食谱默认你已经跑过 `sbu install`。

### 食谱 1 — 打开、点击、填表(经典首杀)

```python
from silent_browser_use import open_url, fill, click, snapshot

open_url("https://www.bing.com")
fill(role="searchbox", name="搜索", value="agent-browser vercel labs")
click(role="button", name="搜索")
print(snapshot().text[:500])
```

### 食谱 2 — 登一次,跑一辈子(Nexus / B 站 / 知乎都行)

```bash
sbu login nexusmods.com
# 窗口呼出,你正常 SSO / 邮箱登录,窗口隐去
```

```python
from silent_browser_use import open_url, snapshot

open_url("https://www.nexusmods.com/users/myaccount")
print(snapshot().text)         # 直接是登录态
```

Cookie 全在 `~/.silent-browser-use/chrome-profile/`。删目录 = 全部退登。

### 食谱 3 — 抓 Nexus mod 详情(BG3 场景)

```python
from silent_browser_use import open_url, snapshot, click

def fetch_mod(mod_id: int) -> dict:
    open_url(f"https://www.nexusmods.com/baldursgate3/mods/{mod_id}")
    s = snapshot()
    title = s.find(role="heading", level=1).text
    desc  = s.find(role="region", name="Description").text
    click(role="link", name="Files")
    s2 = snapshot()
    files = [el.text for el in s2.all(role="listitem")]
    return {"id": mod_id, "title": title, "desc": desc, "files": files}

print(fetch_mod(12345))
```

因为你跑过 `sbu login nexusmods.com`,**付费下载链接、成人内容标记、premium 速度全部自动生效**。批量抓 mod 做汉化字典?日常操作。

### 食谱 4 — 多页翻页 + 断点续抓

```python
from silent_browser_use import open_url, snapshot, click, wait_for
import json, pathlib

out = pathlib.Path("nexus.jsonl").open("a", encoding="utf-8")

open_url("https://www.nexusmods.com/baldursgate3/mods/?BH=0")
while True:
    for card in snapshot().all(role="article"):
        out.write(json.dumps({"title": card.text}, ensure_ascii=False) + "\n")
    nxt = snapshot().find(role="link", name="Next")
    if not nxt:
        break
    click(ref=nxt.ref)
    wait_for(role="article")     # SPA 跳转
```

### 食谱 5 — SPA 等渲染 + 截图

```python
from silent_browser_use import open_url, wait_for, screenshot

open_url("https://www.zhihu.com/question/12345")
wait_for(role="article", timeout=15)
screenshot("zhihu-question.png")
```

### 食谱 6 — BG3 mod 汉化流水线雏形

```python
from silent_browser_use import open_url, snapshot
from your_translator import translate_to_zh   # 你自己的翻译函数

def harvest(mod_id):
    open_url(f"https://www.nexusmods.com/baldursgate3/mods/{mod_id}")
    s = snapshot()
    en = {
        "title": s.find(role="heading", level=1).text,
        "desc":  s.find(role="region", name="Description").text,
    }
    return {"en": en, "zh": {k: translate_to_zh(v) for k, v in en.items()}}
```

完整 pipeline(扔进 bg3-mod-translator 字典 + 生成汉化 pak)在 `examples/bg3_mod_translate.py`。

### 食谱 7 — B 站视频字幕抓取

```python
from silent_browser_use import open_url, snapshot

open_url("https://www.bilibili.com/video/BV1xx411c7XX")
s = snapshot()
title = s.find(role="heading", level=1).text
print("视频标题:", title)
# 字幕/弹幕走 agent-browser 的 eval_js + bilibili API
```

参考 `examples/bilibili_subtitles.py`(配合 [vlv](https://github.com/Jcxu97/vlv) 多媒体工具箱效果更好)。

---

## CLI 速查

```text
sbu install                 # 一键装环境:agent-browser + 专属 Chrome
sbu start                   # 确保专属 Chrome 在 9222 端口跑着
sbu stop                    # 关闭专属 Chrome (profile 保留)
sbu status                  # 显示端口、PID、profile 路径、agent-browser 版本
sbu login <域名>            # 弹窗给你登录,登完自动收
sbu run "<prompt>"          # 把 prompt 喂给 agent-browser,默认用你的 profile
sbu open <url>              # 命令行版 `open_url`
sbu doctor                  # 自检 chrome / 端口 / agent-browser / profile
```

`sbu --help` 查全集。

---

## 架构细节

```
┌────────────────────────────────────────────────────────────────────────┐
│  你的脚本  ──►  silent_browser_use.open_url("…")                       │
│                            ▼                                           │
│                  ProfileManager.ensure_running()                       │
│                            ▼                                           │
│        ┌──────────────────────────────────────────┐                    │
│        │  Chrome (你的二进制 / 你的 profile 目录)│                    │
│        │  --remote-debugging-port=9222            │                    │
│        └────────────┬─────────────────────────────┘                    │
│                     ▼  CDP                                             │
│        ┌──────────────────────────────────────────┐                    │
│        │  agent-browser CLI  (子进程)             │                    │
│        │  --connect=ws://…:9222                   │                    │
│        └──────────────────────────────────────────┘                    │
└────────────────────────────────────────────────────────────────────────┘
```

设计取舍:

- **一个 Chrome、一个端口。** 所有 Python helper 走单例 `BrowserSession`,不会乱开孤儿标签页。
- **subprocess 而非 FFI**。我们直接 `subprocess.Popen(["agent-browser", "connect", "--ws", "ws://…"])` 流 JSON 出来。upstream 出新版,你升级二进制我们自动跟随。
- **Profile 在 `~/.silent-browser-use/chrome-profile/`**。和普通 Chrome profile 一样可以备份。删 = 全部退登。
- **PID 文件锁**。`~/.silent-browser-use/chrome.pid` 防止重复启动,`sbu start` 幂等。
- **没有后台定时器**。Chrome 跨运行常驻,但我们不会偷偷 ping 它。要关就 `sbu stop`。

---

## FAQ

**Q: 跟 agent-browser 啥关系?**
A: agent-browser *是* 引擎,我们是它的 Python 伴侣。我们(a)管你的持久化 Chrome,(b)给 Python API,(c)做自动登录流程。**完全不替代,完全不 fork**,subprocess 调用而已。

**Q: 我登过 Nexus / B 站,会被封号吗?**
A: 这工具跟"反爬"半毛钱关系没有。它就是你的真实 Chrome 加你的真实 cookie,跟你装一个油猴脚本没区别。要做好公民:尊重 robots.txt、限速、别去捅 rate limit。如果某网站 ToS 禁止自动化访问,别拿这个工具去硬刚。

**Q: Headless 吗?**
A: 默认不是 —— 全套设计就是你能看到的真实浏览器。`sbu start --headless` 也能跑,但自动登录流程就废了。要 headless CI 直接用 agent-browser 就行。

**Q: macOS / Linux / Windows 全支持?**
A: 全支持。macOS 13+、Ubuntu 22.04+、Windows 10/11。WSL2 能跑但 cookie 在 WSL 里,别指望 Windows Chrome 共享。

**Q: 我的 Chrome profile 会同步到 Google 吗?**
A: 只要你不在专属 profile 里登 Google 同步就不会。默认是个全新、未同步的 profile,跟你的日常 Chrome 完全隔离。

**Q: 能用我日常的 Chrome profile 吗?**
A: 强烈不建议。CDP(9222 端口)需要 Chrome 用特定 flag 启动,跟日常浏览混用容易崩、丢标签页。专属 profile 才几 MB,隔离干净更省心。

**Q: 支持 Firefox / WebKit 吗?**
A: 不支持。agent-browser 只走 CDP,我们也只走 CDP。

**Q: 撞到验证码怎么办?**
A: agent 撞到验证码时,自动登录流程把窗口呼出,你过验证码,agent 继续。和登录是同一套机制。

**Q: API 稳定吗?**
A: 现在 `0.1.x`,1.0 之前可能有 break change,先 pin 版本。CLI 表面(`sbu install` / `sbu login` / `sbu run`)我们打算先稳定下来。

**Q: 跟国内浏览器(360 / QQ / Edge 中国版)兼容吗?**
A: 只要它们底层是 Chromium 且支持 `--remote-debugging-port`,理论上能。我们没逐一测试,中文社区欢迎报告兼容情况。

---

## Roadmap

- [ ] `sbu install` 跨平台 agent-browser 安装器
- [ ] `sbu doctor` 健康检查
- [ ] 自动登录窗口呼出 / 隐藏在 macOS / Linux 上的细节打磨
- [ ] 食谱:BG3 Nexus、BG3 mod 汉化、B 站字幕、知乎、小红书
- [ ] 多 profile 切换(`sbu profile use bg3` / `sbu profile use bilibili`)
- [ ] 异步 API(`from silent_browser_use.aio import open_url`)
- [ ] `sbu record` —— 手动点几下,自动生成 Python 脚本

PR 欢迎,见下方贡献部分。

---

## 中文社区贡献

我们**特别欢迎**以下 PR(中文 issue / PR 描述完全 OK,我们会认真读):

- **中文垂直案例食谱**:B 站、知乎、小红书、京东、淘宝、Nexus 中文站、Steam、米哈游、起点 ……。抓得干净的脚本扔进 `examples/zh/`,我们带着改进合并。
- **BG3 mod 汉化流水线** 案例(配合 [bg3-mod-translator](https://github.com/Jcxu97/bg3-mod-translator) 之类的工具)。
- **中文文档改进**:任何能让下一个中文开发者少踩坑的内容。
- **国产 Chromium 浏览器(Edge 中国版 / 360 极速 / QQ 浏览器)** 兼容性报告 / 适配补丁。

```bash
git clone https://github.com/Jcxu97/silent-browser-use
cd silent-browser-use
pip install -e ".[dev]"
pytest
```

对上游友好:bug 在 agent-browser 那边就去[他们仓](https://github.com/vercel-labs/agent-browser/issues)报。

---

## 致谢

silent-browser-use 站在以下项目的肩膀上:

- **[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)** —— 真正的浏览器自动化引擎。Apache 2.0。没有它这个仓就是个空壳。我们不 fork,subprocess 调用。
- **[browser-use/browser-harness](https://github.com/browser-use/browser-use)** —— "持久化 agent 窗口"设计范式(单窗口、多 session、snapshot-first)启发了我们整个 UX。MIT。
- **[Playwright](https://playwright.dev)** & **[Puppeteer](https://pptr.dev)** —— 老前辈,很多 helper 函数签名跟它们押韵。
- **中文 mod / agent 开发者社区** —— 一直在喊"让我用我自己的 Chrome,别每次重开干净环境",这整个仓库就是你们的 feature request 兑现版。

完整引用见 [NOTICE](NOTICE)。

---

## License

[MIT](LICENSE) © AKAK 与贡献者。

`agent-browser` 由 Vercel Labs 与贡献者按 Apache 2.0 协议发布。我们以子进程方式调用其 CLI,不重新分发其源码。

---

<div align="center">

**给所有被登录页卡住的 agent。**
帮你省了一小时?顺手点个 ★

[报 issue](https://github.com/Jcxu97/silent-browser-use/issues) ·
[agent-browser](https://github.com/vercel-labs/agent-browser) ·
[English README](README.md)

</div>
