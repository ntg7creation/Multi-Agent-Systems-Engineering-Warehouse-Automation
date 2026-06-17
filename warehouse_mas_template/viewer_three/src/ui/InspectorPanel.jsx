import { useSimulationStore } from '../state/useSimulationStore'

function formatPosition(position) {
  return position ? `(${position[0]}, ${position[1]})` : '-'
}

function Detail({ label, value }) {
  return (
    <span>
      <strong>{label}</strong>
      {value ?? '-'}
    </span>
  )
}

export function InspectorPanel() {
  const state = useSimulationStore((store) => store.state)
  const selectedAgentId = useSimulationStore((store) => store.selectedAgentId)
  const selectAgent = useSimulationStore((store) => store.selectAgent)
  const agents = state?.agents ?? []
  const tasks = state?.tasks ?? []
  const selectedAgent = agents.find((agent) => agent.agent_id === selectedAgentId) ?? agents[0]
  const selectedMetrics = selectedAgent ? state?.metrics?.agents?.[selectedAgent.agent_id] : null

  return (
    <aside className="inspector-panel">
      <section>
        <h2>Selected Agent</h2>
        {selectedAgent ? (
          <div className="details-grid">
            <Detail label="ID" value={selectedAgent.agent_id} />
            <Detail label="Position" value={formatPosition(selectedAgent.position)} />
            <Detail label="Mode" value={selectedAgent.mode ?? selectedAgent.state} />
            <Detail label="Task" value={selectedAgent.current_task_id} />
            <Detail label="Carrying" value={selectedAgent.carrying_item_id} />
            <Detail label="Target" value={formatPosition(selectedAgent.current_target)} />
            <Detail label="Intended" value={selectedAgent.intended_action?.type} />
            <Detail
              label="Previous"
              value={
                selectedAgent.previous_action_result?.success === false
                  ? selectedAgent.previous_action_result.failure_reason
                  : selectedAgent.previous_action_result?.action?.type
              }
            />
            <Detail label="Path cells" value={selectedAgent.planned_path?.length ?? 0} />
            <Detail label="Waits" value={selectedAgent.waiting_counter ?? 0} />
            <Detail label="Failed moves" value={selectedAgent.failed_movement_counter ?? 0} />
            <Detail label="Efficiency" value={selectedMetrics?.efficiency ?? 0} />
            <Detail label="Completed" value={selectedMetrics?.completed_tasks ?? 0} />
            <Detail label="Replans" value={selectedMetrics?.route_replans ?? 0} />
          </div>
        ) : (
          <p className="empty">No agent selected.</p>
        )}
      </section>

      <section>
        <h2>Agents</h2>
        {agents.map((agent) => (
          <button
            key={agent.agent_id}
            type="button"
            className={`inspector-row ${agent.agent_id === selectedAgent?.agent_id ? 'selected' : ''}`}
            onClick={() => selectAgent(agent.agent_id)}
          >
            <strong>{agent.agent_id}</strong>
            <span>{agent.mode ?? agent.state}</span>
            <span>{formatPosition(agent.position)}</span>
          </button>
        ))}
      </section>

      <section>
        <h2>Tasks</h2>
        {tasks.map((task) => (
          <div key={task.task_id} className="inspector-row task-row">
            <strong>{task.task_id}</strong>
            <span>{task.status}</span>
            <span>{task.assigned_agent_id ?? 'unassigned'}</span>
          </div>
        ))}
      </section>
    </aside>
  )
}
