<script setup lang="ts">
</script>

<template>
  <div class="not-found">
    <h1 class="not-found-title">404</h1>
    <p class="not-found-text">
      Falta el parámetro de acceso en la URL. No puedes entrar sin él.
    </p>
  </div>
</template>

<style scoped>
.not-found {
  max-width: 28rem;
  margin: 2rem auto;
  padding: 1.5rem;
  text-align: center;
}
.not-found-title {
  font-size: 3rem;
  margin: 0 0 0.5rem;
  color: var(--p-text-muted-color);
}
.not-found-text {
  margin: 0.5rem 0;
  color: var(--p-text-color);
}
.not-found-text code {
  padding: 0.15rem 0.4rem;
  background: var(--p-content-hover-background);
  border-radius: 4px;
  font-size: 0.9em;
}
</style>
