<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createUser, updateUser } from '@/api/users'
import type { User } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  user: User | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success'): void
}>()

const saving = ref(false)

// 注意：字段名按后端 schema 用 real_name
const form = reactive({
  username: '',
  real_name: '',
  email: '',
  mobile: '',
  password: '',
  is_active: true,
  is_admin: false,
})

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      form.username = props.user?.username ?? ''
      form.real_name = props.user?.real_name ?? ''
      form.email = props.user?.email ?? ''
      form.mobile = props.user?.mobile ?? ''
      form.password = ''
      form.is_active = props.user?.is_active ?? true
      form.is_admin = props.user?.is_admin ?? false
    }
  }
)

async function handleSubmit() {
  if (
    !form.username.trim() ||
    !form.real_name.trim() ||
    !form.email.trim() ||
    !form.mobile.trim()
  ) {
    ElMessage.warning('请填写完整信息')
    return
  }
  if (!props.user && !form.password) {
    ElMessage.warning('请设置初始密码')
    return
  }

  saving.value = true
  try {
    if (props.user) {
      // 编辑：密码留空表示不修改，不传给后端
      const payload: Record<string, unknown> = {
        username: form.username,
        real_name: form.real_name,
        email: form.email,
        mobile: form.mobile,
        is_active: form.is_active,
        is_admin: form.is_admin,
      }
      if (form.password) payload.password = form.password
      await updateUser(props.user.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createUser({
        username: form.username,
        real_name: form.real_name,
        email: form.email,
        mobile: form.mobile,
        password: form.password,
        is_active: form.is_active,
        is_admin: form.is_admin,
      })
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
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="user ? '编辑用户' : '新增用户'"
    width="480px"
    @close="handleClose"
  >
    <el-form label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="用户名" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.real_name" placeholder="真实姓名" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="邮箱" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.mobile" placeholder="手机号" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          :placeholder="user ? '留空表示不修改' : '设置初始密码'"
        />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item label="管理员">
        <el-switch v-model="form.is_admin" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>