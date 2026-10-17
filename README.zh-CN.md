# AxiomPy

[English](README.md) | **简体中文**

[![CI](https://github.com/Riceal28/AxiomPy/actions/workflows/ci.yml/badge.svg)](https://github.com/Riceal28/AxiomPy/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9--3.13-3776AB)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.9.x-41CD52)](https://doc.qt.io/qtforpython/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

AxiomPy 是一个用于构建、检查和运行 FFmpeg 命令的 Windows 桌面工具。它使用 Python
与 PySide6 重写了 [Matt McManis 的 Axiom](https://github.com/MattMcManis/Axiom)，
重点面向日常转码工作流，而不是要求用户直接编写所有 FFmpeg 参数。

![AxiomPy 主界面](docs/images/main-window.png)

## 功能亮点

- 覆盖常用 FFmpeg 工作流的视频、音频、字幕、滤镜、容器和输出命名选项。
- 支持软件与硬件编码，包括 x264/x265、NVENC、QSV 和 AMF。
- 支持 CRF、VBR、CBR、无损、1-pass 和 2-pass 模式。
- 支持外部音频/字幕混流、流选择、元数据设置和字幕烧录。
- 批处理队列支持逐文件显示 `Pending`、`Running`、`Completed`、`Failed` 和
  `Cancelled` 状态。
- 生成的脚本可编辑、排序、复制、保存和加载，并支持进度、取消及可选外部控制台。
- 内置预设、ffprobe 分析、预览、输入/输出拖放以及 PyInstaller 便携版构建。
- 默认采用 1280x720 布局，支持 8–16 pt 界面字体缩放，并可在退出时选择是否恢复
  完整工作区。

## 系统要求

| 组件 | 要求 |
|---|---|
| 操作系统 | Windows 10 或 Windows 11 |
| Python（源码运行） | Python 3.9–3.13 |
| 图形界面 | PySide6 6.9.x |
| FFmpeg | `ffmpeg`、`ffprobe` 和 `ffplay` 位于 `PATH`、在设置中指定，或随便携版打包 |

当前版本以 Windows 为首要支持平台。核心层不依赖 Qt，平台层保留了 POSIX 接口，
但正式发布目标仍是 Windows。

## 快速开始

### 便携版

从 [Releases](https://github.com/Riceal28/AxiomPy/releases) 下载压缩包，解压后运行：

```powershell
.\AxiomPy\AxiomPy.exe
```

便携版已经包含 FFmpeg、FFprobe 和 FFplay。若 `AxiomPy.exe` 同级目录存在 `config`
目录，设置和预设会保存在该目录中。

### 从源码运行

克隆仓库后，在项目根目录执行：

```powershell
git clone https://github.com/Riceal28/AxiomPy.git
cd AxiomPy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m axiom
```

安装后也可以使用 `axiom-gui` 启动图形界面。

### 命令行

CLI 使用与一致性测试工具相同的 JSON 用例格式：

```powershell
python -m axiom.cli --case tools/parity_harness/smoke_cases.json --id webm-vp8-crf-25
axiom-cli --case tools/parity_harness/control_cases.json --id ctl-mp4-x264 --print resolved
```

## 使用说明

1. 选择输入文件或批处理目录。
2. 选择容器和可选预设。
3. 配置视频、音频、字幕和滤镜。
4. 在 Script 停靠面板中检查生成的命令。
5. 运行转换，或在外部执行同一命令。

Input/Output 是独立面板。Script 与 Log 停靠窗口可调整大小，其布局也会被工作区快照
保存。

### 硬件加速

将 **Video → Encoding → Hardware Acceleration** 设置为 `On` 后，可选择硬件编码器。
**HW Transcode** 会在软件与硬件编码器之间同步切换：

- x264 ↔ H.264 AMF / NVENC / QSV
- x265 ↔ HEVC AMF / NVENC / QSV

硬件质量参数沿用原版 Axiom 的参数表。编码器能否实际使用取决于 GPU 驱动和 FFmpeg
构建；仅检测到编码器并不保证驱动会话一定能够成功创建。

### 工作区与界面设置

打开 **Settings → System** 可配置：

- **Font Size**：8–16 pt，立即应用到整个程序和样式表。
- **Save workspace on exit**：启用后，下次启动会恢复窗口位置与尺寸、停靠布局、
  当前 Tab、编辑后的脚本和转换参数。

默认窗口大小为 1280x720；如果存在已保存的工作区，则优先使用工作区中的尺寸。

![AxiomPy 界面设置](docs/images/settings.png)

## 配置与数据

AxiomPy 使用带版本号的 JSON 配置，不再读取旧的 `axiom.conf` 和 INI 预设。

| 数据 | 位置 |
|---|---|
| 便携版配置 | `<portable>/config/axiom.json` |
| 标准配置 | `%APPDATA%\AxiomPy\axiom.json` |
| 用户预设 | `<config>/presets/*.json` |

如果便携版 `config` 目录存在，会优先使用该目录。设置、预设和工作区快照使用 schema
版本 1，并以 UTF-8 JSON 格式写入。

## 构建便携包

安装打包依赖，并将 FFmpeg 三个可执行文件所在目录告诉构建脚本：

```powershell
python -m pip install -e ".[package]"
$env:AXIOM_FFMPEG_BIN = "C:\ffmpeg\bin"
.\packaging\build.ps1
.\packaging\verify.ps1
```

`build.ps1` 也接受 `-FfmpegBin` 和 `-Python`。未设置 `AXIOM_FFMPEG_BIN` 时，脚本会
尝试从 `PATH` 中查找 `ffmpeg.exe`。输出目录为 `dist\AxiomPy`。

## 开发

```powershell
python -m pip install -e ".[dev]"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q
```

当前开发环境的验证结果：

- `342 passed, 2 skipped`
- 可选的 FFmpeg 真实转换测试：`2 passed`
- 13 个原生 Windows 截图页面全部匹配，差异为 `0.0000%`

### 一致性测试工具

C# oracle 会链接原版 Axiom 的生成器、控制层和编解码器源码，生成逐字节一致的黄金
命令。原仓库不会被修改。

```powershell
$env:AXIOM_REFERENCE_SRC = "C:\src\Axiom\source\Axiom\Axiom"
python tools/parity_harness/build_harness.py
python tools/parity_harness/run_goldens.py
pytest -q
```

构建该工具还需要 .NET Framework 4.7.1 参考程序集环境。

### 真实转换测试

```powershell
$env:AXIOM_RUN_E2E = "1"
$env:AXIOM_FFMPEG_BIN = "C:\ffmpeg\bin"
pytest tests/test_e2e_ffmpeg.py -q
```

### 界面截图回归

```powershell
python tools/ui_snapshots.py
python tools/compare_screenshots.py tests/ui-baseline artifacts/ui-current
```

基线覆盖六个顶层 Tab、相关子 Tab 和 1280x720 下的批处理队列。

## 项目结构

| 路径 | 用途 |
|---|---|
| `src/axiom/core` | 不依赖 Qt 的状态模型、参数生成、预设、配置、探测和进程执行 |
| `src/axiom/platform` | Windows/POSIX 平台抽象 |
| `src/axiom/ui` | PySide6 应用、控件和 Axiom Dark 样式表 |
| `packaging` | PyInstaller 配置、便携版构建和启动验证 |
| `tools/parity_harness` | C# 参考 oracle 和黄金用例生成 |
| `tools/codegen` | 默认值、编解码器、控制层和预设表生成器 |
| `tests` | 单元、控制一致性、黄金命令、界面和可选 FFmpeg 测试 |
| `docs` | 交付状态、界面一致性说明和 README 图片 |

## 已知限制

- YouTube/yt-dlp 下载功能已明确移除。
- 当前版本的界面文案仍为英文，字符串已集中管理，便于后续本地化。
- 当前不提供安装器或代码签名证书。
- QSV/AMF 编码器是否可用取决于本机 GPU 运行时和驱动。
- 无效或不受支持的 FFmpeg 参数仍会由 FFmpeg 报错；AxiomPy 会显示退出码和日志。

## 贡献与安全

开发环境、测试命令和 Pull Request 要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。
安全问题请按照 [SECURITY.md](SECURITY.md) 私下报告。参与项目还需遵守
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

仓库：[github.com/Riceal28/AxiomPy](https://github.com/Riceal28/AxiomPy)

## 许可证与致谢

AxiomPy 使用 GPL-3.0-or-later 许可证，与原版 Axiom 保持一致。详见 [LICENSE](LICENSE)。

本项目基于 Matt McManis 的 Axiom，原作者与本项目没有隶属关系。原 WPF 实现仍作为
独立的参考项目保留。
