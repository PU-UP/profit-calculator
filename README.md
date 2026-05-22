# 交易小算盘（profit-calculator）

A 股 / ETF 做 T 净收益估算、涨跌幅与目标价换算，以及基于持仓截图的仓位占比分析。提供 Streamlit Web 界面与命令行工具。

## 功能

| 模块 | 说明 |
|------|------|
| **profit_calc** | 做 T 净收益（佣金万 3 最低 5 元、印花税、过户费等）；两价算涨跌幅；涨跌幅推算目标价 |
| **position_table** | 上传券商持仓截图，识别各标的市值与占总资产占比（依赖 MiniMax Vision） |

Web 应用包含两个标签页：`profit_calc`、`position_table`。

## 环境要求

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/)（推荐，用于依赖与启动）
- 使用 **仓位占比** 功能时还需：
  - Node.js（安装 [mmx-cli](https://www.npmjs.com/package/mmx-cli)）
  - MiniMax API Key（见下方配置）

## 快速开始

### 1. 安装 Python 依赖

在项目根目录执行：

```bash
uv sync
```

### 2. 配置环境变量（可选）

复制示例并按需填写：

```bash
cp .env.example .env
```

| 变量 | 说明 |
|------|------|
| `MINIMAX_API_KEY` | MiniMax 开放平台 API Key（仓位截图识别必填） |
| `MINIMAX_REGION` | `cn`（国内）或 `global`，默认 `cn` |
| `MINIMAX_BASE_URL` | 可选，覆盖 API Base URL |
| `MINIMAX_MMX_BIN` | 可选，`mmx` 可执行文件路径 |

### 3. 安装 mmx CLI（仅仓位功能需要）

```bash
npm install
```

安装后 `mmx` 位于 `node_modules/.bin/`，Python 会优先使用该路径。

### 4. 启动 Web 界面

默认端口 **8001**，浏览器访问：<http://localhost:8001>

**方式一：uv 入口（需先 `uv sync` 安装控制台脚本）**

```bash
uv sync
uv run start
```

指定端口：`uv run start 9000`，或 `PORT=9000 uv run start`。

**方式二：启动脚本**

```powershell
# Windows
.\scripts\start.ps1
.\scripts\start.ps1 9000
```

```bash
# Git Bash / WSL / macOS / Linux
./scripts/start.sh
./scripts/start.sh 9000
```

也可通过环境变量 `PORT` 指定端口。

**方式三：直接 streamlit**

```bash
uv run streamlit run streamlit_app.py --server.port 8001
```

## 命令行工具

安装项目后（`uv sync`），可用 `uv run` 调用：

| 命令 | 说明 |
|------|------|
| `uv run t-net-profit` | 交互式做 T 净收益计算 |
| `uv run price-to-pct` | 两价 → 涨跌幅（%） |
| `uv run pct-to-price` | 涨跌幅 → 目标价 |

### 辅助脚本

```bash
# 校验 MiniMax API Key 与 mmx vision
uv run python scripts/check_mmx_key.py

# 从截图提取持仓表（CLI，默认 screenshots/table.png）
uv run python scripts/minimax_position_table.py
uv run python scripts/minimax_position_table.py screenshots/my.png
```

可将打码后的截图放在 `screenshots/` 目录做本地对照；**勿将含完整账号、资产信息的原图提交到公开仓库**。

## 项目结构

```
profit_calculator/
├── streamlit_app.py      # Web 入口
├── profit_calc/          # 计算与 UI 逻辑
│   ├── ui.py             # profit_calc 页
│   ├── position_ui.py    # position_table 页
│   └── position_extract.py
├── scripts/
│   ├── start.ps1 / start.sh
│   ├── check_mmx_key.py
│   └── minimax_position_table.py
├── screenshots/          # 本地测试截图（勿提交敏感原图）
├── pyproject.toml
└── .env.example
```

## 费用与数据说明

- 做 T 费用模型为常见 A 股规则近似（万 3 佣金、最低 5 元、卖出印花税 0.05%、过户费 0.001% 等），**仅供参考**，实际以券商交割单为准。
- 仓位识别依赖大模型对截图的 OCR/理解，复杂界面或模糊图片可能出错，请人工核对。

## 许可证

本项目为个人工具性质，使用前请自行评估投资风险与 API 费用。
