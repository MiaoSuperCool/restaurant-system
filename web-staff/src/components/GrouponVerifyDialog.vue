<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { verifyGroupon } from '@/api/groupon'
import type { Order } from '@/api/types'
import { GROUPON_PLATFORM_OPTIONS } from '@/constants/groupon'
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
const code = ref('')
const amount = ref<number | null>(null)
const platform = ref('meituan')

/** 团购券只能抵扣，不找零——超过未付部分后端会拒，这里先给出提示 */
const unpaid = computed(() => {
  const current = props.order
  if (!current) return 0
  return Math.round((current.payable_amount - current.paid_amount) * 100) / 100
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    code.value = ''
    // 默认按未付部分填：多数情况是一张券正好抵掉
    amount.value = unpaid.value > 0 ? unpaid.value : null
    platform.value = 'meituan'
  }
)

async function handleSubmit() {
  if (!props.order) return
  if (!code.value.trim()) {
    ElMessage.warning('请扫码或输入券码')
    return
  }
  if (amount.value === null || amount.value <= 0) {
    ElMessage.warning('请填写券面额')
    return
  }

  saving.value = true
  try {
    const result = await verifyGroupon(props.order.id, {
      code: code.value.trim(),
      amount: amount.value,
      platform: platform.value,
    })
    const rest = result.order.payable_amount - result.order.paid_amount
    ElMessage.success(
      rest > 0
        ? `已核销 ¥${result.voucher.amount.toFixed(2)}，还剩 ¥${rest.toFixed(2)}`
        : '已核销，这单付清了'
    )
    emit('success')
    emit('update:modelValue', false)
  } catch {
    // 拦截器已提示（重复核销、超过未付部分等）
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="核销团购券"
    width="460px"
    @close="emit('update:modelValue', false)"
  >
    <template v-if="order">
      <p class="summary">
        <span class="order-no">{{ order.order_no }}</span>
        <span>未付 <strong>{{ formatPrice(unpaid) }}</strong></span>
      </p>

      <el-form label-width="88px">
        <el-form-item label="券码">
          <el-input
            v-model="code"
            placeholder="扫码或手工输入券码"
            autofocus
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="platform" class="full-width">
            <el-option
              v-for="item in GROUPON_PLATFORM_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="券面额">
          <el-input-number
            v-model="amount"
            :min="0.01"
            :max="unpaid"
            :precision="2"
            :step="1"
            class="full-width"
          />
          <div class="field-hint">只能抵扣，不找零；抵不完的部分改用其他方式收款</div>
        </el-form-item>
      </el-form>

      <p class="hint">
        核销会做两件事：记一条核销记录（月底和平台对账用）+ 记一笔团购券收款。
        <strong>同一张券码只能核销一次。</strong>
      </p>
    </template>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">核销</el-button>
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
}

.order-no {
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
