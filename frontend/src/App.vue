<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1><el-icon :size="28" class="header-icon"><Oven /></el-icon> 砖窑作坊温度监控系统</h1>
        <div class="header-subtitle">阶梯窑全流程数字化管理</div>
      </div>
    </el-header>
    
    <el-container>
      <el-aside width="220px" class="app-aside">
        <el-menu
          :default-active="activeMenu"
          router
          class="side-menu"
          background-color="#545c64"
          text-color="#fff"
          active-text-color="#ffd04b"
        >
          <el-menu-item index="/">
            <el-icon><List /></el-icon>
            <span>窑次列表</span>
          </el-menu-item>
          <el-menu-item index="/orders">
            <el-icon><Warning /></el-icon>
            <span>工单待办</span>
          </el-menu-item>
          <el-menu-item index="/loading">
            <el-icon><Van /></el-icon>
            <span>装车操作</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  background-color: #f5f7fa;
}

.app-container {
  height: 100vh;
}

.app-header {
  background: linear-gradient(135deg, #c62828 0%, #e65100 100%);
  color: white;
  display: flex;
  align-items: center;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.header-content h1 {
  font-size: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.header-subtitle {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 4px;
}

.app-aside {
  background-color: #545c64;
  border-right: 1px solid #e4e7ed;
}

.side-menu {
  border-right: none;
  height: 100%;
}

.side-menu .el-menu-item {
  height: 56px;
  line-height: 56px;
  font-size: 15px;
}

.app-main {
  background-color: #f5f7fa;
  padding: 24px;
  overflow-y: auto;
}
</style>
