I'm sorry for not offering an English ver of this document but it's just too much work for me.
If you want to read in English, use a translator.

此文档是MAICA接口后端"幻象引擎"的部署文档, 编纂版本为v1.2.  
请注意"幻象引擎"是协调通信程序, 模型需要另行部署. 自v1.2后, 仓库提供自动的release.

该文档仅为有一定技术基础的用户讲解, 不会提供过于细致的指导.

+ 下载和安装:

    拉取仓库:

    ```
    git clone https://github.com/Mon1-innovation/MAICA.git
    cd MAICA
    ```

    安装:

    ```
    pip install -e .
    ```

    配置:

    ```
    maica -t create
    vim .env
    ```

    启动实例:

    ```
    maica -e .env
    ```

+ 或者, 直接通过pypi安装:

    > 便捷但不适合开发, 兼容性有待测试.

    安装:

    ```
    pip install mi-maica
    ```

    配置:

    ```
    maica -t create
    vim .env
    ```

    启动实例:

    ```
    maica -e .env
    ```

> Anything below this point is written by AI.

# 必要配置

MAICA 要求 Python 3.12 或更高版本。生成 `.env` 后，至少检查以下项目：

* `MAICA_IS_REAL_ENV=1`；
* `MAICA_DB_ADDR`、`MAICA_AUTH_DB`、`MAICA_DATA_DB`；
* `MAICA_MCORE_ADDR/KEY/CHOICE` 与 `MAICA_MFOCUS_ADDR/KEY/CHOICE`；
* 公网声明 `MAICA_SERVERS_LIST`。

SQLite 部署将 `MAICA_DB_ADDR` 设为 `sqlite`，且认证库与数据库必须是不同文件。公开服务建议使用 MySQL/MariaDB。首次启动会生成 RSA 密钥、数据库表和 `.initialized` 迁移标记；不要在未备份的情况下删除或替换 `maica/keys/prv.key`。

# Censor 词表

`maica/mtools/censor` 用于过滤用户输入和 MSpire 检索结果。请在该目录下放置一个或多个 UTF-8 编码的 `.txt` 文件，每个非空行是一条词或短语；文件可任意命名，但扩展名必须为 `.txt`，子目录不会被扫描。词表文件默认被 Git 忽略，部署或迁移时需要单独保留。修改词表后须重启 MAICA。

* `MAICA_CENSOR_QUERY`：用户输入中不同命中项的数量达到该值时拒绝请求；
* `MAICA_CENSOR_MSPIRE`：MSpire 页面标题与摘要中不同命中项的总数达到该值时跳过该页面。

两项均须为非负整数，`0` 表示关闭对应检查，`1` 表示命中任意一项即触发。

# ZSCO 通用模型辅助

`maica/mtools/zsco` 通过 RAG 为未微调的核心模型检索角色对话范例。启用前应配置可用的 Embedding 端点和 Milvus（`MAICA_EMBEDDING_*`、`MAICA_EMBEDDING_DIMS` 与 `MAICA_MILVUS_*`），再设置 `MAICA_MCORE_GENERIC=1`。

请将数据文件放在 `maica/mtools/zsco` 目录下，并使用 UTF-8 编码的 `.jsonl` 格式。每个非空行必须是独立 JSON，可直接使用消息数组，也可使用包含 `messages` 或 `conversations` 数组的对象；消息支持 `role`/`content`，并兼容 ms-swift 的 `from`/`value`，只会保留 `user` 与 `assistant` 消息。例如：

```json
{"messages":[{"role":"user","content":"你好。"},{"role":"assistant","content":"很高兴见到你。"}]}
```

启动时数据会去重、向量化并同步到 Milvus，首次导入可能耗时；修改数据集后须重启 MAICA。若 ZSCO 辅助器因前置条件未满足、目录为空或数据格式错误而初始化失败，WebSocket 服务会记录警告并以受限功能继续运行，不再提供对话范例。

# 网络与安全

默认监听地址为 `0.0.0.0:5000`（WebSocket）和 `0.0.0.0:6000`（HTTP），分别由 `MAICA_WS_HOST/PORT`、`MAICA_HTTP_HOST/PORT` 控制。公开部署应使用反向代理提供 HTTPS/WSS，并限制管理网络和数据库端口。

* HTTP 请求优先通过 `Authorization: Bearer <access_token>` 鉴权；URL 参数仅为兼容旧客户端。
* `POST /register` 用于在线生成令牌；旧的 GET 形式会把凭据放入 URL，不应继续用于新客户端。
* `MAICA_MVISTA_TRUSTED` 接受逗号分隔的主机名、IP 或 CIDR。无前缀条目显式放行，`!` 前缀条目拒绝，`!*` 拒绝所有未显式标记的主机；未标记主机解析出的任一 IP 命中拒绝网段时也会被拒绝。默认拒绝 RFC1918 私网。
* WebSocket 必须在 `MAICA_AUTH_TIMEOUT` 秒内完成认证，默认 60 秒。
* `MAICA_TRUST_XFF` 默认为 `0`；仅当客户端无法绕过可信反向代理直连 MAICA 时才设为 `1`。
* NVWatcher 默认校验 SSH host key。仅在隔离且可信的旧网络中才可设置 `MAICA_NVW_INSECURE_SSH=1`。
* 不要公开 `.env`、认证数据库、私钥或 NVWatcher 密码。

# 启动前验证

仅检查配置格式且不初始化数据库或外部连接：

```bash
maica -e .env --validate-config
```

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check maica tests examples
python -m pip check
```

离线测试不要求模型、Milvus、SSH 或互联网。真实端点可使用 `examples/model_smoke.py` 与 `examples/milvus_smoke.py` 手工检查。
