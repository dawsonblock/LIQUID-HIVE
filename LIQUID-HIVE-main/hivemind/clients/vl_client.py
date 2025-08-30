from transformers import AutoModelForCausalLM, AutoProcessor
import torch

class VLClient:
    def __init__(self, model_id: str):
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
        )

    def generate(self, prompt: str, image):
        inputs = self.processor(text=prompt, images=image, return_tensors="pt").to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=256)
        txt = self.processor.batch_decode(out, skip_special_tokens=True)[0]
        return txt
