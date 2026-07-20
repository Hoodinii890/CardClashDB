import trace
from supabase import create_client, Client

import os
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def get_card(name):
    # Traer todas las cartas
    instance = supabase.table("Cards").select("*").eq("card_name", name).execute()
    return instance.data

def exist_image(filename):
    try:
        supabase.storage.from_("cards").download(filename)
        return True
    except Exception:
        return False

def get_card_image(filename):
    """
    Busca una imagen de carta por nombre de archivo en Supabase Storage (tipo S3).
    Retorna una URL firmada (presigned) si existe, o None si no existe.
    """
    # Verifica si el archivo existe en el bucket
    try:
        public_url = supabase.storage.from_("cards").get_public_url(filename)
        return public_url
    except Exception as e:
        print(f"Error buscando imagen en Supabase Storage: {e}")
        return None

def upload_card_image(filename):
    try:
        with open(os.path.join(os.getenv("CARDS_FOLDER", "./cartas"), filename), "rb") as f:
            res = supabase.storage.from_("cards").upload(
                filename,  # nombre con el que quedará guardado en el bucket
                f.read()             # contenido en bytes
            )
            return res
    except:
        import traceback; traceback.print_exc()
        return None

import json

def insert_card(data):
    # Insert into Supabase
    instance = supabase.table("Cards").insert(data).execute()

    # Insert into local JSON
    json_path = "cards_exists.json"
    try:
        with open(json_path, "r", encoding="utf8") as f:
            curr = json.load(f)
    except Exception:
        curr = {"Cards": []}

    curr_cards = curr.get("Cards", [])

    # Prevent duplicates (by card_name)
    card_names = {card.get("card_name") for card in curr_cards}
    if data.get("card_name") not in card_names:
        curr_cards.append(data)
        # save only if new
        with open(json_path, "w", encoding="utf8") as f:
            json.dump({"Cards": curr_cards}, f, indent=2, ensure_ascii=False)

    return instance.data

def actualizar_carta(name, data):
    # Update in Supabase
    instance = supabase.table("Cards").update(data).eq("card_name", name).execute()

    # Update in local JSON
    json_path = "cards_exists.json"
    try:
        with open(json_path, "r", encoding="utf8") as f:
            curr = json.load(f)
    except Exception:
        curr = {"Cards": []}

    updated = False
    new_cards = []
    for card in curr.get("Cards", []):
        if card.get("card_name") == name:
            # Replace card data
            new_cards.append(data)
            updated = True
        else:
            new_cards.append(card)

    # If not found, append as new
    if not updated:
        new_cards.append(data)

    with open(json_path, "w", encoding="utf8") as f:
        json.dump({"Cards": new_cards}, f, indent=2, ensure_ascii=False)

    return instance.data