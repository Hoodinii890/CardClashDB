"""
card_pipeline_vision.py
-------------------------
Usa un modelo de visión local (model VL u otro VLM cargado
en LM Studio) para analizar la carta DIRECTO desde la imagen, sin OCR
manual ni recortes por coordenadas. Resuelve el problema de layouts
variables (descripciones cortas vs. largas, con o sin caps, etc.)
porque el modelo "ve" la carta completa como un humano lo haría.

Requisitos:
    pip install python-dotenv openai --break-system-packages
    LM Studio corriendo con un modelo de VISIÓN cargado
    (ej. model VL, cuantización Q4_K_M para 8GB VRAM)

.env esperado:
    CARDS_FOLDER=./cartas
    LM_STUDIO_BASE_URL=http://localhost:1234/v1
    LM_STUDIO_MODEL=local-model
    MAX_DMG=14000
    MAX_HP=28000

Uso:
    python card_pipeline_vision.py > resultado.json
"""

import os
import sys
import json
from datetime import datetime, timezone
import base64
from dotenv import load_dotenv
from openai import OpenAI
from client_sb import *

load_dotenv()

CARDS_FOLDER = os.getenv("CARDS_FOLDER", "./cartas")
LM_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_MODEL = os.getenv("LM_STUDIO_MODEL", "local-model")
MAX_DMG = int(os.getenv("MAX_DMG", 14000))
MAX_HP = int(os.getenv("MAX_HP", 28000))

client = OpenAI(base_url=LM_BASE_URL, api_key="lm-studio")

ALL_FIELDS = [
    "card_name", "ability_name", "ability_description", "stats",
    "role", "role_rating", "caps", "revive", "status_effects",
    "debuffs", "counters", "buffs", "fusion", "summons", "support"
]

SYSTEM_PROMPT = f"""You are an AI that receives a fantasy/gacha card image.
Your task:

1. Perform OCR on the image to read all visible text.
2. Identify and classify:
   - card_name: main title (top, bold font).
   - ability_name: highlighted ability name (below card name).
   - ability_description: full ability description text.
   - stats: DMG and HP values shown on the card. Convert shorthand like
     "4.82K" to 4820, "20.18K" to 20180. Keep plain numbers as-is.
3. Analyze the ability and stats to infer:
   - role: must be chosen from the following closed list:
     ["DPS","Burst DPS","Sustained DPS","Tank","Bruiser","Healer","Self-Healer","Support","Self-Support","Buffer","Debuffer","Crowd Control","Summoner","Reviver","Hybrid","Disruptor","Defender","Reflector","Dodger","Nuker","AoE","Single Target Specialist (just put STS)","Control Mage","Utility"]
     Multiple roles allowed if applicable.
   - role_rating: strict "X/10 - reason". MUST weigh both ability
     usefulness AND how stats compare to current max (DMG {MAX_DMG},
     HP {MAX_HP}). If stats are far below max, rating must be **0/10**
     even if the ability sounds strong. Example: a card that explodes
     for 500% of its HP but only has HP=14 will deal 70 damage, which
     is useless against enemies with HP {MAX_HP}, so it must be rated 0/10. You may use up to 1 decimal place for more detailed ratings if necessary.
   - For support cards (support=true, no DMG/HP stats), the rating must
     be based **only** on the real usefulness of their support ability
     (healing, buffs, revive, debuff removal, etc.) in the context of
     battle. Support cards exist to benefit the user's 4 active attack
     cards, so their value must be judged strictly by how much they
     enhance those allies. If their effect is negligible compared to
     the meta, they must also be rated 0/10.
   - caps: here, list the card's "cap" badges that appear near the bottom edge of the card, inside gray rounded containers; but do NOT format them as an array like ["",""], instead write them as a single string, lowercase, separated by commas—for example: "one per party, effect cap, revive limit". Use None if there are none.
   - revive: how/when it revives and the benefit. None if none.
   - status_effects: only list the keywords for each effect type the card applies to the enemy, for example: "burn", "freeze", "sleep", "bleed", "poison", "stun", etc. Do not explain reasons, conditions, or how they are applied—just mention the effect keywords. If the card applies more than one, write a list of the keywords. Use None if there are no effects.
   - debuffs: enemy debuffs (cancel, reduce, weaken). None if none.
   - counters: counter mechanics (block, dodge, reflect). None if none.
   - buffs: buffs to self/allies. None if none.
   - fusion: fusion mode/conditions/effects. None if none.
   - summons: summoned units, how, conditions. None if none.
   - support: This will only be true if the card has neither DMG nor HP; if it has DMG and HP, regardless of any other information, this must be null.

Strict rating scale:
- 0/10 → useless in meta (stats too low or ability irrelevant).
- 1–3/10 → niche but weak overall.
- 4–6/10 → somewhat useful but below average.
- 7–8/10 → strong ability and competitive stats or support effect.
- 9–10/10 → meta-defining card, top tier.

Use this example structure for you response me in JSON:
{{
  "card_name": "Card name here",
  "ability_name": "Ability name here",
  "ability_description": "Full ability description here.",
  "stats": {{"DMG": 1234, "HP": 5678}},
  "role": "Support",
  "role_rating": "7.5/10 - Strong ability and competitive stats for a support role, but the attack reduction is not as impactful as other similar cards.",
  "caps": "cap1, cap2" or null,
  "revive": "description how/when it revives and the benefit" or null,
  "status_effects": "effect1, effect2" or null,
  "debuffs": "enemy debuffs (cancel, reduce, weaken)" or null,
  "counters": "counter mechanics (block, dodge, reflect)" or null,
  "buffs": "buffs to self/allies" or null,
  "fusion": "fusion mode/conditions/effects" or null,
  "summons": "summoned units, how, conditions" or null,
  "support": boolean
}}

No markdown, no text outside the JSON, and no extra formatting or newlines at the top or bottom.
Fields that do not apply must use null (not the string "null").
The "stats" field must always be a JSON object with numbers, for example: {{"DMG": 0, "HP": 1200}}
"""

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def guess_mime(path):
    ext = path.lower().rsplit(".", 1)[-1]
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
    }.get(ext, "image/png")


def analyze_card(path):
    b64 = encode_image(path)
    mime = guess_mime(path)

    response = client.chat.completions.create(
        model=LM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this card image."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            },
        ],
        temperature=0.1,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "invalid_json_from_model", "raw_response": raw}

    # Garantiza que todas las llaves existan siempre
    result = {field: parsed.get(field) for field in ALL_FIELDS}
    if not isinstance(result.get("stats"), dict):
        result["stats"] = {"DMG": 0, "HP": 0}
    # Si tiene stats (no todos son 0 o alguno es distinto de 0), support siempre None
    stats = result.get("stats", {})
    if isinstance(stats, dict):
        dmg = stats.get("DMG")
        hp = stats.get("HP")
        if (dmg == 0 or dmg is None) and (hp == 0 or hp is None):
            result["support"] = True
        else:
            result["support"] = None
    return result


def process_folder(folder_path):
    valid_ext = (".png", ".jpg", ".jpeg", ".webp")
    results = []
    files = [f for f in sorted(os.listdir(folder_path))
            if f.lower().endswith(valid_ext)]

    # Cargar cards_exists.json
    cards_json_path = "cards_exists.json"
    try:
        with open(cards_json_path, "r", encoding="utf8") as f:
            cards_json = json.load(f)
        cards_list = cards_json.get("Cards", [])
    except Exception:
        cards_list = []

    # Crear map de icon => update_at
    icon_update_map = {}
    for card in cards_list:
        icon_url = card.get("icon")
        update_at = card.get("update_at")
        if icon_url and update_at:
            # icon_url example: https://[...]/cards/green_bomber.png => green_bomber.png
            icon_fname = icon_url.split("/")[-1]
            icon_update_map[icon_fname] = update_at

    from tqdm import tqdm

    for i, fname in enumerate(tqdm(files, desc="Procesando", unit="Carta")):
        tqdm.write(f"Procesando {i+1}/{len(files)}: {fname}...", file=sys.stderr)
        full_path = os.path.join(folder_path, fname)

        # Verificar si el fname está en el json (buscamos por nombre de archivo en icon)
        update_at_json = icon_update_map.get(fname)
        if update_at_json:
            # Convertir la fecha del json a objeto datetime
            try:
                dt_json = datetime.strptime(update_at_json, "%Y-%m-%d %H:%M:%S.%f%z")
            except Exception:
                try:
                    dt_json = datetime.strptime(update_at_json, "%Y-%m-%d %H:%M:%S.%f")
                    dt_json = dt_json.replace(tzinfo=timezone.utc)
                except Exception:
                    dt_json = None

            # Conseguir el mtime del archivo
            file_mtime = os.path.getmtime(full_path)
            dt_file = datetime.fromtimestamp(file_mtime, timezone.utc)

            # Comparar
            if dt_json is not None:
                if dt_file <= dt_json:
                    continue
        try:
            card_data = analyze_card(full_path)
            # Comprobar carta en supabase
            icon_name = card_data["card_name"].lower().replace(" ","_")
            print("\n", card_data["card_name"])
            # Verifica si la imagen del archivo tiene el mismo nombre que icon_name
            ext = os.path.splitext(fname)[1].lower()
            expected_fname = f"{icon_name}{ext}"

            updated_full_path = full_path
            filename_to_upload = fname
            if fname != expected_fname:
                # Renombrar el archivo permanentemente al nombre esperado
                new_path = os.path.join(folder_path, expected_fname)
                os.rename(full_path, new_path)
                full_path = new_path
                fname = expected_fname
                updated_full_path = new_path
                filename_to_upload = expected_fname
     

            if exist_image(expected_fname) is False:
                # Subir la imagen usando el nombre correcto
                upload_card_image(filename_to_upload)

            card_data["icon"] = get_card_image(expected_fname)
            
            # Si el archivo fue renombrado, lo dejamos con el nombre original para no alterar el folder localmente
            if fname != expected_fname:
                # Volver a dejar el nombre original en el folder
                original_path = os.path.join(folder_path, fname)
                os.rename(updated_full_path, original_path)
            sb_data = get_card_image(card_data["card_name"])
            if sb_data == []:
                insert_card(card_data)
            else:
                card_data["update_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f%z")
                actualizar_carta(card_data["card_name"], card_data)
            results.append(card_data)

        except Exception as e:
            import traceback; traceback.print_exc()
            results.append({"_file": fname, "error": str(e)})
    return results

if __name__ == "__main__":
    if not os.path.isdir(CARDS_FOLDER):
        print(f"Carpeta no encontrada: {CARDS_FOLDER}", file=sys.stderr)
        sys.exit(1)

    data = process_folder(CARDS_FOLDER)