#!/usr/bin/env python3
"""Build a clean M3U playlist from authorized public sources."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXTINF_RE = re.compile(r"^#EXTINF:(?P<meta>.*?),(?P<name>.*)$", re.IGNORECASE)
ATTR_RE = re.compile(r'(?P<key>[\w-]+)="(?P<value>[^"]*)"')
URL_SCHEMES = {"http", "https", "rtmp", "rtsp"}


@dataclass(frozen=True)
class Channel:
    name: str
    url: str
    extinf: str
    group: str = ""


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def fetch_text(url: str, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "m3u-subscription-builder/1.0",
            "Accept": "application/vnd.apple.mpegurl,application/x-mpegurl,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme.lower() in URL_SCHEMES and bool(parsed.netloc)


def absolutize_url(base_url: str, maybe_url: str) -> str:
    if is_url(maybe_url):
        return maybe_url
    return urllib.parse.urljoin(base_url, maybe_url)


def parse_m3u(text: str, base_url: str = "") -> list[Channel]:
    channels: list[Channel] = []
    pending_extinf = ""
    pending_group = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("#EXTINF:"):
            pending_extinf = line
            continue

        if line.upper().startswith("#EXTGRP:"):
            pending_group = line.split(":", 1)[1].strip()
            continue

        if line.startswith("#"):
            continue

        url = absolutize_url(base_url, line)
        if not is_url(url):
            pending_extinf = ""
            pending_group = ""
            continue

        name = url
        extinf = pending_extinf
        match = EXTINF_RE.match(extinf)
        if match:
            name = match.group("name").strip() or url
        else:
            extinf = f"#EXTINF:-1,{name}"

        channels.append(Channel(name=name, url=url, extinf=extinf, group=pending_group))
        pending_extinf = ""
        pending_group = ""

    return channels


def read_manual_channels(path: Path) -> list[Channel]:
    if not path.exists():
        return []

    channels: list[Channel] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        filtered = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(filtered, fieldnames=["name", "url", "group", "logo", "tvg_id"])
        for row in reader:
            name = (row.get("name") or "").strip()
            url = (row.get("url") or "").strip()
            group = (row.get("group") or "").strip()
            logo = (row.get("logo") or "").strip()
            tvg_id = (row.get("tvg_id") or "").strip()
            if not name or not is_url(url):
                continue

            attrs = []
            if tvg_id:
                attrs.append(f'tvg-id="{escape_attr(tvg_id)}"')
            if logo:
                attrs.append(f'tvg-logo="{escape_attr(logo)}"')
            if group:
                attrs.append(f'group-title="{escape_attr(group)}"')
            attr_text = " " + " ".join(attrs) if attrs else ""
            channels.append(Channel(name=name, url=url, extinf=f"#EXTINF:-1{attr_text},{name}", group=group))
    return channels


def read_logo_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    logo_map: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        filtered = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(filtered, fieldnames=["name", "logo"])
        for row in reader:
            name = (row.get("name") or "").strip()
            logo = (row.get("logo") or "").strip()
            if name and is_url(logo):
                logo_map[normalize_name(name)] = logo
    return logo_map


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def extinf_attrs(extinf: str) -> dict[str, str]:
    match = EXTINF_RE.match(extinf)
    if not match:
        return {}
    return {attr.group("key"): attr.group("value") for attr in ATTR_RE.finditer(match.group("meta"))}


def add_extinf_attr(extinf: str, key: str, value: str) -> str:
    if not value or f"{key}=" in extinf:
        return extinf
    return extinf.replace(",", f' {key}="{escape_attr(value)}",', 1)


def escape_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def normalize_channel(channel: Channel, default_group: str, logo_map: dict[str, str]) -> Channel:
    group = channel.group or default_group
    extinf = channel.extinf
    attrs = extinf_attrs(extinf)
    logo = attrs.get("tvg-logo", "") or logo_map.get(normalize_name(channel.name), "")
    extinf = add_extinf_attr(extinf, "group-title", group)
    extinf = add_extinf_attr(extinf, "tvg-logo", logo)
    return Channel(name=channel.name.strip(), url=channel.url.strip(), extinf=extinf, group=group)


def dedupe(channels: Iterable[Channel]) -> list[Channel]:
    seen_urls: set[str] = set()
    result: list[Channel] = []
    for channel in channels:
        key = channel.url.rstrip("/")
        if key in seen_urls:
            continue
        seen_urls.add(key)
        result.append(channel)
    return result


def probe_url(url: str, timeout: float) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "m3u-subscription-builder/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            return 200 <= status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def write_m3u(path: Path, channels: Iterable[Channel]) -> None:
    lines = ["#EXTM3U"]
    for channel in channels:
        lines.append(channel.extinf)
        lines.append(channel.url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build(args: argparse.Namespace) -> int:
    source_urls = read_lines(Path(args.sources))
    all_channels: list[Channel] = []

    for source_url in source_urls:
        if not is_url(source_url):
            print(f"skip invalid source: {source_url}", file=sys.stderr)
            continue
        try:
            text = fetch_text(source_url, args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"fetch failed: {source_url} ({exc})", file=sys.stderr)
            continue
        all_channels.extend(parse_m3u(text, source_url))

    all_channels.extend(read_manual_channels(Path(args.channels)))
    logo_map = read_logo_map(Path(args.logos))
    normalized = [normalize_channel(channel, args.default_group, logo_map) for channel in all_channels]
    unique = dedupe(normalized)

    if args.check:
        checked: list[Channel] = []
        for channel in unique:
            if probe_url(channel.url, args.probe_timeout):
                checked.append(channel)
            else:
                print(f"dead or unreachable: {channel.name} {channel.url}", file=sys.stderr)
        unique = checked

    if args.limit:
        unique = unique[: args.limit]

    write_m3u(Path(args.output), unique)
    print(f"wrote {len(unique)} channels to {args.output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an M3U playlist from authorized public sources.")
    parser.add_argument("--sources", default="sources.txt", help="text file with source M3U URLs")
    parser.add_argument("--channels", default="channels.csv", help="optional manual channel CSV")
    parser.add_argument("--logos", default="logos.csv", help="optional channel logo CSV")
    parser.add_argument("--output", default="playlist.m3u", help="output M3U path")
    parser.add_argument("--default-group", default="", help="group title added when a channel has no group")
    parser.add_argument("--timeout", type=float, default=20.0, help="source fetch timeout in seconds")
    parser.add_argument("--check", action="store_true", help="probe each stream and keep only reachable URLs")
    parser.add_argument("--probe-timeout", type=float, default=6.0, help="stream probe timeout in seconds")
    parser.add_argument("--limit", type=int, default=0, help="optional max number of channels, useful for testing")
    return build(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
