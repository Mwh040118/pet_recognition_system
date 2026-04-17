import json
from database import insert_pet

def init_pets():
    with open("data/pets.json", "r", encoding="utf-8") as f:
        pets = json.load(f)

    for pet in pets:
        insert_pet(pet["name"], pet["type"], pet["description"])