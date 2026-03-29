const gridEl = document.getElementById('grid');
const turnEl = document.getElementById('turn');
const rawStateEl = document.getElementById('rawState');

function key(x, y) {
  return `${x},${y}`;
}

function render(state) {
  turnEl.textContent = state.turn;
  rawStateEl.textContent = JSON.stringify(state, null, 2);

  const { width, height, cells } = state.grid;
  gridEl.style.gridTemplateColumns = `repeat(${width}, 56px)`;
  gridEl.innerHTML = '';

  const agentsByPos = new Map();
  for (const agent of state.agents) {
    agentsByPos.set(key(agent.x, agent.y), agent);
  }

  const itemsByPos = new Map();
  for (const item of state.items) {
    const [x, y] = item.position;
    itemsByPos.set(key(x, y), item);
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const cellType = cells[y][x];
      const cell = document.createElement('div');
      cell.className = `cell ${cellType}`;
      cell.dataset.x = x;
      cell.dataset.y = y;
      cell.textContent = `${x},${y}`;

      const agent = agentsByPos.get(key(x, y));
      if (agent) {
        const agentTag = document.createElement('div');
        agentTag.className = 'agent';
        agentTag.textContent = agent.agent_id;
        cell.appendChild(agentTag);
      }

      const item = itemsByPos.get(key(x, y));
      if (item && item.status !== 'delivered') {
        const itemTag = document.createElement('div');
        itemTag.className = 'item';
        itemTag.textContent = item.item_id;
        cell.appendChild(itemTag);
      }

      gridEl.appendChild(cell);
    }
  }
}

async function loadInitialState() {
  const response = await fetch('/api/state');
  const state = await response.json();
  render(state);
}

const socket = io();
socket.on('state', (state) => {
  render(state);
});

loadInitialState().catch((error) => {
  rawStateEl.textContent = `Failed to load initial state: ${error}`;
});
