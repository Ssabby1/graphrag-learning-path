<template>
  <div class="app-shell">
    <GraphView />
  </div>
</template>

<script setup>
import GraphView from "./views/GraphView.vue";
</script>

<style>
:root {
  color-scheme: light;
  font-family: "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: linear-gradient(180deg, #f7f8fa 0%, #f2f4f7 100%);
  color: #0f172a;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  min-height: 100%;
  margin: 0;
}

body {
  background: linear-gradient(180deg, #f7f8fa 0%, #f2f4f7 100%);
}

button,
input,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
}
</style>
