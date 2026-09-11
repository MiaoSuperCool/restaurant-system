<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, deleteUser } from '@/api/users'
import type { User } from '@/api/types'
import UserFormDialog from '@/components/UserFormDialog.vue'

const users = ref<User[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const editingUser = ref<User | null>(null)

async function loadUsers() {
  loading.value = true
  try {
    const data = await getUsers({ search: search.value, page: page.value })
    users.value = data.users
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadUsers()
}

function openCreate() {
  editingUser.value = null
  dialogVisible.value = true
}

function openEdit(user: User) {
  editingUser.value = user
  dialogVisible.value = true
}

async function handleDelete(user: User) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${user.username} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteUser(user.id)
    ElMessage.success('删除成功')
    if (users.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadUsers()
  } catch {
    // 拦截器已提示
  }
}

function handleDialogSuccess() {
  dialogVisible.value = false
  loadUsers()
}

onMounted(loadUsers)
</script>

<template>
  <div class="users">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索用户名/姓名/邮箱"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <el-button
        type="primary"
        class="ml-auto add-btn"
        title="新增用户"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="users">
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="real_name" label="姓名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="mobile" label="手机号" />
        <el-table-column label="状态" width="70">
          <template #default="{ row }">{{ row.is_active ? '启用' : '禁用' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="80">
          <template #default="{ row }">{{ row.is_admin ? '管理员' : '员工' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" class="btn-delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadUsers"
      />
    </div>

    <UserFormDialog
      v-model="dialogVisible"
      :user="editingUser"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.users {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 260px;
}


.table-card {
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  overflow: hidden;
  padding: 20px;
}

.table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #ebebeb;
  --el-table-border-color: #e2e2e2;
}

.add-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  font-size: 20px;
  line-height: 1;
}

/* 删除按钮：黑边框 + 灰底白字；悬停变黑底白字 */
.btn-delete {
  background: #6b6b6b;
  border-color: #1f1f1f;
  color: #fff;
}

.btn-delete:hover,
.btn-delete:focus {
  background: #1f1f1f;
  border-color: #1f1f1f;
  color: #fff;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>