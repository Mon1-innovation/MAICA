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

# 必要配置

MAICA 要求 Python 3.12 或更高版本。生成 `.env` 后，至少检查以下项目：

* `MAICA_IS_REAL_ENV=1`；
* `MAICA_DB_ADDR`、`MAICA_AUTH_DB`、`MAICA_DATA_DB`；
* `MAICA_MCORE_ADDR/KEY/CHOICE` 与 `MAICA_MFOCUS_ADDR/KEY/CHOICE`；
* 公网声明 `MAICA_SERVERS_LIST`。

SQLite 部署将 `MAICA_DB_ADDR` 设为 `sqlite`，且认证库与数据库必须是不同文件。公开服务建议使用 MySQL/MariaDB。首次启动会生成 RSA 密钥、数据库表和 `.initialized` 迁移标记；不要在未备份的情况下删除或替换 `maica/keys/prv.key`。

# 网络与安全

默认监听地址为 `0.0.0.0:5000`（WebSocket）和 `0.0.0.0:6000`（HTTP），分别由 `MAICA_WS_HOST/PORT`、`MAICA_HTTP_HOST/PORT` 控制。公开部署应使用反向代理提供 HTTPS/WSS，并限制管理网络和数据库端口。

* HTTP 请求优先通过 `Authorization: Bearer <access_token>` 鉴权；URL 参数仅为兼容旧客户端。
* `POST /register` 用于在线生成令牌；旧的 GET 形式会把凭据放入 URL，不应继续用于新客户端。
* 设置 `MAICA_VISION_HOST_ALLOWLIST`，避免视觉模型读取非预期主机。
* NVWatcher 默认校验 SSH host key。仅在隔离且可信的旧网络中才可设置 `MAICA_NVW_INSECURE_SSH=1`。
* 不要公开 `.env`、认证数据库、私钥或 NVWatcher 密码。

# 启动前验证

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check maica tests examples
python -m pip check
```

离线测试不要求模型、Milvus、SSH 或互联网。真实端点可使用 `examples/model_smoke.py` 与 `examples/milvus_smoke.py` 手工检查。

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
