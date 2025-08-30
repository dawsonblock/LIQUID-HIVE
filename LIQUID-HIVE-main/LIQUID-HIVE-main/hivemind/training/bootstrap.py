import os
import pathlib
import json
from datetime import datetime
from . import sft_text

DEFAULT_OUT = pathlib.Path("/app/adapters/foundational/champion_v1")


def run_bootstrap(
    out_dir: str | os.PathLike = DEFAULT_OUT,
    base_model: str | None = None,
):
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    base_model = base_model or os.environ.get("BASE_MODEL", "unsloth/llama-3.1-8b-instruct-bnb-4bit")

    # Curated mix: SlimOrca + OpenHermes-2.5
    datasets = [
        "Open-Orca/SlimOrca",
        "teknium/OpenHermes-2.5",
    ]

    # Train a compact foundational adapter with moderate steps
    sft_text.train_sft(
        out_dir=str(out_path),
        base_model=base_model,
        datasets=datasets,
        max_seq_len=4096,
        learning_rate=2e-4,
        num_epochs=1.0,
        per_device_batch_size=2,
        grad_accum=8,
        max_train_samples=int(os.environ.get("BOOTSTRAP_MAX_TRAIN", "40000")),
        max_eval_samples=int(os.environ.get("BOOTSTRAP_MAX_EVAL", "2000")),
    )

    meta = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "base_model": base_model,
        "datasets": datasets,
        "strategy": "Unsloth QLoRA 4-bit + packing",
    }
    with open(out_path / "adapter_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return str(out_path)


if __name__ == "__main__":
    p = run_bootstrap()
    print(p)