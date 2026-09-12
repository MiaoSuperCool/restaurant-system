<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getOrder } from '@/api/orders'
import type { Order } from '@/api/types'
import { formatPrice, formatTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const order = ref<Order | null>(null)
const loading = ref(false)

/** 已收的每一笔都打出来——顾客要看清楚钱是怎么付的 */
const paymentLines = computed(() => order.value?.payments ?? [])

async function loadOrder() {
  loading.value = true
  try {
    order.value = await getOrder(Number(route.params.id))
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
}

function handlePrint() {
  window.print()
}

onMounted(loadOrder)
</script>

<template>
  <div class="receipt-page">
    <!-- 屏幕上的工具条。打印时会被 @media print 隐藏 -->
    <div class="toolbar no-print">
      <el-button @click="router.back()">返回</el-button>
      <el-button type="primary" :disabled="!order" @click="handlePrint">打印小票</el-button>
      <span class="tip">打印宽度按 80mm 热敏纸设置</span>
    </div>

    <div v-loading="loading" class="paper-wrap">
      <div v-if="order" class="paper">
        <div class="center store-name">{{ order.store_name }}</div>
        <div class="center small">
          {{ order.source_label }} · {{ formatTime(order.created_at) }}
        </div>
        <div class="divider"></div>

        <div class="row small">
          <span>单号</span><span>{{ order.order_no }}</span>
        </div>
        <div class="row small">
          <span>操作人</span><span>{{ order.operator_name || '顾客自助' }}</span>
        </div>
        <div v-if="order.remark" class="row small">
          <span>备注</span><span>{{ order.remark }}</span>
        </div>

        <div class="divider"></div>

        <!-- 明细：菜名一行、规格一行、金额右对齐 -->
        <div v-for="item in order.items" :key="item.id" class="item">
          <div class="item-name">{{ item.dish_name }}</div>
          <div v-if="item.options_text" class="item-options">{{ item.options_text }}</div>
          <div class="item-amount">
            <span>{{ formatPrice(item.unit_price) }} × {{ item.quantity }}</span>
            <span>{{ formatPrice(item.subtotal) }}</span>
          </div>
        </div>

        <div class="divider"></div>

        <div class="row">
          <span>合计</span><span>{{ formatPrice(order.total_amount) }}</span>
        </div>
        <div v-if="order.discount_amount > 0" class="row">
          <span>优惠</span><span>-{{ formatPrice(order.discount_amount) }}</span>
        </div>
        <div class="row total">
          <span>应付</span><span>{{ formatPrice(order.payable_amount) }}</span>
        </div>

        <div class="divider"></div>

        <div v-for="payment in paymentLines" :key="payment.id" class="row small">
          <span>{{ payment.method_label }}</span><span>{{ formatPrice(payment.amount) }}</span>
        </div>
        <div v-if="order.refunded_amount > 0" class="row small">
          <span>已退</span><span>-{{ formatPrice(order.refunded_amount) }}</span>
        </div>
        <!-- 没付款的单子也要能打（预结单），但必须印清楚还没付——
             不然打出来和已付款的长得一样，容易当成收过钱了 -->
        <div v-if="paymentLines.length === 0" class="row small unpaid">
          <span>未付款</span><span>{{ formatPrice(order.payable_amount) }}</span>
        </div>
        <div v-else-if="!order.is_paid" class="row small unpaid">
          <span>还差</span>
          <span>{{ formatPrice(order.payable_amount - order.paid_amount) }}</span>
        </div>

        <div class="divider"></div>
        <div class="center thanks">谢谢惠顾，欢迎再来</div>
        <div class="center small">{{ order.store_name }}</div>
      </div>

      <p v-else-if="!loading" class="empty">订单不存在</p>
    </div>
  </div>
</template>

<style scoped>
.receipt-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24px 0 40px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.tip {
  font-size: 12px;
  color: #8a8a8a;
}

.paper-wrap {
  display: flex;
  justify-content: center;
}

/* 80mm 是常见的热敏小票纸宽；屏幕上按 1:1 显示，
   打印时用同样的宽度，所见即所得 */
.paper {
  width: 80mm;
  background: #fff;
  padding: 10mm 5mm;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  font-size: 12px;
  line-height: 1.6;
  color: #1f1f1f;
}

.center {
  text-align: center;
}

.store-name {
  font-size: 15px;
  font-weight: 600;
}

.small {
  font-size: 11px;
  color: #333;
}

.divider {
  border-top: 1px dashed #999;
  margin: 6px 0;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.row.total {
  font-size: 14px;
  font-weight: 600;
}

.item {
  margin-bottom: 4px;
}

.item-name {
  font-weight: 600;
}

.item-options {
  font-size: 11px;
  color: #555;
}

.item-amount {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #333;
}

.thanks {
  margin-top: 4px;
}

.unpaid {
  font-weight: 600;
}

.empty {
  font-size: 14px;
  color: #8a8a8a;
}

/* 打印时只留纸面：工具条、阴影、灰底、页边距都不要，
   否则打出来会多一圈灰边、还浪费纸 */
@media print {
  .receipt-page {
    padding: 0;
    background: #fff;
  }

  .no-print {
    display: none;
  }

  .paper {
    width: auto;
    box-shadow: none;
    padding: 0;
  }

  @page {
    margin: 4mm;
  }
}
</style>
