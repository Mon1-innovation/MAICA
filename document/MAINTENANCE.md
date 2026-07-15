# MAICA 后端维护说明

## 运行结构

`maica_starter.py` 负责配置、初始化、连接创建和服务生命周期。WebSocket 主链路位于 `maica_ws.py`，HTTP 补充接口位于 `maica_http.py`。每个请求通过 `FullSocketsContainer` 聚合用户状态、模型连接与向量连接。

生成流程依次为：请求模型校验 → 会话/存档/触发器加载 → `pre_core_pipelines`（MFocus、MPostal、MSpire、MVista）→ 核心模型 → `post_core_pipelines`（MTrigger、质量检查、缓存和会话持久化）。数据库模型与会话工厂位于 `maica_utils/database_*.py`，版本迁移位于 `initializer/migrations/`。

## 不变量

* 必须先调用 `maica.init()`，再调用异步 `maica.start_all()`；命令行入口会自动完成两步。
* 认证数据库只读，业务数据库可写。SQLite 的两个数据库文件不得相同。
* `online_dict` 的修改必须在 `online_dict_guard` 内完成；清理连接时仅删除仍指向自身的条目。
* `DbBoundObject` 必须通过 `acquire_dbo()` / `acquire_session()` 使用，以保证同一用户和会话串行写入。
* LLM 输出统一由 `llm_request()` 解析 Responses API 的流式与非流式事件。
* schema 迁移全部成功后才能推进 `.initialized` 中的版本。

## 验证

```bash
python -m pytest -q
python -m ruff check maica tests examples
python -m compileall -q maica tests examples
python -m pip check
```

测试必须保持离线、确定且无外部副作用。需要模型、Milvus 或 SSH 的检查放在 `examples/`，不要以 `test_*.py` 命名。涉及数据库的测试使用内存 SQLite，并在 `finally` 中恢复 `DatabaseUtils` 的全局工厂。

## 发布检查

版本来源仅为 `maica/env_basis` 的 `MAICA_CURR_VERSION`。新增或修改数据库结构时，必须新增幂等迁移并同步提升版本；不要修改已发布迁移的触发版本。构建后应执行 `twine check` 并检查 wheel 只包含 `maica*` 包、`env_basis` 和两种 SERP 二进制。

视觉 URL 仍由模型服务实际抓取。公开部署应配置 `MAICA_VISION_HOST_ALLOWLIST`，并在网络层阻断模型容器访问云元数据、数据库和管理网段。预编译 SERP 二进制属于独立外部组件，升级时应核对其来源和校验值。
