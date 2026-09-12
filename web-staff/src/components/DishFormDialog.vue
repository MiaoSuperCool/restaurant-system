<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getCategoryOptions } from '@/api/categories'
import { createDish, getDish, updateDish } from '@/api/dishes'
import type { DishOptionGroupPayload } from '@/api/dishes'
import type { CategoryOption, Dish } from '@/api/types'
import { DISH_STATUS_OPTIONS, SELECTION_TYPE_OPTIONS } from '@/constants/menu'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  modelValue: boolean
  dish: Dish | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()

// 改价和上下架各有专门的权限码，后端会拦；
// 前端禁用输入框只是别让人白填一遍再吃 403
const canEditPrice = computed(() => authStore.hasPermission('dish:price:edit'))
const canToggleOnline = computed(() => authStore.hasPermission('dish:online'))

const saving = ref(false)
const loading = ref(false)
const categoryOptions = ref<CategoryOption[]>([])

// 字段名与 DishCreateSchema 保持一致
const form = reactive({
  category_id: null as number | null,
  name: '',
  image: '',
  description: '',
  base_price: 0,
  status: 'active',
  option_groups: [] as DishOptionGroupPayload[],
})

async function loadCategoryOptions() {
  try {
    const data = await getCategoryOptions()
    categoryOptions.value = data.categories
  } catch {
    // 拦截器已提示
  }
}

/** 编辑时拉详情：列表接口不带规格结构，回填规格得单独取 */
async function loadDishDetail(dishId: number) {
  loading.value = true
  try {
    const dish = await getDish(dishId)
    form.category_id = dish.category_id
    form.name = dish.name
    form.image = dish.image
    form.description = dish.description
    form.base_price = dish.base_price
    form.status = dish.status
    // 带上 id 原样回填——后端靠 id 认出「还是原来那个选项」，
    // 不然会当成新选项，历史订单就指空了
    form.option_groups = (dish.option_groups ?? []).map((group) => ({
      id: group.id,
      name: group.name,
      selection_type: group.selection_type,
      is_required: group.is_required,
      options: group.options.map((option) => ({
        id: option.id,
        name: option.name,
        extra_price: option.extra_price,
      })),
    }))
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.category_id = null
  form.name = ''
  form.image = ''
  form.description = ''
  form.base_price = 0
  form.status = 'active'
  form.option_groups = []
}

function addGroup() {
  form.option_groups.push({
    name: '',
    selection_type: 'single',
    is_required: true,
    options: [{ name: '', extra_price: 0 }],
  })
}

function removeGroup(index: number) {
  form.option_groups.splice(index, 1)
}

function addOption(group: DishOptionGroupPayload) {
  group.options.push({ name: '', extra_price: 0 })
}

function removeOption(group: DishOptionGroupPayload, index: number) {
  group.options.splice(index, 1)
}

function validate(): string | null {
  if (!form.category_id) return '请选择分类'
  if (!form.name.trim()) return '请填写菜品名称'
  for (const group of form.option_groups) {
    if (!group.name.trim()) return '规格组名称不能为空'
    if (group.options.length === 0) return `规格组「${group.name}」至少要有一个选项`
    if (group.options.some((option) => !option.name.trim())) {
      return `规格组「${group.name}」里有选项没填名称`
    }
  }
  return null
}

async function handleSubmit() {
  const error = validate()
  if (error) {
    ElMessage.warning(error)
    return
  }

  saving.value = true
  try {
    // 不传 sort_order：规格组/选项的顺序由数组顺序表达，后端按出现次序落库
    const payload = {
      category_id: form.category_id!,
      name: form.name.trim(),
      image: form.image.trim(),
      description: form.description.trim(),
      base_price: form.base_price,
      status: form.status,
      option_groups: form.option_groups.map((group) => ({
        id: group.id,
        name: group.name.trim(),
        selection_type: group.selection_type,
        is_required: group.is_required,
        options: group.options.map((option) => ({
          id: option.id,
          name: option.name.trim(),
          extra_price: option.extra_price,
        })),
      })),
    }
    if (props.dish) {
      await updateDish(props.dish.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createDish(payload)
      ElMessage.success('创建成功')
    }
    emit('success')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    resetForm()
    loadCategoryOptions()
    if (props.dish) loadDishDetail(props.dish.id)
  }
)

onMounted(loadCategoryOptions)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="dish ? '编辑菜品' : '新增菜品'"
    width="720px"
    @close="handleClose"
  >
    <el-form v-loading="loading" label-width="88px">
      <el-form-item label="分类">
        <el-select v-model="form.category_id" placeholder="选择分类" class="full-width">
          <el-option
            v-for="item in categoryOptions"
            :key="item.id"
            :label="`${item.icon} ${item.name}`.trim()"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="菜品名称">
        <el-input v-model="form.name" placeholder="如 牛肉面" />
      </el-form-item>
      <el-form-item label="基础价">
        <el-input-number
          v-model="form.base_price"
          :min="0"
          :precision="2"
          :step="1"
          :disabled="!canEditPrice"
        />
        <div v-if="!canEditPrice" class="field-hint">没有改价权限，价格不可修改</div>
        <div v-else class="field-hint">门店可以在「门店菜品」里覆盖这个价格</div>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="form.status" :disabled="!canToggleOnline" class="full-width">
          <el-option
            v-for="item in DISH_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <div v-if="!canToggleOnline" class="field-hint">没有上下架权限，状态不可修改</div>
      </el-form-item>
      <el-form-item label="图片">
        <el-input v-model="form.image" placeholder="图片地址（一期不做上传）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>

      <el-divider content-position="left">规格与选项</el-divider>

      <div v-for="(group, groupIndex) in form.option_groups" :key="groupIndex" class="group-card">
        <div class="group-head">
          <el-input v-model="group.name" placeholder="规格组名，如 份量 / 辣度 / 加料" class="group-name" />
          <el-select v-model="group.selection_type" class="group-type">
            <el-option
              v-for="item in SELECTION_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-checkbox v-model="group.is_required">必选</el-checkbox>
          <el-button link type="danger" @click="removeGroup(groupIndex)">删除组</el-button>
        </div>

        <div class="option-rows">
          <div
            v-for="(option, optionIndex) in group.options"
            :key="optionIndex"
            class="option-row"
          >
            <el-input v-model="option.name" placeholder="选项名，如 大份 / 加蛋" class="option-name" />
            <el-input-number
              v-model="option.extra_price"
              :min="0"
              :precision="2"
              :step="1"
              :controls="false"
              class="option-price"
            />
            <span class="option-unit">元</span>
            <el-button link type="danger" @click="removeOption(group, optionIndex)">×</el-button>
          </div>
          <el-button link type="primary" @click="addOption(group)">+ 添加选项</el-button>
        </div>
      </div>

      <el-button class="add-group-btn" @click="addGroup">+ 添加规格组</el-button>
      <div class="field-hint">
        没必要的规格就别建：顾客每次点单都要多做一次选择。
        加价填 0 表示这个选项不加钱（微辣和特辣同价）。
      </div>
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
  line-height: 1.6;
  margin-top: 4px;
}

.group-card {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafafa;
}

.group-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.group-name {
  width: 220px;
}

.group-type {
  width: 100px;
}

.option-rows {
  padding-left: 16px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.option-name {
  width: 200px;
}

.option-price {
  width: 120px;
}

.option-unit {
  font-size: 13px;
  color: #666;
}

.add-group-btn {
  width: 100%;
}
</style>