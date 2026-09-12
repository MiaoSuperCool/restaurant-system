<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { StoreMenuRow } from '@/api/types'
import { formatPrice } from '@/utils/format'

/** 选完规格后交给购物车的东西 */
export interface PickedDish {
  dish_id: number
  name: string
  unit_price: number
  quantity: number
  option_ids: number[]
  options_text: string
}

const props = defineProps<{
  modelValue: boolean
  dish: StoreMenuRow | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', picked: PickedDish): void
}>()

/** 组 id → 选中的选项 id 列表（单选组最多一个，多选组任意） */
const selected = ref<Record<number, number[]>>({})
const quantity = ref(1)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    quantity.value = 1
    // 必选组默认选第一个——收银员点得最快，不用每次都手动选「标准份」
    const initial: Record<number, number[]> = {}
    for (const group of props.dish?.option_groups ?? []) {
      initial[group.id] = group.is_required && group.options.length > 0
        ? [group.options[0].id]
        : []
    }
    selected.value = initial
  }
)

/** 按规格组的顺序铺平选中的选项，算加价合计 */
const chosenOptions = computed(() => {
  const result: { id: number; name: string; extra_price: number }[] = []
  for (const group of props.dish?.option_groups ?? []) {
    const ids = selected.value[group.id] ?? []
    for (const option of group.options) {
      if (ids.includes(option.id)) {
        result.push({ id: option.id, name: option.name, extra_price: option.extra_price })
      }
    }
  }
  return result
})

const unitPrice = computed(() => {
  const base = props.dish?.price ?? 0
  return chosenOptions.value.reduce((sum, option) => sum + option.extra_price, base)
})

const subtotal = computed(() => unitPrice.value * quantity.value)

/** 单选组用 radio，多选组用 checkbox——el-radio-group 的 v-model 是单值，这里转一下 */
function singleValue(groupId: number): number | undefined {
  return selected.value[groupId]?.[0]
}

function setSingle(groupId: number, value: number) {
  selected.value = { ...selected.value, [groupId]: [value] }
}

function handleConfirm() {
  const dish = props.dish
  if (!dish) return

  // 和后端同样的校验，错了在这里就说清楚，别等到提交才报 400
  for (const group of dish.option_groups) {
    const picked = selected.value[group.id] ?? []
    if (group.is_required && picked.length === 0) {
      ElMessage.warning(`请选择「${group.name}」`)
      return
    }
  }

  emit('confirm', {
    dish_id: dish.dish_id,
    name: dish.name,
    unit_price: unitPrice.value,
    quantity: quantity.value,
    option_ids: chosenOptions.value.map((option) => option.id),
    options_text: chosenOptions.value.map((option) => option.name).join(','),
  })
  emit('update:modelValue', false)
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="dish?.name"
    width="460px"
    @close="handleClose"
  >
    <template v-if="dish">
      <p v-if="dish.description" class="dish-desc">{{ dish.description }}</p>

      <div v-for="group in dish.option_groups" :key="group.id" class="group">
        <div class="group-title">
          {{ group.name }}
          <span v-if="group.is_required" class="required">必选</span>
          <span class="group-type">{{ group.selection_type_label }}</span>
        </div>

        <!-- 单选组 -->
        <el-radio-group
          v-if="group.selection_type === 'single'"
          :model-value="singleValue(group.id)"
          @update:model-value="(value: string | number | boolean | undefined) =>
            setSingle(group.id, value as number)"
        >
          <el-radio
            v-for="option in group.options"
            :key="option.id"
            :value="option.id"
            class="option"
          >
            {{ option.name }}
            <span v-if="option.extra_price > 0" class="extra">+{{ option.extra_price }}</span>
          </el-radio>
        </el-radio-group>

        <!-- 多选组 -->
        <el-checkbox-group v-else v-model="selected[group.id]">
          <el-checkbox
            v-for="option in group.options"
            :key="option.id"
            :value="option.id"
            class="option"
          >
            {{ option.name }}
            <span v-if="option.extra_price > 0" class="extra">+{{ option.extra_price }}</span>
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <div class="footer-row">
        <el-input-number v-model="quantity" :min="1" :max="99" />
        <div class="price">
          <span class="price-main">{{ formatPrice(subtotal) }}</span>
          <span class="price-hint">
            单价 {{ formatPrice(unitPrice) }}<template v-if="quantity > 1"> × {{ quantity }}</template>
          </span>
        </div>
      </div>
    </template>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleConfirm">加入点单</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dish-desc {
  font-size: 13px;
  color: #8a8a8a;
  margin-bottom: 16px;
}

.group {
  margin-bottom: 18px;
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 8px;
}

.required {
  font-size: 11px;
  font-weight: 400;
  color: #c45656;
  margin-left: 6px;
}

.group-type {
  font-size: 11px;
  font-weight: 400;
  color: #a0a0a0;
  margin-left: 6px;
}

.option {
  display: block;
  margin: 0 0 4px;
}

.extra {
  color: #c45656;
  font-size: 12px;
  margin-left: 2px;
}

.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #e5e5e5;
}

.price {
  text-align: right;
}

.price-main {
  font-size: 20px;
  font-weight: 600;
  color: #1f1f1f;
}

.price-hint {
  display: block;
  font-size: 12px;
  color: #8a8a8a;
}
</style>
