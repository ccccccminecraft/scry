<template>
  <nav class="nav">
    <router-link to="/" class="nav__title">Scry</router-link>
    <router-link to="/stats" class="nav__item">統計</router-link>
    <router-link to="/matches" class="nav__item">対戦履歴</router-link>
    <hr class="nav__divider" />
    <router-link to="/deck-builder" class="nav__item">デッキ管理</router-link>
    <router-link to="/decks" class="nav__item">デッキ定義</router-link>
    <hr class="nav__divider" />
    <router-link to="/analysis" class="nav__item">AI 分析</router-link>
    <router-link to="/export" class="nav__item">AI用エクスポート</router-link>
    <hr class="nav__divider" />
    <router-link to="/import" class="nav__item">インポート</router-link>
    <hr class="nav__divider" />
    <router-link to="/presets" class="nav__item">プリセット管理</router-link>
    <router-link to="/settings" class="nav__item">設定</router-link>
  </nav>
</template>

<style scoped>
.nav {
  width: 160px;
  min-height: 100vh;
  background: #2c2416;
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  flex-shrink: 0;
}

.nav__title {
  color: #f0ece0;
  font-size: 1.1rem;
  font-weight: bold;
  padding: 0 16px 16px;
  color: #f0ece0;
  text-decoration: none;
  cursor: pointer;
}

.nav__item {
  display: block;
  padding: 8px 16px;
  color: #c8b89a;
  text-decoration: none;
  font-size: 14px;
}

.nav__item:hover {
  background: #3a3020;
  color: #f0ece0;
}

.nav__item.router-link-active {
  background: #4a6fa5;
  color: #fff;
}

.nav__divider {
  border: none;
  border-top: 1px solid #4a3c2a;
  margin: 8px 16px;
}
</style>
