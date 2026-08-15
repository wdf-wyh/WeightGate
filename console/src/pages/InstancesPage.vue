<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { api, type Host, type Instance, type Preset, type Tenant } from "../api";

const tenants = ref<Tenant[]>([]);
const presets = ref<Preset[]>([]);
const hosts = ref<Host[]>([]);
const instances = ref<Instance[]>([]);
const tenantId = ref("");
const presetId = ref("");
const hostId = ref("");
const error = ref("");
const busy = ref(false);

async function bootstrap() {
  error.value = "";
  try {
    tenants.value = await api.listTenants();
    presets.value = await api.listPresets();
    hosts.value = await api.listHosts();
    if (!tenantId.value && tenants.value.length) tenantId.value = tenants.value[0].id;
    if (!presetId.value && presets.value.length) presetId.value = presets.value[0].id;
    await refreshInstances();
  } catch (e) {
    error.value = String(e);
  }
}

async function refreshInstances() {
  if (!tenantId.value) {
    instances.value = [];
    return;
  }
  instances.value = await api.listInstances(tenantId.value);
}

async function create() {
  busy.value = true;
  error.value = "";
  try {
    await api.createInstance(tenantId.value, presetId.value, hostId.value || undefined);
    await refreshInstances();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function stop(id: string) {
  busy.value = true;
  error.value = "";
  try {
    await api.stopInstance(id);
    await refreshInstances();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function wake(id: string) {
  busy.value = true;
  error.value = "";
  try {
    await api.wakeInstance(id);
    await refreshInstances();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

watch(tenantId, () => {
  refreshInstances().catch((e) => (error.value = String(e)));
});

onMounted(bootstrap);
</script>

<template>
  <section>
    <h1>实例</h1>
    <p class="lead">
      通过控制面启动 / 停止 / 唤醒租户运行时（本地 Docker 或远程 SSH 主机）。
    </p>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row wrap">
        <select v-model="tenantId">
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <select v-model="presetId">
          <option v-for="p in presets" :key="p.id" :value="p.id">
            {{ p.id }} ({{ p.backend }})
          </option>
        </select>
        <select v-model="hostId">
          <option value="">本地 Docker</option>
          <option v-for="h in hosts" :key="h.id" :value="h.id">
            {{ h.name }} ({{ h.ssh_host }})
          </option>
        </select>
        <button class="primary" :disabled="busy || !tenantId || !presetId" @click="create">
          创建 / 启动
        </button>
        <button :disabled="busy || !tenantId" @click="refreshInstances">刷新</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>预设</th>
            <th>后端</th>
            <th>主机</th>
            <th>状态</th>
            <th>备注</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in instances" :key="i.id">
            <td class="mono">{{ i.id }}</td>
            <td class="mono">{{ i.preset_id }}</td>
            <td><span class="badge">{{ i.backend }}</span></td>
            <td class="mono">{{ i.host_id || "本地" }}</td>
            <td><span class="badge">{{ i.status }}</span></td>
            <td class="muted">{{ i.note || "—" }}</td>
            <td>
              <div class="row" style="margin: 0">
                <button :disabled="busy" @click="stop(i.id)">停止</button>
                <button :disabled="busy" @click="wake(i.id)">唤醒</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!instances.length" class="muted">该租户暂无实例。</p>
    </div>
  </section>
</template>
