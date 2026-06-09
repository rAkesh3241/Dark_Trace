import os, torch
from datasets import Dataset
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    Trainer, TrainingArguments, DataCollatorForLanguageModeling,
)

# ── Config ────────────────────────────────────────────────────────────────────
DATA_FILE  = os.getenv("DATA_FILE",    "training_data.txt")
MODEL_NAME = os.getenv("BASE_MODEL",   "distilgpt2")       # or "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
OUTPUT_DIR = os.getenv("MODEL_OUTPUT", "./models/honeypot_model")
EPOCHS     = int(os.getenv("EPOCHS",   "3"))
BATCH_SIZE = int(os.getenv("BATCH",    "4"))


def load_texts(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Split on end-of-text token
    blocks = [b.strip() for b in content.split("<|endoftext|>") if b.strip()]
    print(f"Loaded {len(blocks)} training blocks")
    return blocks


def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Run prepare_data.py first. Missing: {DATA_FILE}")

    texts = load_texts(DATA_FILE)
    if not texts:
        raise ValueError("No training data found.")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.add_special_tokens({
        "additional_special_tokens": ["<|attacker|>", "<|system|>", "<|endoftext|>"]
    })
    tokenizer.pad_token = tokenizer.eos_token

    dataset = Dataset.from_dict({"text": texts})

    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=512,
            padding="max_length",
        )

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    model.resize_token_embeddings(len(tokenizer))

    use_gpu = torch.cuda.is_available()
    print(f"Using {'GPU' if use_gpu else 'CPU'} for training")

    args = TrainingArguments(
        output_dir            = "./results",
        overwrite_output_dir  = True,
        num_train_epochs      = EPOCHS,
        per_device_train_batch_size = BATCH_SIZE,
        gradient_accumulation_steps = 2,
        save_steps            = 200,
        save_total_limit      = 2,
        logging_dir           = "./logs_train",
        logging_steps         = 25,
        warmup_steps          = 50,
        weight_decay          = 0.01,
        lr_scheduler_type     = "cosine",
        report_to             = "none",
        fp16                  = use_gpu,
        use_cpu               = not use_gpu,
    )

    trainer = Trainer(
        model           = model,
        args            = args,
        train_dataset   = tokenized,
        data_collator   = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    print("Starting training...")
    trainer.train()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"✅ Model saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()