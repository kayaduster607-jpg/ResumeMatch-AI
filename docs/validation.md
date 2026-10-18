# 公开发布验证记录

验证日期：2026-10-18。

## 验证结果

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 前端依赖安装 | 通过 | 使用原有 `package-lock.json` 执行 `npm ci --ignore-scripts --no-audit --no-fund` |
| 前端类型与构建 | 通过 | `npm run build`，Node.js 22.22.2，锁文件解析得到 Vite 6.4.2 |
| 后端现有单元测试 | **87 通过，4 失败** | `backend/tests/` 全部 91 项测试；失败项目见下表 |
| 架构图 | 通过 | SVG 导出 PNG 后检查中文显示、边界和连接线 |
| 发布文件检查 | 通过 | 排除所有 env 文件、浏览器配置/登录态、数据库、虚拟环境、Node 依赖、输出目录、压缩包和 Word 文档 |

后端验证使用隔离的 Python 3.13.5 环境，仅安装服务层测试需要的 pytest、Pydantic、pydantic-settings、SQLAlchemy、PyMySQL、FastAPI 和 python-multipart 等依赖。没有安装 sentence-transformers 等完整模型依赖，没有连接 MySQL 或真实模型服务。运行测试前关闭了 Pydantic dotenv 加载，并设置 `LLM_PROVIDER=mock`、`LLM_STRICT_MODE=false`、`DEBUG=false`；没有读取原项目的任何 `.env` 文件。

该结果验证了现有单元测试在上述环境中的表现，**不等于完整后端安装、数据库集成、真实模型或招聘平台端到端验证**。README 推荐 Python 3.11 是为了配合原有依赖锁定组合，未声称完整依赖已在 Python 3.13 上验证。

## 已有失败测试

| 测试 | 实际结果 | 当前影响 |
| --- | --- | --- |
| `test_jd_parse_service.py::TestMockParseJD::test_english_jd` | 英文 JD 的 `responsibilities` 为空 | 英文职责段落的规则解析需要完善 |
| `test_scoring_service.py::TestScoreSkills::test_perfect_match` | 必备技能全命中但无加分技能时返回 90，测试期望 100 | 技能评分实现和测试的满分定义不同 |
| `test_scoring_service.py::TestScoreSkills::test_alias_matching` | 别名匹配成功，但同样返回 90，测试期望 100 | 同上；应先明确评分规则，再同步实现和测试 |
| `test_skill_normalizer.py::TestNormalizeSkill::test_unknown_skill` | `SomeUnknownTech` 被识别为 `C` | 技能模糊匹配需要增加词边界约束 |

本次没有更改这些评分、解析或归一化规则，也没有修改断言以掩盖失败。

## 本次发布调整

- 重写中文 README，按代码核实功能、权重、配置、端口、数据存储和部署方式。
- 新增可维护的架构 SVG、PNG 及标准库绘图脚本。
- 为 `InterviewStartData` 补充后端两种会话路径均已返回的 `used_ai: boolean`，修复原有 TS2339 构建错误。
- 加强 `.gitignore`，使用独立、无旧 Git 历史的发布副本；原暂存区含浏览器运行资料，未用于推送。
- 将公开示例简历中的联系方式替换为 `13800000000` 和 `demo@example.com`。示例经历及数字仅为演示内容。

## 本地复现单元测试

按 README 安装后端依赖并激活后端虚拟环境后运行：

```bash
python -m pip install pytest==8.3.4
cd backend
python -m pytest -q -o addopts=
```

如需完全关闭 dotenv 加载，可从 `backend/` 目录使用以下启动方式：

```python
import os
import pytest
from app.core.config import Settings

# Disable local dotenv loading; use an explicit test configuration.
Settings.model_config["env_file"] = None
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LLM_STRICT_MODE"] = "false"
os.environ["DEBUG"] = "false"

raise SystemExit(pytest.main(["-q", "-o", "addopts=", "tests"]))
```
