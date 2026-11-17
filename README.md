# B 站视频到 Obsidian

[English guide](README.en.md)

把一条 B 站视频变成可以回查原话的学习笔记，再用积累的方法回答投资问题。三个技能可以分开调用。字幕、笔记和投资记录都保存在自己的 Obsidian 知识库中。

| 什么时候用 | 发给助手 | 得到什么 |
| --- | --- | --- |
| 看完一条视频 | 粘贴视频链接、BV 号、`b23.tv` 短链或只附一条视频的动态 | 带时间戳的全文字幕，以及合并进已有笔记的 1～3 个学习要点。未指定集数的多 P 视频先选分集。 |
| 已积累几条或几十条视频 | **更新投资核心文件** | 《投资推演核心框架》整理可复用的方法，《决策问题与证据导航》指向细笔记。再次调用时处理新增或修改的材料。 |
| 有具体的投资问题 | **用知识库推演，下个月的新增资金适合买什么？** | 从核心方法回查细笔记，默认查最新公开资料。独立质询者先挑战每项判断，再复核修订稿。答复列出依据、仍有的分歧和改判条件。 |

## 先准备 Obsidian

1. 准备一个**本机可读写的文件夹**作为知识库。安装后，在 Obsidian 的库管理器中选「打开本地仓库 / Open folder as vault」，选择同一文件夹。已有库可直接使用。然后在 Codex 或 WorkBuddy 中打开**库根目录**作为工作区，使助手能读取笔记并写回该库。[Obsidian 建库指南](https://help.obsidian.md/vault)
2. 使用 Obsidian 自带的 **Markdown 笔记、内部链接和属性**即可。笔记用 `[[来源笔记]]` 跳到字幕，用 `[03:12–03:42]` 标出原话位置。文件顶部的属性保存 BV 号、分集、发布日期和字幕类型。**不需要安装社区插件、启用同步或运行 Obsidian CLI**。助手直接读写本地 Markdown，运行时可以关闭 Obsidian。[内部链接](https://help.obsidian.md/links) · [属性](https://help.obsidian.md/properties)
3. 安装器会在库根补齐 `AGENTS.md`、`方法论/学习目标.md` 和 `raw/B站/`。助手通过这三项识别目标库。先花一分钟改好[学习目标模板](vault-template/方法论/学习目标.md)，写下自己想学什么。已有规则和目标文件会保留；目录名请按原样使用。
4. **Wiki 摄入是可选的独立流程。** 如果你另外使用 Karpathy LLM Wiki，可在 Obsidian 中手动把选定的原始资料摄入 Wiki。三个技能直接使用 `raw/B站/` 和 `方法论/`；不要对方法论笔记执行 Wiki Ingest。

## 安装到 Codex 或 WorkBuddy

[下载项目 ZIP](https://github.com/ylimingtju/bilibili-to-obsidian/archive/refs/heads/main.zip) 并解压，或用 Git 下载。使用 Git 时按下面三行操作；已下载 ZIP 的读者，在解压后的项目目录执行第三行即可。字幕工具推荐 Python 3.11，Windows 可用 `py -3.11` 替代 `python3`。

```sh
git clone https://github.com/ylimingtju/bilibili-to-obsidian.git
cd bilibili-to-obsidian
python3 install.py --host both --vault "/path/to/My Vault"
```

把路径换成自己的库目录。只用一端时把 `both` 换成 `codex` 或 `workbuddy`。例如 Windows PowerShell：

```powershell
py -3.11 install.py --host workbuddy --vault "D:\Notes\My Vault"
```

- **Codex**　在 Codex 中打开库根目录，然后新建对话。如果要求信任工作区，信任你选择的库。三个技能装在 `<库>/.agents/skills/`。可以直接发上表中的提示，也可以显式输入 `$bilibili-to-obsidian`、`$bilibili-to-obsidian-investment-core` 或 `$bilibili-to-obsidian-investment-analysis`。[Codex 技能](https://learn.chatgpt.com/docs/build-skills) · [子智能体](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- **WorkBuddy 桌面端**　将同一库选为**本地工作区**，首次信任提示选择「正常打开」，再开启新任务。三个技能装在 `<库>/.codebuddy/skills/`，安装器同时放入 `.codebuddy/agents/investment-challenger.md`。做投资分析时，使用可调度成员的专家团。可在「专家 → 我的专家 → 创建专家团」建立团队，让团长调用 `investment-challenger`，并把修订稿发回同一成员。可直接说「请让独立质询者逐条挑战投资判断，再让同一位成员复核修订稿」。如果当前模式无法调度或续接同一成员，答复会标注哪一轮未完成。字幕和核心文件两个技能可单独使用。[项目配置](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project) · [工作区信任](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Permission-Modes) · [专家团](https://open.workbuddy.cn/en/docs/expert-team)

更新时重新下载项目或运行 `git pull`，再用原安装命令加 `--update`。它会替换项目提供的技能和质询者文件，保留笔记、学习目标和库规则。

## 字幕需要哪些工具

在**运行字幕脚本的 Python 环境**安装 yt-dlp，再用桌面 Chrome 登录有权观看该视频的 B 站账号。脚本在首次联网时读取本机 Chrome 登录状态，网络会话仅使用与 B 站有关的 Cookie。系统可能要求允许读取钥匙串。遇到登录失效、Chrome 配置无法解密、充电权限不足时，按错误提示检查当前账号和配置。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -U "yt-dlp[default]"
```

Windows PowerShell 可用 `py -3.11 -m venv .venv`，再运行 `.\.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"`。首次发链接时告诉助手这个 Python 解释器的**绝对路径**，也可以记入自己的库规则。核心更新和投资推演脚本无需安装 yt-dlp。

优先使用 UP 主字幕，其次用平台 AI 字幕。有权播放但两者都缺失时，本地 Whisper 可把音频转成带时间戳的字幕。用同一解释器运行 `-m pip install -U openai-whisper`，并将 FFmpeg 加入 `PATH`。首次使用 `large-v3` 需要下载模型；预先下载的模型可用 `WHISPER_MODEL_DIR` 或 `--model-dir` 指定目录。FFmpeg 也用于转换部分平台 WebVTT 字幕。只处理音频和文本。[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Whisper 安装及 FFmpeg](https://github.com/openai/whisper#setup)

需要直接运行脚本排查时，在项目根目录使用下列命令，用实际链接替换示例。返回 `select_part` 时加 `--part 2` 等所选集数；`created` 和 `existing` 都会返回原字幕路径。**直接运行 Python 只得到字幕**，提炼和合并笔记需要在助手中调用技能。

```sh
.venv/bin/python skills/bilibili-to-obsidian/scripts/fetch_subtitles.py "https://www.bilibili.com/video/<BV号>" --vault "/path/to/My Vault"
```

可以用 `--chrome-profile "Profile 1"` 或 `BILIBILI_CHROME_PROFILE` 选择已登录的 Chrome 配置。两个 Python 脚本优先采用显式 `--vault`，其次用 `BILIBILI_OBSIDIAN_VAULT`，最后从当前目录向上查找知识库。

## 成果保存在哪里

| 库内路径 | 内容 |
| --- | --- |
| `raw/B站/` | 原始字幕，一条视频的每个分 P 单独识别。重复发送时复用原文。 |
| `方法论/宏观与投资/` | 投资细笔记、按日期保存的作者观点，以及调用更新技能后生成的两份核心文件。其他主题也可在 `方法论/` 下整理。 |
| `方法论/投资推演记录/YYYY-MM.md` | 针对该月份的原问题、实际作答时间、资料截止时间、完整投资答复与质询结果。11 月问 12 月就写进 12 月，后续修订与结果另行追加。 |
| `AI 工作日记/` | 当天对知识库的修改。 |

空库先提取一条投资视频，再说「更新投资核心文件」，便可开始基于自己的材料推演。之后可以问「只用本地材料，按上月底可获得的信息重新判断」，或说明资金用途、期限和已有持仓，请助手比较可行选择。投资建议会归档，交易由使用者自行决定。核心更新的进度保存在本机用户状态目录中的 SQLite 文件，移动知识库或换机会重新识别材料。


## 已验证范围

在 macOS 的临时库验证了双平台安装、已有规则保留，以及 Codex 从项目目录发现全部三个技能。字幕测试使用本地样例，覆盖多分 P、时间戳、重复输入、音轨下载和 FFmpeg 时长检查。核心更新测试覆盖增量处理及恢复。WorkBuddy 的目录结构和角色定义已按官方格式检查；WorkBuddy 桌面双轮协作、Windows 实机、真实账号抓取和完整 large-v3 转写尚待实机验证。
