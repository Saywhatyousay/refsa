# RefSA - Reference Search and Add

RefSA（Reference Search and Add）是一个面向 Windows 的参考文献自动添加工具。它在后台常驻，监听一个全局快捷键。当你在任意程序中选中一段文献引用文字、按下快捷键后，RefSA 会无感地自动完成：读取选中文本、到 Crossref 检索、对候选结果打分、把最佳匹配作为一篇期刊文章（journalArticle）写入你的本地 Zotero 数据库，并用 Windows 系统通知（Toast）告诉你结果。

本工具不弹出任何窗口或对话框，全程无感运行，所有状态都记录到日志文件中。

## 运行条件

- 操作系统：Windows 10 或 Windows 11。
- Zotero：已安装并正在运行，且本地 HTTP 服务器已启用。
  - 打开 Zotero，菜单「编辑」-「设置」-「高级」-「常规」，勾选「允许本机上的其他应用程序连接 Zotero」（对应配置项 `extensions.zotero.httpServer.enabled = true`，端口默认 23119）。
- 网络：能够访问 Crossref（`https://api.crossref.org`），用于文献检索与匹配。
- 使用打包版（`RefSA.exe`）：无需安装 Python 及任何依赖。
- 使用源码版：需要 Python 3.11 及项目依赖（见下文「源码运行」）。

## 使用方式

### 方式一：使用打包好的 exe（推荐）

下载并解压 `RefSA.exe`，在命令提示符或 PowerShell 中进入其所在目录后按需调用。第一次运行时，RefSA 会在 Zotero 中请求一次写权限授权（弹一次授权框，选择「始终允许」即可），之后不再弹出。

### 方式二：源码运行

```bash
# 创建并激活环境（可选，示例用 mamba）
mamba create -n refsa python=3.11 -c conda-forge --override-channels
mamba activate refsa

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 命令行用法

| 命令 | 说明 |
| --- | --- |
| `RefSA.exe` | 启动常驻后台，开始监听全局热键。运行后不退出，保持后台待命。 |
| `RefSA.exe -l`（等价 `--list-collections`） | 以「我的文库」为根，列出 Zotero 中的所有分类（含子分类），并用 `*` 标记当前目标位置。 |
| `RefSA.exe -c 分类名`（等价 `--collection 分类名`） | 将目标分类设为指定名称，并持久化保存。之后导入的文献会放入该分类。 |
| `RefSA.exe --clear-collection` | 清除目标分类设置，回到默认的「我的文库」根目录。 |

说明：

- 默认目标为「我的文库」根目录。
- `-c` 只接受分类名称，不接受分类的 key；若存在多个同名分类，请使用唯一名称。
- 目标分类会持久化到用户数据目录（`%APPDATA%\RefSA\refsa_config.json`），在 exe 版本中同样有效。

## 完整使用步骤（选中并导入一篇文献）

1. 启动 Zotero（保持运行）。
2. 双击 `RefSA.exe` 启动后台监听（或用源码版 `python main.py`）。启动成功后右下角不弹窗，日志显示热键已注册。
3. 设置目标分类（可选）：默认放到「我的文库」。若想放入指定分类，先执行 `RefSA.exe -l` 查看有哪些分类，再执行 `RefSA.exe -c 分类名`。
4. 打开任意程序（网页、PDF 阅读器、Word 等），用鼠标选中一段完整的文献引用文字，例如：

   > Robins, M. (2002). Spatial variability and the . . .
5. 按下全局快捷键 `Ctrl + Alt + R`。
6. RefSA 自动完成检索与匹配：
   - 若匹配可靠，右下角出现成功通知，内容为文献标题、作者和年份，以及一行「Imported to 目标位置」（我的文库或指定分类）。文献已作为一篇期刊文章写入 Zotero。
   - 若未找到可靠匹配或无法连接 Zotero，右下角出现失败通知及原因。
7. 打开 Zotero，即可在目标分类中看到刚导入的条目。

## 全局快捷键

默认热键为 `Ctrl + Alt + R`。

注意：Zotero 的「朗读选中内容」功能占用 `Ctrl + Shift + R`，故 RefSA 默认使用 `Ctrl + Alt + R` 以避免冲突。如需更改，请编辑 `config.py` 中的 `HOTKEY` 后重新运行（源码版）。

## 配置与数据

所有可调配置集中在 `config.py`：

- `HOTKEY`：全局快捷键。
- `SCORE_THRESHOLD`：Crossref 匹配分数阈值，低于该值视为不可靠而不创建条目。
- `NOTIFY_DURATION`：通知显示时长（short/long）。

运行数据与配置保存在用户数据目录 `%APPDATA%\RefSA\`：

- `refsa_config.json`：持久化的目标分类设置。
- `credentials.json`：Zotero 本地写 API 的授权凭证。
- `logs/runtime.log`：运行日志，所有状态与错误都记录在这里。

## 原理

1. 读取选中文本：保存剪贴板内容，发送一次模拟的 `Ctrl+C`，稍作等待后读取剪贴板（带重试），再恢复原剪贴板。
2. Crossref 检索：将引用文本作为查询请求 `https://api.crossref.org/works`，返回若干候选。
3. 评分筛选：对候选结果按相似度打分，超过 `SCORE_THRESHOLD` 才采用。
4. 写入 Zotero：通过 Zotero 本地 HTTP API（`localhost:23119`）创建一条 `journalArticle` 类型的条目，包含标题、作者、期刊、卷期页、年份、DOI 与链接等字段，并放入目标分类。
5. 结果通知：用 Windows 原生 Toast 报告成功（含「Imported to 目标位置」）或失败原因。

## 版本

当前版本：1.0.0
