from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path


DEFAULT_EXCLUDE_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "project_minimal"}


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def should_skip(path: Path, root: Path, include_venv: bool) -> bool:
    if include_venv:
        return False
    rel_parts = path.relative_to(root).parts
    return any(part in DEFAULT_EXCLUDE_DIRS for part in rel_parts)


def collect_files(root: Path, include_venv: bool) -> list[tuple[int, Path]]:
    files: list[tuple[int, Path]] = []
    for path in root.rglob("*"):
        if should_skip(path, root, include_venv):
            continue
        if not path.is_file():
            continue
        try:
            files.append((path.stat().st_size, path.relative_to(root)))
        except OSError:
            continue
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Print project size summaries.")
    parser.add_argument("root", nargs="?", default=".", help="Project root to analyze")
    parser.add_argument("--include-venv", action="store_true", help="Include .venv/.git/cache folders")
    parser.add_argument("--top", type=int, default=30, help="Number of entries to print")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files = collect_files(root, args.include_venv)
    total = sum(size for size, _path in files)

    folder_sizes: dict[Path, int] = defaultdict(int)
    ext_sizes: dict[str, int] = defaultdict(int)
    for size, rel_path in files:
        parts = rel_path.parts
        for depth in range(1, len(parts)):
            folder_sizes[Path(*parts[:depth])] += size
        ext_sizes[rel_path.suffix.lower() or "<no_ext>"] += size

    print(f"Root: {root}")
    print(f"Total: {human_size(total)} ({total:,} bytes)")

    print(f"\nLargest folders TOP {args.top}")
    for folder, size in sorted(folder_sizes.items(), key=lambda item: item[1], reverse=True)[: args.top]:
        print(f"{human_size(size):>10}  {folder}")

    print(f"\nLargest files TOP {args.top}")
    for size, rel_path in sorted(files, reverse=True)[: args.top]:
        print(f"{human_size(size):>10}  {rel_path}")

    print(f"\nExtension sizes TOP {args.top}")
    for ext, size in sorted(ext_sizes.items(), key=lambda item: item[1], reverse=True)[: args.top]:
        print(f"{human_size(size):>10}  {ext}")


if __name__ == "__main__":
    main()
