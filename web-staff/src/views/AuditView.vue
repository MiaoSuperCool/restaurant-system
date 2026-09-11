<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getAuditLogs } from '@/api/audit'
import type { AuditLog } from '@/api/types'

const logs = ref<AuditLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

// 详情弹窗
const detailVisible = ref(false)
const currentLog = ref<AuditLog | null>(null)

/** 后端存的英文 action → 中文显示 */
const actionMap: Record<string, string> = {
  Login: '登录',
  Logout: '登出',
  CREATE_USER: '创建用户',
  UPDATE_USER: '修改用户',
  DELETE_USER: '删除用户',
  BookCreated: '创建图书',
  BookUpdated: '修改图书',
  BookDeleted: '删除图书',
  CreateSaleLog: '录入销售',
}

function actionText(action: string): string {
  return actionMap[action] ?? action
}

function statusText(status: string): string {
  return status === 'success' ? '成功' : '失败'
}

async function loadLogs() {
  loading.value = true
  try {
    const data = await getAuditLogs({ search: search.value, page: page.value })
    logs.value = data.logs
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadLogs()
}

function openDetail(log: AuditLog) {
  currentLog.value = log
  detailVisible.value = true
}

function formatJson(value: unknown): string {
  return value ? JSON.stringify(value, null, 2) : '（无）'
}

onMounted(loadLogs)
</script>

<template>
  <div class="audit">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索操作人或操作"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="logs">
        <el-table-column prop="user_name" label="操作人" width="120" />
        <el-table-column label="操作" width="110">
          <template #default="{ row }">{{ actionText(row.action) }}</template>
        </el-table-column>
        <el-table-column prop="resource" label="对象" width="100" />
        <el-table-column prop="datetime" label="时间" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
        <el-table-column label="详情" width="90">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
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
        @current-change="loadLogs"
      />
    </div>

    <!-- 详情弹窗：展示变更前后的 JSON -->
    <el-dialog v-model="detailVisible" title="日志详情" width="640px">
      <template v-if="currentLog">
        <div class="detail-meta">
          <span>{{ currentLog.user_name }} · {{ actionText(currentLog.action) }}</span>
          <span>{{ currentLog.datetime }}</span>
        </div>
        <h4 class="detail-title">变更前</h4>
        <pre class="json-block">{{ formatJson(currentLog.old_value) }}</pre>
        <h4 class="detail-title">变更后</h4>
        <pre class="json-block">{{ formatJson(currentLog.new_value) }}</pre>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit {
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

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.detail-meta {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #1f1f1f;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 13px;
  font-weight: 500;
  color: #8a8a8a;
  margin: 12px 0 8px;
}

.json-block {
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>