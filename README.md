# M3U subscription builder

这个目录是一套“公开/授权直播源聚合”脚本：从 `sources.txt` 里的 M3U 地址拉取频道，合并 `channels.csv` 里的手工频道，最后生成电视可用的 `playlist.m3u`。

如果源本身没有台标，可以在 `logos.csv` 里补：

```csv
CCTV-1,https://example.com/cctv1.png
湖南卫视,https://example.com/hunan.png
```

生成时脚本会按频道名自动添加 `tvg-logo`。

## 从哪抓取

优先用这些来源：

1. 你自己有授权的源：运营商 IPTV、酒店/校园网/公司内网、自家摄像头、你购买服务明确允许外部播放器使用的 M3U。
2. 电视台或平台公开提供的 HLS/M3U8：例如官网播放页、官方 App 抓包得到且条款允许个人使用的地址。
3. 公开聚合库：例如 iptv-org 的公开频道列表 `https://iptv-org.github.io/iptv/index.m3u`。

不建议抓：

1. 写着“全网 VIP / 央视卫视秒播 / 港澳台付费源”的资源站。
2. 需要破解、绕登录、绕地区限制、绕 DRM、带盗播切片的地址。
3. 来路不明的短链订阅。电视端会直接访问它们，隐私和稳定性都很差。

关于你提到的频道类型：

1. 中国各省卫视：建议使用电视台官网、运营商 IPTV、或明确授权的公开 HLS/M3U8。
2. 电影/动漫频道：很多属于付费或版权频道，只添加你有授权的源。
3. 成人频道：只添加你所在地区合法、你有授权、且仅供成年人使用的源；不要把违法或未授权源放进公开仓库。

网速是否流畅主要看直播源服务器，不看 GitHub。GitHub 只托管 `playlist.m3u`，电视播放时会直接访问每个频道 URL。想减少卡顿：

1. 优先选离你网络近的 CDN/运营商源。
2. 少用短链和多层代理源。
3. 用 `--check` 定期剔除当前不可访问的源。
4. 同一个频道保留 1-2 个稳定地址即可，别堆太多重复源。

## 使用

```bash
cd /Users/xxx/Documents/Codex/2026-06-18/new-chat/outputs/m3u-subscription
python3 build_playlist.py --output playlist.m3u
```

如果想过滤掉当前不可访问的流：

```bash
python3 build_playlist.py --output playlist.m3u --check
```

如果只想生成中国各省卫视、电影、动漫：

```bash
python3 build_playlist.py --preset china-tv --check --output playlist.m3u
```

如果你的源台标很全，再加 `--require-logo`。

如果只想先测试前 20 个频道：

```bash
python3 build_playlist.py --output playlist.m3u --limit 20
```

本地验证中国频道筛选规则：

```bash
python3 build_playlist.py \
  --sources tests/fixtures/empty-sources.txt \
  --channels tests/fixtures/china-tv-channels.csv \
  --preset china-tv \
  --require-logo \
  --output /tmp/china-tv-test.m3u
diff -u tests/fixtures/expected-china-tv.m3u /tmp/china-tv-test.m3u
```

## 发布到 Gitee

先在 Gitee 创建一个公开仓库，比如 `iptv-subscribe`，然后克隆到本机：

```bash
git clone https://gitee.com/你的用户名/iptv-subscribe.git
```

生成并推送：

```bash
python3 build_playlist.py --output playlist.m3u --check
bash publish_to_gitee.sh /path/to/iptv-subscribe playlist.m3u
```

电视订阅地址通常可用其中一种：

```text
https://gitee.com/你的用户名/iptv-subscribe/raw/master/playlist.m3u
https://gitee.com/你的用户名/iptv-subscribe/raw/main/playlist.m3u
```

如果你开启 Gitee Pages，也可以用 Pages 地址，例如：

```text
https://你的用户名.gitee.io/iptv-subscribe/playlist.m3u
```

## 放到 GitHub 自动执行

把这个目录里的所有文件上传到一个 GitHub 仓库根目录，包含隐藏目录 `.github/workflows/update-playlist.yml`。

GitHub Actions 会：

1. 每 6 小时自动运行一次。
2. 读取 `sources.txt`。
3. 只保留中国相关的卫视、电影、动漫/少儿频道。
4. 确认生成结果不是空文件。
5. 生成 `playlist.m3u` 并自动提交回仓库。

默认不会在 GitHub runner 上探测直播流，因为很多中国源在 GitHub 海外网络上不可达，但在电视所在网络可以播放。手动运行 workflow 时可以把 `check_streams` 设为 `true`，让 GitHub 先探测再发布。

也可以在 GitHub 仓库页面手动运行：

```text
Actions -> Update IPTV playlist -> Run workflow
```

电视订阅地址用 raw 链接：

```text
https://raw.githubusercontent.com/你的用户名/你的仓库名/main/playlist.m3u
```

如果默认分支是 `master`：

```text
https://raw.githubusercontent.com/你的用户名/你的仓库名/master/playlist.m3u
```

如果你想让我直接帮你推到 GitHub，需要你本机已经配置好 `git` 登录，或者给我一个你创建好的空仓库 HTTPS 地址。不要把 GitHub 密码发给我；如果需要令牌，只用 GitHub fine-grained token，并且只给这个仓库的 `Contents: Read and write` 权限。
