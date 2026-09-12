<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { applyRefund } from '@/api/refunds'
import type { Order } from '@/api/types'
import { REFUND_TYPE_OPTIONS } from '@/constants/refund'
import { formatPrice } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  order: Order | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)
const amount = ref<number | null>(null)
const reason = ref('')
const type = ref('online')

/** 还能退多少——超了后端会拒，这里先挡住免得白填 */
const refundable = computed(() => props.order?.refundable_amount ?? 0)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    // 默认全额退：多数情况是整单退，部分退款再改小
    amount.value = refundable.value > 0 ? refundable.value : null
    reason.value = ''
    type.value = 'online'
  }
)

async function handleSubmit() {
  if (!props.order) return
  if (amount.value === null || amount.value <= 0) {
    ElMessage.warning('请填写退款金额')
    return
  }
  if (!reason.value.trim()) {
    ElMessage.warning('请写退款原因——留痕靠它')
    return
  }

  saving.value = true
  try {
    await applyRefund(props.order.id, {
      amount: amount.value,
      reason: reason.value.trim(),
      type: type.value,
    })
    ElMessage.success('退款申请已提交，等待审批')
    emit('success')
    emit('update:modelValue', false)
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="申请退款"
    width="480px"
    @close="emit('update:modelValue', false)"
  >
    <template v-if="order">
      <p class="summary">
        <span class="summary-order">{{ order.order_no }}</span>
        <span>已收 {{ formatPrice(order.paid_amount) }}</span>
        <span>已退 {{ formatPrice(order.refunded_amount) }}</span>
        <span><strong>可退 {{ formatPrice(refundable) }}</strong></span>
      </p>

      <el-form label-width="88px">
        <el-form-item label="退款金额">
          <el-input-number
            v-model="amount"
            :min="0.01"
            :max="refundable"
            :precision="2"
            :step="1"
            class="full-width"
          />
        </el-form-item>
        <el-form-item label="退款类型">
          <el-select v-model="type" class="full-width">
            <el-option
              v-for="item in REFUND_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <div class="field-hint">
            线下补录用于「钱已经用现金退给顾客了，事后补录留痕」的情况
          </div>
        </el-form-item>
        <el-form-item label="退款原因">
          <el-input
            v-model="reason"
            type="textarea"
            :rows="2"
            placeholder="如：顾客投诉菜品有问题 / 点错单当场退货"
          />
          <div class="field-hint">必填。审批的人要知道为什么退，事后追查也靠它</div>
        </el-form-item>
      </el-form>

      <p class="hint">
        提交后只是发起申请，<strong>钱一分没动</strong>——要等审批通过、再确认打款。
      </p>
    </template>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">提交申请</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.summary {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
  line-height: 1.8;
}

.summary-order {
  font-weight: 600;
  color: #1f1f1f;
}

.summary strong {
  color: #1f1f1f;
}

.full-width {
  width: 100%;
}

.field-hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.6;
  margin-top: 4px;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
}
</style>
