# 手机随时访问部署步骤

目标：把 `weight-loss-assistant` 单独上传到 GitHub，再部署到 Streamlit Community Cloud。完成后，手机不在电脑旁边也能打开。

## 1. 只上传这个文件夹

不要上传上一级目录 `New project`。它里面有很多无关文件。

应该上传的目录是：

```text
/Users/mac/Documents/New project/weight-loss-assistant
```

不要上传这些本地文件：

```text
.env
.venv/
data/
.pytest_cache/
__pycache__/
```

这些已经写进 `.gitignore`，正常 Git 上传不会带上它们。

## 2. 创建 GitHub 仓库

推荐仓库名：

```text
weight-loss-assistant
```

如果你用 GitHub Desktop：

1. 选择 Add local repository。
2. 选择 `weight-loss-assistant` 文件夹。
3. 如果提示不是 Git 仓库，选择 create a repository。
4. Commit 后 Publish repository。
5. 建议选 Private。

如果你用命令行：

```bash
cd "/Users/mac/Documents/New project/weight-loss-assistant"
git init
git add .env.example .gitignore .streamlit DEPLOY.md README.md app.py fatloss pyproject.toml requirements.txt runtime.txt tests
git commit -m "Initial weight loss assistant"
```

然后在 GitHub 网页创建一个空仓库，按 GitHub 提示添加 remote 并 push。

## 3. 部署到 Streamlit Community Cloud

1. 打开 Streamlit Community Cloud。
2. 用 GitHub 登录。
3. New app。
4. Repository 选择 `weight-loss-assistant`。
5. Branch 选 `main`。
6. Main file path 填：

```text
app.py
```

如果你把整个大项目传到了 GitHub，而不是单独传 `weight-loss-assistant`，Main file path 才需要填：

```text
weight-loss-assistant/app.py
```

## 4. 配置 DeepSeek Secrets

在 Streamlit Cloud 的 app Settings -> Secrets 中填写：

```toml
DEEPSEEK_API_KEY = "你的 DeepSeek Key"
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
REQUEST_TIMEOUT = "30"
```

不要把真实 Key 写进 GitHub 文件。

## 5. 手机上的用法

部署完成后，Streamlit 会给你一个 `https://...streamlit.app` 网址。

在手机 Safari 或 Chrome 打开这个网址，然后添加到主屏幕即可。电脑关机、合盖、断网都不影响云端访问。

## 6. 数据备份

免费云端环境可能休眠或重启。长期记录体重和打卡时，建议每隔几天在“设置”里点击“导出备份 JSON”。换设备或数据丢失时，再用“导入备份 JSON”恢复。

