# MixCut 素材组合工作台

Windows 本地视频批量拼接工具。把素材分组放在主文件夹的直接子文件夹内，选择顺序后，每组取一条，生成结构固定、组合不同的成片。所有视频处理都在本机完成。

## 下载后怎么用

1. 在 GitHub 仓库右侧 **Releases** 下载 `MixCut-Windows-x64.zip`。
2. 完整解压，进入 `MixCut` 文件夹，双击 **MixCut.exe**。
3. 选择素材主文件夹，等待扫描；检查 A → B → C → D 等顺序。
4. 设置本次新增数量、输出尺寸及输出位置，点击“新增并开始生成”。

发行包目标为 Windows 10 / 11 的64位系统。使用发行包不需要另装 Python 或 FFmpeg；不要只拷贝 EXE，须保留整个解压文件夹。当前开发交付为源码，实际 Windows 兼容性以 GitHub Windows 构建和本机运行结果为准。

如果还没有 Release：进入 **Actions → Build Windows EXE → 成功的构建 → Artifacts**，下载 `MixCut-Windows-x64`，解压后再解压其中的程序ZIP。自动构建的下载文件保留30天；发布版本的 Release 下载长期保留。

## 差异规则

| 素材子文件夹数 | 同一项目任意两条成片的最低差异 |
| --- | --- |
| 2 | 至少1段素材不同 |
| 3 | 至少1段素材不同 |
| 4 | 至少2段素材不同 |
| 5个及以上 | 默认至少2段素材不同 |

比较的是**相同段位所用的素材内容标识**，不是输出文件名。比较范围包括本次所有组合、此前完成的组合和保留待续跑的组合。单条素材可以在多条成片中复用。同组内字节内容完全相同的文件即使改名也只计一次；近似画面、重新压缩的视频不做语义相似度判断。

每个子文件夹素材数允许不同。2 / 3组的新项目容量为素材数乘积；4组及以上的新项目容量为素材数乘积除以最大组素材数。例如：

| 各组素材数 | 差异要求 | 新项目最大组合数 |
| --- | --- | --- |
| 3 × 3 | 1段 | 9 |
| 3 × 3 × 3 | 1段 | 27 |
| 3 × 3 × 3 × 3 | 2段 | 27 |
| 3 × 4 × 2 × 5 | 2段 | 24 |

使用最大组作为校验位构造组合，可达到新项目的上述上限；遍历使用无重复的索引置换，不展开庞大的笛卡尔积。历史记录通过删除一位的签名索引进行全局检查，确保不只是相邻成片满足规则。

**增删素材之后，历史约束可能降低可新增数量。**软件会筛选安全的新组合，不承诺在变动后的素材集上求得最大可追加集合。界面的“从零开始理论上限”不等于剩余数量。单次最多新增100000条，搜索候选数上限为 `max(200000, 本次数量×100)`；不足时显示本轮找到数量，不会用重复组合凑数，也不会提交半份计划。

## 已包含的功能

- 自动扫描直接子文件夹和视频，按名称自然排序；首次生成前可上移、下移调整顺序。
- MP4、MOV、MKV、AVI、M4V、WebM、TS、MTS 素材识别；最终导出 H.264 / AAC 的 MP4。
- 完整使用片段，硬切拼接；支持竖屏1080p、竖屏720p、横屏1080p、方形1080p。
- 统一30帧，等比缩放加黑边，不强行拉伸；混合有声/无声片段补齐音轨。
- 默认保留原声，可选择静音输出；声音统一48kHz双声道。
- 后台处理，无 FFmpeg 控制台弹窗；进度、错误日志、暂停/继续和停止。
- SQLite 持久记录组合；关闭再开可续跑，失败重试沿用原组合，不新增重复成片。
- 已标准化的片段在本次任务中复用，结束后自动清理本次缓存。
- 成片组合CSV，可查每条成片使用了哪些原始素材。
- 项目锁，防止两个程序窗口同时处理同一项目；已有目标文件不会被覆盖。

## 项目与历史记录

素材主文件夹内自动创建 `.mixcut/project.sqlite3`。该记录跟随素材项目，切换成片输出目录不会重置历史。**不要删除 `.mixcut`；移动素材项目时请一起移动。**删除数据库后，软件无法知道之前生成过什么。不同主文件夹是独立项目，不跨项目比较。

首次计划保存后，子文件夹名称、数量和顺序锁定。可以往原来的组里增加素材；改结构请使用新的主文件夹。重命名单条文件后重新扫描即可按内容匹配；未完成任务所需素材不能删除或改写。

输出目录必须在素材主文件夹之外。处理期间不要改写源视频。发生停止或异常后，可恢复素材并点“继续未完成任务”。继续任务沿用原来的输出目录和输出设置；新设置只影响新建任务。未完成任务处理完后才能新增任务。

## 上传 GitHub 与自动构建

把本项目**内部文件**作为仓库根目录上传，保留 `.github/workflows/build-windows.yml`，不要把整个项目多套一层放入仓库。推送到 `main` / `master` 自动构建；其他分支可在 Actions 手动运行。

开发者首次上传示例（将地址改为你自己的空仓库）：

```bash
git init
git add .
git commit -m "Initial MixCut desktop application"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/mixcut-desktop.git
git push -u origin main
```

自动流程安装依赖 → 运行测试 → 打包 Windows EXE → 从打包后的 EXE 实际生成测试视频 → 验证 GUI 可以启动 → 输出ZIP及SHA256。

测试成功后，推送版本标签可自动发布下载页：

```bash
git tag v0.1.0
git push origin v0.1.0
```

版本发布由标签触发；普通代码推送仅产生 Actions 下载文件，不覆盖已有 Release。

## 本地开发及构建

需要 Python 3.11+，使用64位Python。Windows的官方Python安装包含Tkinter。

```bash
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

在 Windows PowerShell 运行 `./scripts/build_windows.ps1`，生成 `dist/MixCut-Windows-x64.zip`。Windows EXE 由 Windows 环境构建，不把Linux程序改名为EXE。

参考：[PyInstaller 构建平台说明](https://pyinstaller.org/en/stable/)、[GitHub Actions 构建文件](https://docs.github.com/en/actions/tutorials/store-and-share-data)、[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)。

详细操作参见 [USER_GUIDE.md](USER_GUIDE.md)，第三方组件说明参见 [THIRD_PARTY.md](THIRD_PARTY.md)。
