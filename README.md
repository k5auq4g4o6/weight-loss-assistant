# 减脂计划小助手

一个本地和手机云端都能用的 Streamlit 小助手。它会根据个人档案、当天实际状态、午饭外食限制和晚饭自煮条件，生成每天的稳健减脂计划。

## 功能

- 今日计划：只填写今天可爬坡时间，助手会根据档案和历史记录生成热量、蛋白、爬坡、午饭外食、晚饭自煮。
- 打卡记录：记录体重、是否完成、实际爬坡分钟和练完感觉。
- 自动调整：第二天计划会参考近 7 天完成次数、实际分钟和练完感觉，自动决定进阶、维持或保守一点。
- DeepSeek 生成：默认调用 DeepSeek 直接安排当天计划，本地规则负责热量下限、训练安全边界和忌口硬过滤。
- 忌口过滤：忌口/过敏和不喜欢的食物是硬规则，AI 返回含禁用食材时会自动替换。
- 手机备份：一键导出/导入 JSON，适合 Streamlit Cloud 这种免费托管环境。
- 手机使用：页面顶部有导航，不依赖侧边栏；今日计划可一键生成 PNG 图片并保存/分享。

本助手面向普通成年人，不处理慢病、孕产、伤病、药物影响或康复训练。任何胸闷、头晕、关节刺痛或异常心率都应立即停止训练并寻求专业意见。

## 本地启动

```bash
cd weight-loss-assistant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

首次进入后，打开“设置”填写个人档案。每天在“今日计划”只选择今天可爬坡时间，然后点击“让助手安排今天”。没有 DeepSeek Key 时会自动使用本地规则版计划。

## DeepSeek 配置

本地运行可以复制示例文件：

```bash
cp .env.example .env
```

然后在 `.env` 中填写：

```bash
DEEPSEEK_API_KEY=你的 Key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

也可以在应用“设置”页保存到本机 `.env`。

## 手机使用

### 电脑在身边

电脑运行应用后，手机和电脑连同一个 Wi-Fi，手机浏览器打开电脑局域网 IP 的 8501 端口即可。电脑关机或断网后手机无法访问。

### 电脑不在身边

你已经有 GitHub 账号，推荐用 Streamlit Community Cloud：

1. 把整个项目推送到 GitHub 仓库。
2. 打开 Streamlit Community Cloud，选择该仓库。
3. Main file path 填：

   ```text
   weight-loss-assistant/app.py
   ```

4. 在应用 Settings 的 Secrets 中填写：

   ```toml
   DEEPSEEK_API_KEY = "你的 Key"
   DEEPSEEK_API_BASE = "https://api.deepseek.com"
   DEEPSEEK_MODEL = "deepseek-v4-flash"
   ```

5. 部署成功后，手机浏览器打开 Streamlit 提供的网址。

免费云端环境可能会休眠或重启，因此应用内提供“导出备份 JSON”和“导入备份 JSON”。建议每隔几天导出一次，尤其是在手机端长期使用时。

更详细的独立部署步骤见 [DEPLOY.md](DEPLOY.md)。

## 测试

```bash
cd weight-loss-assistant
pytest -q
```

测试覆盖：

- 档案缺失时给出补全提示。
- 热量缺口不会过激。
- 爬坡计划会根据当天可运动时间和近 7 天打卡历史调整。
- AI 返回的午晚餐会再次检查忌口和不喜欢的食物。
- 午饭只生成外食点餐建议，晚饭包含可煮步骤。
- DeepSeek 失败时自动回退本地规则版。
