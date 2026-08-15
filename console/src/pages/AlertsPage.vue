<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type Alert } from "../api";

const alerts = ref<Alert[]>([]);
const filter = ref("open");
const error = ref("");
const busy = ref(false);
const scanInfo = ref("");

async function refresh() {
  error.value = "";
  try {
    alerts.value = await api.listAlerts(filter.value);
  } catch (e) {
    error.value = String(e);
  }
}

async function scan() {
  busy.value = true;
  error.value = "";
  scanInfo.value = "";
  try {
    const r = await api.scanAlerts();
    scanInfo.value = `新建 ${r.created}，未关闭 ${r.open_total}`;
    filter.value = "open";
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function ack(id: string) {
  await api.ackAlert(id);
  await refresh();
}

async function resolve(id: string) {
  await api.resolveAlert(id);
  await refresh();
}

onMounted(refresh);
</script>

<template>
  <section>
    <h1>告警</h1>
    <p class="lead">实例宕机、RPM 将耗尽、磁盘压力。</p>
    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="scanInfo" class="muted">{{ scanInfo }}</p>

    <div class="panel">
      <div class="row">
        <select v-model="filter" @change="refresh">
          <option value="open">未关闭</option>
          <option value="acked">已确认</option>
          <option value="resolved">已解决</option>
          <option value="">（全部）</option>
        </select>
        <button class="primary" :disabled="busy" @click="scan">立即扫描</button>
        <button :disabled="busy" @click="refresh">刷新</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>级别</th>
            <th>类型</th>
            <th>租户</th>
            <th>消息</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in alerts" :key="a.id">
            <td>{{ a.severity }}</td>
            <td class="mono">{{ a.kind }}</td>
            <td class="mono">{{ a.tenant_id || "—" }}</td>
            <td>{{ a.message }}</td>
            <td class="row">
              <button v-if="a.status === 'open'" @click="ack(a.id)">确认</button>
              <button v-if="a.status !== 'resolved'" @click="resolve(a.id)">解决</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!alerts.length" class="muted">当前筛选条件下无告警。</p>
    </div>
  </section>
</template>
