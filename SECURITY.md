# Security Policy

## 敏感信息

AifaQuant 需要访问同花顺 iFind MCP 服务，因此你的 `.env` 文件中包含敏感 token。

**绝对不要将 `.env` 文件或任何包含 token 的内容提交到 Git。**

`.env` 已默认加入 `.gitignore`。如果你意外提交了 token：

1. 立即从 iFind 后台重置 token。
2. 从 Git 历史中删除相关提交（可参考 [GitHub 文档](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)）。
3. 联系我们报告情况。

## 报告安全问题

如果你发现任何安全漏洞或潜在风险，请通过邮件联系：

- jiangjas@gmail.com

请不要通过公开 Issue 披露敏感安全问题。

## 数据使用

- 本项目的回测数据仅供研究使用。
- 公开的 Release 附件（如 `v0.2.0-data`）中的 CSV 数据不构成投资建议。
