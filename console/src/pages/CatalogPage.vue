<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type License, type MirrorProduct, type Tenant } from "../api";

const products = ref<MirrorProduct[]>([]);
const tenants = ref<Tenant[]>([]);
const tenantId = ref("");
const licenses = ref<License[]>([]);
const lastKey = ref("");
const activateKey = ref("");
const error = ref("");
const busy = ref(false);

async function refresh() {
  error.value = "";
  try {
    products.value = await api.listMirrors();
    tenants.value = await api.listTenants();
    if (!tenantId.value && tenants.value.length) tenantId.value = tenants.value[0].id;
    if (tenantId.value) licenses.value = await api.listLicenses(tenantId.value);
  } catch (e) {
    error.value = String(e);
  }
}

async function issue(productId: string) {
  busy.value = true;
  error.value = "";
  lastKey.value = "";
  try {
    const lic = await api.issueLicense(productId, tenantId.value);
    lastKey.value = lic.license_key || "";
    licenses.value = await api.listLicenses(tenantId.value);
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function activate() {
  busy.value = true;
  error.value = "";
  try {
    await api.activateLicense(activateKey.value.trim());
    licenses.value = await api.listLicenses(tenantId.value);
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
    <h1>Mirror catalog</h1>
    <p class="lead">Vertical packs (law / trade). Issue a license, then activate to install a tenant marker.</p>
    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="lastKey" class="mono">Issued key (copy once): {{ lastKey }}</p>

    <div class="panel">
      <div class="row">
        <select v-model="tenantId" @change="refresh">
          <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.id }}</option>
        </select>
      </div>
      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Domain</th>
            <th>Price</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in products" :key="p.id">
            <td>
              <div>{{ p.display_name }}</div>
              <div class="muted">{{ p.description }}</div>
            </td>
            <td class="mono">{{ p.domain }}</td>
            <td>¥{{ p.price_cny }}</td>
            <td>
              <button class="primary" :disabled="busy || !tenantId" @click="issue(p.id)">
                Issue license
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Activate</h2>
      <div class="row">
        <input v-model="activateKey" placeholder="lic-af-…" style="min-width: 22rem" />
        <button :disabled="busy || !activateKey" @click="activate">Activate → install marker</button>
      </div>
    </div>

    <div class="panel">
      <h2>Licenses for {{ tenantId || "—" }}</h2>
      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Prefix</th>
            <th>Status</th>
            <th>Activated</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in licenses" :key="l.id">
            <td class="mono">{{ l.product_id }}</td>
            <td class="mono">{{ l.key_prefix }}</td>
            <td>{{ l.status }}</td>
            <td class="muted">{{ l.activated_at || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
