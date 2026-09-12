<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createCategory, updateCategory } from '@/api/categories'
import { getStoreOptions } from '@/api/stores'
import type { Category, StoreOption } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  category: Category | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)
const storeOptions = ref<StoreOption[]>([])

// 字段名与 CategoryCreateSchema 保持一致
const form = reactive({
  name: '',
  icon: '',
  is_visible: true,
  sort_order: null as number | null,
  store_ids: [] as number[],
})

async function loadStoreOptions() {
  try {
    const data = await getStoreOptions()
    storeOptions.value = data.stores
  } catch {
    // 拦截器已提示；拉不到门店就只按「全公司通用」处理
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    form.name = props.category?.name ?? ''
    form.icon = props.category?.icon ?? ''
    form.is_visible = props.category?.is_visible ?? true
    form.sort_order = props.category?.sort_order ?? null
    form.store_ids = props.category?.store_ids ?? []
    loadStoreOptions()
  }
)

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      icon: form.icon.trim(),
      is_visible: form.is_visible,
      sort_order: form.sort_order,
      store_ids: form.store_ids,
    }
    if (props.category) {
      await updateCategory(props.category.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createCategory(payload)
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

onMounted(loadStoreOptions)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="category ? '编辑分类' : '新增分类'"
    width="520px"
    @close="handleClose"
  >
    <el-form label-width="88px">
      <el-form-item label="分类名称">
        <el-input v-model="form.name" placeholder="如 面食、饮品、套餐" />
      </el-form-item>
      <el-form-item label="图标">
        <el-input v-model="form.icon" placeholder="emoji（🍜）或图片地址" />
      </el-form-item>
      <el-form-item label="显示">
        <el-switch v-model="form.is_visible" />
        <div class="field-hint">关掉之后该分类不出现在菜单里</div>
      </el-form-item>
      <el-form-item label="适用门店">
        <el-select v-model="form.store_ids" multiple clearable placeholder="不选 = 全公司通用" class="full-width">
          <el-option
            v-for="store in storeOptions"
            :key="store.id"
            :label="`${store.name}（${store.code}）`"
            :value="store.id"
          />
        </el-select>
        <div class="field-hint">不选表示所有门店都有这个分类</div>
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" placeholder="留空排到最后" />
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
</style>