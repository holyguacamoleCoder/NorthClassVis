<template>
  <ul v-if="skills.length" class="agent-skill-tags">
    <li v-for="(name, i) in skills" :key="i" class="agent-skill-tag">{{ name }}</li>
  </ul>
</template>

<script>
export default {
  name: 'AgentSkillTags',
  props: {
    skills: { type: Array, default: () => [] },
  },
}
</script>

<style scoped lang="less">
.agent-skill-tags {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-skill-tag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 12px;
  background: #e8f0fc;
  color: #2c5282;
  border: 1px solid #c5d9f5;
  font-family: ui-monospace, monospace;
}
</style>
