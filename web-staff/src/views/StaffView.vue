<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteStaff, getStaffList } from '@/api/staff'
import type { Staff } from '@/api/types'
import StaffFormDialog from '@/components/StaffFormDialog.vue'

const staffList = ref<Staff[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const editingStaff = ref<Staff | null>(null)

async function loadStaff() {
  loading.value = true
  try {
    const data = await getStaffList({ search: search.value, page: page.value })
    staffList.value = data.staff
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadStaff()
}

function openCreate() {
  editingStaff.value = null
  dialogVisible.value = true
}

function openEdit(staff: Staff) {
  editingStaff.value = staff
  dialogVisible.value = true
}

async function handleDelete(staff: Staff) {
  try {
    await ElMessageBox.confirm(`确定删除员工 ${staff.real_name} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteStaff(staff.id)
    ElMessage.success('删除成功')
    if (staffList.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadStaff()
  } catch {
    // 拦截器已提示
  }
}

function handleDialogSuccess() {
  dialogVisible.value = false
  loadStaff()
}

onMounted(loadStaff)
</script>

<template>
  <div class="staff">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索用户名/姓名/手机号/邮箱"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <el-button
        type="primary"
        class="ml-auto add-btn"
        title="新增员工"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="staffList">
        <!-- 列宽是算过的，内容区实际只有 892px。放不下的表现不是出现滚动条，
             而是 fixed 的操作列盖住「角色」列，标签被截成「超级管」这种半截字。
             所以用户名并进姓名列做成两行——它是次要信息，登录才用得上 -->
        <el-table-column label="姓名" min-width="130">
          <template #default="{ row }">
            <div class="staff-name">{{ row.real_name }}</div>
            <div class="staff-username">{{ row.username }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="mobile" label="手机号" width="120" />
        <el-table-column label="归属门店" width="110">
          <template #default="{ row }">
            {{ row.store_name ?? '总部' }}
          </template>
        </el-table-column>
        <el-table-column prop="employment_type_label" label="用工类型" width="85" />
        <el-table-column label="账号" width="65">
          <template #default="{ row }">
            <el-tag v-if="row.is_shared" type="warning" size="small" disable-transitions>公用</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="65">
          <template #default="{ row }">{{ row.is_active ? '启用' : '禁用' }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="130">
          <template #default="{ row }">
            <span v-if="row.is_admin" class="super-admin">超级管理员</span>
            <template v-else-if="row.roles.length">
              <el-tag
                v-for="role in row.roles"
                :key="role.id"
                size="small"
                class="role-tag"
                disable-transitions
              >
                {{ role.name }}
              </el-tag>
            </template>
            <el-tag v-else type="info" size="small" disable-transitions>未分配</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
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
        @current-change="loadStaff"
      />
    </div>

    <StaffFormDialog
      v-model="dialogVisible"
      :staff="editingStaff"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.staff {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 280px;
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

.staff-name {
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

/* 用户名做成姓名下面的小字：它是次要信息，只在登录时用得上 */
.staff-username {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.4;
}

.role-tag {
  margin-right: 4px;
}

/* 超级管理员是旁路，不是角色，跟普通角色标签区分开 */
.super-admin {
  font-weight: 600;
  color: #1f1f1f;
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