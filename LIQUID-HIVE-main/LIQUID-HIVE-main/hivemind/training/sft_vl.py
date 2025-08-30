import argparse, json, pathlib
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoProcessor, TrainingArguments, default_data_collator
from peft import LoraConfig, get_peft_model, TaskType
from torch.utils.data import DataLoader

# Minimal SFT for VL: dataset rows: {"image_path": "...", "text": "..."}
def to_dataset(path):
    return load_dataset("json", data_files=str(path))["train"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="LiquidAI/LFM2-VL-1.6B")
    ap.add_argument("--data", default="datasets/sft_vl.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--r", type=int, default=8)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--lr", type=float, default=1e-4)
    args = ap.parse_args()

    ds = to_dataset(args.data)
    proc = AutoProcessor.from_pretrained(args.base, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(args.base, trust_remote_code=True)

    lora = LoraConfig(
        r=args.r, lora_alpha=16, lora_dropout=0.1, bias="none",
        task_type=TaskType.CAUSAL_LM, target_modules=["q_proj","v_proj","k_proj","o_proj"]
    )
    model = get_peft_model(model, lora)

    def map_fn(e):
        import PIL.Image as Image, os
        img = Image.open(e["image_path"]).convert("RGB")
        out = proc(text=e["text"], images=img, return_tensors="pt")
        out = {k:v[0] for k,v in out.items()}
        return out

    ds = ds.map(map_fn, remove_columns=ds.column_names)

    tr = TrainingArguments(output_dir=args.out, max_steps=args.steps, learning_rate=args.lr,
                           per_device_train_batch_size=1, gradient_accumulation_steps=4, bf16=True, logging_steps=10)
    # Using Trainer directly due to vision inputs
    from transformers import Trainer
    trainer = Trainer(model=model, args=tr, train_dataset=ds, tokenizer=None, data_collator=default_data_collator)
    trainer.train()
    model.save_pretrained(args.out)

if __name__ == "__main__":
    main()
