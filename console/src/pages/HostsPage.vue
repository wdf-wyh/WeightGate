<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type Host, type Tenant } from "../api";

const hosts = ref<Host[]>([]);
const tenants = ref<Tenant[]>([]);
const name = ref("customer-gpu-1");
const sshHost = ref("127.0.0.1");
const sshPort = ref(22);
const sshUser = ref("ubuntu");
const tenantId = ref("");
const error = ref("");
const busy = ref(false);

async function refresh() {
  error.value = "";
  try {
    hosts.value = await api.listHosts();
    tenants.value = await api.listTenants();
  } catch (e) {
    error.value = String(e);
  }
}

async function create() {
  busy.value = true;
  error.value = "";
  try {
    await api.createHost({
      name: name.value,
      ssh_host: sshHost.value,
      ssh_port: sshPort.value,
      ssh_user: sshUser.value,
      tenant_id: tenantId.value || undefined,
    });
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function probe(id: string) {
  busy.value = true;
  error.value = "";
  try {
    await api.probeHost(id);
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function install(id: string) {
  busy.value = true;
  error.value = "";
  try {
    await api.installAgent(id);
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <section>
    <h1>主机</h1>
    <p class="lead">
      客户自有 SSH 目标。默认驱动为模拟（`AF_SSH_DRIVER=off`），避免产生 GPU 费用。
    </p>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row wrap">
        <input v-model="name" placeholder="名称" />
        <input v-model="sshHost" placeholder="SSH 主机" />
        <input v-model.number="sshPort" type="number" placeholder="端口" />
        <input v-model="sshUser" placeholder="用户" />
        <select v-model="tenantId">
          <option value="">（任意租户）</option>
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <button class="primary" :disabled="busy" @click="create">添加主机</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>端点</th>
            <th>状态</th>
            <th>备注</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in hosts" :key="h.id">
            <td class="mono">{{ h.name }}</td>
            <td class="mono">{{ h.ssh_user }}@{{ h.ssh_host }}:{{ h.ssh_port }}</td>
            <td>{{ h.status }}</td>
            <td class="muted">{{ h.note || "—" }}</td>
            <td class="row">
              <button :disabled="busy" @click="probe(h.id)">探测</button>
              <button :disabled="busy" @click="install(h.id)">安装 Agent</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!hosts.length" class="muted">暂无主机。</p>
    </div>
  </section>
</template>
