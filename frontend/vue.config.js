const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  // webSocketServer: false,  // !!!!! 关键
})
