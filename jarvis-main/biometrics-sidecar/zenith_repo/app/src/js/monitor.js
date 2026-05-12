const monitorList = document.getElementById('tool-monitor-list')
const MAX_EVENTS = 50

export function addToolEvent(event) {
  if (!monitorList) return
  const el = document.createElement('div')
  el.className = 'tool-event'
  el.innerHTML = `
    <span class="tool-name">${escapeHtml(event.tool)}</span>
    <span class="tool-time">${new Date(event.timestamp).toLocaleTimeString()}</span>
  `
  monitorList.prepend(el)
  while (monitorList.children.length > MAX_EVENTS) {
    monitorList.removeChild(monitorList.lastChild)
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
