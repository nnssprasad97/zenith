const orb = document.getElementById('zenith-orb')
const orbLabel = document.getElementById('orb-label')

const states = ['idle', 'listening', 'thinking', 'speaking']

export function setOrbState(state) {
  if (!orb) return
  states.forEach((s) => orb.classList.remove(s))
  orb.classList.add(state)
  if (orbLabel) orbLabel.textContent = state.toUpperCase()
}

export function initOrb() {
  setOrbState('idle')
}
