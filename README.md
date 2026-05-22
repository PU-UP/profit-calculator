# 交易小算盘（profit-calculator）

A 股 / ETF 做 T 净收益估算、涨跌幅与目标价换算，以及基于持仓截图的仓位占比分析。提供 **Streamlit** 与 **NiceGUI（PWA）** 双 Web 入口及命令行工具。

## 功能

| 模块 | 说明 |
|------|------|
| **profit_calc** | 做 T 净收益（佣金万 3 最低 5 元、印花税、过户费等）；两价算涨跌幅；涨跌幅推算目标价 |
| **position_table** | 上传券商持仓截图，识别各标的市值与占总资产占比（MiniMax Vision + Text，Python httpx） |

Web 应用包含两个标签页：`profit_calc`、`position_table`。

## Web 入口对比

| 项目 | Streamlit | NiceGUI |
|------|-----------|---------|
| 启动 | `uv run start` | `uv run start-nicegui` |
| 移动端 | 一般 | 较好（Quasar） |
| PWA / 加主屏幕 | 否 | 是 |
| 计算历史 | `session_state`（刷新可能丢失） | `app.storage.user`（持久） |
| 仓位识别后端 | Python httpx（与 NiceGUI 共用） | 同左 |

## 环境要求

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/)（推荐，用于依赖与启动）
- 使用 **仓位占比** 功能时需配置 **MiniMax API Key**（见下方）
- **Node.js / mmx CLI**：仓位识别默认优先 mmx（与改版前一致），需 `npm install`；无 mmx 时自动改用 httpx

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
| `MINIMAX_MMX_BIN` | 可选，仅 mmx 诊断脚本使用 |
| `NICEGUI_STORAGE_SECRET` | 可选，NiceGUI 用户存储加密密钥（生产环境请设置） |

### 3. 启动 Web 界面

默认端口 **8001**。

**Streamlit（原界面）**

```bash
uv run start
# 或 .\scripts\start.ps1  /  ./scripts/start.sh
```

**NiceGUI（改进 UI + PWA）**

```bash
uv run start-nicegui
# 或 .\scripts\start-nicegui.ps1  /  ./scripts/start-nicegui.sh
```

指定端口：`uv run start 9000` / `uv run start-nicegui 9000`，或 `PORT=9000`。

浏览器访问：<http://localhost:8001>

**iPhone PWA（NiceGUI）**：部署到 HTTPS 后，Safari → 分享 →「添加到主屏幕」。

### 4. mmx CLI（可选）

仅运行 `scripts/check_mmx_key.py` 时需要：

```bash
npm install
```

## 命令行工具

| 命令 | 说明 |
|------|------|
| `uv run t-net-profit` | 交互式做 T 净收益计算 |
| `uv run price-to-pct` | 两价 → 涨跌幅（%） |
| `uv run pct-to-price` | 涨跌幅 → 目标价 |

### 辅助脚本

```bash
# 校验 MiniMax API Key 与 mmx vision（需 npm install）
uv run python scripts/check_mmx_key.py

# 从截图提取持仓表（Python httpx，默认 screenshots/table.png）
uv run python scripts/minimax_position_table.py
uv run python scripts/minimax_position_table.py screenshots/my.png
```

### Linux 部署（NiceGUI）

参考 `scripts/deploy/deploy.sh` 与 `scripts/deploy/profit-calculator.service`（使用 pip，与本地 `uv` 工作流独立）。

## 项目结构

```
profit-calculator/
├── streamlit_app.py       # Streamlit 入口
├── nicegui_app.py         # NiceGUI 入口 + PWA
├── profit_calc/
│   ├── ui.py              # Streamlit 计算器
│   ├── position_ui.py     # Streamlit 仓位页
│   ├── nicegui_calc.py    # NiceGUI 计算器
│   ├── nicegui_position.py
│   ├── minimax_client.py  # MiniMax Python API
│   └── position_extract.py
├── scripts/
│   ├── start.ps1 / start.sh
│   ├── start-nicegui.ps1 / start-nicegui.sh
│   └── deploy/            # Linux 部署参考
├── pyproject.toml
└── .env.example
```

## 费用与数据说明

- 做 T 费用模型为常见 A 股规则近似（万 3 佣金、最低 5 元、卖出印花税 0.05%、过户费 0.001% 等），**仅供参考**，实际以券商交割单为准。
- 仓位识别依赖大模型对截图的 OCR/理解，复杂界面或模糊图片可能出错，请人工核对。

## 许可证

本项目为个人工具性质，使用前请自行评估投资风险与 API 费用。
