# Bilibili to Obsidian

[中文指南](README.md)

Turn a Bilibili video into timestamped notes, build an investment framework from the videos you collect, and use that framework to evaluate a financial decision. All three skills work with a local Obsidian vault.

| When | What to tell the assistant | What you get |
| --- | --- | --- |
| After finding a video | Paste a Bilibili link, a BV ID, a `b23.tv` short link, or a post containing one video. | A complete timestamped transcript and one to three ideas merged into your notes. For a multipart video, choose a part when prompted. |
| After collecting a batch | **Update my core investment notes.** | One note on reusable methods and an index linking each decision question to its evidence. The next update processes new and changed material. |
| When making a decision | **Use my vault to assess where to put next month's savings.** | An answer that uses the core methods, detailed notes, original transcripts and, by default, current public sources. An independent reviewer challenges each proposed action and reviews the revision. The answer states the evidence, remaining disagreement and what would change the decision. |

## What you need from Obsidian

1. Choose a **local folder that the assistant can read and write**. After installation, use **Open folder as vault** in Obsidian's vault switcher and select that folder. An existing vault works too. Open the **same vault root** as the workspace in Codex or WorkBuddy. [Obsidian vault guide](https://help.obsidian.md/vault)
2. The workflow uses Obsidian's built-in **Markdown notes, internal links and properties**. A link such as `[[source note]]` opens the transcript. A label such as `[03:12–03:42]` identifies the passage. Note properties hold the video ID, part, publication date and subtitle type. No community plugin, Obsidian Sync subscription or Obsidian CLI is required. The assistant can read and write these files while Obsidian is closed. [Internal links](https://help.obsidian.md/links) · [Properties](https://help.obsidian.md/properties)
3. The installer adds the three items used to locate a vault: `AGENTS.md`, `方法论/学习目标.md` (learning goals), and the `raw/B站/` folder. Keep these names, including the Chinese characters. Edit the bilingual [learning goals template](vault-template/方法论/学习目标.md) in your vault to describe what you want to learn. The installer preserves existing rules and goals.
4. **Wiki ingestion is optional.** If you separately use the Karpathy LLM Wiki plugin, you can manually ingest selected raw notes in Obsidian. The skills read the transcripts and methodology notes directly. Leave `方法论/` outside the plugin ingestion workflow.

## Install for Codex or WorkBuddy

[Download and extract the project ZIP](https://github.com/ylimingtju/bilibili-to-obsidian/archive/refs/heads/main.zip), or clone it with Git. When using Git, run all three commands below. If you downloaded the ZIP, open the extracted project folder and run the third command. Use Python 3.11 for the subtitle tools. On Windows, `py -3.11` can replace `python3`.

```sh
git clone https://github.com/ylimingtju/bilibili-to-obsidian.git
cd bilibili-to-obsidian
python3 install.py --host both --vault "/path/to/My Vault"
```

Use your own vault path. Choose `codex` or `workbuddy` instead of `both` to install for one host. For example, in Windows PowerShell:

```powershell
py -3.11 install.py --host workbuddy --vault "D:\Notes\My Vault"
```

- **Codex.** Open the vault root in Codex, trust the folder if prompted, and start a new chat. The installer puts the skills in `<vault>/.agents/skills/`. Use the phrases above or invoke `$bilibili-to-obsidian`, `$bilibili-to-obsidian-investment-core` or `$bilibili-to-obsidian-investment-analysis` directly. [Codex skills](https://learn.chatgpt.com/docs/build-skills) · [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- **WorkBuddy Desktop.** Open the vault as a **local workspace**, choose the normal/trusted opening mode, and start a new task. The installer puts the skills under `<vault>/.codebuddy/skills/` and the reviewer at `.codebuddy/agents/investment-challenger.md`. For investment decisions, use a team with access to a separate reviewer. You can create one under **Experts → My Experts → Create Expert Team**. Tell its lead, “Have investment-challenger challenge each decision, then send the revised answer back to the same member.” If the host cannot start a separate member or reach it for the second round, the answer identifies the incomplete round. The transcript and core-note skills also work on their own. [Project settings](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project) · [Workspace trust](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Permission-Modes) · [Expert teams](https://open.workbuddy.cn/en/docs/expert-team)

For an update, download the new version or run `git pull` and repeat the install command with `--update`. This replaces the packaged skill and reviewer files while keeping your notes, rules and learning goals.

## Set up subtitles

Sign in to Bilibili in desktop Chrome with an account that can play the video. Install yt-dlp in the **Python environment that will run the subtitle script**. The first network request uses your local Chrome session. Only Bilibili-related cookies are used for the network session. Your OS may prompt you for keychain access. If the browser profile cannot be decrypted, your login has expired or a paid video is unavailable, check the selected Chrome profile and account access.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -U "yt-dlp[default]"
```

In Windows PowerShell use `py -3.11 -m venv .venv`, then `.\.venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"`. Give the assistant the **absolute path to this interpreter** when sending your first link. You can add it to your own vault rules for future sessions. The core-note and investment-analysis skills can work with existing notes without yt-dlp.

The script tries uploader captions first, then platform AI captions. For an accessible video with neither, it can transcribe the audio locally. To enable that fallback, use the same interpreter to run `-m pip install -U openai-whisper` and make FFmpeg available on your `PATH`. Whisper downloads the `large-v3` model on first use. To use an existing model cache, pass `--model-dir` or set `WHISPER_MODEL_DIR`. Some WebVTT subtitle tracks also use FFmpeg for conversion. The workflow uses audio and text only. [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Whisper and FFmpeg setup](https://github.com/openai/whisper#setup)

To run the subtitle step directly, replace the placeholder with a real video ID:

```sh
.venv/bin/python skills/bilibili-to-obsidian/scripts/fetch_subtitles.py "https://www.bilibili.com/video/<BV-ID>" --vault "/path/to/My Vault"
```

If the result is `select_part`, repeat with your choice, such as `--part 2`. Both `created` and `existing` return a path to the transcript. **The Python command retrieves the transcript only.** Invoke the skill in the assistant to extract and merge the ideas. Select a Chrome profile with `--chrome-profile "Profile 1"` or `BILIBILI_CHROME_PROFILE`. Both Python helpers look for the vault in this order: an explicit `--vault`, the `BILIBILI_OBSIDIAN_VAULT` environment variable, then the current directory and its parents.

## Where to find the results

| Vault path | Contents |
| --- | --- |
| `raw/B站/` | Original timestamped transcripts, identified by BV ID and part. Existing transcripts are reused. |
| `方法论/宏观与投资/` | Detailed investment notes, dated views attributed to their authors, and the two core notes: `投资推演核心框架.md` (methods) and `决策问题与证据导航.md` (evidence index). Notes on other topics can go elsewhere under `方法论/`. |
| `方法论/投资推演记录/YYYY-MM.md` | Full investment answers, original questions, actual response times, evidence cutoffs and review outcomes. The file is named for the **month being discussed**. A December decision made in November goes in the December file. Revisions and outcomes are appended. |
| `AI 工作日记/` | A dated log of changes to the vault. |

In an empty vault, start with one investment video, then ask for a core-note update. Later you can request “Use only local material available by the end of last month,” or provide a time horizon, expected expenses and holdings to compare choices. The skills record investment judgments; the user executes any trades. Core-note progress is kept in a local SQLite database outside the vault. Moving a vault or switching computers makes the next update scan the inputs again.


## Tested scope

On macOS, a temporary vault was used to check installation for both hosts, preservation of existing vault rules, and discovery of all three project skills by Codex. Local fixtures covered multipart selection, timestamps, duplicate input, audio download and FFmpeg duration checks. Core-note tests covered incremental updates and recovery. The WorkBuddy layout and reviewer definition were checked against its documented format. Live two-round review in WorkBuddy Desktop, Windows execution, retrieval with a real Bilibili account, and full large-v3 inference have not been tested for this distribution.
