import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "database", "pets.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

MODEL_PATH = os.path.join(BASE_DIR, "model", "pet_model.pth")
CLASS_JSON = os.path.join(BASE_DIR, "model", "class_names.json")

BREED_MODEL_PATH = os.path.join(BASE_DIR, "model", "breed_model.pth")
BREED_CLASS_JSON = os.path.join(BASE_DIR, "model", "breed_class_names.json")
BREED_INFO_JSON = os.path.join(BASE_DIR, "model", "breed_info.json")
TRAIN_LOG_JSON = os.path.join(BASE_DIR, "model", "train_log.json")
