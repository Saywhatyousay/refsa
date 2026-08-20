# RefSA - Reference Search and Add

RefSA（Reference Search and Add）是一个 Windows 桌面小工具。它常驻后台，监听一个全局快捷键。当你在任意程序中选中一段期刊文献的引用文字、按下快捷键后，RefSA 会自动完成：读取选中文字、到 Crossref 检索、挑选最佳匹配、把它作为一篇期刊文章（journalArticle）导入为你的本地 Zotero 条目，并用 Windows 系统通知（Toast）告诉你结果。


## 运行条件

- 操作系统：Windows 10 或 Windows 11。
- Zotero：需使用 **Zotero 10 或更新版本**，已安装且正在运行，并启用本地 HTTP 服务器。
  - 打开 Zotero，菜单「编辑 - 设置 - 高级 - 杂项」，勾选「允许本机上的其他应用程序与 Zotero 通讯」。
- 网络：能访问 Crossref（用于检索与匹配文献）；建议开启 VPN.

## 使用方式

下载 `RefSA.exe`，把它放在你喜欢的目录（例如 `D:\refsa\`）。双击运行时，控制台会短暂出现，打印出热键与目标分类等初始化信息后自动关闭；随后右下角弹出一条通知，提示热键、目标分类和后台就绪。也可以在命令行里用 `refsa` 命令启动，效果相同。**每次重启电脑后通过双击或命令行启动一次即可。**

### 让命令行能直接使用 refsa

想让任意目录下都能敲 `refsa` 而不必输入完整路径，把 `RefSA.exe` 所在的文件夹加入 Windows 的 PATH 即可：

1. 按 `Win`，输入「编辑系统环境变量」，回车打开「系统属性 - 环境变量」。
2. 在「用户变量」里找到 `Path`，选中后点「编辑」。
3. 点「新建」，把 `RefSA.exe` 所在的文件夹路径粘贴进去（例如 `D:\refsa\`），确定保存。
4. **重新打开**一个命令提示符或 PowerShell 窗口（已打开的窗口不会自动生效）。

之后即可直接使用 `refsa` 命令。

## 命令行用法

| 命令 | 说明 |
| --- | --- |
| `refsa` | 启动后台监听。先打印热键与目标分类等初始化信息，随后立即把命令行交还给你（后台继续运行，不阻塞终端），并弹出启动通知。 |
| `refsa -v`（`--version`） | 输出版本号。 |
| `refsa -l` | 列出 Zotero 里的所有分类（含子分类），用 `*` 标记当前目标位置。 |
| `refsa -c 分类名` | 把目标分类设为指定分类并保存，之后导入的文献会放入该分类。 |
| `refsa --clear-collection` | 清除目标分类设置，回到默认的「我的文库」。 |

说明：

- 默认目标为「我的文库」根目录。
- `-c` 只接受分类名称；若存在多个同名分类，请使用唯一名称。
- 目标分类设置会保存，下次启动仍然有效。

## 完整使用步骤

1. 启动 Zotero（后台保持运行）。
2. 双击 `RefSA.exe`（或运行 `refsa`）启动后台监听。
3. 可选：设置目标分类。默认放到「我的文库」；想放入指定分类就先运行 `refsa -l` 查看有哪些分类，再运行 `refsa -c 分类名`。
4. 打开任意程序（网页、PDF 阅读器、Word 等），选中一段完整的**期刊文献**引用文字。引用格式任意，如同一文献的以下三种格式均可以指向原文献（需要注意，仅划出文献名或作者+年份无法保证指向正确的文献）:

  > **APA 格式 (第7版)**
  > Panofsky, H. A. (1974). The atmospheric boundary layer below 150 m. *Annual Review of Fluid Mechanics*, *6*, 147-172.

  > **MLA 格式 (第9版)**
  > Panofsky, H. A. "The Atmospheric Boundary Layer Below 150 M." *Annual Review of Fluid Mechanics*, vol. 6, 1974, pp. 147-72.

  > **Chicago 格式**
  > Panofsky, H. A. 1974. "The Atmospheric Boundary Layer Below 150 M." *Annual Review of Fluid Mechanics* 6: 147-72.

5. 按下全局快捷键 `Ctrl + Alt + R`。
6.  等待结果：
   - 成功时右下角弹出通知，显示文献标题、作者与年份，以及一行「Imported to 目标位置」。文献已写入 Zotero 条目（不包括 PDF 附件）。
   - 失败时右下角弹出通知及失败原因。
7. 打开 Zotero，在目标分类中查看刚导入的条目。

## 支持的文献范围

RefSA 专门处理**期刊文章（journalArticle）**。它只检索期刊文献，因此书章、学位论文、会议论文、报纸等其他类型的引用**不会被匹配**，遇到这类文献时会提示找不到可靠匹配，而不会创建条目。

## 全局快捷键

默认热键为 `Ctrl + Alt + R` ，暂不支持更改。

## 版本

当前版本：1.0.0
