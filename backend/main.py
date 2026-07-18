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
  GEMINI_API_KEY   -> AQ.Ab8RN6IZDYHb1QzlPqeJfuCLCSgPnwD2g5LkubiXd0s1umlS7Q
  SUPABASE_URL     -> https://acygynvrlutuezjdhetd.supabase.co
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

def extract_json(raw: str) -> dict:
    """Extrait un objet JSON même si le modèle a ajouté du texte ou des
    balises markdown autour, en repérant la première { et la dernière }."""
    cleaned = raw.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("Aucun objet JSON trouvé", cleaned, 0)
    return json.loads(cleaned[start:end + 1])


GEMINI_MODEL = "gemini-flash-latest"  # alias qui pointe toujours vers le Flash le plus récent

STUDIO_AGENT_IDS = {
    "game_designer", "level_designer", "narratif", "artiste",
    "sound_designer", "programmeur",
    "technicien_reseau", "visionnaire", "controleur_3d",
    "ergonomie", "optimisation_temps_reel",
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
        "technicien_reseau": {
            "name": "Technicien Réseaux & Compatibilité",
            "system_prompt": """Tu es le Technicien Réseaux et Compatibilité du studio.
Tu analyses les problèmes de connexion (backend, API, hébergement gratuit),
de compatibilité entre appareils/versions (Android, Godot, navigateurs), et
proposes des solutions concrètes et diagnostics étape par étape. Réponds en
texte libre, concis, orienté résolution de problème.""",
            "output_type": "text",
            "parent_id": None,
        },
        "visionnaire": {
            "name": "Visionnaire",
            "system_prompt": """Tu es le Visionnaire du studio : direction créative à long
terme. Tu proposes des idées ambitieuses et cohérentes pour faire évoluer le
jeu (mécaniques futures, identité de la licence, ambitions à moyen/long
terme), sans te soucier des contraintes techniques immédiates — c'est le
rôle des autres agents. Réponds en texte libre, inspirant, 5-10 lignes.""",
            "output_type": "text",
            "parent_id": None,
        },
        "controleur_3d": {
            "name": "Contrôleur de Code & Rendu 3D",
            "system_prompt": """Tu es le Contrôleur Qualité, spécialisé code et rendu 3D
(Godot/GDScript). Tu relis un extrait de code ou une description de scène et
signales les erreurs probables, problèmes de performance de rendu 3D
(nombre de draw calls, éclairage, LOD), et bonnes pratiques Godot 4.
Réponds en texte libre, concret, avec des corrections précises si possible.""",
            "output_type": "text",
            "parent_id": None,
        },
        "ergonomie": {
            "name": "Ergonomie / UX",
            "system_prompt": """Tu es le responsable Ergonomie et Expérience Utilisateur
du studio. Tu évalues l'utilisabilité d'une interface ou d'un flux de jeu
(clarté, accessibilité, friction sur mobile) et proposes des améliorations
concrètes et priorisées. Réponds en texte libre, 5-8 lignes.""",
            "output_type": "text",
            "parent_id": None,
        },
        "optimisation_temps_reel": {
            "name": "Optimisation Temps Réel",
            "system_prompt": """Tu es l'agent Optimisation Temps Réel : tu surveilles la
performance de l'application ForgeGameIA elle-même (temps de réponse du
backend, coûts d'appel aux API IA, taille des requêtes) et proposes des
optimisations concrètes et mesurables. Réponds en texte libre, orienté
métriques et actions priorisées.""",
            "output_type": "text",
            "parent_id": None,
        },
    }


MAX_PROJECTS = 5


def default_project(name: str) -> dict:
    return {"name": name, "last_level": None, "level_history": []}


STATE = {
    "agents": seed_agents(),
    "manager_notes": "",
    "projects": {},          # id -> {name, last_level, level_history}
    "active_project_id": None,
}

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
    STATE["manager_notes"] = kv_get("manager_notes", "")
    STATE["projects"] = kv_get("projects", {})
    STATE["active_project_id"] = kv_get("active_project_id", None)

    if not STATE["projects"]:
        import uuid
        pid = uuid.uuid4().hex[:8]
        STATE["projects"][pid] = default_project("Projet 1")
        STATE["active_project_id"] = pid
        kv_set("projects", STATE["projects"])
        kv_set("active_project_id", pid)
    elif STATE["active_project_id"] not in STATE["projects"]:
        STATE["active_project_id"] = next(iter(STATE["projects"]))
        kv_set("active_project_id", STATE["active_project_id"])


def save_agents():
    kv_set("agents", STATE["agents"])


def save_projects():
    kv_set("projects", STATE["projects"])


def active_project() -> dict:
    return STATE["projects"][STATE["active_project_id"]]


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


def get_groq_client():
    try:
        from groq import Groq
    except ImportError:
        return None
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def call_groq(system: str, message: str) -> str:
    """Solution de secours gratuite (modèles open source, via Groq) quand
    le quota gratuit de Gemini est épuisé. Ne gère pas les pièces jointes."""
    client = get_groq_client()
    if client is None:
        raise RuntimeError("GROQ_API_KEY manquante — pas de solution de secours disponible.")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        max_tokens=1500,
    )
    return (response.choices[0].message.content or "").strip()


def _is_quota_error(e: Exception) -> bool:
    s = str(e)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _with_retry(fn, attempts: int = 3):
    """Réessaie automatiquement en cas de surcharge temporaire (503) de l'API."""
    import time
    last_error = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(2 * (i + 1))
                continue
            raise
    raise last_error


def call_agent(system: str, message: str, attachments: list) -> str:
    from google.genai import types
    client = get_gemini_client()
    parts = [types.Part.from_text(text=message)] + attachments_to_parts(attachments)

    def _do():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=1500),
        )
        return (response.text or "").strip()

    try:
        return _with_retry(_do)
    except Exception as e:
        if _is_quota_error(e):
            # Quota Gemini épuisé : secours gratuit via Groq (texte seul,
            # les pièces jointes ne sont pas transmises dans ce mode).
            return call_groq(system, message)
        raise


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

    def _do():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=manager_system_prompt(), max_output_tokens=400
            ),
        )
        return (response.text or "").strip()

    try:
        raw = _with_retry(_do)
    except Exception as e:
        if _is_quota_error(e):
            raw = call_groq(manager_system_prompt(), message)
        else:
            raise
    try:
        decision = extract_json(raw)
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
    project = active_project()

    if agent["output_type"] == "level_json":
        try:
            try:
                level = extract_json(raw)
            except json.JSONDecodeError:
                # Le modèle a peut-être ajouté du texte malgré la consigne :
                # on retente une fois en le lui redemandant plus strictement.
                raw_retry = call_agent(
                    agent["system_prompt"] + "\n\nRAPPEL: réponds UNIQUEMENT avec l'objet JSON, rien d'autre.",
                    req.message, req.attachments,
                )
                level = extract_json(raw_retry)

            project["last_level"] = level

            import uuid
            import datetime
            entry = {
                "id": uuid.uuid4().hex[:8],
                "name": level.get("name", "Niveau sans nom"),
                "created_at": datetime.datetime.utcnow().isoformat(),
                "level": level,
            }
            project["level_history"].insert(0, entry)
            project["level_history"] = project["level_history"][:20]
            save_projects()

            reply_text = (
                f"[{agent['name']}] Niveau \"{level.get('name', '?')}\" généré : "
                f"{level['grid_width']}x{level['grid_height']}, "
                f"{len(level.get('units', []))} unités."
            )
        except json.JSONDecodeError:
            reply_text = f"[{agent['name']}] Erreur: réponse JSON invalide même après une nouvelle tentative."
    else:
        reply_text = f"[{agent['name']}] {raw}"

    return {
        "agent": agent_id,
        "agent_name": agent["name"],
        "reply": reply_text,
        "output_type": agent["output_type"],
        "project_id": STATE["active_project_id"],
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


# ---------------------------------------------------------------------
# Projets (jusqu'à 5 en parallèle, chacun avec son propre historique)
# ---------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str


@app.get("/projects")
def list_projects():
    return {
        "active_project_id": STATE["active_project_id"],
        "projects": [
            {"id": pid, "name": p["name"], "level_count": len(p["level_history"])}
            for pid, p in STATE["projects"].items()
        ],
    }


@app.post("/projects")
def create_project(req: ProjectCreate):
    if len(STATE["projects"]) >= MAX_PROJECTS:
        raise HTTPException(400, f"Limite de {MAX_PROJECTS} projets atteinte. Supprime-en un pour en créer un nouveau.")
    import uuid
    pid = uuid.uuid4().hex[:8]
    STATE["projects"][pid] = default_project(req.name or f"Projet {len(STATE['projects']) + 1}")
    STATE["active_project_id"] = pid
    save_projects()
    kv_set("active_project_id", pid)
    return {"id": pid, "name": STATE["projects"][pid]["name"]}


@app.post("/projects/{project_id}/activate")
def activate_project(project_id: str):
    if project_id not in STATE["projects"]:
        raise HTTPException(404, "Projet introuvable.")
    STATE["active_project_id"] = project_id
    kv_set("active_project_id", project_id)
    return {"status": "ok", "name": STATE["projects"][project_id]["name"]}


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    if project_id not in STATE["projects"]:
        raise HTTPException(404, "Projet introuvable.")
    if len(STATE["projects"]) <= 1:
        raise HTTPException(400, "Impossible de supprimer le dernier projet restant.")
    del STATE["projects"][project_id]
    save_projects()
    if STATE["active_project_id"] == project_id:
        STATE["active_project_id"] = next(iter(STATE["projects"]))
        kv_set("active_project_id", STATE["active_project_id"])
    return {"status": "ok"}


@app.get("/levels")
def list_levels():
    project = active_project()
    return [
        {"id": e["id"], "name": e["name"], "created_at": e["created_at"]}
        for e in project["level_history"]
    ]


@app.post("/levels/{level_id}/activate")
def activate_level(level_id: str):
    project = active_project()
    for e in project["level_history"]:
        if e["id"] == level_id:
            project["last_level"] = e["level"]
            save_projects()
            return {"status": "ok", "name": e["name"]}
    raise HTTPException(404, "Niveau introuvable.")


@app.get("/latest-level")
def latest_level():
    project = active_project()
    if project["last_level"] is None:
        raise HTTPException(404, "Aucun niveau généré pour le moment.")
    return project["last_level"]


@app.get("/health")
def health():
    return {"status": "ok"}
