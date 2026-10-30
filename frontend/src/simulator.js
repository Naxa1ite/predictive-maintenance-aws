// Scenario-based sensor simulator. Readings are SYNTHETIC; the ML model (not this
// code) decides the risk level. Scenario definitions are shared with the Python CLI.
import scenarios from '../../simulator/scenarios.json'

export { scenarios }

function gauss(rng) {
  const u = 1 - rng(), v = rng()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

export function nextReading(spec, tick, rng = Math.random) {
  const g = (p) => p[0] + p[1] * gauss(rng)
  const air = g(spec.air_temperature)
  return {
    machine_id: spec.machine_id,
    machine_type: spec.machine_type,
    air_temperature: +air.toFixed(1),
    process_temperature: +(air + g(spec.temp_delta)).toFixed(1),
    rotational_speed: Math.max(0, Math.round(g(spec.rotational_speed))),
    torque: +Math.max(0, g(spec.torque)).toFixed(1),
    tool_wear: Math.round(Math.min(500, spec.tool_wear_start + tick * spec.tool_wear_per_tick)),
    source: 'simulated',
  }
}

export function scenarioMachines(keys) {
  return keys.flatMap((k) => scenarios[k].machines)
}
