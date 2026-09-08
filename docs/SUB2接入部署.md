# Sub2 独立接入部署

此部署只运行 DataAgent 的管理库、后端和前端，不创建 `enterprise_demo` 演示数据库。Sub2 保持官方镜像运行，作为外部只读业务数据源接入。

## 组件边界

- `metadata-db`：只保存 Agent、模型、数据源、会话和审计配置。
- `backend`：执行语义召回、只读 NL2SQL 和报告生成。
- `frontend`：管理 Agent、模型和数据源。
- Sub2 PostgreSQL：由 Sub2 官方镜像维护，DataAgent 只使用只读账号查询。

## 启动

```bash
cp .env.sub2.example .env.sub2
# 编辑 .env.sub2，至少替换 SUB2_AGENT_MYSQL_ROOT_PASSWORD
export SUB2_UPSTREAM_NETWORK="$(docker inspect -f '{{range $name, $network := .NetworkSettings.Networks}}{{$name}}{{end}}' sub2api-postgres)"
docker compose --env-file .env.sub2 -f compose.sub2.yaml up -d --build
docker compose --env-file .env.sub2 -f compose.sub2.yaml ps
```

访问 `http://服务器地址:3001`。创建一个 Sub2 Agent，并在数据源页面填写 Sub2 数据库连接信息：主机填写 `sub2api-postgres`，端口 `5432`，数据库名、管理员账号和密码以 Sub2 的 `.env` 为准。数据源类型选择 PostgreSQL，数据库账号必须只授予目标表的 `SELECT` 权限。

在 Sub2 的 PostgreSQL 中创建只读账号（密码只保存在服务器终端或密码管理器中）：

```bash
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" sub2api-postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE dataagent_ro LOGIN PASSWORD '在此处填写只读账号密码';" \
  -c "GRANT CONNECT ON DATABASE \"$POSTGRES_DB\" TO dataagent_ro;" \
  -c "GRANT USAGE ON SCHEMA public TO dataagent_ro;" \
  -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO dataagent_ro;" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dataagent_ro;"
```

## Sub2 数据库权限

不要把 `credentials`、`extra`、API Key、监控密钥、请求正文等字段加入 Agent 的字段白名单。`deploy/sub2/application.yml` 已提供一组默认安全字段，接入后应根据当前 Sub2 版本的实际表结构复核。

## AstrBot 调用

发布 Sub2 Agent 并生成 Agent API Key 后，AstrBot 或外部适配器调用：

```text
GET http://服务器地址:8066/api/stream/search
```

请求参数至少包含 `agentId` 和 `query`，并在 `Authorization` 或项目支持的 API Key 方式中携带该 Agent Key。该接口返回 SSE，调用方读取最终答案事件。项目自带 MCP 当前主要暴露 Agent 列表和 NL2SQL 工具；如果需要 AstrBot 直接拿到完整报告，建议使用一个很薄的 SSE 转 JSON 适配器。

## 更新

```bash
git pull --ff-only
export SUB2_UPSTREAM_NETWORK="$(docker inspect -f '{{range $name, $network := .NetworkSettings.Networks}}{{println $name}}{{end}}' sub2api-postgres | head -n1)"
docker compose --env-file .env.sub2 -f compose.sub2.yaml up -d --build
```

这不会修改 Sub2 源码或 Sub2 数据卷。

## 自动配置数据源和 Agent

模型配置完成后，可以在服务器上用脚本重复配置 Sub2 数据源、创建或复用 Agent、绑定数据源、选择安全表并初始化 Schema。脚本通过 DataAgent 管理 API 操作，不修改 Sub2 源码。

```bash
cd /opt/enterprise-finance-agent
export SUB2_DB_PASSWORD='只读账号 dataagent_ro 的密码'
# 可选：指定表名；不指定时使用 deploy/sub2/application.yml 中的安全表交集
export SUB2_TABLES='usage_logs,ops_error_logs,ops_system_metrics,channels'
python3 deploy/sub2/configure_sub2_agent.py
unset SUB2_DB_PASSWORD SUB2_TABLES
```

脚本默认访问 `http://127.0.0.1:8066`，可通过 `DATA_AGENT_URL` 覆盖。数据库密码只从环境变量或交互式隐藏输入读取，不写入仓库；已有名为 `sub2api` 的数据源和 `Sub2 数据问答助手` Agent 会被复用。首次运行如果没有匹配的安全表，会列出实际表名并要求通过 `SUB2_TABLES` 明确指定，避免把敏感表自动加入语义索引。
