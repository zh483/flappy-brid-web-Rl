"""Export the deterministic PPO actor and verify it against SB3 before deployment."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from stable_baselines3 import PPO

from .engine_loader import check_engine_config, load_engine
from .env import OBSERVATION_VERSION
from .settings import check_observation, find_run, read_json, write_json


class Actor(torch.nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def forward(self, observation):
        features = self.policy.extract_features(observation)
        return self.policy.action_net(self.policy.mlp_extractor.forward_actor(features))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path, default=Path("saver/models/ppo-bird.onnx"))
    args = parser.parse_args()
    run = find_run(args.model)
    manifest = read_json(run / "manifest.json")
    check_observation(manifest)
    check_engine_config(load_engine(), manifest["engine_config"])
    torch.set_num_threads(1)
    model = PPO.load(str(args.model.resolve()), device="cpu")
    if model.observation_space.shape != (8,) or model.action_space.n != 2:
        raise ValueError("Expected eight observations and two discrete actions")
    if not model.policy.share_features_extractor:
        raise ValueError("This exporter expects shared policy features")
    actor = Actor(model.policy).eval()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(actor, torch.zeros(1, 8), str(args.output),
                      input_names=["observation"], output_names=["logits"],
                      dynamic_axes={"observation": {0: "batch"}, "logits": {0: "batch"}},
                      opset_version=17, dynamo=False)
    onnx.checker.check_model(onnx.load(str(args.output)))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(args.output), options, providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(20261008)
    observations = rng.uniform([-1, -1, 0, -1, 0, 0, 0, 0],
                               [2, 1, 1, 4, 1, 1, 1, 1], (512, 8)).astype(np.float32)
    observations[:, 7] = (observations[:, 7] >= 0.5).astype(np.float32)
    with torch.no_grad():
        expected_logits = actor(torch.from_numpy(observations)).numpy()
        expected_actions, _ = model.predict(observations, deterministic=True)
    actual = session.run(["logits"], {"observation": observations})[0]
    np.testing.assert_allclose(actual, expected_logits, atol=2e-5, rtol=2e-5)
    np.testing.assert_array_equal(actual.argmax(axis=1), expected_actions)
    write_json(args.output.with_suffix(".json"), {
        "schema_version": 1, "observation_version": OBSERVATION_VERSION,
        "engine_config": manifest["engine_config"], "training_steps": model.num_timesteps,
        "source_model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "onnx_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "observation_order": ["y", "vy", "vx", "pipe_dx", "gap_down", "gap_up", "x", "has_pipe"],
        "actions": {"0": "no_jump", "1": "jump"}, "parity_cases": len(observations),
    })
    write_json(args.output.with_name("policy-cases.json"), {
        "cases": [{"observation": obs.tolist(), "logits": logits.tolist(), "action": int(action)}
                  for obs, logits, action in zip(observations, expected_logits, expected_actions)]})
    print(f"Exported {args.output}: all {len(observations)} SB3/ONNX actions match")


if __name__ == "__main__":
    main()
