# OpenAI-compatible contracts (Phase 0)

Gateway edge will expose OpenAI-shaped HTTP APIs.

| Method | Path | Schema |
|--------|------|--------|
| `POST` | `/v1/chat/completions` | [request](./chat-completions.request.json) → [response](./chat-completions.response.json) or [stream chunk](./chat-completions.stream-chunk.json) |
| `GET` | `/v1/models` | [models.list.json](./models.list.json) (tenant-scoped in Phase 1) |
| — | 4xx/5xx body | [error.response.json](./error.response.json) |

Auth (Phase 1): `Authorization: Bearer <tenant_api_key>`. Tenant is derived only from the key; never from body fields.

Auth header is **not** part of these JSON Schemas; it is transport-level.

Streaming: when `stream=true`, response is `text/event-stream` with `data:` lines conforming to the stream-chunk schema, terminated by `data: [DONE]`.

Python mirrors (Pydantic v2): `packages/contracts/` — importable as `packages.contracts` when repo root is on `PYTHONPATH`.
