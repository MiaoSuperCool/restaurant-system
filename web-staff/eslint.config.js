// ESLint 9 扁平配置：JS/TS 基础规则 + Vue SFC + Prettier 兼容
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettier from 'eslint-config-prettier'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // 全局忽略
  { ignores: ['dist/**', 'node_modules/**'] },
  // 基础推荐规则
  js.configs.recommended,
  // TypeScript 推荐规则
  ...tseslint.configs.recommended,
  // Vue SFC 推荐规则（含 template 里的常见错误检查）
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },
  {
    // 前端代码跑在浏览器里，window / document / localStorage 这些是全局的。
    // typescript-eslint 只对 .ts 文件关掉了 no-undef，.vue 不在此列，
    // 不显式声明的话 `window.open(...)` 会被报成「未定义」。
    files: ['src/**/*.{ts,vue}', 'tests/**/*.ts'],
    languageOptions: {
      globals: { ...globals.browser },
    },
  },
  // 关闭与 Prettier 冲突的格式规则（放在最后覆盖前面的规则）
  prettier,
  {
    rules: {
      // 允许单词组件名（Sidebar 等布局组件很常见，且与 HTML 原生元素无冲突）
      'vue/multi-word-component-names': 'off',
    },
  },
)