# MacroPulse — 美股新闻 AI 监控

MacroPulse 的自动处理链路：

```text
免费财经 RSS → 最新未发送新闻 → 情绪/事件分析 → 受影响股票
             → QQQ 成交量 + VIX + 10 年期收益率验证
             → Telegram 预警 → SQLite 去重历史
```
<img width="889" height="1920" alt="dad37a6c25928fbebc7884824fd27fe6" src="https://github.com/user-attachments/assets/0c11863e-ef21-42a1-862f-b46d3656b1d4" />

## 本地快速运行

演示行情不需要额外依赖：

```powershell
python -m macropulse "Fed unexpectedly cuts rates"
```

安装并使用 yfinance 行情：

```powershell
python -m pip install -e ".[market]"
python -m macropulse "Fed unexpectedly cuts rates" --market yfinance
```

## RSS 自动模式

设置 Telegram 环境变量后，获取最新且未成功发送的 RSS 新闻：

```powershell
$env:TELEGRAM_BOT_TOKEN="你的 Bot Token"
$env:TELEGRAM_CHAT_ID="你的 Chat ID"
python -m macropulse --latest --market yfinance --telegram
```

默认使用 Google News 的最近一天美股新闻 RSS。可以更换来源：

```powershell
$env:NEWS_RSS_URL="https://example.com/finance.rss"
python -m macropulse --latest --market yfinance --telegram
```

程序只在 Telegram 成功返回后将新闻标记为已发送；发送失败会在下一轮重试。历史数据库位于：

```text
data/macropulse.db
```

数据库的 `deliveries` 表保存标题、链接、发布时间、发送时间、成功状态、错误信息及完整分析 JSON。

## 部署到 GitHub 私有仓库

### 1. 提交项目

在 GitHub 新建一个 Private repository，然后在项目目录执行（替换远端地址）：

```powershell
git add .github .env.example .gitignore README.md data macropulse pyproject.toml tests
git commit -m "feat: add automated MacroPulse RSS monitor"
git branch -M main
git remote add origin https://github.com/你的用户名/你的私有仓库.git
git push -u origin main
```

如果已经配置过 `origin`，不要再次执行 `git remote add origin`。

### 2. 添加 Telegram Secrets

进入私有仓库：

```text
Settings → Secrets and variables → Actions → New repository secret
```

添加两个 Secret：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

可选：在同一页面的 `Variables` 标签添加 `NEWS_RSS_URL`，不添加则使用内置免费 RSS。

### 3. 允许工作流保存 SQLite

进入：

```text
Settings → Actions → General → Workflow permissions
```

选择 `Read and write permissions` 并保存。工作流需要将更新后的 `data/macropulse.db` 提交回私有仓库，才能在不同临时 Runner 之间去重。

### 4. 首次手动测试

进入：

```text
Actions → MacroPulse RSS Monitor → Run workflow
```

成功后应看到 Telegram 消息，并在仓库中出现 `data/macropulse.db`。之后 [.github/workflows/macropulse.yml](.github/workflows/macropulse.yml) 会每 30 分钟自动执行一次。

GitHub 定时任务可能有几分钟排队延迟，并不保证在整点精确启动。私有仓库 Actions 是否产生费用取决于账户套餐包含的运行分钟数；此工作流每轮很短，但仍应在 GitHub Billing 页面查看实际用量。

## 运行测试

```powershell
python -m unittest discover -s tests -v
```

可选 FinBERT：

```powershell
python -m pip install -e ".[ai]"
python -m macropulse "Fed unexpectedly cuts rates" --analyzer finbert
```
