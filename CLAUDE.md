# CLAUDE.md

Single-file Python 3 CLI (`mergefolders.py`, stdlib only) that merges sibling folders sharing a name prefix/suffix.
Docs: `README.md`, man page `mergefolders.1`, and `--help` (epilog text `EPILOG` in the script). Keep all three in sync when changing options.

## Conventions
- Every switch must work in upper and lower case. Short options are registered in both cases in `build_parser`; long options are lower-cased by `normalize_argv`.
- Each option has a Unix-style long alias (`--dry-run`, `--begin`, `--end`, `--overwrite`, `--log`, `--undo`, `--help`, `--version`).
- All file moves go through `Mover.move`, which handles collisions, `--dry-run`, and undo records. Never move files directly.
- Undo data is `undo_merge.json` (cross-platform, no shell). Overwritten files are not recoverable.
- Cross-platform: no `os.system`, no `.bat` generation.

## Testing
No test suite. Test manually in a scratch directory with `--dry-run` first, then a real run, then `--undo`:

    python mergefolders.py --dry-run -b 4
