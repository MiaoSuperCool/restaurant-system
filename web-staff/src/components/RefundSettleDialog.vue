<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { settleRefund } from '@/api/refunds'
import type { Refund } from '@/api/types'
import { REFUND_METHOD_OPTIONS } from '@/constants/refund'
import { formatPrice } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  refund: Refund | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)
const method = ref('original')
const transactionNo = ref('')

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    method.value = props.refund?.type === 'offline' ? 'cash' : 'original'
    transactionNo.value = ''
  }
)

async function handleSubmit() {
  if (!props.refund) return
  saving.value = true
  try {
    await settleRefund(props.refund.id, {
      method: method.value,
      transaction_no: transactionNo.value.trim(),
    })
    ElMessage.success('已确认退款')
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
    title="确认退款"
    width="460px"
    @close="emit('update:modelValue', false)"
  >
    <template v-if="refund">
      <p class="amount">
        退款金额 <strong>{{ formatPrice(refund.amount) }}</strong>
      </p>
      <p class="hint">
        确认之后钱就真的退出去并记一条退款流水。<strong>审批通过不等于钱退了</strong>——
        线上要等微信退款接口返回，线下要等财务把现金给到顾客，所以这一步单独确认。
      </p>

      <el-form label-width="88px" class="form">
        <el-form-item label="退款方式">
          <el-select v-model="method" class="full-width">
            <el-option
              v-for="item in REFUND_METHOD_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="退款单号">
          <el-input v-model="transactionNo" placeholder="第三方退款单号；现金留空" />
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">确认已退款</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.amount {
  font-size: 14px;
  color: #1f1f1f;
  margin-bottom: 10px;
}

.amount strong {
  font-size: 20px;
}

.hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.7;
  margin-bottom: 16px;
}

.form {
  margin-top: 8px;
}

.full-width {
  width: 100%;
}
</style>
