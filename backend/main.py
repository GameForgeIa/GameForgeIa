"""
ForgeGameIA - Backend V2
===========================
Changements majeurs :
- LLM : Google Gemini (API gratuite, sans carte bancaire, quota quotidien
  généreux) à la place de l'API Anthropic (payante à l'usage).
- Persistance : Supabase (base Postgres gratuite en permanence) pour que
  l'équipe d'agents (grands agents + sous-agents créés dynamiquement)
  survive aux redémarrages du serveur.
- Apprentissage web : le Manager peut faire une vraie recherche Google
  (fonctionnalité "grounding" de Gemini) pour apprendre son rôle de
  studio de jeu vidéo, et garder ces notes en mémoire durable.

Variables d'environnement nécessaires (à définir dans Render) :
  GEMINI_API_KEY   -> clef gratuite sur aistudio.google.com
  SUPABASE_URL     -> URL de ton projet Supabase
  SUPABASE_KEY     -> clef "anon" ou "service_role" de ton projet Supabase

⚠️ Note sur le coût : Gemini est gratuit pour la génération de texte/JSON
normale. La fonctionnalité de recherche web (grounding) peut être facturée
séparément même sur les comptes gratuits selon la politique actuelle de
Google — vérifie la page tarifs de aistudio.google.com avant d'appuyer
souvent sur le bouton "apprentissage". Pour cette raison, ce backend ne
l'utilise que sur demande explicite (bouton dédié), jamais à chaque message.
"""

import base64
import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ForgeGameIA Backend V2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GEMINI_MODEL = "gemini-2.5-flash"

STUDIO_AGENT_IDS = {
    "game_designer", "level_designer", "narratif", "artiste",
    "sound_designer", "programmeur",
}


def seed_agents() -> dict:
    return {
        "game_designer": {
            "name": "Game Designer",
            "system_prompt": """Tu es le Game Designer d'un studio de tactical-RPG isométrique
(façon Final Fantasy Tactics). Réponds UNIQUEMENT en JSON (sans texte autour) :
{
  "name": "string", "grid_width": 8, "grid_height": 8,
  "tiles": [{"x": 0, "y": 0, "height": 0, "type": "grass"}],
  "units": [{"x": 1, "y": 1, "team": "player", "type": "knight", "hp": 20, "atk": 5, "move": 4}],
  "objective": "string"
}
"type" de tile parmi: grass, dirt, water, wall, sand. "height" entre 0 et 3.
"team" parmi: player, enemy. hp entre 10 et 30, atk entre 3 et 8, move entre 3 et 5
selon le type d'unité (ex: un archer a plus de move et moins de hp qu'un chevalier).
Couvre toute la grille (grid_width * grid_height tuiles), places 2 à 4 unités
de chaque camp, évite de placer une unité sur un mur ("wall"). Si des fichiers
sont joints (images/documents de référence), inspire-toi en pour le style et
le contenu du niveau.""",
            "output_type": "level_json",
            "parent_id": None,
        },
        "level_designer": {
            "name": "Level Designer",
            "system_prompt": """Tu es le Level Designer. Même format JSON que le Game
Designer (avec hp/atk/move sur chaque unité), concentré sur le relief et les
obstacles d'une carte tactique.""",
            "output_type": "level_json",
            "parent_id": None,
        },
        "narratif": {
            "name": "Narrative Designer",
            "system_prompt": """Tu es le Narrative Designer. Réponds en texte libre,
concis (5-8 lignes), scénario/dialogue/quête.""",
            "output_type": "text",
            "parent_id": None,
        },
        "artiste": {
            "name": "Directeur Artistique",
            "system_prompt": """Tu es le Directeur Artistique. Réponds en texte libre
(5-8 lignes) : palette, ambiance, style.""",
            "output_type": "text",
            "parent_id": None,
        },
        "sound_designer": {
            "name": "Sound Designer",
            "system_prompt": """Tu es le Sound Designer / Compositeur. Réponds en texte
libre (5-8 lignes) avec des suggestions concrètes d'ambiance sonore.""",
            "output_type": "text",
            "parent_id": None,
        },
        "programmeur": {
            "name": "Programmeur Gameplay",
            "system_prompt": """Tu es le Programmeur Gameplay. Réponds en texte libre,
notes techniques concrètes orientées implémentation.""",
            "output_type": "text",
            "parent_id": None,
        },
    }


STATE = {"agents": seed_agents(), "last_level": None, "manager_notes": "", "level_history": []}

# ---------------------------------------------------------------------
# Persistance (Supabase) — un simple magasin clef/valeur
# ---------------------------------------------------------------------

def get_supabase():
    try:
        from supabase import create_client
    except ImportError:
        return None
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def kv_get(key: str, default):
    client = get_supabase()
    if client is None:
        return default
    try:
        res = client.table("kv_store").select("value").eq("key", key).execute()
        if res.data:
            return res.data[0]["value"]
    except Exception:
        pass
    return default


def kv_set(key: str, value) -> None:
    client = get_supabase()
    if client is None:
        return
    try:
        client.table("kv_store").upsert({"key": key, "value": value}).execute()
    except Exception:
        pass


@app.on_event("startup")
def load_state():
    STATE["agents"] = kv_get("agents", seed_agents())
    STATE["last_level"] = kv_get("last_level", None)
    STATE["manager_notes"] = kv_get("manager_notes", "")
    STATE["level_history"] = kv_get("level_history", [])


def save_agents():
    kv_set("agents", STATE["agents"])


# ---------------------------------------------------------------------
# Appels au modèle Gemini
# ---------------------------------------------------------------------

def get_gemini_client():
    try:
        from google import genai
    except ImportError:
        raise HTTPException(500, "Le paquet 'google-genai' n'est pas installé sur le serveur.")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(500, "Variable d'environnement GEMINI_API_KEY manquante.")
    return genai.Client(api_key=api_key)


def attachments_to_parts(attachments: list) -> list:
    from google.genai import types
    parts = []
    for att in attachments:
        if att.mime_type.startswith("image/") or att.mime_type == "application/pdf":
            parts.append(types.Part.from_bytes(
                data=base64.b64decode(att.data_base64), mime_type=att.mime_type
            ))
        else:
            try:
                text = base64.b64decode(att.data_base64).decode("utf-8", errors="replace")
            except Exception:
                text = "(fichier illisible)"
            parts.append(types.Part.from_text(
                text=f"--- Fichier joint: {att.filename} ---\n{text[:6000]}\n--- fin ---"
            ))
    return parts


def call_agent(system: str, message: str, attachments: list) -> str:
    from google.genai import types
    client = get_gemini_client()
    parts = [types.Part.from_text(text=message)] + attachments_to_parts(attachments)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=1500),
    )
    return (response.text or "").strip()


def call_grounded(prompt: str) -> str:
    """Appel avec la recherche Google activée (grounding)."""
    from google.genai import types
    client = get_gemini_client()
    search_tool = types.Tool(google_search=types.GoogleSearch())
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[search_tool], max_output_tokens=1200),
    )
    return (response.text or "").strip()


# ---------------------------------------------------------------------
# Le Manager : routage + création de sous-agents (sortie JSON structurée,
# pas de function-calling, pour rester simple et fiable)
# ---------------------------------------------------------------------

def manager_system_prompt() -> str:
    lines = []
    for aid in STUDIO_AGENT_IDS:
        a = STATE["agents"][aid]
        lines.append(f"- {aid} ({a['name']})")
        for sid, s in STATE["agents"].items():
            if s["parent_id"] == aid:
                lines.append(f"    -> {sid} ({s['name']})")
    roster = "\n".join(lines)
    notes = STATE.get("manager_notes") or "(pas encore de notes d'apprentissage)"

    return f"""Tu es le Manager du studio ForgeGameIA, au sommet de la hiérarchie.
Notes d'apprentissage sur le métier de studio de jeu vidéo :
{notes}

Équipe actuelle (grands agents et leurs sous-agents) :
{roster}

Réponds UNIQUEMENT avec un objet JSON (rien d'autre, pas de texte autour),
selon un de ces deux formats exacts :

1) Pour confier la tâche à un agent déjà existant :
{{"action": "route", "agent_id": "identifiant_existant"}}

2) Pour créer un nouveau sous-agent (uniquement si aucun agent existant ne
convient, ou pour automatiser une tâche répétitive précise). Le sous-agent
doit TOUJOURS être rattaché à l'un des grands agents du studio
(game_designer, level_designer, narratif, artiste, sound_designer,
programmeur) — jamais à toi directement, jamais à un autre sous-agent :
{{"action": "create_subagent", "id": "id_court_snake_case", "name": "Nom lisible",
  "system_prompt": "instructions complètes du sous-agent",
  "output_type": "level_json ou text", "parent_id": "un_grand_agent"}}

Ne recrée jamais un sous-agent qui existe déjà pour un besoin proche."""


def route_with_manager(message: str, attachments: list) -> str:
    from google.genai import types
    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=manager_system_prompt(), max_output_tokens=400
        ),
    )
    raw = (response.text or "").strip()
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        decision = json.loads(cleaned)
    except json.JSONDecodeError:
        return "game_designer"

    if decision.get("action") == "route":
        agent_id = decision.get("agent_id")
        if agent_id in STATE["agents"]:
            return agent_id
    elif decision.get("action") == "create_subagent":
        new_id = decision.get("id")
        parent_id = decision.get("parent_id")
        if parent_id not in STUDIO_AGENT_IDS:
            parent_id = "game_designer"
        if new_id and new_id not in STUDIO_AGENT_IDS:
            STATE["agents"][new_id] = {
                "name": decision.get("name", new_id),
                "system_prompt": decision.get("system_prompt", ""),
                "output_type": decision.get("output_type", "text"),
                "parent_id": parent_id,
            }
            save_agents()
            return new_id

    return "game_designer"


# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

class Attachment(BaseModel):
    filename: str
    mime_type: str
    data_base64: str


class ChatRequest(BaseModel):
    message: str
    attachments: list[Attachment] = []


@app.post("/chat")
def chat(req: ChatRequest):
    agent_id = route_with_manager(req.message, req.attachments)
    agent = STATE["agents"][agent_id]
    raw = call_agent(agent["system_prompt"], req.message, req.attachments)

    if agent["output_type"] == "level_json":
        cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            level = json.loads(cleaned)
            STATE["last_level"] = level
            kv_set("last_level", level)

            import uuid
            import datetime
            entry = {
                "id": uuid.uuid4().hex[:8],
                "name": level.get("name", "Niveau sans nom"),
                "created_at": datetime.datetime.utcnow().isoformat(),
                "level": level,
            }
            STATE["level_history"].insert(0, entry)
            STATE["level_history"] = STATE["level_history"][:20]
            kv_set("level_history", STATE["level_history"])

            reply_text = (
                f"[{agent['name']}] Niveau \"{level.get('name', '?')}\" généré : "
                f"{level['grid_width']}x{level['grid_height']}, "
                f"{len(level.get('units', []))} unités."
            )
        except json.JSONDecodeError:
            reply_text = f"[{agent['name']}] Erreur: réponse JSON invalide."
    else:
        reply_text = f"[{agent['name']}] {raw}"

    return {
        "agent": agent_id,
        "agent_name": agent["name"],
        "reply": reply_text,
        "output_type": agent["output_type"],
    }


@app.post("/studio-learn")
def studio_learn():
    """Déclenche une vraie recherche web (Gemini grounding) pour que le
    Manager apprenne son rôle de studio de jeu vidéo. À utiliser à la
    demande (bouton dédié), pas à chaque message, pour rester gratuit."""
    prompt = (
        "Tu es sur le point de devenir le Manager IA d'un studio de jeu "
        "vidéo indépendant, spécialisé dans les tactical-RPG isométriques "
        "façon Final Fantasy Tactics. Recherche sur le web comment est "
        "structuré un studio de jeu vidéo professionnel : rôles clés, "
        "pipeline de production, bonnes pratiques de coordination d'équipe. "
        "Résume en 15-20 lignes maximum, sous forme de notes actionnables "
        "que tu réutiliseras pour diriger ton équipe d'agents IA."
    )
    notes = call_grounded(prompt)
    STATE["manager_notes"] = notes
    kv_set("manager_notes", notes)
    return {"notes": notes}


@app.get("/agents")
def list_agents():
    return STATE["agents"]


@app.get("/levels")
def list_levels():
    return [
        {"id": e["id"], "name": e["name"], "created_at": e["created_at"]}
        for e in STATE["level_history"]
    ]


@app.post("/levels/{level_id}/activate")
def activate_level(level_id: str):
    for e in STATE["level_history"]:
        if e["id"] == level_id:
            STATE["last_level"] = e["level"]
            kv_set("last_level", e["level"])
            return {"status": "ok", "name": e["name"]}
    raise HTTPException(404, "Niveau introuvable.")


@app.get("/latest-level")
def latest_level():
    if STATE["last_level"] is None:
        raise HTTPException(404, "Aucun niveau généré pour le moment.")
    return STATE["last_level"]


@app.get("/health")
def health():
    return {"status": "ok"}
