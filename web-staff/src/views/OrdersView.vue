<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { acceptOrder, cancelOrder, completeOrder, getOrders } from '@/api/orders'
import { getStoreOptions } from '@/api/stores'
import type { Order, StoreOption } from '@/api/types'
import OrderDetailDialog from '@/components/OrderDetailDialog.vue'
import { ORDER_STATUS_OPTIONS, ORDER_STATUS_TAG } from '@/constants/order'
import { useAuthStore } from '@/stores/auth'
import { formatPrice, formatTime } from '@/utils/format'

const authStore = useAuthStore()

const canReceive = computed(() => authStore.hasPermission('order:receive'))
const canCancel = computed(() => authStore.hasPermission('order:cancel'))
const canCollect = computed(() => authStore.hasPermission('pay:collect'))
const canViewStores = computed(() => authStore.hasPermission('store:view'))

const orders = ref<Order[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const statusFilter = ref<string | null>(null)
const storeFilter = ref<number | null>(null)
const storeOptions = ref<StoreOption[]>([])
const loading = ref(false)

const detailVisible = ref(false)
const detailOrderId = ref<number | null>(null)

async function loadStores() {
  if (!canViewStores.value) return
  try {
    const data = await getStoreOptions()
    storeOptions.value = data.stores
  } catch {
    // 拦截器已提示
  }
}

async function loadOrders() {
  loading.value = true
  try {
    const data = await getOrders({
      search: search.value,
      page: page.value,
      status: statusFilter.value ?? undefined,
      store_id: storeFilter.value ?? undefined,
    })
    orders.value = data.orders
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadOrders()
}

function openDetail(order: Order) {
  detailOrderId.value = order.id
  detailVisible.value = true
}

async function handleAccept(order: Order) {
  try {
    await acceptOrder(order.id)
    ElMessage.success(`订单 ${order.order_no} 已接单`)
    loadOrders()
  } catch {
    // 拦截器已提示
  }
}

async function handleComplete(order: Order) {
  try {
    await completeOrder(order.id)
    ElMessage.success(`订单 ${order.order_no} 已完成`)
    loadOrders()
  } catch {
    // 拦截器已提示
  }
}

async function handleCancel(order: Order) {
  try {
    await ElMessageBox.confirm(
      `确定取消订单 ${order.order_no} 吗？\n已经收过款的订单不能直接取消，需要先走退款流程。`,
      '取消订单',
      { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  try {
    await cancelOrder(order.id)
    ElMessage.success('订单已取消')
    loadOrders()
  } catch {
    // 拦截器已提示
  }
}

/** 待接单的行加底色，收银员一眼看到要处理的单子 */
function rowClassName({ row }: { row: Order }) {
  return row.status === 'pending' ? 'row-pending' : ''
}

onMounted(() => {
  loadStores()
  loadOrders()
})
</script>

<template>
  <div class="orders">
    <div class="toolbar">
      <el-select
        v-if="canViewStores"
        v-model="storeFilter"
        placeholder="全部门店"
        clearable
        class="store-filter"
        @change="handleSearch"
      >
        <el-option
          v-for="store in storeOptions"
          :key="store.id"
          :label="`${store.name}（${store.code}）`"
          :value="store.id"
        />
      </el-select>
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        class="status-filter"
        @change="handleSearch"
      >
        <el-option
          v-for="item in ORDER_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-input
        v-model="search"
        placeholder="搜索单号"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="loadOrders">刷新</el-button>
    </div>

    <div class="table-card">
      <el-table v-loading="loading" :data="orders" :row-class-name="rowClassName">
        <el-table-column prop="order_no" label="单号" min-width="200" />
        <el-table-column prop="store_name" label="门店" width="120" />
        <el-table-column prop="source_label" label="来源" width="80" />
        <el-table-column label="应付" width="100" align="right">
          <template #default="{ row }">{{ formatPrice(row.payable_amount) }}</template>
        </el-table-column>
        <el-table-column label="已收" width="100" align="right">
          <template #default="{ row }">
            <span :class="{ unpaid: !row.is_paid }">{{ formatPrice(row.paid_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="ORDER_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下单时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending' && canReceive"
              size="small"
              type="primary"
              @click="handleAccept(row)"
            >
              接单
            </el-button>
            <el-button
              v-if="row.status === 'accepted' && canReceive"
              size="small"
              @click="handleComplete(row)"
            >
              完成
            </el-button>
            <el-button
              v-if="row.status !== 'cancelled' && !row.is_paid && canCollect"
              size="small"
              @click="openDetail(row)"
            >
              收款
            </el-button>
            <el-button size="small" link @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="['pending', 'accepted'].includes(row.status) && row.paid_amount === 0 && canCancel"
              size="small"
              link
              class="btn-cancel"
              @click="handleCancel(row)"
            >
              取消
            </el-button>
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
        @current-change="loadOrders"
      />
    </div>

    <OrderDetailDialog
      v-model="detailVisible"
      :order-id="detailOrderId"
      @changed="loadOrders"
    />
  </div>
</template>

<style scoped>
.orders {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.store-filter {
  width: 200px;
}

.status-filter {
  width: 140px;
}

.search-input {
  width: 200px;
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

/* 待接单：左侧加一条红杠 + 淡淡底色，收银台一眼扫到 */
.table-card :deep(.row-pending) {
  --el-table-tr-bg-color: #fdf3f3;
}

.table-card :deep(.row-pending td:first-child) {
  box-shadow: inset 3px 0 0 #c45656;
}

.unpaid {
  color: #c45656;
}

.btn-cancel {
  color: #c45656;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
