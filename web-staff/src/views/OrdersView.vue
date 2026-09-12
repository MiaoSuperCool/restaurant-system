<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { acceptOrder, completeOrder, getOrders } from '@/api/orders'
import { getStoreOptions } from '@/api/stores'
import type { Order, StoreOption } from '@/api/types'
import OrderDetailDialog from '@/components/OrderDetailDialog.vue'
import { ORDER_STATUS_OPTIONS, ORDER_STATUS_TAG } from '@/constants/order'
import { useAuthStore } from '@/stores/auth'
import { formatPrice, formatTime } from '@/utils/format'

const authStore = useAuthStore()
const route = useRoute()

const canReceive = computed(() => authStore.hasPermission('order:receive'))
const canCollect = computed(() => authStore.hasPermission('pay:collect'))
const canViewStores = computed(() => authStore.hasPermission('store:view'))

const orders = ref<Order[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
// 首页「处理订单」快捷入口会带 ?status=pending 进来，直接落在待接单上
const statusFilter = ref<string | null>((route.query.status as string) || null)
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
        <!-- 列宽是算过的，内容区实际只有 892px
             （1440 − 侧边栏 200 − 用户卡 240 − 页面 32×2 − 卡片 20×2）。
             塞不下时的表现不是出现滚动条，而是 fixed 的操作列盖住前一列，
             看起来像渲染坏了——所以来源和时间并进单号列做成两行，
             省下两列的宽度，也更像收银台看单子的方式。 -->
        <el-table-column label="单号" min-width="230">
          <template #default="{ row }">
            <div class="order-no">{{ row.order_no }}</div>
            <div class="order-meta">
              {{ row.source_label }} · {{ formatTime(row.created_at) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="store_name" label="门店" min-width="115" />
        <el-table-column label="应付" width="95" align="right">
          <template #default="{ row }">{{ formatPrice(row.payable_amount) }}</template>
        </el-table-column>
        <el-table-column label="已收" width="95" align="right">
          <template #default="{ row }">
            <span :class="{ unpaid: !row.is_paid }">{{ formatPrice(row.paid_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="92">
          <template #default="{ row }">
            <el-tag :type="ORDER_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 取消不放这里：一行四个按钮太挤，而且取消是低频操作，
             挪到详情弹窗里多点一下、也看得更清楚 -->
        <el-table-column label="操作" width="180" fixed="right">
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

.order-no {
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

/* 来源和时间做成单号下面的一行小字：它们是次要信息，
   单独占两列会把表格挤爆 */
.order-meta {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.4;
}

.unpaid {
  color: #c45656;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
