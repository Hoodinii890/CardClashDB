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
   - stats: DMG and HP values shown on the card. Convert shorthand like "4.82K" to 4820, "20.18K" to 20180. Keep plain numbers as-is.
3. Analyze the ability and stats to infer:
   - support: This will only be true if the card has no damage (DMG) or health points (HP); if it has damage and health points, regardless of any other information, this value must be null.
   - role: Analyze the card's ability and stats. You MUST provide multiple roles if applicable, separated by a comma and a space.
     
     CRITICAL RULES FOR 7B MODEL:
     - If the text mentions "deal 75% DMG" or hitting multiple enemies/domains, you MUST add "AoE".
     - If the text mentions "rewind DMG", "restore HP", or "healing", you MUST add "Healer".
     - If a card has more than 2 roles from the list below, you MUST add "Hybrid".
     
     Choose ONLY from this list:
     - "DPS": Main damage dealer or self-damage buffs.
     - "Tank": Soaks up damage, high HP, or cancels enemy attacks.
     - "Bruiser": Durable and deals good damage (scales with MAX HP).
     - "Counter-attacker": Attacks immediately after dodging, blocking, or canceling an enemy move.
     - "AoE": Attacks multiple enemies or creates passive damage zones/domains/rewinds.
     - "Healer": Restores health, rewinds damage taken, or revives allies.
     - "Support": Buffs allies or debuffs enemies without dealing direct damage.
     - "Summoner": Calls independent units, tokens, or entities onto the field (e.g., summon Colossal Giants).
     - "Hybrid": Combines multiple main roles (e.g., Tank + AoE + Counter-attacker).

     Format example: "Tank, Counter-attacker, AoE, Healer, Hybrid"

   - caps: List the gray badge text from the bottom of the card as a single lowercase string separated by commas (e.g., "one per party, effect cap"). Use null if there are none.
   
   - revive: Identify if the card brings anyone back or creates extra lives. Look for: "revive", "resurrect", "backup life", "keep stats as a backup", "return from death". Summarize the timing and benefit. Use null if there is no revive mechanic.
   
   - status_effects: List ONLY the effect keywords applied to enemies (e.g., "burn, freeze, sleep, bleed, poison, stun, brand"). Do not explain conditions. Use null if there are no effects.
   
   - debuffs: List mechanics that weaken enemies. Look for: "cancel action", "reduce stats", "weaken", "steal DMG/stats", "remove bonus stats". Use null if empty.
   
   - counters: List reactive actions when attacked. Look for: "block", "dodge", "reflect", "cancel attack", "counter attack", "strike back", "revert last damaging effect", "rewind DMG". Use null if empty.
   
   - buffs: List enhancements to self or allies. Look for: "gain % DMG", "gain a shield", "healing", "restore % max HP", "gain lost time". Use null if empty.
   
   - fusion: Extract fusion conditions or modes if the text explicitly states "enter fusion mode". Use null if empty.
   
   - summons: Extract entities or fields created. Look for: "summon [unit]", "create a domain", "create a zone". Briefly state what is called or created. Use null if empty.

   CRITICAL COMPLIANCE FOR ALL FIELDS: You MUST read the full card text from first to last word. Do not skip secondary triggers or end-of-turn conditions.

   - role_rating: Provide a strict "X/10 - reason" rating. Evaluate the overall UTILITY and competitive strength of the full card. You MUST analyze all text phases, stats (DMG and HP), and combined mechanical chains (e.g., defense that builds into AoE damage, shield-breaking that converts to healing, or fusion mode entry). 

     CRITICAL: Do not grade based only on the first sentence. Complex multi-phase cards or hybrid units with massive secondary effects deserve a high competitive score. If stats or effects are completely useless in the meta, rate it 0/10.

     Strict Rating Scale:
     - 0/10: Useless in meta (extremely low stats, irrelevant effects, or pure self-harming skills).
     - 1.0 - 3.0 / 10: Niche but weak overall.
     - 4.0 - 6.0 / 10: Somewhat useful but below-average utility (e.g., a simple stat stick or blocker with no follow-up mechanics).
     - 7.0 - 8.5 / 10: Strong utility and highly competitive hybrid cards (e.g., cards combining active shields, fusion, or reliable counter-AoE fields).
     - 9.0 - 10 / 10: Meta-defining, top-tier utility with multi-phase mechanics that completely dominate the match.

     For Support Cards (support=true, no DMG/HP stats): Base the rating strictly on how effectively their support utility (healing, buffs, revives, debuff removal) enhances the 4 active attackers in battle. If the effect is negligible vs the meta, rate it 0/10.

Use this example structure for you response me in JSON:
{{
  "card_name": "Example Title",
  "ability_name": "Example Ability",
  "ability_description": "Example description text.",
  "stats": {{"DMG": 0, "HP": 0}},
  "role": "Example, Rols",
  "role_rating": "5.0/10 - Example reasoning.",
  "caps": null,
  "revive": null,
  "status_effects": null,
  "debuffs": null,
  "counters": null,
  "buffs": null,
  "fusion": null,
  "summons": null,
  "support": null
}}

No markdown, no text outside the JSON, and no extra formatting or newlines at the top or bottom.
Fields that do not apply must use the JSON null value (not the string "null" or "None").
The "stats" field must always be a JSON object with numbers, for example: {{"DMG": 0, "HP": 0}}
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
        if (dmg == 0 or dmg is None) or (hp == 0 or hp is None):
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