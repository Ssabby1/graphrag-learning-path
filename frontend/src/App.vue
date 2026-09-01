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
  --page: #f4f7f6; --surface: #fcfdfc; --surface-alt: #edf2f1;
  --ink: #16252d; --ink-soft: #344850; --muted: #607078; --quiet: #78878c;
  --line: #d8e0de; --line-strong: #b8c5c2;
  --accent: #159582; --accent-strong: #087c6b; --accent-soft: #dff3ef;
  --font-display: "Avenir Next", "Trebuchet MS", "PingFang SC", sans-serif;
  --font-body: "Avenir", "Gill Sans", "PingFang SC", sans-serif;
  --font-data: "SFMono-Regular", "Cascadia Code", "Liberation Mono", monospace;
  font-family: var(--font-body); background: var(--page); color: var(--ink);
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
  background: var(--page); overflow-x: hidden; -webkit-font-smoothing: antialiased;
}

button,
input,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
}

button, a, input, textarea { touch-action: manipulation; -webkit-tap-highlight-color: rgba(21, 149, 130, 0.16); }
:focus-visible { outline: 3px solid rgba(21, 149, 130, 0.35); outline-offset: 3px; }
::selection { background: var(--accent-soft); color: var(--ink); }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
