"""Install the three skills into an Obsidian vault for Codex, WorkBuddy, or both."""

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
HOST_DIRS = {"codex": ".agents", "workbuddy": ".codebuddy"}
VAULT_DIRS = ("raw/B站", "方法论/宏观与投资", "方法论/投资推演记录", "AI 工作日记")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True, help="New or existing local vault")
    parser.add_argument("--host", choices=(*HOST_DIRS, "both"), required=True)
    parser.add_argument("--update", action="store_true",
                        help="Replace changed packaged skills/agent files; keep existing vault notes and rules")
    args = parser.parse_args()
    vault = args.vault.expanduser().resolve()
    hosts = HOST_DIRS if args.host == "both" else [args.host]
    files = {}
    for host in hosts:
        config = vault / HOST_DIRS[host]
        for source in (ROOT / "skills").rglob("*"):
            if source.is_file() and source.suffix in {".md", ".py"}:
                files[config / source.relative_to(ROOT)] = source
        if host == "workbuddy":
            role = Path("agents/investment-challenger.md")
            files[config / role] = ROOT / "workbuddy" / role

    templates = {vault / p.relative_to(ROOT / "vault-template"): p
                 for p in (ROOT / "vault-template").rglob("*.md")}
    for dest in (*files, *templates, *(vault / folder for folder in VAULT_DIRS)):
        if dest.resolve() != dest:
            parser.error(f"Destination follows a symbolic link: {dest}")
    for dest, source in files.items():
        if dest.exists() and dest.read_bytes() != source.read_bytes() and not args.update:
            parser.error(f"Existing skill differs: {dest}. Use --update to replace packaged files.")
    for folder in VAULT_DIRS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    for dest, source in templates.items():
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    for dest, source in files.items():
        if not dest.exists() or dest.read_bytes() != source.read_bytes():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    print(f"Vault: {vault}")
    for host in hosts:
        print(f"{host}: {vault / HOST_DIRS[host] / 'skills'}")
    if "workbuddy" in hosts:
        print(f"WorkBuddy critic: {vault / '.codebuddy/agents/investment-challenger.md'}")


if __name__ == "__main__":
    main()
