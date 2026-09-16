<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMember } from '@/api/members'
import { cancelOrder, collectPayment, getOrder } from '@/api/orders'
import type { Member, Order } from '@/api/types'
import { ORDER_STATUS_TAG, PAYMENT_METHOD_OPTIONS } from '@/constants/order'
import { REFUND_STATUS_TAG } from '@/constants/refund'
import RefundApplyDialog from '@/components/RefundApplyDialog.vue'
import GrouponVerifyDialog from '@/components/GrouponVerifyDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { formatPrice, formatTime } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  orderId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'changed'): void
}>()

const authStore = useAuthStore()
const canCollect = computed(() => authStore.hasPermission('pay:collect'))
const canRefund = computed(() => authStore.hasPermission('refund:apply'))

/** 还有钱可退才能申请退款 */
const canApplyRefund = computed(() => {
  const current = order.value
  return current !== null && canRefund.value && current.refundable_amount > 0
})

const refundApplyVisible = ref(false)
const grouponVisible = ref(false)
const canVerifyGroupon = computed(() => authStore.hasPermission('coupon:verify'))

// 取消放在详情里而不是列表行上：一行四个按钮太挤，而且取消是低频操作，
// 值得多点一下看清楚再点
const canCancelThis = computed(() => {
  const current = order.value
  return current !== null
    && authStore.hasPermission('order:cancel')
    && ['pending', 'accepted'].includes(current.status)
    && current.paid_amount === 0
})

const order = ref<Order | null>(null)
const loading = ref(false)
const saving = ref(false)

const payMethod = ref('cash')
const payAmount = ref<number | null>(null)
const transactionNo = ref('')

/**
 * 订单挂的会员（选了「储值」才去查）
 *
 * 别的支付方式用不着，白查一次没意义。而且**每次切过去都重新查**——
 * 余额是活的，缓存一个数字没意义，收银员要看到的是此刻能不能抵这单。
 */
const memberInfo = ref<Member | null>(null)
const memberLoading = ref(false)

watch(payMethod, async (method) => {
  memberInfo.value = null
  const memberId = order.value?.member_id
  if (method !== 'balance' || !memberId) return

  memberLoading.value = true
  try {
    memberInfo.value = await getMember(memberId)
  } catch {
    // 拦截器已提示；查不到就按「看不到余额」处理，后端收款时还会再拦一次
    memberInfo.value = null
  } finally {
    memberLoading.value = false
  }
})

/** 还没收的钱。用「分」做单位算一次再换回来，避开浮点误差 */
const remaining = computed(() => {
  if (!order.value) return 0
  const cents = Math.round(order.value.payable_amount * 100)
    - Math.round(order.value.paid_amount * 100)
  return cents / 100
})

const canSubmitPayment = computed(
  () => canCollect.value && order.value !== null
    && order.value.status !== 'cancelled' && remaining.value > 0
)

async function load() {
  if (props.orderId === null) return
  loading.value = true
  try {
    order.value = await getOrder(props.orderId)
    // 默认把未付部分填上——多数情况是一次付清，要组合支付再改小
    payAmount.value = remaining.value > 0 ? remaining.value : null
    payMethod.value = 'cash'
    transactionNo.value = ''
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) load()
  }
)

async function handleCollect() {
  if (!order.value || payAmount.value === null || payAmount.value <= 0) {
    ElMessage.warning('请填写收款金额')
    return
  }
  saving.value = true
  try {
    const result = await collectPayment(order.value.id, {
      method: payMethod.value,
      amount: payAmount.value,
      transaction_no: transactionNo.value.trim(),
    })
    ElMessage.success(
      result.order.is_paid ? '已收清' : `已收款，还剩 ${formatPrice(
        result.order.payable_amount - result.order.paid_amount)}`
    )
    emit('changed')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

async function handleCancel() {
  if (!order.value) return
  try {
    await ElMessageBox.confirm(
      `确定取消订单 ${order.value.order_no} 吗？\n已经收过款的订单不能直接取消，需要先走退款流程。`,
      '取消订单',
      { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  try {
    await cancelOrder(order.value.id)
    ElMessage.success('订单已取消')
    emit('changed')
    await load()
  } catch {
    // 拦截器已提示
  }
}

/** 退款申请提交后刷新详情：退款记录要立刻显示出来 */
async function handleRefundApplied() {
  emit('changed')
  await load()
}

function openReceipt() {
  if (!order.value) return
  window.open(`/receipt/${order.value.id}`, '_blank')
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="订单详情"
    width="720px"
    @close="handleClose"
  >
    <div v-loading="loading">
      <template v-if="order">
        <!-- 头部：单号 + 状态 -->
        <div class="order-head">
          <div>
            <span class="order-no">{{ order.order_no }}</span>
            <el-tag
              :type="ORDER_STATUS_TAG[order.status] ?? 'info'"
              class="status-tag"
              disable-transitions
            >
              {{ order.status_label }}
            </el-tag>
          </div>
          <span class="head-meta">
            {{ order.store_name }} · {{ order.source_label }} · {{ formatTime(order.created_at) }}
            <!-- 小票开新窗口：它是独立页面，不进主布局（打印时不该带上侧边栏） -->
            <el-button link type="primary" class="print-link" @click="openReceipt">
              打印小票
            </el-button>
          </span>
        </div>

        <div class="meta-row">
          <span>操作人：{{ order.operator_name || '顾客自助' }}</span>
          <span v-if="order.remark">备注：{{ order.remark }}</span>
        </div>

        <!-- 明细 -->
        <h4 class="section-title">菜品明细</h4>
        <el-table :data="order.items" size="small" class="detail-table">
          <el-table-column prop="dish_name" label="菜品" min-width="120" />
          <el-table-column label="规格" min-width="140">
            <template #default="{ row }">
              <span v-if="row.options_text">{{ row.options_text }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="90" align="right">
            <template #default="{ row }">{{ formatPrice(row.unit_price) }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="60" align="center" />
          <el-table-column label="小计" width="100" align="right">
            <template #default="{ row }">{{ formatPrice(row.subtotal) }}</template>
          </el-table-column>
        </el-table>

        <!-- 金额 -->
        <div class="amounts">
          <div class="amount-row">
            <span>合计</span><span>{{ formatPrice(order.total_amount) }}</span>
          </div>
          <div v-if="order.discount_amount > 0" class="amount-row">
            <span>优惠</span><span>-{{ formatPrice(order.discount_amount) }}</span>
          </div>
          <div class="amount-row total">
            <span>应付</span><span>{{ formatPrice(order.payable_amount) }}</span>
          </div>
          <div class="amount-row">
            <span>已收</span>
            <span :class="{ unpaid: remaining > 0 }">{{ formatPrice(order.paid_amount) }}</span>
          </div>
          <div v-if="order.refunded_amount > 0" class="amount-row refunded">
            <span>已退</span><span>-{{ formatPrice(order.refunded_amount) }}</span>
          </div>
          <div v-if="remaining > 0" class="amount-row remaining">
            <span>还差</span><span>{{ formatPrice(remaining) }}</span>
          </div>
        </div>

        <!-- 支付记录 -->
        <h4 class="section-title">支付记录</h4>
        <el-table v-if="order.payments?.length" :data="order.payments" size="small" class="detail-table">
          <el-table-column prop="payment_no" label="流水号" min-width="200" />
          <el-table-column prop="method_label" label="方式" width="90" />
          <el-table-column label="金额" width="100" align="right">
            <template #default="{ row }">{{ formatPrice(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="operator_name" label="收款人" width="90" />
          <el-table-column label="时间" width="140">
            <template #default="{ row }">{{ formatTime(row.paid_at) }}</template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">还没有收款记录</p>

        <!-- 退款：申请单是流程，退款流水才是钱。批了不等于钱退了 -->
        <h4 class="section-title">
          退款记录
          <el-button
            v-if="canApplyRefund"
            link
            type="primary"
            class="title-action"
            @click="refundApplyVisible = true"
          >
            申请退款
          </el-button>
        </h4>
        <el-table v-if="order.refunds?.length" :data="order.refunds" size="small" class="detail-table">
          <el-table-column prop="refund_no" label="退款单号" min-width="200" />
          <el-table-column label="金额" width="100" align="right">
            <template #default="{ row }">{{ formatPrice(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="130">
            <template #default="{ row }">
              <el-tag :type="REFUND_STATUS_TAG[row.status] ?? 'info'" size="small" disable-transitions>
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" min-width="140" />
          <el-table-column label="流程" width="150">
            <template #default="{ row }">
              <div class="flow-line">{{ row.applicant_name }} 申请</div>
              <div class="flow-line muted">
                {{ row.approver_name || '等待审批' }}
              </div>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="muted">没有退过款</p>

        <!-- 收款 -->
        <template v-if="canSubmitPayment">
          <h4 class="section-title">收款</h4>
          <div class="collect-row">
            <el-select v-model="payMethod" class="collect-method">
              <el-option
                v-for="item in PAYMENT_METHOD_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-input-number
              v-model="payAmount"
              :min="0.01"
              :max="remaining"
              :precision="2"
              :step="1"
              class="collect-amount"
            />
            <el-input
              v-model="transactionNo"
              placeholder="第三方流水号（现金可不填）"
              class="collect-txn"
            />
            <el-button type="primary" :loading="saving" @click="handleCollect">收款</el-button>
            <el-button v-if="canVerifyGroupon" @click="grouponVisible = true">
              核销团购券
            </el-button>
          </div>

          <!-- 选了「储值」才提示余额：收银员得先知道够不够，而不是点完才吃「余额不足」 -->
          <p v-if="payMethod === 'balance'" v-loading="memberLoading" class="balance-line">
            <template v-if="!order.member_id">
              <span class="balance-warn">
                这单没关联会员，用不了储值——点单时先挂上会员，散客单扣不了任何人的余额
              </span>
            </template>
            <template v-else-if="memberInfo?.balance">
              <span class="balance-ok">
                {{ memberInfo.nickname || memberInfo.mobile }}
                · 余额 <strong>{{ formatPrice(memberInfo.balance.total) }}</strong>
                <span class="balance-detail">
                  （本金 {{ formatPrice(memberInfo.balance.principal) }}
                  · 赠送 {{ formatPrice(memberInfo.balance.bonus) }}）
                </span>
              </span>
            </template>
            <span v-else class="muted">正在查余额…</span>
          </p>

          <p class="hint">
            一个订单可以收多笔：组合支付（储值 + 现金）、先定金后尾款，分几次收都行。
            第三方流水号是财务对账的依据，线上支付务必填。
            顾客用美团/抖音团购券的，走「核销团购券」——它会同时记核销记录和收款。
          </p>
        </template>
        <p v-else-if="!canCollect" class="hint">没有收款权限</p>
      </template>
    </div>

    <template #footer>
      <el-button v-if="canCancelThis" class="btn-cancel" @click="handleCancel">
        取消订单
      </el-button>
      <el-button @click="handleClose">关闭</el-button>
    </template>

    <RefundApplyDialog
      v-model="refundApplyVisible"
      :order="order"
      @success="handleRefundApplied"
    />

    <GrouponVerifyDialog
      v-model="grouponVisible"
      :order="order"
      @success="handleRefundApplied"
    />
  </el-dialog>
</template>

<style scoped>
.order-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.order-no {
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
}

.status-tag {
  margin-left: 8px;
}

.head-meta {
  font-size: 12px;
  color: #8a8a8a;
}

.meta-row {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: #8a8a8a;
  margin: 18px 0 8px;
}

.detail-table {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}

.amounts {
  width: 260px;
  margin-left: auto;
  margin-top: 14px;
}

.amount-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #666;
  padding: 3px 0;
}

.amount-row.total {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
  border-top: 1px solid #e5e5e5;
  margin-top: 4px;
  padding-top: 8px;
}

.unpaid {
  color: #c45656;
}

.amount-row.remaining {
  font-weight: 600;
  color: #c45656;
}

.amount-row.refunded {
  color: #c45656;
}

.title-action {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
}

.flow-line {
  font-size: 12px;
  line-height: 1.5;
}

.print-link {
  margin-left: 10px;
  font-size: 12px;
}

.collect-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.collect-method {
  width: 120px;
}

.collect-amount {
  width: 140px;
}

.collect-txn {
  flex: 1;
}

.muted {
  font-size: 13px;
  color: #a0a0a0;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-top: 8px;
}

/* 选「储值」时那一行余额提示 */
.balance-line {
  font-size: 13px;
  line-height: 1.7;
  margin-top: 10px;
  min-height: 22px;
}

.balance-ok {
  color: #1f1f1f;
}

.balance-detail {
  color: #8c8c8c;
}

/* 订单没挂会员：这不是「查不到」，是「这单根本用不了储值」——用红字说清楚 */
.balance-warn {
  color: #c45656;
}

.btn-cancel {
  float: left;
  color: #c45656;
  border-color: #f0d0d0;
}
</style>
