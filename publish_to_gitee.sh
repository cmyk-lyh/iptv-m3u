#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/your/gitee/repo [playlist.m3u]" >&2
  exit 2
fi

repo_dir="$1"
playlist="${2:-playlist.m3u}"

if [[ ! -d "$repo_dir/.git" ]]; then
  echo "Not a git repository: $repo_dir" >&2
  exit 2
fi

if [[ ! -f "$playlist" ]]; then
  echo "Playlist not found: $playlist" >&2
  exit 2
fi

cp "$playlist" "$repo_dir/playlist.m3u"
git -C "$repo_dir" add playlist.m3u
git -C "$repo_dir" commit -m "Update IPTV playlist" || true
git -C "$repo_dir" push

echo "Published playlist.m3u to Gitee repository."

