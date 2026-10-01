# codex-baseline

把少量 Codex 设置整理成一份可共享基线，再用每台机器自己的差异文件生成配置，
并解释哪些设置发生了偏离。Python 3.11 以上、运行时零依赖、完全离线。

[English](README.md) · [真实终端演示](docs/demo.txt) · [支持字段](docs/scope.md) · [安全边界](SECURITY.md)

首版 **0.1.0** 只支持 **Codex CLI 0.159.3** 的明确小范围字段。
这是独立项目，不隶属于 OpenAI；不是整个 Codex 目录的备份或搬家工具。

## 直接试用

下载仓库后，在仓库根目录运行。Windows 下把 `python` 改成 `py`。
示例中的模型名和路径全是合成数据，不会访问你的 Codex 真实目录。

```sh
python -m codex_baseline inspect --config examples/shared.toml --codex-version 0.159.3
python -m codex_baseline export --config examples/shared.toml --codex-version 0.159.3 --out baseline-demo
python -m codex_baseline render --baseline baseline-demo --overlay examples/mac-overlay.toml --out review-demo
python -m codex_baseline compare --baseline baseline-demo --overlay examples/mac-overlay.toml --config review-demo/config.toml
python -m codex_baseline compare --baseline baseline-demo --overlay examples/mac-overlay.toml --config examples/drifted.toml
```

前四步检查、导出、生成、比对。最后一步发现三个故意制造的差异：编辑器、推理等级、
额外可写路径；同时说明期望值来自共享基线还是机器差异文件。机器路径不会写入报告。
输出目录必须不存在或为空。重复体验可运行 `python tools/demo.py`，它只使用并清理
本仓库 `work/` 下的合成临时文件。

## 使用方式

- `inspect` 分类便于共享的设置、机器本地设置、明确阻止的部分，并统计未知字段。
- `export` 检查完整输入，只导出便于共享的设置与哈希清单。
- `render` 将基线和显式指定的机器差异合并，输出供人工审核的 `config.toml`。
- `compare` 比对显式指定的配置文件，解释新增、缺失和改变的字段。
- `policy` 查看支持范围、版本和官方依据。

机器差异中的已给出字段优先，数组整体替换，不会合并路径或默默添加默认设置。
支持 12 个共享字段和 2 个机器本地字段，准确范围见 [字段表](docs/scope.md)。
遇到未知字段、阻止的部分、坏格式或可能的凭据内容，会拒绝导出和生成。
含其他配置部分时，请先检查，然后另建一份人工审核的小范围输入文件。

退出码：`0` 表示成功或一致，`1` 表示发现偏离，`2` 表示拒绝输入或操作失败。
输入版本由调用者明确声明，不会探测本机 Codex 版本；模型与推理等级是否可用也不会联网检查。
`compare` 只比较你指定的文件，不解析项目层、profiles、管理员规则或命令行覆盖后的最终配置。

## 安装与限制

在仓库根目录用 `python -m codex_baseline` 不需要安装任何依赖。
也可以在自己新建的虚拟环境中执行 `python -m pip install .`，安装后使用
`codex-baseline` 命令。源码安装可能下载 setuptools 构建工具，CLI 运行时不会联网。
尚未发布 PyPI 包。Windows 的虚拟环境创建命令为 `py -m venv .venv`。

只读取你显式指定的 TOML 文件及基线清单，不自动扫描目录、不读认证文件、会话、
数据库、日志、不执行配置中的命令、不自动写入 Codex 的真实目录。
AGENTS.md、skills、MCP、自定义 provider、项目信任、插件状态暂不支持。
生成的安全策略会影响以后手工使用 Codex 的权限，使用前必须检查。

拒绝路径中的 `..`、符号链接、Windows junction/reparse point、输入硬链接和覆盖操作。
凭据识别使用有限启发式规则，**不能保证发现所有秘密**。输出仍应由你检查后再分享。
哈希清单不含源路径、时间、机器标识；相同输入生成相同字节。哈希不是签名。
不保证能抵御另一进程同时替换目录所造成的所有竞争条件，完整边界见 [SECURITY.md](SECURITY.md)。

## 开发和维护

```sh
python -m unittest discover -s tests -v
python tools/demo.py
python -m pip wheel --no-deps --wheel-dir dist .
```

测试全部使用合成数据。CI 工作流位于 `.github/workflows/ci.yml`，
覆盖 Linux、Windows、测试、演示和安装检查；详见 [CI 说明](docs/ci/README.md)。
托管 CI 验证尚待完成，请在 Actions 页面核对对应提交的实际结果。版本更新需重新核对官方 schema、字段范围和安全测试，
不能仅扩大版本号范围。详见 [贡献说明](CONTRIBUTING.md)。

需求依据：[多机器基线](https://github.com/openai/codex/issues/26691)、
[可移植设置](https://github.com/openai/codex/issues/31130)、
[配置与运行状态分离](https://github.com/openai/codex/issues/45627)。
字段依据：[官方配置参考](https://developers.openai.com/codex/config-reference/)
及 [0.159.3 固定版本 schema](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/core/config.schema.json)。

MIT 许可证；没有付费服务、遥测或 API 费用。
