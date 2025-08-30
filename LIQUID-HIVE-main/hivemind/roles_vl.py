import json
from typing import Any
from .utils import clamp_json

PERCEPTOR_SYS = (
    "You are the Perceptor. Extract a compact JSON: {caption:str, entities:[str], doc_like:bool}."
)
DOCVQA_SYS = (
    "You are DocVQA. Answer strictly from the image. If not found, reply JSON {answer:'NOT FOUND'}."
)
MMJUDGE_SYS = (
    "You are a Multimodal Judge. Given an image and candidate answers, select the best and "
    "synthesise a superior answer that corrects factual errors and merges strengths. "
    "Return strict JSON {winner_id:int, critique:str, synthesized_answer:str}."
)

class VisionRoles:
    def __init__(self, vl_client):
        self.vl = vl_client

    async def perceptor(self, question, image):
        txt = self.vl.generate(PERCEPTOR_SYS + "\nQuestion:" + question, image)
        return clamp_json(txt, defaults={"caption":"", "entities":[], "doc_like":False})

    async def docvqa(self, question, image, context):
        txt = self.vl.generate(DOCVQA_SYS + "\nQuestion:" + question, image)
        try:
            return json.loads(txt)
        except Exception:
            return {"answer": txt}

    async def vl_committee(self, question, image, k=3, context=None):
        cands = []
        for i in range(k):
            cands.append(self.vl.generate(f"Answer the user question concisely. Q:{question}", image))
        return cands

    async def mm_judge(self, question, image, candidates):
        prompt = MMJUDGE_SYS + "\n" + "\n\n".join([f"[{i}] {c}" for i,c in enumerate(candidates)])
        txt = self.vl.generate(prompt, image)
        try:
            j = json.loads(txt)
            j["winner_text"] = candidates[j.get("winner_id",0)]
            return j
        except Exception:
            return {"winner_id":0, "winner_text": candidates[0], "critique": txt}

    def grounding_validator(self, question: str, image: Any, answer: str) -> dict[str, any]:
        """
        Validate that the answer is grounded in the contents of the image.

        This is a simplistic implementation of the grounding validator.  It
        attempts to extract textual content from the image using the
        ``rapidocr_onnxruntime`` library if available.  If the answer
        contains any token that does not appear in the OCR text the
        validator returns a ``fail`` status.  Otherwise it returns
        ``pass``.  A list of verified claims can also be returned.

        Parameters
        ----------
        question: str
            The user's question about the image.
        image: Any
            The image data to analyse.
        answer: str
            The generated answer to validate.

        Returns
        -------
        dict
            A JSON object with ``status`` set to ``pass`` or ``fail`` and
            an optional list of ``claims`` with evidence.  If OCR is
            unavailable the function returns a ``pass`` status by default.
        """
        # Attempt to import rapidocr only when called to avoid heavy import
        try:
            from rapidocr_onnxruntime import get_ocr
        except Exception:
            return {"status": "pass", "claims": []}
        try:
            ocr = get_ocr()
            result, _ = ocr(image)
            # Concatenate all recognised text
            extracted = " ".join([item[1][0] for item in result])
            # Check that each word in the answer appears in the OCR text
            missing = [w for w in answer.split() if w.strip().lower() not in extracted.lower()]
            status = "pass" if not missing else "fail"
            return {"status": status, "claims": [] if status == "pass" else missing}
        except Exception:
            return {"status": "fail", "claims": []}
