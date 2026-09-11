<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteStore, getStores } from '@/api/stores'
import type { Store } from '@/api/types'
import { BUSINESS_STATUS_TAG } from '@/constants/store'
import StoreFormDialog from '@/components/StoreFormDialog.vue'

const stores = ref<Store[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const editingStore = ref<Store | null>(null)

async function loadStores() {
  loading.value = true
  try {
    const data = await getStores({ search: search.value, page: page.value })
    stores.value = data.stores
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadStores()
}

function openCreate() {
  editingStore.value = null
  dialogVisible.value = true
}

function openEdit(store: Store) {
  editingStore.value = store
  dialogVisible.value = true
}

async function handleDelete(store: Store) {
  try {
    await ElMessageBox.confirm(
      `确定删除门店「${store.name}」吗？该门店的历史数据会失去归属。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteStore(store.id)
    ElMessage.success('删除成功')
    if (stores.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadStores()
  } catch {
    // 拦截器已提示
  }
}

function handleDialogSuccess() {
  dialogVisible.value = false
  loadStores()
}

onMounted(loadStores)
</script>

<template>
  <div class="stores">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索编码/名称/地址"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <el-button
        type="primary"
        class="ml-auto add-btn"
        title="新增门店"
        @click="openCreate"
      >
        +
      </el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="stores">
        <el-table-column prop="code" label="编码" width="90" />
        <el-table-column prop="name" label="门店名称" min-width="140" />
        <el-table-column prop="store_type_label" label="类型" width="100" />
        <el-table-column prop="address" label="地址" min-width="180" />
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column label="营业状态" width="100">
          <template #default="{ row }">
            <el-tag :type="BUSINESS_STATUS_TAG[row.business_status] ?? 'info'" disable-transitions>
              {{ row.business_status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="run_mode_label" label="运行模式" width="100" />
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
        @current-change="loadStores"
      />
    </div>

    <StoreFormDialog
      v-model="dialogVisible"
      :store="editingStore"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.stores {
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