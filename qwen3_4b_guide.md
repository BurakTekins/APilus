# Qwen3-4B Local Inference Guide

A step-by-step guide to downloading and running Qwen3-4B locally using HuggingFace Transformers.

---

## Prerequisites

```bash
pip install transformers huggingface_hub torch
```

---

## Cell 1 — Download the Model

Downloads Qwen3-4B from HuggingFace and saves it to a local `models/Qwen3-4B/` folder.
If the model already exists, the download is skipped automatically.

```python
import os
from huggingface_hub import snapshot_download

model_name = "Qwen/Qwen3-4B"
save_dir = os.path.join(os.getcwd(), "models", "Qwen3-4B")

os.makedirs(save_dir, exist_ok=True)
print(f"Model will be saved to: {save_dir}")

if os.path.exists(save_dir) and os.listdir(save_dir):
    print("Model already exists, skipping download.")
else:
    snapshot_download(
        repo_id=model_name,
        local_dir=save_dir,
    )
    print("Download complete!")

print(f"Files in model directory: {os.listdir(save_dir)}")
```

**Expected output:**
```
Model will be saved to: /your/project/models/Qwen3-4B
Model already exists, skipping download.
Files in model directory: ['config.json', 'tokenizer.json', 'model-00001-of-00003.safetensors', ...]
```

---

## Cell 2 — Load the Model

Loads the tokenizer and model from the local directory and defines an `ask()` function for inference.

> ⚠️ If you see `Some parameters are on the meta device because they were offloaded to the cpu`,
> it means the model is too large for your GPU VRAM and some layers are being offloaded to CPU RAM.
> This is expected behavior on machines with limited VRAM — the model will still work, just slower.

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import os

model_path = os.path.join(os.getcwd(), "models", "Qwen3-4B")

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Load model — automatically selects GPU if available, falls back to CPU
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype="auto",    # Uses float16 on GPU, float32 on CPU
    device_map="auto"      # Automatically distributes layers across available devices
)

def ask(prompt, enable_thinking=False, max_new_tokens=512):
    """
    Send a prompt to the model and return its response.

    Args:
        prompt (str):             The user message to send.
        enable_thinking (bool):   If True, the model will show its internal reasoning
                                  process before the final answer. Default is False.
        max_new_tokens (int):     Maximum number of tokens to generate. Default is 512.

    Returns:
        str: The model's response.
    """
    messages = [{"role": "user", "content": prompt}]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    generated_ids = model.generate(**model_inputs, max_new_tokens=max_new_tokens)
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):]

    return tokenizer.decode(output_ids, skip_special_tokens=True).strip()
```

---

## Cell 3 — Test the Model

Run a quick test to make sure everything is working correctly.

```python
# Basic test
response = ask("What is the capital of France?")
print(response)
```

```python
# Test with Turkish input
response = ask("Sanırım Türkçen çok iyi değil")
print(response)
```

```python
# Test with thinking mode enabled (model shows its reasoning before answering)
response = ask("What is 17 multiplied by 38?", enable_thinking=True)
print(response)
```

---

## Notes

| Parameter | Description |
|---|---|
| `enable_thinking=False` | Returns only the final answer (faster, cleaner output) |
| `enable_thinking=True` | Returns the model's reasoning steps + final answer |
| `max_new_tokens=512` | Controls response length — increase for longer answers |
| `device_map="auto"` | Automatically uses GPU if available, otherwise CPU |
| `torch_dtype="auto"` | Uses the most efficient precision for your hardware |
