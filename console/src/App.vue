<script setup lang="ts">
</script>

<template>
  <div class="shell">
    <header>
      <div class="brand">Weight<span>Gate</span> 控制台</div>
    </header>
    <nav class="nav">
      <RouterLink to="/tenants">租户</RouterLink>
      <RouterLink to="/instances">实例</RouterLink>
      <RouterLink to="/hosts">主机</RouterLink>
      <RouterLink to="/alerts">告警</RouterLink>
      <RouterLink to="/catalog">目录</RouterLink>
      <RouterLink to="/usage">用量</RouterLink>
    </nav>
    <RouterView />
  </div>
</template>
