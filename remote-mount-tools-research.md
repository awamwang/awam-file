# 远程存储挂载工具调研（SFTP / WebDAV / 网盘 → 本地盘符）

> 调研日期：2026-10-02
> 目标：把 SFTP 等远程存储挂载为本地存储；评估 CLI 可操作性，为 AI 自动化交互选型
> 状态：已完成调研，待开发落地（已补充挂载命令示例与模式区分）

---

## 1. 结论速览

| 需求 | 推荐方案 |
|---|---|
| 人手动用资源管理器浏览远程文件 | **RaiDrive**（Windows，免费够用） |
| 只挂 SFTP，要免费轻量 | **SSHFS-Win**（WinFsp） |
| 多种网盘/协议 + 命令行自动化 | **rclone**（首选，无挂载依赖） |
| 纯服务器文件操作（删/拷/同步） | **sftp / scp / ssh / rclone 命令**（根本不用挂载） |
| 付费省心、跨 Win/Mac | Mountain Duck、NetDrive、ExpanDrive |

**核心认知**：挂载类工具解决的是"像本地一样浏览"；而 AI 自动化场景下，挂载是中间层（引入缓存不一致、文件锁、常驻进程等坑），直接用 rclone/sftp 命令更稳。

---

## 2. RaiDrive 关键事实

- 把 SFTP、FTP、WebDAV、各大网盘（Google Drive / OneDrive / Dropbox…）映射为 Windows 资源管理器盘符
- 免费版：SFTP/FTP/WebDAV **支持读写**；限制为最多 8~10 个虚拟盘、有广告；大文件传输等高级功能需 Pro 版
- 基于 **WinFsp** 用户态文件系统，数据按需读取 + 本地缓存，不占本地磁盘空间
- 软件必须后台常驻，退出后挂载盘符立即断开
- 默认有元数据缓存，远端被其他客户端修改后本地不自动感知，需手动刷新
- 文件锁为本地模拟，多客户端并发写可能互相覆盖
- 不是网络重定向器，`net use X: /delete` 卸不掉，需在 RaiDrive 内断开

## 3. 替代工具对比

| 工具 | 平台 | 协议 | 费用 | CLI 可用 | 备注 |
|---|---|---|---|---|---|
| RaiDrive | Win | SFTP/FTP/WebDAV/网盘 | 免费版有限制 | ✅ 盘符透明 | 后台常驻 |
| SSHFS-Win | Win | SFTP | 开源免费 | ✅ | 依赖 WinFsp |
| rclone mount | Win/Mac/Linux | 几十种 | 开源免费 | ✅ | 可配 VFS 缓存参数 |
| WinSCP 挂载 | Win | SFTP/SCP/FTP | 开源免费 | ⚠️ 可访问但依赖驻留 | 适合顺手用，不适合自动化 |
| Mountain Duck | Win/Mac | 多协议+网盘 | 付费 | ✅ | 体验好，支持离线缓存 |
| NetDrive / ExpanDrive | Win/Mac | 多协议+网盘 | 付费 | ✅ | 开箱即用 |
| macOS Finder ⌘K | Mac | smb/sftp(只读体验差) | 内置 | ⚠️ | 无独立盘符 |

### 3.1 按平台选型建议
| 场景 | 首选 | 备选 |
|---|---|---|
| Linux 服务器 | **SSHFS**（最简） | rclone mount（多协议、缓存更强） |
| Windows | **rclone mount**（开源免费） | 不想折腾命令行则 RaiDrive |
| macOS | rclone mount | SSHFS + macFUSE |

## 4. CLI / AI 交互方案（重点）

### 4.1 挂载后透明使用（盘符/目录 = 普通路径）
挂载类工具挂出盘符或挂载点后，cmd / PowerShell / bash / Python / robocopy 等直接以原生命令操作：
```powershell
copy a.txt X:\upload\          # Windows 盘符
robocopy .\dist X:\site /MIR
```
各平台挂载命令示例（挂载点一旦就绪，`ls/cp/rm/mv/del` 与本地完全一致）：
```bash
# SSHFS（Linux）
sshfs user@host:/remote/path ~/mnt/sftp
fusermount -u ~/mnt/sftp

# SSHFS（macOS，需 macFUSE）
sshfs user@host:/remote/path ~/mnt/sftp
umount ~/mnt/sftp

# rclone mount（Linux/macOS 挂到目录）
rclone mount mysftp:/remote/path ~/mnt/sftp --vfs-cache-mode full

# rclone mount（Windows 挂到盘符 X:）
rclone mount mysftp:/remote/path X: --vfs-cache-mode full
```
> `--vfs-cache-mode full` 开启本地完整缓存，随机读写体验大幅提升；不缓存（off）时每次读走网络，性能差。

> **模式澄清**：挂载类工具（SSHFS / rclone mount / RaiDrive）是「模式 A：虚拟文件系统挂载」，挂载点即普通路径，原生命令 `copy/del/rm` 直接用；而 `sftp` 交互终端是「模式 B」，只能 `put/get`，不能直接用系统原生 `copy/rm`，不满足「像本地文件一样操作」的需求。

### 4.2 推荐：rclone 直接命令化（无挂载依赖）
```bash
rclone copy ./dist mysftp:var/www/html     # 上传
rclone delete mysftp:var/www/old.txt       # 删除
rclone move mysftp:a mysftp:b              # 移动/重命名
rclone lsd mysftp:var/www                  # 列目录
rclone sync ./src mysftp:backup --dry-run  # 同步（先干跑）
```
优点：每条命令独立、无常驻进程、可审计、几十种后端统一语法。

### 4.3 纯 SSH 系命令（服务器场景最简）
```bash
sftp user@host          # put / get / rm / mkdir 交互式
scp ./file user@host:/path/
ssh user@host "rm /path/file"
```

## 5. 开发注意事项

- [ ] 选定时，确认目标协议（SFTP / WebDAV / S3 / 网盘 API）是否被工具支持
- [ ] CLI 自动化优先 rclone 命令，挂载仅用于人工浏览场景
- [ ] 若必须挂载供脚本用：注意缓存一致性（远端变更需刷新）、并发写冲突、常驻进程守护
- [ ] Windows 长路径（>260 字符）在部分挂载实现上可能异常
- [ ] 凭证管理：rclone 用 `rclone config` 加密存储，RaiDrive 存在本地配置

## 6. 待办 / 下一步

- [ ] 在开发机实测 rclone + SFTP 后端（config 文件 + 常用命令）
- [ ] 如需挂载体验，对比 RaiDrive 免费版 vs rclone mount 的稳定性
- [ ] 封装常用操作（copy/delete/sync/list）为项目内脚本或 AI 工具调用
