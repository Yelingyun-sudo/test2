# External Tools

本目录用于存放 website_analytics 项目所需的外部工具和依赖组件。

这些工具通常需要单独构建（如 Docker 镜像），或者作为独立服务运行，不直接集成到主项目的 Python 依赖中。

## 目录结构

```
external/
├── README.md                 # 本文件
└── cloudflare-bypass/        # Cloudflare 验证绕过工具
```

## 工具列表

| 工具 | 说明 | 运行方式 |
|------|------|----------|
| [cloudflare-bypass](./cloudflare-bypass/) | Cloudflare Turnstile 验证绕过工具 | Docker 容器 |

## 使用说明

每个工具目录下都有独立的 `README.md` 文件，详细说明该工具的：

- 功能介绍
- 构建方法
- 使用示例
- 集成方式

## 添加新工具

如需添加新的外部工具，请：

1. 在本目录下创建独立的子目录
2. 提供完整的构建文件（如 Dockerfile、Makefile 等）
3. 编写详细的 README.md 说明文档
4. 更新本文件的工具列表
