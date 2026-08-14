<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type RoutePolicy, type Tenant } from "../api";

const tenants = ref<Tenant[]>([]);
const error = ref("");
const busy = ref(false);
const newId = ref("");
const newName = ref("");
const selected = ref("");
const policy = ref<RoutePolicy | null>(null);
const issuedKey = ref("");
const policyMode = ref<"local_only" | "cloud_only" | "hybrid">("hybrid");

async function refresh() {
  error.value = "";
  try {
    tenants.value = await api.listTenants();
    if (!selected.value && tenants.value.length) {
      selected.value = tenants.value[0].id;
      await loadPolicy();
    }
  } catch (e) {
    error.value = String(e);
  }
}

async function loadPolicy() {
  if (!selected.value) return;
  policy.value = await api.getPolicy(selected.value);
  policyMode.value = policy.value.mode;
}

async function createTenant() {
  busy.value = true;
  error.value = "";
  issuedKey.value = "";
  try {
    await api.createTenant({ id: newId.value.trim(), name: newName.value.trim() });
    newId.value = "";
    newName.value = "";
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function savePolicy() {
  if (!selected.value) return;
  busy.value = true;
  error.value = "";
  try {
    policy.value = await api.putPolicy(selected.value, { mode: policyMode.value });
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function issueKey() {
  if (!selected.value) return;
  busy.value = true;
  error.value = "";
  try {
    const key = await api.issueKey(selected.value);
    issuedKey.value = key.api_key || "(not returned)";
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
    <h1>Tenants</h1>
    <p class="lead">Manage tenants, route policy, and API key issuance via control-plane only.</p>

    <p v-if="error" class="err">{{ error }}</p>

    <div class="panel">
      <div class="row">
        <input v-model="newId" placeholder="tenant_id" />
        <input v-model="newName" placeholder="display name" />
        <button class="primary" :disabled="busy || !newId || !newName" @click="createTenant">
          Create
        </button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tenants" :key="t.id">
            <td class="mono">{{ t.id }}</td>
            <td>{{ t.name }}</td>
            <td><span class="badge">{{ t.status }}</span></td>
            <td class="muted mono">{{ t.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h1 style="font-size: 1.05rem">Route policy & keys</h1>
      <div class="row">
        <select v-model="selected" @change="loadPolicy">
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
        <select v-model="policyMode">
          <option value="local_only">local_only</option>
          <option value="cloud_only">cloud_only</option>
          <option value="hybrid">hybrid</option>
        </select>
        <button class="primary" :disabled="busy || !selected" @click="savePolicy">Save policy</button>
        <button :disabled="busy || !selected" @click="issueKey">Issue API key</button>
      </div>
      <p v-if="policy" class="muted">
        Current: <span class="mono">{{ policy.mode }}</span> · short_max_chars
        {{ policy.short_max_chars }}
      </p>
      <p v-if="issuedKey" class="ok">
        New key (copy once): <span class="mono">{{ issuedKey }}</span>
      </p>
    </div>
  </section>
</template>
