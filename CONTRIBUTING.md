# Contributing to AifaQuant

感谢你对 AifaQuant 的兴趣！本项目目前以个人研究和学习为主，但仍欢迎你提出问题、建议或代码贡献。

## 如何参与

1. **提交 Issue**：发现 bug、有功能建议、或对回测结果有疑问，欢迎开 Issue。
2. **提交 Pull Request**：
   - Fork 本仓库
   - 创建特性分支：`git checkout -b feature/your-feature`
   - 提交前运行：`ruff format . && ruff check . && pytest tests/ -v`
   - 提交 PR 并描述改动

## 代码规范

- Python 3.10+
- 使用 `ruff` 进行 lint 和 format
- 核心模块需补充单元测试
- 不要提交 `.env`、DuckDB 文件或个人 token

## 核心设计原则

- **核心层稳定**：接口定义在 `core/`、`models/base.py`、`strategy/base.py`
- **外部长处插件化**：新数据源/模型/执行器通过适配器接入，参考 `docs/INTEGRATION_ROADMAP.md`
- **回测结果必须带免责声明**：任何性能数字都要说明存在过拟合风险

## 联系方式

- 维护者：ivyzhi0807 / jiangjas@gmail.com
- 仓库：https://github.com/ivyzhi0807/aifa-quant
