"""Which Terraform resources a change deletes, read from the files' text.

    pubhost terraform deletes BASE HEAD [--labelled]

Compares the .tf files of two git revisions, per directory, and lists every
resource and module BASE has that HEAD no longer has, except those HEAD says
moved (a `moved` block) or only forgets (a `removed` block with
`destroy = false`). It fails on any, unless --labelled says the pull request
carries the label that allows deletes (terraform.yml's terraform-destroy).

It reads no plan, so it needs no credentials and no state, and it runs on a
pull request's code safely. It cannot see a delete that does not remove a
block: a changed for_each or count, a changed name, a replacement. terraform.yml
still checks the real plan after the merge.

Only the standard library is used, so the actions can run this file directly.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

BLOCK = re.compile(r'^[ \t]*(resource|module)[ \t]+"([^"]+)"(?:[ \t]+"([^"]+)")?[ \t]*\{', re.MULTILINE)
MOVED = re.compile(r"^[ \t]*moved[ \t]*\{(.*?)^\}", re.MULTILINE | re.DOTALL)
REMOVED = re.compile(r"^[ \t]*removed[ \t]*\{(.*?)^\}", re.MULTILINE | re.DOTALL)
FROM = re.compile(r"\bfrom[ \t]*=[ \t]*(\S+)")
KEEPS = re.compile(r"\bdestroy[ \t]*=[ \t]*false\b")


def address(kind: str, first: str, second: str | None) -> str:
    return f"module.{first}" if kind == "module" else f"{first}.{second}"


def reference(text: str) -> str:
    """The address a `from =` names: its first two segments, with no index
    (a moved resource in a module is the module's concern)."""
    text = re.sub(r"\[[^\]]*\]", "", text.strip())
    return ".".join(text.split(".")[:2])


HEREDOC = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)[ \t]*\n")


def string_end(text: str, start: int) -> int:
    """Where the quoted string starting at `start` ends: the index of its
    closing quote, skipping escapes and what lies inside ${...} and %{...}."""
    depth = 0
    index = start + 1
    while index < len(text):
        char = text[index]
        if depth == 0 and char == "\\":
            index += 2
            continue
        if depth == 0 and char == '"':
            return index
        if text.startswith(("$${", "%%{"), index):
            index += 3
            continue
        if text.startswith(("${", "%{"), index):
            depth += 1
            index += 2
            continue
        if depth and char == "{":
            depth += 1
        elif depth and char == "}":
            depth -= 1
        index += 1
    return len(text)


def code(text: str) -> str:
    """The text without comments (/* */, # and //) and heredoc bodies, which
    may hold a resource block as text that Terraform never reads. Quoted
    strings are kept whole, so a "/*" or "#" in one starts nothing."""
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        heredoc = HEREDOC.match(text, index) if text.startswith("<<", index) else None
        if char == '"':
            end = string_end(text, index)
            out.append(text[index:end + 1])
            index = end + 1
        elif heredoc:
            closing = re.compile(rf"^[ \t]*{re.escape(heredoc.group(1))}[ \t]*$", re.MULTILINE).search(text, heredoc.end())
            out.append(text[index:heredoc.end()])
            index = closing.end() if closing else len(text)
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
        elif char == "#" or text.startswith("//", index):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
        else:
            out.append(char)
            index += 1
    return "".join(out)


def blocks(text: str) -> set[str]:
    return {address(kind, first, second) for kind, first, second in BLOCK.findall(code(text))}


def forgotten(text: str) -> set[str]:
    """What the files' moved and removed blocks leave out of the deletes: the
    old address of a move, and what a removed block keeps (destroy = false)."""
    found = set()
    text = code(text)
    for body in MOVED.findall(text):
        found |= {reference(m) for m in FROM.findall(body)}
    for body in REMOVED.findall(text):
        if KEEPS.search(body):
            found |= {reference(m) for m in FROM.findall(body)}
    return found


# What may reach git as a revision: a name (a commit, a tag, a branch,
# HEAD~1), never an option, so it cannot start with "-".
REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/@^~-]*")
HASH = re.compile(r"[0-9a-f]{40,64}")


def checked(revision: str) -> str:
    """A revision, as REVISION allows; anything else stops the check."""
    if not REVISION.fullmatch(revision):
        sys.exit(f"pubhost: {revision!r} is not a revision")
    return revision


def commit(revision: str) -> str:
    """The commit a revision names, as its full hash: later git calls take only
    that, so nothing given on the command line reaches git as anything else."""
    sha = git("rev-parse", "--verify", "--end-of-options", f"{checked(revision)}^{{commit}}").strip()
    if not HASH.fullmatch(sha):
        sys.exit(f"pubhost: {revision!r} does not name a commit")
    return sha


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if done.returncode:
        sys.exit(f"pubhost: git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def terraform_files(revision: str) -> list[str]:
    return [path for path in git("ls-tree", "-r", "--name-only", revision).splitlines()
            if path.endswith(".tf")]


def directories(revision: str, wanted: set[str]) -> dict[str, str]:
    """The text of each wanted directory's .tf files at a revision, joined."""
    texts: dict[str, list[str]] = {}
    for path in terraform_files(revision):
        directory = str(PurePosixPath(path).parent)
        if directory in wanted:
            texts.setdefault(directory, []).append(git("show", f"{revision}:{path}"))
    return {directory: "\n".join(parts) for directory, parts in texts.items()}


def deletes(base: str, head: str) -> list[tuple[str, str]]:
    """(directory, address) for each resource or module the change deletes."""
    base, head = commit(base), commit(head)
    changed = git("diff", "--no-renames", "--name-only", base, head, "--", "*.tf").splitlines()
    wanted = {str(PurePosixPath(path).parent) for path in changed}
    before = directories(base, wanted)
    after = directories(head, wanted)
    found = []
    for directory in sorted(wanted):
        gone = blocks(before.get(directory, "")) - blocks(after.get(directory, ""))
        gone -= forgotten(after.get(directory, ""))
        found += [(directory, name) for name in sorted(gone)]
    return found


def run(base: str, head: str, labelled: bool, label: str = "terraform-destroy") -> int:
    found = deletes(base, head)
    if not found:
        print("This change deletes no resource or module block.")
        return 0
    for directory, name in found:
        print(f"deletes {name} in {directory}/")
    if labelled:
        print(f"The pull request has the label {label}: the deletes are allowed.")
        return 0
    print(f"pubhost: this change deletes what is listed above, and the pull request has no "
          f"label {label}. Add the label if the deletes are meant.", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pubhost terraform deletes", description=__doc__.split("\n")[0])
    parser.add_argument("base", help="the revision the change starts from")
    parser.add_argument("head", help="the revision with the change")
    parser.add_argument("--labelled", action="store_true",
                        help="the pull request has the label that allows deletes")
    parser.add_argument("--label", default="terraform-destroy", help="its name, for the messages")
    args = parser.parse_args(argv)
    return run(args.base, args.head, args.labelled, args.label)


if __name__ == "__main__":
    sys.exit(main())
