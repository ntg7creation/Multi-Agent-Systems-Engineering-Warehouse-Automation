import { useSimulationStore } from '../state/useSimulationStore'

export function InspectorPanel() {
  const state = useSimulationStore((store) => store.state)
  const agents = state?.agents ?? []
  const tasks = state?.tasks ?? []

  return (
    <aside className="inspector-panel">
      <section>
        <h2>Agents</h2>
        {agents.map((agent) => (
          <div key={agent.agent_id} className="inspector-row">
            <strong>{agent.agent_id}</strong>
            <span>{agent.state}</span>
          </div>
        ))}
      </section>
      <section>
        <h2>Tasks</h2>
        {tasks.map((task) => (
          <div key={task.task_id} className="inspector-row">
            <strong>{task.task_id}</strong>
            <span>{task.status}</span>
          </div>
        ))}
      </section>
    </aside>
  )
}
