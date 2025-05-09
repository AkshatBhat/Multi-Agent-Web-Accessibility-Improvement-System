import json
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

class ContrastAgent:
    def __init__(self, model_dir: str = "virajns2/contrast-violation-t5", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = T5Tokenizer.from_pretrained(model_dir)
        self.model     = T5ForConditionalGeneration.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()

    def preprocess(self, raw_json: str) -> list[str]:
        """
        Parse the JSON and return a list of input strings (only for contrast violations).
        """
        doc = json.loads(raw_json)
        prompts = []

        for vp in doc.get("viewports", []):
            for c in vp.get("contrast", []):
                contrast_val = c.get("contrast", 1.0)
                # Only keep if below WCAG minimum contrast ratio (e.g., 4.5 for normal text)
                if contrast_val < 4.5:
                    role = c.get("role", "unknown")
                    fg = ",".join(map(str, c.get("fg", [0, 0, 0])))
                    bg = ",".join(map(str, c.get("bg", [255, 255, 255])))
                    prompt = f"role: {role}, fg: {fg}, bg: {bg}, contrast: {contrast_val:.2f}"
                    prompts.append(prompt)

        if not prompts:
            raise ValueError("No contrast violations found in JSON.")

        return prompts

    def generate_description(self, prompt: str, max_input_len: int = 64, max_output_len: int = 64, num_beams: int = 1) -> str:
        inputs = self.tokenizer(
            prompt,
            max_length=max_input_len,
            truncation=True,
            padding="longest",
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            out = self.model.generate(
                input_ids=inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_length=max_output_len,
                num_beams=num_beams,
                early_stopping=True
            )
        return self.tokenizer.decode(out[0], skip_special_tokens=True)

    def handle(self, raw_json: str) -> str:
        """
        Generate a summary for all contrast violations in the input JSON.
        Returns a concatenated string of all descriptions.
        """
        prompts = self.preprocess(raw_json)
        descriptions = [self.generate_description(p) for p in prompts]
        return " ".join(descriptions)