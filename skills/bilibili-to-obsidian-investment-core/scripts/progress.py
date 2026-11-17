"""List new/changed investment inputs and remember only the versions processed."""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path


TOPIC = Path("方法论/宏观与投资")
RAW = Path("raw/B站")
CORE = (TOPIC / "投资推演核心框架.md", TOPIC / "决策问题与证据导航.md")
SCHEMA = "CREATE TABLE IF NOT EXISTS seen (vault TEXT, path TEXT, digest TEXT, PRIMARY KEY (vault, path))"


def is_vault(path):
    return ((path / "AGENTS.md").is_file()
            and (path / "方法论/学习目标.md").is_file()
            and (path / RAW).is_dir())


def find_vault(explicit):
    chosen = explicit or os.environ.get("BILIBILI_OBSIDIAN_VAULT")
    if chosen:
        path = Path(chosen).expanduser().resolve()
        return path if is_vault(path) else None
    here = Path.cwd()
    return next((p for p in (here, *here.parents) if is_vault(p)), None)


def input_versions(vault):
    versions = {}
    for folder in (TOPIC, RAW):
        for path in sorted((vault / folder).rglob("*.md")):
            relative = path.relative_to(vault)
            if relative in CORE or path.is_symlink() or not path.is_file():
                continue
            versions[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return versions


def main():
    parser = argparse.ArgumentParser(description="列出待参考的笔记，或记录实际完成的 JSON 行。")
    parser.add_argument("action", choices=("pending", "done"))
    parser.add_argument("--vault", type=Path, help="知识库根目录（优先于环境变量及当前目录）")
    parser.add_argument("--rows", type=Path, help="done：已处理的 UTF-8 JSON 行文件，省略时读标准输入")
    args = parser.parse_args()
    if args.action == "pending" and args.rows:
        parser.error("--rows 仅适用于 done。")
    vault = find_vault(args.vault)
    if vault is None:
        parser.error("找不到同时包含 AGENTS.md、方法论/学习目标.md 和 raw/B站/ 的知识库。请指定正确目录，或先按 README 使用知识库模板。")

    versions = input_versions(vault)
    state = (os.environ.get("XDG_STATE_HOME")
             or (os.environ.get("LOCALAPPDATA") if os.name == "nt" else None)
             or Path.home() / ".local/state")
    db = Path(state) / "bilibili-to-obsidian-investment-core" / "progress.sqlite3"
    has_core = all((vault / path).is_file() for path in CORE)

    if args.action == "pending":
        saved = {}
        if db.is_file():
            with sqlite3.connect(db) as conn:
                conn.execute(SCHEMA)
                if has_core:
                    saved = dict(conn.execute("SELECT path, digest FROM seen WHERE vault = ?", (str(vault),)))
                else:
                    # After a partial rebuild, the remaining inputs must still be pending.
                    conn.execute("DELETE FROM seen WHERE vault = ?", (str(vault),))
        for path, digest in versions.items():
            if saved.get(path) != digest:
                print(json.dumps({"path": path, "sha256": digest}, ensure_ascii=False))
        return

    if not has_core:
        parser.error("两份核心文件尚未全部创建，未记录进度。")
    contents = args.rows.read_text(encoding="utf-8-sig") if args.rows else sys.stdin.read()
    completed = []
    for number, line in enumerate(contents.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            path, digest = row["path"], row["sha256"]
            if not isinstance(path, str) or not isinstance(digest, str):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            parser.error(f"第 {number} 行不是含 path 和 sha256 的进度记录，未保存本批。")
        if versions.get(path) == digest:
            completed.append((str(vault), path, digest))
        else:
            print(f"文件已变动或不在输入目录，本次不记录：{path}", file=sys.stderr)
    if completed:
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute(SCHEMA)
            conn.executemany("INSERT OR REPLACE INTO seen VALUES (?, ?, ?)", completed)


if __name__ == "__main__":
    main()
