import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 1. MUTLAK YOL (Absolute Path) Tanımı - Başındaki / işaretine dikkat!
BASE_DIR = "/home/yesoytur/APilus"
# Modelin gerçekten bulunduğu klasör
MODEL_LOCAL_PATH = os.path.join(BASE_DIR, "models/qwen")
# Eğer model internetten indirilecekse kullanılacak ID
MODEL_ID = "Qwen/Qwen3.5-4B"

class QwenService:
    _instance = None
    model = None
    tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QwenService, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        if self.model is None:
            # Önce yerel klasörde model dosyaları var mı diye bakıyoruz
            load_path = MODEL_LOCAL_PATH if os.path.exists(MODEL_LOCAL_PATH) else MODEL_ID
            
            print(f"--- Loading Qwen Model from: {load_path} ---")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                load_path, 
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.model = AutoModelForCausalLM.from_pretrained(
                load_path,
                torch_dtype=torch.float16, 
                device_map="auto",
                trust_remote_code=True
            )
            
            self.model.config.pad_token_id = self.tokenizer.pad_token_id
            print("--- Model successfully loaded! ---")
            
        return self.model, self.tokenizer

    def generate_answer(self, user_prompt):
        if not self.model:
            self.load_model()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_prompt}
        ]
        
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.6,
                top_p=0.95,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        # Sadece yeni üretilen kısmı al
        input_length = model_inputs.input_ids.shape[1]
        generated_ids = generated_ids[:, input_length:]

        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response.strip()

qwen_service = QwenService()