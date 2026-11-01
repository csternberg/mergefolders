#!/usr/bin/env python3
"""mergefolders - merge sibling folders whose names share a common prefix/suffix.

Run `mergefolders.py --help` for usage, or see README.md / mergefolders.1.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

VERSION = "1.2"
SCRIPT_NAME = "mergefolders"

UNDO_FILE = "undo_merge.json"
LOG_FILE = "log.txt"

EPILOG = """\
modes:
  -b N / --begin N   group folders in the current directory by their first N characters
  -e N / --end N     group folders in the current directory by their last N characters
  N = 0              special case: move every file from all subfolders (recursively)
                     into the current directory

For each group of two or more folders, the folder with the shortest name
(ties: alphabetical) is the target; files from the other folders are moved
into it. Folders are never deleted, only their files are moved.

With -t DIR / --target DIR, nothing is merged into an existing folder; instead
every group gets its own folder DIR/<key> (created if needed, key = the shared
characters) and the files of ALL folders in the group are moved there. With
N = 0 all files are moved straight into DIR.

On a name collision the incoming file is renamed name_01.ext, name_02.ext, ...
unless --overwrite is given, in which case the existing file is REPLACED
(this cannot be undone).

Every switch is case-insensitive: -b == -B, --dry-run == --DRY-RUN.
Use --dry-run first to preview what would happen.

examples:
  mergefolders.py --dry-run -b 8      preview grouping by first 8 characters
  mergefolders.py -b 8 -l             merge, and append to log.txt
  mergefolders.py -e 4 --overwrite    group by last 4 characters, replace on collision
  mergefolders.py -b 0                flatten all subfolders into the current directory
  mergefolders.py -t condensed -b 5   put files of folders sharing their first 5
                                      characters into condensed/<those 5 characters>
  mergefolders.py -u                  undo the last run (reads undo_merge.json)
"""


def normalize_argv(argv):
    """Lower-case long options so --DRY-RUN and --Dry-Run work like --dry-run.

    Short options are handled by registering both cases in the parser.
    """
    result = []
    for token in argv:
        if token == "--":
            result.append(token)
            continue
        if token.startswith("--"):
            name, sep, value = token.partition("=")
            token = name.lower() + sep + value
        result.append(token)
    return result


def non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {text!r}")
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog=f"{SCRIPT_NAME}.py",
        description="Merge sibling folders sharing the same name prefix or suffix.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
    )

    parser.add_argument("-h", "-H", "--help", action="help",
                        help="show this help and exit")
    parser.add_argument("-v", "-V", "--version", action="version",
                        version=f"{SCRIPT_NAME} {VERSION}",
                        help="show version and exit")
    parser.add_argument("-n", "-N", "-d", "-D", "--dry-run", dest="dry_run",
                        action="store_true",
                        help="show what would be done, change nothing")
    parser.add_argument("-o", "-O", "--overwrite", dest="overwrite",
                        action="store_true",
                        help="replace existing files instead of renaming (not undoable)")
    parser.add_argument("-l", "-L", "--log", dest="log", action="store_true",
                        help=f"append actions to {LOG_FILE}")
    parser.add_argument("-u", "-U", "--undo", dest="undo", action="store_true",
                        help=f"undo the last run using {UNDO_FILE}")

    parser.add_argument("-t", "-T", "--target", dest="target", metavar="DIR",
                        help="move files into DIR/<shared characters> instead of "
                             "the shortest-named folder")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-b", "-B", "--begin", dest="begin", type=non_negative_int,
                      metavar="N", help="group by the first N characters of the name")
    mode.add_argument("-e", "-E", "--end", dest="end", type=non_negative_int,
                      metavar="N", help="group by the last N characters of the name")
    return parser


class Logger:
    """Prints messages and optionally appends them to a log file."""

    def __init__(self, path=None):
        self.file = open(path, "a", encoding="utf-8") if path else None

    def __call__(self, msg):
        print(msg)
        if self.file:
            self.file.write(msg + "\n")

    def close(self):
        if self.file:
            self.file.close()


class Mover:
    """Moves files, handling collisions, dry-run and undo bookkeeping."""

    def __init__(self, overwrite, dry_run, log):
        self.overwrite = overwrite
        self.dry_run = dry_run
        self.log = log
        self.undo = []          # list of [current_path, original_path]
        self.errors = 0
        self._planned = set()   # destinations claimed during a dry run

    def _exists(self, path):
        return os.path.lexists(path) or os.path.normcase(path) in self._planned

    def _unique_path(self, dst_dir, filename):
        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(dst_dir, f"{name}_{counter:02d}{ext}")
            if not self._exists(candidate):
                return candidate
            counter += 1

    def move(self, src_path, dst_dir):
        filename = os.path.basename(src_path)
        dst_path = os.path.join(dst_dir, filename)

        if self._exists(dst_path):
            if self.overwrite:
                action = "overwrite"
            else:
                dst_path = self._unique_path(dst_dir, filename)
                action = "rename"
        else:
            action = "move"

        prefix = "[DRY] " if self.dry_run else ""
        if self.dry_run:
            self._planned.add(os.path.normcase(dst_path))
            self.log(f"{prefix}{action.upper()}: {src_path} -> {dst_path}")
            return

        try:
            os.makedirs(dst_dir, exist_ok=True)
            if action == "overwrite":
                os.replace(src_path, dst_path)
            else:
                shutil.move(src_path, dst_path)
        except Exception as e:
            self.errors += 1
            self.log(f"[SKIP] {src_path} ({e})")
            return

        self.log(f"{action.upper()}: {src_path} -> {dst_path}")
        self.undo.append([dst_path, src_path])

    def save_undo(self):
        if self.dry_run or not self.undo:
            return
        with open(UNDO_FILE, "w", encoding="utf-8") as f:
            json.dump({"tool": SCRIPT_NAME, "created": datetime.now().isoformat(),
                       "moves": self.undo}, f, indent=2)
        self.log(f"Undo information written to {UNDO_FILE}")


def is_within(path, parent):
    """True if path is parent or lies inside it."""
    path = os.path.normcase(os.path.abspath(path))
    parent = os.path.normcase(os.path.abspath(parent))
    return path == parent or path.startswith(parent + os.sep)


def list_folders(exclude=None):
    """Real (non-symlink) directories in the current directory.

    Folders that are, or contain, the `exclude` destination are left out.
    """
    with os.scandir(".") as it:
        return sorted(e.name for e in it
                      if e.is_dir(follow_symlinks=False)
                      and not (exclude and is_within(exclude, e.name)))


def build_key(name, begin, end):
    if begin is not None:
        return name[:begin]
    return name[-end:]


def list_files(folder):
    with os.scandir(folder) as it:
        return sorted(e.name for e in it if e.is_file())


def collect_all(mover, dest="."):
    """Move every file below the current directory into `dest`."""
    flat = os.path.abspath(dest) == os.path.abspath(".")
    sources = []
    for root, dirs, files in os.walk("."):
        # don't pick files up from the destination folder itself
        dirs[:] = sorted(d for d in dirs
                         if flat or not is_within(os.path.join(root, d), dest))
        if os.path.abspath(root) == os.path.abspath("."):
            continue
        sources.extend(os.path.join(root, f) for f in sorted(files))

    for src_path in sources:
        mover.move(src_path, dest)


def merge_groups(mover, begin, end, dest_root=None):
    groups = {}
    for folder in list_folders(dest_root):
        groups.setdefault(build_key(folder, begin, end), []).append(folder)

    found = False
    for key, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        found = True

        if dest_root:
            target = os.path.join(dest_root, key)
        else:
            target = min(group, key=lambda n: (len(n), n))
        mover.log(f"\nGroup '{key}' -> target '{target}'")

        for src in group:
            if src == target:
                continue
            for item in list_files(src):
                mover.move(os.path.join(src, item), target)

    if not found:
        mover.log("No groups of two or more folders found.")


def run_undo(dry_run, log):
    if not os.path.exists(UNDO_FILE):
        log("No undo file found.")
        return 1

    try:
        with open(UNDO_FILE, encoding="utf-8") as f:
            moves = json.load(f)["moves"]
    except (OSError, ValueError, KeyError) as e:
        log(f"Cannot read {UNDO_FILE}: {e}")
        return 1

    log(f"Undoing {len(moves)} move(s) from {UNDO_FILE}")
    errors = 0
    for current, original in reversed(moves):
        if not os.path.exists(current):
            log(f"[SKIP] {current} no longer exists")
            errors += 1
        elif os.path.lexists(original):
            log(f"[SKIP] {original} already exists, not restoring {current}")
            errors += 1
        elif dry_run:
            log(f"[DRY] RESTORE: {current} -> {original}")
        else:
            try:
                os.makedirs(os.path.dirname(original) or ".", exist_ok=True)
                shutil.move(current, original)
                log(f"RESTORE: {current} -> {original}")
            except Exception as e:
                log(f"[SKIP] {current} ({e})")
                errors += 1

    if not dry_run and not errors:
        os.remove(UNDO_FILE)
    return 1 if errors else 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(normalize_argv(sys.argv[1:] if argv is None else argv))

    if not args.undo and args.begin is None and args.end is None:
        parser.error("you must specify -b/--begin or -e/--end (or -u/--undo)")

    log = Logger(LOG_FILE if args.log else None)
    try:
        log(f"=== Run started {datetime.now()} ===")
        if args.undo:
            return run_undo(args.dry_run, log)

        mover = Mover(args.overwrite, args.dry_run, log)
        try:
            if args.begin == 0 or args.end == 0:
                collect_all(mover, args.target or ".")
            else:
                merge_groups(mover, args.begin, args.end, args.target)
        finally:
            mover.save_undo()
        log("=== Run finished ===\n")
        return 1 if mover.errors else 0
    finally:
        log.close()


if __name__ == "__main__":
    sys.exit(main())
