# -*- coding: utf-8 -*-
# @Project: index_test
# @Module: embedding_service
# @Author: Anonymous
# @Time: 2024/9/24 14:26

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"  # "-1"

import torch
import transformers

import json
from sentence_transformers import SentenceTransformer

import uvicorn
from fastapi import FastAPI
from typing import List
from pydantic import BaseModel

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

app = FastAPI()


class Messages(BaseModel):
    query: str


# class Messages(BaseModel):
#     messages: List[Chat_Template]


def init_model(model_id):
    model = SentenceTransformer(model_id)
    # device = model.device
    for param in model.parameters():
        param.requires_grad = False

    return model


def invoke_model(query):
    global model
    print(query)
    return json.dumps(model.encode(query.query).tolist())


@app.post("/get_embedding_result")
def get_embedding_result(query: Messages):
    return invoke_model(query)


if __name__ == "__main__":
    model_id = "/data/user/index/sql_convertor/LLM4DB/LLM4DB/data/pretrained_model/all-MiniLM-L6-v2"
    model = init_model(model_id)

    # invoke_model("query")

    uvicorn.run(app, host="0.0.0.0", port=35555)
