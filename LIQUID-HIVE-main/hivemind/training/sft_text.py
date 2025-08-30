import argparse
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from datasets import load_dataset, Dataset, concatenate_datasets
from unsloth import FastLanguageModel
from peft import LoraConfig
from trl import SFTTrainer
from transformers import TrainingArguments


SYSTEM_PREFIX = "### Instruction:\n"
ASSISTANT_PREFIX = "\n\n### Response:\n"


def _format_sample(sample: Dict[str, Any]) -> Optional[str]:
    """
    Normalize different HF dataset formats to a single instruction-response text.
    Supported patterns:
      - {input, output}
      - {instruction, response/answer}
      - {prompt, response}
      - {conversations: [{role, content}, ...]}
    Returns a single concatenated string or None if not usable.
    """
    # Conversations format (ShareGPT-style)
    conv = sample.get("conversations") or sample.get("messages")
    if isinstance(conv, list) and conv:
        user_msgs = [m.get("content", "") for m in conv if (m.get("role") or m.get("from")) in ("user", "human")]
        asst_msgs = [m.get("content", "") for m in conv if (m.get("role") or m.get("from")) in ("assistant", "gpt")]
        if user_msgs and asst_msgs:
            return f"{SYSTEM_PREFIX}{user_msgs[0].strip()}{ASSISTANT_PREFIX}{asst_msgs[0].strip()}"

    # Simple pairs
    for in_key, out_key in (
        ("input", "output"),
        ("instruction", "response"),
        ("instruction", "answer"),
        ("prompt", "response"),
        ("question", "answer"),
    ):
        if in_key in sample and out_key in sample:
            ins = str(sample.get(in_key, "")).strip()
            out = str(sample.get(out_key, "")).strip()
            if ins and out:
                return f"{SYSTEM_PREFIX}{ins}{ASSISTANT_PREFIX}{out}"

    # Fallback: single field that already contains prompt and response
    txt = sample.get("text")
    if isinstance(txt, str) and len(txt.strip()) > 0:
        return txt

    return None


@dataclass
class DataConfig:
    datasets: List[str]
    split: str = "train"
    eval_split: Optional[str] = None
    max_train_samples: Optional[int] = None
    max_eval_samples: Optional[int] = None


DEFAULT_DATASETS = [
    "Open-Orca/SlimOrca",
    "teknium/OpenHermes-2.5",
]


def load_mixture(cfg: DataConfig) -> (Dataset, Optional[Dataset]):
    train_parts: List[Dataset] = []
    eval_parts: List[Dataset] = []
    for ds_name in cfg.datasets:
        try:
            ds = load_dataset(ds_name)
        except Exception:
            # Allow specifying split-qualified datasets like repo:config or repo:split
            try:
                name, split = ds_name.split(":", 1)
                ds = load_dataset(name, split=split)
            except Exception:
                continue
        split_name = cfg.split
        train_ds = ds[split_name] if split_name in ds else (ds.get("train") or next(iter(ds.values())))
        if cfg.max_train_samples:
            train_ds = train_ds.select(range(min(len(train_ds), cfg.max_train_samples)))
        train_parts.append(train_ds)

        # Eval selection
        if cfg.eval_split:
            if cfg.eval_split in ds:
                eval_ds = ds[cfg.eval_split]
            else:
                eval_ds = ds.get("validation") or ds.get("test")
            if eval_ds is not None:
                if cfg.max_eval_samples:
                    eval_ds = eval_ds.select(range(min(len(eval_ds), cfg.max_eval_samples)))
                eval_parts.append(eval_ds)

    def map_to_text(d: Dataset) -> Dataset:
        return d.map(lambda x: {"text": _format_sample(x)}, remove_columns=d.column_names).filter(lambda x: x["text"] is not None)

    train = concatenate_datasets([map_to_text(d) for d in train_parts]) if len(train_parts) > 1 else map_to_text(train_parts[0])
    evalset = None
    if eval_parts:
        evalset = concatenate_datasets([map_to_text(d) for d in eval_parts]) if len(eval_parts) > 1 else map_to_text(eval_parts[0])
    return train, evalset


def train_sft(
    out_dir: str,
    base_model: str,
    datasets: List[str] | None = None,
    max_seq_len: int = 4096,
    learning_rate: float = 2e-4,
    num_epochs: float = 1.0,
    per_device_batch_size: int = 2,
    grad_accum: int = 8,
    max_train_samples: Optional[int] = None,
    max_eval_samples: Optional[int] = None,
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # Load model with Unsloth at 4-bit for QLoRA
    model, tokenizer = FastLanguageModel.from_pretrained(
        base_model,
        max_seq_length=max_seq_len,
        dtype=None,
        load_in_4bit=True,
    )

    # Enable gradient checkpointing & get PEFT LoRA model
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0.0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=True,
    )

    # Prepare data
    cfg = DataConfig(datasets=datasets or DEFAULT_DATASETS, max_train_samples=max_train_samples, max_eval_samples=max_eval_samples)
    train_set, eval_set = load_mixture(cfg)

    # Trainer with packing to maximize throughput
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_set,
        eval_dataset=eval_set,
        packing=True,
        dataset_text_field="text",
        max_seq_length=max_seq_len,
        args=TrainingArguments(
            output_dir=out_dir,
            per_device_train_batch_size=per_device_batch_size,
            gradient_accumulation_steps=grad_accum,
            num_train_epochs=num_epochs,
            warmup_ratio=0.03,
            learning_rate=learning_rate,
            bf16=True,
            logging_steps=10,
            save_strategy="epoch",
            evaluation_strategy="no" if eval_set is None else "epoch",
            optim="paged_adamw_8bit",
            lr_scheduler_type="cosine",
            report_to="none",
        ),
    )

    trainer.train()

    # Save LoRA adapter and tokenizer
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)


def main():
    parser = argparse.ArgumentParser(description="SFT with Unsloth QLoRA")
    parser.add_argument("--out", required=True, help="Output directory for the adapter")
    parser.add_argument("--base_model", default=os.environ.get("BASE_MODEL", "unsloth/llama-3.1-8b-instruct-bnb-4bit"))
    parser.add_argument("--dataset", action="append", help="HF dataset repo id. Can be passed multiple times.")
    parser.add_argument("--max_train_samples", type=int, default=None)
    parser.add_argument("--max_eval_samples", type=int, default=None)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=8)
    parser.add_argument("--max_seq_len", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=2e-4)
    args = parser.parse_args()

    train_sft(
        out_dir=args.out,
        base_model=args.base_model,
        datasets=args.dataset,
        max_seq_len=args.max_seq_len,
        learning_rate=args.lr,
        num_epochs=args.epochs,
        per_device_batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
    )


if __name__ == "__main__":
    main()