"""Import the compiled module using the build/python directory."""

import flappy_engine as engine

settings = engine.GameSet(size=1, speed=1, characters=[0] * 8)
engine.begin(settings, seed=42)

try:
    for tick in range(240):
        state = engine.get_state()
        bird = state.birds[0]
        actions = [False] * 8
        # A demonstration controller, not a trained policy.
        actions[0] = bird.respawn_ms == 0 and bird.position.y < 150
        engine.step(actions)

        if tick % 24 == 0:
            state = engine.get_state()
            bird = state.birds[0]
            print(f"tick={tick + 1}, x={bird.position.x:.1f}, "
                  f"y={bird.position.y:.1f}, respawn_ms={bird.respawn_ms:.1f}")

        if engine.is_finished():
            break
finally:
    engine.clear()
