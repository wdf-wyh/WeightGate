<script setup lang="ts">
</script>

<template>
  <div class="shell">
    <header>
      <div class="brand">automatic-<span>funicular</span> console</div>
    </header>
    <nav class="nav">
      <RouterLink to="/tenants">Tenants</RouterLink>
      <RouterLink to="/instances">Instances</RouterLink>
      <RouterLink to="/hosts">Hosts</RouterLink>
      <RouterLink to="/alerts">Alerts</RouterLink>
      <RouterLink to="/catalog">Catalog</RouterLink>
      <RouterLink to="/usage">Usage</RouterLink>
    </nav>
    <RouterView />
  </div>
</template>
