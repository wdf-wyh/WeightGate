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
    scanInfo.value = `created ${r.created}, open ${r.open_total}`;
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
    <h1>Alerts</h1>
    <p class="lead">Instance down, RPM near-exhaustion, and disk pressure.</p>
    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="scanInfo" class="muted">{{ scanInfo }}</p>

    <div class="panel">
      <div class="row">
        <select v-model="filter" @change="refresh">
          <option value="open">open</option>
          <option value="acked">acked</option>
          <option value="resolved">resolved</option>
          <option value="">(all)</option>
        </select>
        <button class="primary" :disabled="busy" @click="scan">Scan now</button>
        <button :disabled="busy" @click="refresh">Refresh</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Kind</th>
            <th>Tenant</th>
            <th>Message</th>
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
              <button v-if="a.status === 'open'" @click="ack(a.id)">Ack</button>
              <button v-if="a.status !== 'resolved'" @click="resolve(a.id)">Resolve</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!alerts.length" class="muted">No alerts in this filter.</p>
    </div>
  </section>
</template>
