<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getRoles } from '@/api/roles'
import type { Permission, Role } from '@/api/types'

const roles = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const loading = ref(false)

/** 权限按域分组，顺序沿用后端的 sort_order */
const groupedPermissions = computed(() => {
  const groups: { name: string; items: Permission[] }[] = []
  for (const permission of permissions.value) {
    let group = groups.find((item) => item.name === permission.group)
    if (!group) {
      group = { name: permission.group, items: [] }
      groups.push(group)
    }
    group.items.push(permission)
  }
  return groups
})

/** 一个角色有没有这个权限码——矩阵里 8×37 个格子每个都要问一次 */
function has(role: Role, code: string): boolean {
  return role.permission_codes.includes(code)
}

async function load() {
  loading.value = true
  try {
    const data = await getRoles()
    roles.value = data.roles
    permissions.value = data.permissions
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="roles">
    <div class="head">
      <h1 class="title">角色与权限</h1>
      <p class="subtitle">
        {{ roles.length }} 个角色 × {{ permissions.length }} 个权限码。
        角色矩阵定义在 <code>backend/app/rbac.py</code>，改完执行 <code>flask seed-rbac</code> 同步。
      </p>
    </div>

    <div v-loading="loading" class="matrix-wrap">
      <table class="matrix">
        <thead>
          <tr>
            <th class="perm-col">权限</th>
            <th v-for="role in roles" :key="role.id" :title="role.description">
              {{ role.name }}
            </th>
          </tr>
          <!-- 数据范围是「能碰哪些数据」，和「能不能干」是两回事，
               所以单独占一行，别和权限格子混在一起看 -->
          <tr class="scope-row">
            <th class="perm-col">数据范围</th>
            <td v-for="role in roles" :key="role.id">{{ role.data_scope_label }}</td>
          </tr>
        </thead>
        <tbody v-for="group in groupedPermissions" :key="group.name">
          <tr class="group-row">
            <td :colspan="roles.length + 1">{{ group.name }}</td>
          </tr>
          <tr v-for="permission in group.items" :key="permission.code">
            <td class="perm-col perm-name">
              <div class="perm-label">{{ permission.name }}</div>
              <div class="perm-code">{{ permission.code }}</div>
            </td>
            <td
              v-for="role in roles"
              :key="role.id"
              class="cell"
              :class="{ granted: has(role, permission.code) }"
            >
              {{ has(role, permission.code) ? '✓' : '' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="legend">
      <span class="legend-item"><span class="tick">✓</span> 该角色拥有这个权限</span>
      <span class="legend-item">空白 = 没有</span>
      <span class="legend-item">
        「数据范围」只有两档：<strong>本店</strong> = 只能碰自己归属门店的数据，
        <strong>全部</strong> = 6 家店都能碰
      </span>
    </div>
  </div>
</template>

<style scoped>
.roles {
  padding: 32px;
}

.head {
  margin-bottom: 20px;
}

.title {
  font-size: 22px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 13px;
  color: #8a8a8a;
}

.subtitle code {
  background: #f2f2f2;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}

.matrix-wrap {
  overflow-x: auto;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  background: #fafafa;
}

.matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.matrix thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f5f5f5;
  font-weight: 600;
  color: #1f1f1f;
  padding: 12px 6px;
  border-bottom: 1px solid #e5e5e5;
  text-align: center;
  white-space: nowrap;
}

.matrix .perm-col {
  width: 240px;
  min-width: 240px;
  text-align: left;
  padding-left: 20px;
}

.matrix thead th:not(.perm-col) {
  width: 80px;
}

/* 数据范围那一行：它不是权限，颜色区分开 */
.scope-row th,
.scope-row td {
  background: #fff;
  font-size: 12px;
  color: #8a8a8a;
  padding: 8px 6px;
  border-bottom: 2px solid #e5e5e5;
}

.scope-row .perm-col {
  color: #1f1f1f;
  font-weight: 600;
}

.group-row td {
  background: #f2f2f2;
  font-weight: 600;
  color: #1f1f1f;
  font-size: 12px;
  padding: 6px 20px;
}

.matrix tbody td {
  padding: 7px 6px;
  border-bottom: 1px solid #ededed;
  text-align: center;
}

.matrix tbody tr:hover td {
  background: #f7f7f7;
}

.perm-name {
  text-align: left;
  line-height: 1.35;
}

.perm-label {
  color: #1f1f1f;
}

/* 权限码单独一行、等宽字体：一眼看出「资源:动作」的命名规律，
   也不用和中文名挤在一起（长名字换行时会错位） */
.perm-code {
  font-family: Consolas, Monaco, monospace;
  font-size: 11px;
  color: #b0b0b0;
}

.cell {
  color: #c0c0c0;
}

.cell.granted {
  color: #1f1f1f;
  font-weight: 600;
}

.legend {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-top: 16px;
  font-size: 12px;
  color: #8a8a8a;
}

.tick {
  color: #1f1f1f;
  font-weight: 600;
  margin-right: 4px;
}

.legend strong {
  color: #1f1f1f;
}
</style>
