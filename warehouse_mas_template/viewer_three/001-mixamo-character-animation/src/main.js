import './styles.css'

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'

let mixer = null

const clock = new THREE.Clock()
const loader = new FBXLoader()
const canvas = document.querySelector('#scene')

const scene = new THREE.Scene()
scene.background = new THREE.Color(0xf2f5f9)

const camera = new THREE.PerspectiveCamera(
  45,
  window.innerWidth / window.innerHeight,
  0.1,
  1000,
)
camera.position.set(2.5, 2.0, 4.0)

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
renderer.setSize(window.innerWidth, window.innerHeight)
renderer.shadowMap.enabled = true

const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true
controls.target.set(0, 1, 0)

const ambientLight = new THREE.AmbientLight(0xffffff, 0.65)
scene.add(ambientLight)

const directionalLight = new THREE.DirectionalLight(0xffffff, 1.25)
directionalLight.position.set(3, 5, 4)
directionalLight.castShadow = true
scene.add(directionalLight)

const grid = new THREE.GridHelper(8, 8, 0x6b7280, 0xd1d5db)
scene.add(grid)

loadCharacter()
animate()

function loadCharacter() {
  loader.load(
    '/models/character.fbx',
    (character) => {
      console.log('character loaded:', character)

      character.name = 'MixamoCharacter'
      character.scale.setScalar(0.01)
      character.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })

      scene.add(character)
      loadAnimation(character)
    },
    undefined,
    (error) => {
      console.error(
        'Error loading /models/character.fbx. Make sure public/models/character.fbx exists locally.',
        error,
      )
    },
  )
}

function loadAnimation(character) {
  loader.load(
    '/models/walking.fbx',
    (walkingFbx) => {
      console.log('animation loaded:', walkingFbx)

      if (!walkingFbx.animations || walkingFbx.animations.length === 0) {
        console.warn('No animations found in /models/walking.fbx.')
        return
      }

      const clip = walkingFbx.animations[0]
      console.log('animation clip name:', clip.name || '(unnamed clip)')

      warnIfTrackNamesLookIncompatible(character, clip)

      mixer = new THREE.AnimationMixer(character)
      const action = mixer.clipAction(clip)
      action.reset()
      action.play()

      console.warn(
        'If the character does not animate, the Mixamo skeleton or animation track names may not match the base character.',
      )
    },
    undefined,
    (error) => {
      console.error(
        'Error loading /models/walking.fbx. Make sure public/models/walking.fbx exists locally.',
        error,
      )
    },
  )
}

function warnIfTrackNamesLookIncompatible(character, clip) {
  const nodeNames = new Set()
  character.traverse((node) => {
    if (node.name) nodeNames.add(node.name)
  })

  const matchingTracks = clip.tracks.filter((track) => {
    const nodeName = track.name.split('.')[0]
    return nodeNames.has(nodeName)
  })

  if (matchingTracks.length === 0) {
    console.warn(
      'No animation track names matched character node names. The animation may not play on this character. Check Mixamo skeleton compatibility and track names.',
    )
  }
}

function animate() {
  requestAnimationFrame(animate)

  const delta = clock.getDelta()
  if (mixer) mixer.update(delta)

  controls.update()
  renderer.render(scene, camera)
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
})
