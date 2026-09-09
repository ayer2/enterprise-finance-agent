# Sub2 DataAgent AstrBot 插件

通过 `/sub2 <问题>` 调用已发布的 Sub2 DataAgent。插件使用
`event.unified_msg_origin` 生成稳定的 `conversationId`，因此同一个私聊或群聊可以继续多轮查询。

环境变量：

- `SUB2_DATA_AGENT_URL`：DataAgent 地址。AstrBot 与 DataAgent 同一 Docker 网络时默认使用 `http://sub2-data-agent-backend:8065`。
- `SUB2_DATA_AGENT_ID`：Agent ID，默认为 `1`。
- `SUB2_DATA_AGENT_TIMEOUT`：单次查询超时秒数，默认为 `180`。
