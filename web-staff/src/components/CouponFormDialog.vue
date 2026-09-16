<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createCouponTemplate, updateCouponTemplate } from '@/api/coupons'
import { getStoreOptions } from '@/api/stores'
import type { CouponTemplate, StoreOption } from '@/api/types'
import { COUPON_TYPE_OPTIONS } from '@/constants/coupon'
import { toLocalInput, toUtcIso } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  template: CouponTemplate | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)
const stores = ref<StoreOption[]>([])

// 字段名与 CouponTemplateCreateSchema 保持一致
const form = reactive({
  name: '',
  type: 'full_cut',
  value: 10,
  min_amount: 0,
  valid_from: '',
  valid_to: '',
  total_quantity: null as number | null,
  status: 'active',
  store_ids: [] as number[],
})

const isDiscount = computed(() => form.type === 'discount')

/** 发出去过的模板不让改类型——见模板里那段说明 */
const typeLocked = computed(() => !!props.template && props.template.issued_count > 0)

/** 折扣率的面额步长小一些——八折八五折九折是 0.8 / 0.85 / 0.9，按 1 跳没法填 */
const valueStep = computed(() => (isDiscount.value ? 0.05 : 1))

const valueHint = computed(() =>
  isDiscount.value
    ? '填折扣率：0.85 就是八五折。必须在 0 和 1 之间（1 = 没打折、0 = 白送）'
    : '填减多少钱，比如满 100 减 20 就填 20'
)

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return

    form.name = props.template?.name ?? ''
    form.type = props.template?.type ?? 'full_cut'
    form.value = props.template?.value ?? 10
    form.min_amount = props.template?.min_amount ?? 0
    // 后端给的是 UTC，选择器要本地时间——直接用原值回填会差 8 小时
    form.valid_from = toLocalInput(props.template?.valid_from)
    form.valid_to = toLocalInput(props.template?.valid_to)
    form.total_quantity = props.template?.total_quantity ?? null
    form.status = props.template?.status ?? 'active'
    form.store_ids = props.template ? [...props.template.store_ids] : []

    if (!stores.value.length) {
      try {
        stores.value = (await getStoreOptions()).stores
      } catch {
        // 拦截器已提示；下拉空着，等于「全公司通用」
      }
    }
  }
)

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('券名必填——顾客在小程序里看到的就是它')
    return
  }
  if (isDiscount.value && !(form.value > 0 && form.value < 1)) {
    // 后端也会拦（BusinessError），这里先拦一道是为了不用等一次往返
    ElMessage.warning('折扣率要在 0 和 1 之间，八五折填 0.85')
    return
  }
  if (form.valid_from && form.valid_to && form.valid_from >= form.valid_to) {
    ElMessage.warning('失效时间要在生效时间之后')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      type: form.type,
      value: form.value,
      min_amount: form.min_amount || 0,
      valid_from: toUtcIso(form.valid_from),
      valid_to: toUtcIso(form.valid_to),
      total_quantity: form.total_quantity,
      status: form.status,
      store_ids: form.store_ids,
    }
    if (props.template) {
      await updateCouponTemplate(props.template.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createCouponTemplate(payload)
      ElMessage.success('创建成功')
    }
    emit('success')
  } catch {
    // 拦截器已提示（折扣率越界、券名重复等）
  } finally {
    saving.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="template ? '编辑券模板' : '新建券模板'"
    width="540px"
    @close="handleClose"
  >
    <el-form label-width="88px">
      <el-form-item label="券名">
        <el-input v-model="form.name" placeholder="如 满 100 减 20，顾客在券包里看到的就是它" />
      </el-form-item>

      <el-form-item label="类型">
        <el-radio-group v-model="form.type" :disabled="typeLocked">
          <el-radio-button
            v-for="item in COUPON_TYPE_OPTIONS"
            :key="item.value"
            :value="item.value"
          >
            {{ item.label }}
          </el-radio-button>
        </el-radio-group>
        <div v-if="typeLocked" class="field-hint">
          已经发出去 {{ template?.issued_count }} 张，类型锁住了——改类型等于把顾客
          手里那张券换一套算法（满减变折扣）。后端的接口没拦，这是前端自己加的锁
        </div>
      </el-form-item>

      <el-form-item :label="isDiscount ? '折扣率' : '减多少'">
        <el-input-number
          v-model="form.value"
          :min="0"
          :max="isDiscount ? 0.99 : 100000"
          :step="valueStep"
          :precision="2"
        />
        <div class="field-hint">{{ valueHint }}</div>
      </el-form-item>

      <el-form-item label="门槛">
        <el-input-number v-model="form.min_amount" :min="0" :precision="2" :step="10" />
        <div class="field-hint">
          满多少才能用，0 = 无门槛。按<strong>商品原价</strong>算，不看积分抵扣后剩多少
        </div>
      </el-form-item>

      <el-form-item label="有效期">
        <div class="date-range">
          <el-date-picker
            v-model="form.valid_from"
            type="datetime"
            placeholder="立即生效"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
          <span class="date-sep">至</span>
          <el-date-picker
            v-model="form.valid_to"
            type="datetime"
            placeholder="长期有效"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </div>
        <div class="field-hint">
          都不填 = 长期有效。到点自动失效——<strong>过期是算出来的，不写库</strong>
        </div>
      </el-form-item>

      <el-form-item label="发放总量">
        <el-input-number
          v-model="form.total_quantity"
          :min="1"
          :step="100"
          :value-on-clear="null"
          placeholder="不限量"
        />
        <div class="field-hint">
          留空 = 不限量。只约束「发」，不约束「用」——发出去的券不会因为发超了就用不了
        </div>
      </el-form-item>

      <el-form-item label="适用门店">
        <el-select
          v-model="form.store_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="不选 = 全公司通用"
          class="full-width"
        >
          <el-option
            v-for="store in stores"
            :key="store.id"
            :label="store.name"
            :value="store.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="状态">
        <el-radio-group v-model="form.status">
          <el-radio value="active">启用</el-radio>
          <el-radio value="disabled">停用</el-radio>
        </el-radio-group>
        <div class="field-hint">
          停用只停「发」——<strong>已经发到顾客手里的券照常能用</strong>，不能赖账
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full-width {
  width: 100%;
}

.field-hint {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
  margin-top: 4px;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.date-range :deep(.el-date-editor) {
  flex: 1;
  min-width: 0;
}

.date-sep {
  color: #8c8c8c;
  flex-shrink: 0;
}
</style>