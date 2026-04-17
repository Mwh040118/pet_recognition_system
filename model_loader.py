import torch
import json
from torchvision.models import resnet18
from config import *

def load_main_model():
    with open(CLASS_JSON, "r", encoding="utf-8") as f:
        class_names = json.load(f)

    model = resnet18()
    model.fc = torch.nn.Linear(model.fc.in_features, len(class_names))
    model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
    model.eval()

    return model, class_names

def load_breed_model():
    with open(BREED_CLASS_JSON, "r", encoding="utf-8") as f:
        class_names = json.load(f)

    model = resnet18()
    model.fc = torch.nn.Linear(model.fc.in_features, len(class_names))
    model.load_state_dict(torch.load(BREED_MODEL_PATH, map_location="cpu"))
    model.eval()

    return model, class_names