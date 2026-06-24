export const CELL_SIZE = 1.25
export const TURN_PORTION_OF_STEP = 0.35
export const DEFAULT_CARRY_BOX_OFFSET = {
  x: 0,
  y: 0.25,
  z: 0.25,
}
export const CARRY_BOX_ANCHOR_POSITION = {
  x: 0,
  y: CELL_SIZE * 0.78,
  z: 0,
}

export const MODEL_ASSETS = {
  character: ['/character.fbx', '/models/character.fbx'],
  normalWalking: '/models/Normal_Walking.fbx',
  carryWalking: '/models/Carry_walking.fbx',
  idle: '/models/Idle.fbx',
  carryIdle: '/models/Carrying_idle.fbx',
  pickup: ['/Picking Up.fbx', '/models/Picking Up.fbx'],
  turnLeft: '/models/Carrying_Turn_left.fbx',
}
