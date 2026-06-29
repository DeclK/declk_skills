---
name: arxiv-download
description: 使用国内镜像快速下载 arXiv 论文 PDF。当用户要下载 arXiv 论文、获取 arxiv 文章、下载论文 PDF 时触发。用户可调用 /arxiv-download 来激活。
user-invocable: true
allowed-tools: "Bash"
---

# Arxiv Download — 国内镜像下载 arXiv 论文

国内直接访问 `arxiv.org` 速度极慢（几 KB/s），使用国内镜像可秒级下载。

## 方法

将 arXiv URL 中的 `arxiv.org` 替换为 `cn.arxiv.org`：

```bash
# 原始链接
https://arxiv.org/pdf/2508.02317

# 镜像链接
https://cn.arxiv.org/pdf/2508.02317
```

## 执行

```bash
wget -O <output.pdf> "https://cn.arxiv.org/pdf/<paper_id>"
```
