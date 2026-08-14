import { createRouter, createWebHistory } from "vue-router";
import TenantsPage from "./pages/TenantsPage.vue";
import InstancesPage from "./pages/InstancesPage.vue";
import UsagePage from "./pages/UsagePage.vue";
import HostsPage from "./pages/HostsPage.vue";
import AlertsPage from "./pages/AlertsPage.vue";
import CatalogPage from "./pages/CatalogPage.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/tenants" },
    { path: "/tenants", name: "tenants", component: TenantsPage },
    { path: "/instances", name: "instances", component: InstancesPage },
    { path: "/hosts", name: "hosts", component: HostsPage },
    { path: "/alerts", name: "alerts", component: AlertsPage },
    { path: "/catalog", name: "catalog", component: CatalogPage },
    { path: "/usage", name: "usage", component: UsagePage },
  ],
});
