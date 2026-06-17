# 001 - Mixamo Character Animation in Three.js

## Goal

Load a Mixamo base character FBX and apply a separate Mixamo animation FBX downloaded without skin.

## No Blender workflow

This experiment intentionally avoids Blender.

Use this workflow:

1. Download the base character from Mixamo:
   - Format: FBX Binary
   - Pose: T-pose
   - This file contains the mesh and skeleton
   - Rename it to `character.fbx`

2. Download the animation from Mixamo:
   - Format: FBX Binary
   - Skin: Without Skin
   - Frames per Second: 30
   - Keyframe Reduction: none
   - For walking/running, In Place can be ON
   - Rename it to `walking.fbx`

3. Place both files here:

```text
public/models/character.fbx
public/models/walking.fbx
```

4. Run the viewer:

```bash
npm install
npm run dev
```

## Expected result

The browser opens a Three.js scene.
The base character loads from `public/models/character.fbx`.
The animation loads from `public/models/walking.fbx`.
The animation clip is played on the base character.

## Important note

This works only if the skeleton/track names are compatible.
If the animation does not affect the character, the most likely reason is that the animation FBX track names do not match the base character skeleton names.

## Do not commit assets

Do not commit FBX files.
Keep them local.
