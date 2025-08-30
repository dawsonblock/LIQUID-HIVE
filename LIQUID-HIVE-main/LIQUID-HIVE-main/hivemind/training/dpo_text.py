import argparse, json, pathlib
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model, TaskType
from trl import DPOTrainer

def to_dataset(path):
    # jsonl with {"prompt","chosen","rejected"}
    return load_dataset("json", data_files=str(path))["train"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="LiquidAI/LFM2-1.2B")
    ap.add_argument("--data", default="datasets/dpo_text.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--steps", type=int, default=800)
    args = ap.parse_args()

    ds = to_dataset(args.data).rename_columns({
        "prompt":"prompt",
        "chosen":"chosen",
        "rejected":"rejected"
    })

    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.base, trust_remote_code=True)
    lora = LoraConfig(
        r=args.r, lora_alpha=16, lora_dropout=0.05, bias="none",
        task_type=TaskType.CAUSAL_LM, target_modules=["q_proj","v_proj","k_proj","o_proj"]
    )
    model = get_peft_model(model, lora)

    args_tr = TrainingArguments(
        output_dir=args.out, per_device_train_batch_size=1, gradient_accumulation_steps=8,
        max_steps=args.steps, learning_rate=args.lr, logging_steps=10, save_steps=100, bf16=True
    )
    trainer = DPOTrainer(
        model=model, ref_model=None,  # implicit reference = frozen base behavior in LoRA
        args=args_tr, beta=0.1, train_dataset=ds, tokenizer=tok
    )
    trainer.train()
    trainer.save_model(args.out)

if __name__ == "__main__":
    main()
