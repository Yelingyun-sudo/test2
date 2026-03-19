# 批量拉取站点详情脚本

## 功能说明

`fetch_site_details.py` 用于批量拉取站点数据：
1. 自动遍历所有分页，获取所有 records
2. 对每个 record 调用 `getInfoById` 接口获取详细信息
3. 将结果打印到控制台并保存为 JSON 文件

## 使用方法

### 基本用法

```bash
# 拉取所有数据（默认状态为 3，即已完成的任务）
uv run python scripts/fetch_site_details.py \
  --url http://43.143.137.121:8081 \
  --cookie "JSESSIONID=35B9F7549242D7DD140E75C3FAAEBD23" \
  --no-verify

# 指定输出文件
uv run python scripts/fetch_site_details.py \
  --url http://43.143.137.121:8081 \
  --cookie "JSESSIONID=xxxxx" \
  --output resources/my_output.json \
  --no-verify

# 测试模式（只拉取前 2 页）
uv run python scripts/fetch_site_details.py \
  --url http://43.143.137.121:8081 \
  --cookie "JSESSIONID=xxxxx" \
  --max-pages 2 \
  --no-verify
```

### 命令行参数

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--url` | ✅ | - | API 基础 URL |
| `--cookie` | ✅ | - | Cookie 字符串（如 `JSESSIONID=xxxxx`） |
| `--output` | ❌ | `backend/resources/site_details.json` | 输出 JSON 文件路径 |
| `--status` | ❌ | `3` | 筛选任务状态（3=已完成） |
| `--limit` | ❌ | `10` | 每页记录数 |
| `--max-pages` | ❌ | 无限制 | 最大页数限制（用于测试） |
| `--delay` | ❌ | `0.5` | 请求间隔（秒） |
| `--no-verify` | ❌ | - | 禁用 SSL 证书验证 |

### 输出格式

输出的 JSON 文件结构：

```json
{
  "total": 10,
  "failed_count": 0,
  "failed_ids": [],
  "records": [
    {
      "id": 3906,
      "sourceUrl": "https://example.com",
      "status": 3,
      "result": "...",
      "siteText": "...",
      "imageInfo": [...],
      ...
    }
  ]
}
```

## 注意事项

1. **Cookie 有效期**：确保提供的 Cookie 未过期
2. **请求频率**：默认每个请求间隔 0.5 秒，避免请求过快被限流
3. **SSL 证书**：如果目标服务器使用自签名证书，需要添加 `--no-verify` 参数
4. **网络稳定性**：脚本内置了重试机制，但如果网络不稳定可能导致部分请求失败
5. **数据量**：如果总数据量很大（如 505 条记录），完整拉取可能需要较长时间

## 错误处理

- 遇到单个请求失败时，脚本会继续处理下一个，并在最后汇总失败的 ID
- 失败的 ID 会记录在输出 JSON 的 `failed_ids` 字段中
- 可以根据失败的 ID 单独重新拉取

## 示例输出

```
🚀 开始拉取站点数据...
   基础 URL: http://43.143.137.121:8081
   状态筛选: 3
   每页记录: 10
   请求间隔: 0.5 秒

📄 正在获取第 1 页...
   ✓ 获取到 10 条记录（累计 10/505）
📄 正在获取第 2 页...
   ✓ 获取到 10 条记录（累计 20/505）
...

📊 共获取 505 条 record

🔍 开始获取每个站点的详细信息...

  [1/505] 正在获取站点 3906 的详细信息...
    ✓ 成功获取站点 3906 详情
  [2/505] 正在获取站点 3899 的详细信息...
    ✓ 成功获取站点 3899 详情
...

✅ 详情获取完成：成功 505 条，失败 0 条

💾 结果已保存到: backend/resources/site_details.json
   总记录数: 505
   文件大小: 9123.45 KB

🎉 任务完成！
```

## 常见问题

### Q: Cookie 如何获取？

A: 在浏览器中登录目标网站，打开开发者工具（F12），在 Network 标签页中找到任意请求，复制 Cookie 请求头的值。

### Q: 如何只拉取部分数据测试？

A: 使用 `--max-pages` 参数限制页数，例如 `--max-pages 2` 只拉取前 2 页。

### Q: 遇到 SSL 证书错误怎么办？

A: 添加 `--no-verify` 参数禁用 SSL 证书验证。

### Q: 如何加快拉取速度？

A: 可以减小 `--delay` 参数的值，但要注意不要设置太小导致被限流。建议不低于 0.3 秒。

