<h1 align="center">MAICA-幻象引擎</h1>
<div align="center">
<img src="https://maica.monika.love/assets/maica-text-finish-p.png" width=150>
</div>

***

<p align="center">中文 | <a href="/README_EN.md">English</a></p>

本页面是MAICA的指引页面, 当前位置是MAICA后端仓库.

MAICA项目的详细介绍页是https://maica.monika.love/.

要快速开始或了解授权, 请参阅https://maica.monika.love/tos.

MAICA的后端仓库地址是https://github.com/Mon1-innovation/MAICA.

MAICA的后端compact分支地址是https://github.com/Mon1-innovation/MAICA_Server_Submod

MAICA的子模组前端仓库地址是https://github.com/Mon1-innovation/MAICA_ChatSubmod.

MAICA LIA分支的模型地址是https://huggingface.co/edgeinfinity/MAICAv0-LIA-72B.

MAICA LOA分支的模型地址是https://huggingface.co/edgeinfinity/MAICAv0-LOA-7B.

MAICA-MTTS的子模组前端仓库地址是https://github.com/Mon1-innovation/MAICA_MttsSubmod.

MAICA-MTTS的仓库地址是https://github.com/Mon1-innovation/MAICA_MTTS.

MAICA-MTTS模型地址是https://huggingface.co/edgeinfinity/MTTSv0-VoiceClone.

MAICA的基本数据集仓库位于https://huggingface.co/datasets/edgeinfinity/MAICA_ds_basis.

MAICA的相关文档存储于https://github.com/Mon1-innovation/MAICA/tree/main/document.

## 快速开始

MAICA 后端需要 Python 3.12 或更高版本，并支持 Windows 与 Linux。核心模型与 MFocus 模型使用 OpenAI-compatible Responses API，需要另行部署；数据库可使用 MySQL/MariaDB，单机测试也可使用 SQLite。

```bash
python -m pip install -e .
maica -t create
# 编辑 .env：至少设置 MAICA_IS_REAL_ENV、数据库以及 MCORE/MFOCUS 连接
maica -e .env
```

默认监听 WebSocket `:5000` 与 HTTP `:6000`，可通过 `MAICA_WS_HOST/PORT` 和 `MAICA_HTTP_HOST/PORT` 修改。完整配置项及说明见 [`maica/env_basis`](maica/env_basis)；部署步骤见 [`document/Backend Deployment.md`](document/Backend%20Deployment.md)，接口协议见 [`document/API Documents.md`](document/API%20Documents.md)。

## 开发与验证

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check maica tests examples
```

`examples/` 中的脚本是需要真实模型或 Milvus 的手工连通性检查，不属于离线测试。维护者应同时阅读 [`document/MAINTENANCE.md`](document/MAINTENANCE.md)。

## 部署安全

公开实例应在反向代理上启用 TLS；HTTP 鉴权优先使用 `Authorization: Bearer <access_token>`，避免把令牌写入 URL。请保管 `maica/keys/prv.key`，为 NVWatcher 配置 SSH host key，并通过 `MAICA_VISION_HOST_ALLOWLIST` 限制可发送给视觉模型的图片域名。
