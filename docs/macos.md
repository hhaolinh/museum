# Cabinet for macOS

[返回项目首页](../README.zh-CN.md)

适用于 Apple Silicon（M 系列芯片），macOS 12 或更新版本。不需要安装 Python、使用终端或下载源码。

## 第一次使用

从 [最新版本](https://github.com/hhaolinh/museum/releases/latest) 下载 `Cabinet-<版本>-arm64.zip`，解压并打开 `Cabinet.app`，点击「安装并打开」。应用会安装到你自己的「应用程序」文件夹，可以从启动台或 Spotlight 再次打开。

目前没有 Apple Developer ID 签名和公证。通过网络下载后，macOS 的安全检查可能会阻止首次打开；这不是可以靠自动更新消除的步骤。请参考 [Apple 关于打开应用与安全检查的说明](https://support.apple.com/102445)。不要关闭系统安全保护。

## 后续更新

默认自动检查、下载更新，在退出藏阁时安装。再次打开即使用新版，不需要重复下载到「下载」文件夹或拖拽替换应用。

「藏阁 → 检查更新…」可手动检查；「自动下载并安装更新」可以开关自动更新。更新来自本项目的 GitHub Releases，并使用独立的更新签名密钥验证。

## 收藏与备份

收藏独立保存在：

```text
~/Library/Application Support/Cabinet/
```

其中 `museum.db` 是藏品记录，`storage/` 是照片。应用更新不会替换这个文件夹。数据库结构升级前会自动备份到 `backups/`；若应用版本太旧，无法读取更高版本的数据库，会停止打开，不会覆盖数据。

从「帮助 → 打开收藏文件夹」访问数据。退出应用后，一起备份数据库和照片。日志可从「帮助 → 打开日志文件夹」访问。

桌面版首次使用是空收藏，不会把开发者电脑上的数据库或照片打包给别人。

---

## Maintainer: build and publish

The native AppKit/WKWebView host embeds a PyInstaller helper and Sparkle. The helper listens only on a random loopback port and requires a fresh app-only session. Python is bundled; user data is outside the app bundle.

```bash
python3 -m venv .venv-macos
source .venv-macos/bin/activate
pip install -r desktop/requirements-build.txt
python tools/build_macos.py
python tools/smoke_macos.py
python tools/release_macos.py
```

Outputs: `dist/Cabinet.app`, then the signed archive and `appcast.xml` under `dist/release/`. The build is Apple Silicon only. It is currently ad-hoc signed, not Developer ID signed or notarized.

The Sparkle Ed25519 private key belongs to the Keychain account `io.github.hhaolinh.cabinet`. Only the public key is committed at `desktop/macos/update-public-key.txt`. Do not export a private key into this repository. Keep the signing Keychain backed up; without Developer ID signing, losing this key prevents existing installations from trusting future updates.

For each release:

1. Increment both the version and the monotonically increasing build number in `desktop/macos/version.json`.
2. Build, test, and prepare release assets with the commands above. The release tool validates that the app's public key matches Keychain, signs the archive and feed together, and verifies the archive using the public key.
3. Create a GitHub release tagged `v<version>` in `hhaolinh/museum`, upload the generated ZIP and `appcast.xml`, then publish it. Do not mark stable releases as prereleases. Do not modify either signed file after signing.

The app follows `https://github.com/hhaolinh/museum/releases/latest/download/appcast.xml`. Release assets must be uploaded before publishing; a normal code push alone does not publish an application update. Private collection files and build outputs are excluded from Git.

A local signed update test can use `--feed-url http://127.0.0.1:<port>/appcast.xml --allow-local-feed` on a separate test build and `--download-url-prefix` plus `--allow-local-feed` on the release tool. Production builds reject non-HTTPS feeds. `CABINET_SKIP_INSTALL=1` and `CABINET_TEST_DATA_DIR` keep this test isolated from the installed app and personal collection.
