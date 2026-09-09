# Sub2 DataAgent AstrBot 插件

通过 `/sub2 <问题>` 调用已发布的 Sub2 DataAgent。插件为每个私聊或群聊保存独立的
`conversationId`，因此可以继续多轮查询。发送 `/sub2 新会话`、`/sub2 新对话`、
`/sub2 重置` 或 `/sub2 清空上下文` 会立即切换到全新的上下文。

环境变量：

- `SUB2_DATA_AGENT_URL`：DataAgent 地址。AstrBot 与 DataAgent 同一 Docker 网络时默认使用 `http://sub2-data-agent-backend:8065`。
- `SUB2_DATA_AGENT_ID`：Agent ID，默认为 `1`。
- `SUB2_DATA_AGENT_TIMEOUT`：单次查询超时秒数，默认为 `600`。
