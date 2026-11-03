# 启用 qBittorrent WebUI（awam://downloads/qb）

1. 打开 qBittorrent → **工具** → **选项** → **Web UI**
2. 勾选 **启用 Web 用户界面（远程控制）**
3. 地址默认 `http://127.0.0.1:8080`
4. 设置用户名/密码后，可用环境变量告知网关：

```powershell
$env:AWAM_QB_URL = "http://127.0.0.1:8080"
$env:AWAM_QB_USER = "admin"
$env:AWAM_QB_PASS = "your-password"
```

5. 验证：

```powershell
$env:PYTHONPATH = "G:\Projects\19AI\skills\awam-file\src"
python -m awam_resource_gateway backends
python -m awam_resource_gateway list "awam://downloads/qb/"
```
