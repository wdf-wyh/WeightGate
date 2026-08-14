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
    <h1>Hosts</h1>
    <p class="lead">
      Customer-owned SSH targets. Default driver is simulated (`AF_SSH_DRIVER=off`) so you never
      pad GPU cost.
    </p>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row wrap">
        <input v-model="name" placeholder="name" />
        <input v-model="sshHost" placeholder="ssh host" />
        <input v-model.number="sshPort" type="number" placeholder="port" />
        <input v-model="sshUser" placeholder="user" />
        <select v-model="tenantId">
          <option value="">(any tenant)</option>
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <button class="primary" :disabled="busy" @click="create">Add host</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Endpoint</th>
            <th>Status</th>
            <th>Note</th>
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
              <button :disabled="busy" @click="probe(h.id)">Probe</button>
              <button :disabled="busy" @click="install(h.id)">Install agent</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!hosts.length" class="muted">No hosts yet.</p>
    </div>
  </section>
</template>
