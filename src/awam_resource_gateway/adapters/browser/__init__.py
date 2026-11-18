"""浏览器书签后端：`awam://browser/...`。

通过 `readers` 注册表按浏览器产品发现配置目录并解析收藏夹。
当前注册 Chrome / Edge（Chromium Bookmarks JSON）；新增浏览器只需加一个 Reader。
"""

from awam_resource_gateway.adapters.browser.adapter import BrowserAdapter

__all__ = ["BrowserAdapter"]
