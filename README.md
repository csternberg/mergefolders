# mergefolders

Merge sibling folders whose names share the same first or last *N* characters.
Pure Python 3 standard library, works on Windows, Linux and macOS.

## Usage

```
mergefolders.py [-h] [-v] [-n] [-o] [-l] [-u] [-b N | -e N]
```

| Short | Long          | Description                                              |
|-------|---------------|----------------------------------------------------------|
| `-b N`| `--begin N`   | Group folders by the first N characters of the name      |
| `-e N`| `--end N`     | Group folders by the last N characters of the name       |
| `-n`, `-d` | `--dry-run` | Show what would happen, change nothing                |
| `-t DIR` | `--target DIR` | Put each group's files in `DIR/<shared characters>` |
| `-o`  | `--overwrite` | Replace existing files instead of renaming (not undoable)|
| `-l`  | `--log`       | Append all actions to `log.txt`                          |
| `-u`  | `--undo`      | Undo the last run using `undo_merge.json`                |
| `-h`  | `--help`      | Show help                                                |
| `-v`  | `--version`   | Show version                                             |

All switches are case-insensitive (`-B` = `-b`, `--DRY-RUN` = `--dry-run`).
`-b` and `-e` are mutually exclusive. Run from the directory that contains the folders.

## How it works

* Folders in the current directory are grouped by the chosen prefix/suffix.
* In each group of two or more, the folder with the shortest name (ties: alphabetical) is the target;
  files from the other folders are moved into it. Folders themselves are left in place.
* With `-t DIR`, each group instead gets its own folder `DIR/<key>` (created if missing, key = the shared
  characters), and files from *all* folders in the group are moved there. With `-b 0`/`-e 0`, files go straight into `DIR`.
* On a name collision the incoming file becomes `name_01.ext`, `name_02.ext`, ... unless `--overwrite`.
* `-b 0` / `-e 0` is a special mode: every file in all subfolders (recursively) is moved into the current directory.
* A successful run writes `undo_merge.json`; `--undo` moves files back and removes it.
  Files replaced by `--overwrite` cannot be restored.

## Examples

```
mergefolders.py --dry-run -b 8     # preview
mergefolders.py -b 8 -l            # merge and log
mergefolders.py -e 4 --overwrite
mergefolders.py -t condensed -b 5  # -> condensed/<first 5 chars>/
mergefolders.py -b 0               # flatten
mergefolders.py -u                 # undo
```

## Exit status

`0` success, `1` error or some files skipped, `2` bad command line.

## Man page

`mergefolders.1` is included; view with `man ./mergefolders.1`.
