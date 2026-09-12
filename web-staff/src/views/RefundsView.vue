<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { approveRefund, getRefunds, rejectRefund } from '@/api/refunds'
import type { Refund } from '@/api/types'
import RefundSettleDialog from '@/components/RefundSettleDialog.vue'
import { REFUND_STATUS_OPTIONS, REFUND_STATUS_TAG } from '@/constants/refund'
import { useAuthStore } from '@/stores/auth'
import { formatPrice, formatTime } from '@/utils/format'

const authStore = useAuthStore()
const canApprove = computed(() => authStore.hasPermission('refund:approve'))

const refunds = ref<Refund[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const statusFilter = ref<string | null>(null)
const loading = ref(false)

const settleVisible = ref(false)
const settlingRefund = ref<Refund | null>(null)

async function loadRefunds() {
  loading.value = true
  try {
    const data = await getRefunds({
      search: search.value,
      page: page.value,
      status: statusFilter.value ?? undefined,
    })
    refunds.value = data.refunds
    total.value = data.pagination.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadRefunds()
}

async function handleApprove(refund: Refund) {
  try {
    const { value } = await ElMessageBox.prompt(
      `批准「${refund.refund_no}」退 ${formatPrice(refund.amount)}？\n批准之后还要再确认一次打款，钱才会真的出去。`,
      '批准退款',
      {
        confirmButtonText: '批准',
        cancelButtonText: '取消',
        inputPlaceholder: '审批意见（可不填）',
      }
    )
    await approveRefund(refund.id, value || '')
    ElMessage.success('已批准，请确认打款')
    loadRefunds()
  } catch {
    // 取消 或 拦截器已提示
  }
}

async function handleReject(refund: Refund) {
  try {
    const { value } = await ElMessageBox.prompt(
      `驳回「${refund.refund_no}」的退款申请`,
      '驳回退款',
      {
        confirmButtonText: '驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '驳回原因（必填）',
        inputValidator: (input: string) => (input && input.trim() ? true : '必须写原因'),
      }
    )
    await rejectRefund(refund.id, value)
    ElMessage.success('已驳回')
    loadRefunds()
  } catch {
    // 取消 或 拦截器已提示
  }
}

function openSettle(refund: Refund) {
  settlingRefund.value = refund
  settleVisible.value = true
}

function handleSettleSuccess() {
  settleVisible.value = false
  loadRefunds()
}

onMounted(loadRefunds)
</script>

<template>
  <div class="refunds">
    <div class="toolbar">
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        class="status-filter"
        @change="handleSearch"
      >
        <el-option
          v-for="item in REFUND_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-input
        v-model="search"
        placeholder="搜索退款单号 / 订单号"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button @click="loadRefunds">刷新</el-button>
    </div>

    <p class="hint">
      退款分三步走：<strong>申请 → 审批 → 确认打款</strong>。
      审批通过不等于钱退了——线上要等退款接口返回，线下要等财务把现金给到顾客，
      所以最后一步要单独确认，那一刻才记退款流水。
    </p>

    <div class="table-card">
      <el-table v-loading="loading" :data="refunds">
        <!-- 列宽合计 865px，内容区 892px。
             退款单号本身就能看出是哪张订单（订单号 + -R序号），
             所以不再单开一列放订单号 -->
        <el-table-column label="退款单" min-width="210">
          <template #default="{ row }">
            <div class="refund-no">{{ row.refund_no }}</div>
            <div class="refund-sub">{{ row.type_label }}</div>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="95" align="right">
          <template #default="{ row }">{{ formatPrice(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="95">
          <template #default="{ row }">
            <el-tag :type="REFUND_STATUS_TAG[row.status] ?? 'info'" disable-transitions>
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流程" min-width="150">
          <template #default="{ row }">
            <div class="flow">{{ row.applicant_name }} 申请</div>
            <div class="refund-sub">
              {{ row.approver_name ? `${row.approver_name} 审批` : '等待审批' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="135">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <template v-if="canApprove && row.status === 'pending'">
              <el-button size="small" type="primary" @click="handleApprove(row)">批准</el-button>
              <el-button size="small" link class="btn-reject" @click="handleReject(row)">
                驳回
              </el-button>
            </template>
            <el-button
              v-else-if="canApprove && row.status === 'approved'"
              size="small"
              type="primary"
              @click="openSettle(row)"
            >
              确认退款
            </el-button>
            <span v-else class="muted">—</span>
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
        @current-change="loadRefunds"
      />
    </div>

    <RefundSettleDialog
      v-model="settleVisible"
      :refund="settlingRefund"
      @success="handleSettleSuccess"
    />
  </div>
</template>

<style scoped>
.refunds {
  padding: 32px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.status-filter {
  width: 180px;
}

.search-input {
  width: 240px;
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

.refund-no {
  font-weight: 600;
  color: #1f1f1f;
  line-height: 1.4;
}

.refund-sub,
.flow {
  font-size: 12px;
  color: #a0a0a0;
  line-height: 1.4;
}

.btn-reject {
  color: #c45656;
}

.muted {
  color: #c0c0c0;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
