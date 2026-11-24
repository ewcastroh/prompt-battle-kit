#!/usr/bin/env python3
"""PreToolUse guard for D-028: nothing is changed directly on `main`.

Runs before Edit, Write, NotebookEdit and Bash. For the three repos (the parent
and the two child repos cloned inside it) it blocks, while the checked-out
branch is `main` or `master`:
  - editing or writing any file that git does not ignore;
  - git commit, merge, rebase, cherry-pick, revert, reset, am and pull
    (pull is allowed with --ff-only, to sync after the owner merges a PR);
and anywhere it blocks a git push that targets `main`/`master` (including a
push with no refspec while on `main`, `--all` and `--mirror`).

Exit code 2 blocks the call and the message on stderr goes back to Claude.
This is a local guardrail, not a security boundary: the real protection is the
GitHub ruleset `protect-main` (docs/DEPLOYMENT.md). It does not look inside
variables, subshells or scripts, and it does not see writes made by shell
redirections or tools such as sed -i.
"""
import json
import os
import shlex
import subprocess
import sys

PROJECT = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
REPOS = {
    PROJECT,
    os.path.join(PROJECT, "prompt-battle-api"),
    os.path.join(PROJECT, "prompt-battle-ui"),
}
PROTECTED = {"main", "master"}
HISTORY_COMMANDS = {"commit", "merge", "rebase", "cherry-pick", "revert", "reset", "am", "pull"}
SAFE_FLAGS = {"--abort", "--quit"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")"}


def block(reason):
    print(
        f"Blocked by the main-branch guard (D-028): {reason}\n"
        "Work on a branch: git switch -c <phase-or-type>/<short-topic> "
        "(for example a4/queue-fix or docs/branch-per-change), then repeat there. "
        "Changes reach main only through a pull request that the owner merges.",
        file=sys.stderr,
    )
    sys.exit(2)


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, timeout=10
    )
    return result.returncode, result.stdout.strip()


def existing_dir(path):
    path = os.path.abspath(path)
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


def toplevel(path):
    code, out = git(existing_dir(path), "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if code == 0 and out else None


def current_branch(root):
    return git(root, "branch", "--show-current")[1]


def protected_repo(root):
    """The repo's protected branch name when it is checked out, else None."""
    if root in REPOS:
        branch = current_branch(root)
        if branch in PROTECTED:
            return branch
    return None


def check_file(path, cwd):
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    root = toplevel(os.path.dirname(path))
    branch = root and protected_repo(root)
    if not branch:
        return
    if git(root, "check-ignore", "-q", path)[0] == 0:
        return  # git-ignored files (secrets/, data/, .env) are not tracked changes
    block(f"{os.path.relpath(path, root)} is in a repo whose current branch is `{branch}`.")


def split_segments(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    segments, current = [], []
    for token in lex:
        if token in SEPARATORS or set(token) <= set(";&|()\n"):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def parse_git(words):
    """Return (dir_changes, subcommand, args) for a segment that runs git, else None."""
    i = 0
    while i < len(words):
        word = words[i]
        if "=" in word and not word.startswith("-") and "/" not in word.split("=")[0]:
            i += 1  # VAR=value prefix
        elif os.path.basename(word) in {"sudo", "env", "command", "time", "nohup"}:
            i += 1
        else:
            break
    if i >= len(words) or os.path.basename(words[i]) != "git":
        return None
    i += 1
    dirs = []
    while i < len(words) and words[i].startswith("-"):
        option = words[i]
        if option == "-C" and i + 1 < len(words):
            dirs.append(words[i + 1])
            i += 2
        elif option == "-c" and i + 1 < len(words):
            i += 2
        elif option.startswith("--work-tree="):
            dirs.append(option.split("=", 1)[1])
            i += 1
        else:
            i += 1
    if i >= len(words):
        return None
    return dirs, words[i], words[i + 1 :]


def check_push(args, cur):
    flags = [a for a in args if a.startswith("-")]
    if "--all" in flags or "--mirror" in flags:
        block("`git push --all/--mirror` would push `main` too.")
    positional = [a for a in args if not a.startswith("-")]
    refspecs = positional[1:]  # first positional is the remote
    if not refspecs:
        if cur in PROTECTED:
            block(f"`git push` while on `{cur}` pushes it.")
        return
    for spec in refspecs:
        spec = spec.lstrip("+")
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        dst = dst.removeprefix("refs/heads/")
        if dst in PROTECTED:
            block(f"`git push {spec}` targets `{dst}`.")
        if dst == "HEAD" and cur in PROTECTED:
            block(f"`git push {spec}` while on `{cur}` pushes it.")


def check_bash(command, cwd):
    try:
        segments = split_segments(command)
    except ValueError:
        segments = []
    for words in segments:
        if words[0] == "cd" and len(words) > 1 and words[1] != "-":
            cwd = os.path.abspath(os.path.join(cwd, os.path.expanduser(words[1])))
            continue
        parsed = parse_git(words)
        if not parsed:
            continue
        dirs, sub, args = parsed
        repo_dir = cwd
        for d in dirs:
            repo_dir = os.path.abspath(os.path.join(repo_dir, os.path.expanduser(d)))
        root = toplevel(repo_dir)
        if not root or root not in REPOS:
            continue
        cur = current_branch(root)
        if sub == "push":
            check_push(args, cur)
        elif sub in HISTORY_COMMANDS and cur in PROTECTED:
            if SAFE_FLAGS & set(args):
                continue
            if sub == "pull" and "--ff-only" in args:
                continue
            block(f"`git {sub}` while the current branch is `{cur}` in {os.path.basename(root)}.")


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()
    if tool in {"Edit", "Write", "NotebookEdit"}:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path:
            check_file(path, cwd)
    elif tool == "Bash":
        check_bash(tool_input.get("command", ""), cwd)


if __name__ == "__main__":
    main()
