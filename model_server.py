from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any
from uuid import UUID, uuid4
from io import BytesIO
import asyncio

import torch
from promptcap import PromptCap


DEFAULT_VQA_PROMPT = "Please describe the damage in this image."


PROMPTCAP_MODEL = PromptCap(
    "vqascore/promptcap-coco-vqa"
)  # also support OFA checkpoints. e.g. "OFA-Sys/ofa-large"
if torch.cuda.is_available():
    PROMPTCAP_MODEL.cuda()


class CaptionOut(BaseModel):
    caption: str


app = FastAPI()


@app.post("/promptcap")
async def inference(image: UploadFile, prompt: str = DEFAULT_VQA_PROMPT) -> CaptionOut:
    image = BytesIO(await image.read())
    return await asyncio.get_event_loop().run_in_executor(
        None, lambda: CaptionOut(caption=PROMPTCAP_MODEL.caption(prompt, image))
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
