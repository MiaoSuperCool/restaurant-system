<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getGrouponVouchers } from '@/api/groupon'
import type { GrouponVoucher } from '@/api/types'
import { formatPrice, formatTime } from '@/utils/format'

const vouchers = ref<GrouponVoucher[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

/** 当前页的券面额合计——对账时最常看的数 */
function pageTotal(): number {
  return vouchers.value.reduce((sum, item) => sum + item.amount, 0)
}

async function loadVouchers() {
  loading.value = true
  try {
    const data = await getGrouponVouchers({ search: search.value, page: page.value })
    vouchers.value = data.vouchers
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadVouchers()
}

onMounted(loadVouchers)
</script>

<template>
  <div class="vouchers">
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索券码 / 订单号"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="handleSearch">搜索</el-button>
      <el-button @click="loadVouchers">刷新</el-button>
    </div>

    <p class="hint">
      核销记录是用来和平台对账的：月底按平台拉一份，核对核销了多少张、多少钱。
      券码在系统里<strong>全局唯一</strong>——同一张券核销第二次会被拒。
    </p>

    <div class="table-card">
      <el-table v-loading="loading" :data="vouchers">
        <el-table-column label="券码" min-width="200">
          <template #default="{ row }">
            <div class="code">{{ row.code }}</div>
            <div class="sub">{{ row.platform_label }}</div>
          </template>
        </el-table-column>
        <el-table-column label="券面额" width="100" align="right">
          <template #default="{ row }">{{ formatPrice(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="order_no" label="核销订单" min-width="200" />
        <el-table-column prop="verified_by_name" label="核销人" width="110" />
        <el-table-column label="核销时间" width="140">
          <template #default="{ row }">{{ formatTime(row.verified_at) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-wrap">
      <span class="page-total">本页合计 {{ formatPrice(pageTotal()) }}</span>
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadVouchers"
      />
    </div>
  </div>
</template>

<style scoped>
.vouchers {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.search-input {
  width: 260px;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-bottom: 16px;
}

.hint strong {
  color: #1f1f1f;
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

.code {
  font-family: Consolas, Monaco, monospace;
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

.sub {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.4;
}

.pagination-wrap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.page-total {
  font-size: 13px;
  color: #666;
}
</style>
