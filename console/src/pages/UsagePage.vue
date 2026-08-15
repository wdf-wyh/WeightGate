<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { api, type Tenant, type UsageSummary } from "../api";

const tenants = ref<Tenant[]>([]);
const tenantId = ref("");
const usage = ref<UsageSummary | null>(null);
const error = ref("");

async function bootstrap() {
  error.value = "";
  try {
    tenants.value = await api.listTenants();
    if (!tenantId.value && tenants.value.length) tenantId.value = tenants.value[0].id;
    await load();
  } catch (e) {
    error.value = String(e);
  }
}

async function load() {
  if (!tenantId.value) {
    usage.value = null;
    return;
  }
  usage.value = await api.getUsage(tenantId.value);
}

watch(tenantId, () => {
  load().catch((e) => (error.value = String(e)));
});

onMounted(bootstrap);
</script>

<template>
  <section>
    <h1>用量</h1>
    <p class="lead">网关经控制面记录的 Token 与路由用量。</p>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row">
        <select v-model="tenantId">
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <button @click="load">刷新</button>
      </div>
      <p v-if="usage" class="muted">
        事件：<span class="mono">{{ usage.total_events }}</span> · Token
        <span class="mono">{{ usage.total_tokens }}</span>
        （提示 {{ usage.prompt_tokens }} / 补全 {{ usage.completion_tokens }}）
      </p>
      <p v-if="usage" class="muted">
        按路由：
        <span v-for="(n, route) in usage.by_route" :key="route" class="badge" style="margin-right: 0.35rem">
          {{ route }}: {{ n }}
        </span>
        <span v-if="!Object.keys(usage.by_route || {}).length">—</span>
      </p>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>模型</th>
            <th>路由</th>
            <th>Token</th>
            <th>延迟</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in usage?.events || []" :key="e.id">
            <td class="mono muted">{{ e.created_at }}</td>
            <td class="mono">{{ e.model }}</td>
            <td><span class="badge">{{ e.route }}</span></td>
            <td class="mono">{{ e.total_tokens }}</td>
            <td class="mono">{{ e.latency_ms }}ms</td>
          </tr>
        </tbody>
      </table>
      <p v-if="usage && !usage.events.length" class="muted">暂无用量事件。</p>
    </div>
  </section>
</template>
