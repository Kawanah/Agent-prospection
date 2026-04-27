"""
API endpoints pour l'agent de prospection autonome.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
import json

limiter = Limiter(key_func=get_remote_address)

from app.database import get_db
from app.agent.agent_service import ProspectionAgent, AgentMode, AgentMessage

router = APIRouter()

# Store pour les sessions d'agent (en production: Redis)
agent_sessions: dict[str, ProspectionAgent] = {}
# Timestamp de dernière activité par session
_session_last_activity: dict[str, datetime] = {}

# Durée d'inactivité avant expiration (30 minutes)
SESSION_TTL = timedelta(minutes=30)


def _cleanup_expired_sessions() -> None:
    """Supprime les sessions inactives depuis plus de SESSION_TTL."""
    now = datetime.utcnow()
    expired = [
        sid for sid, last in _session_last_activity.items() if now - last > SESSION_TTL
    ]
    for sid in expired:
        agent_sessions.pop(sid, None)
        _session_last_activity.pop(sid, None)
        logger.info(f"Session agent '{sid}' expirée après inactivité")


def _touch_session(session_id: str) -> None:
    """Met à jour le timestamp d'activité d'une session."""
    _session_last_activity[session_id] = datetime.utcnow()


class ChatRequest(BaseModel):
    """Requête de chat avec l'agent."""

    message: str
    session_id: Optional[str] = "default"
    mode: Optional[str] = "supervised"  # supervised, autonomous, manual


class ChatResponse(BaseModel):
    """Réponse de l'agent."""

    session_id: str
    messages: List[dict]
    requires_human_input: bool = False
    human_question: Optional[str] = None


class HumanResponse(BaseModel):
    """Réponse humaine à une question de l'agent."""

    session_id: str
    response: str


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_with_agent(
    request: Request,
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Envoie un message à l'agent et reçoit sa réponse.

    L'agent peut:
    - Rechercher des leads
    - Analyser des sites web
    - Générer des messages personnalisés
    - Demander des validations humaines

    Exemples de messages:
    - "Trouve-moi des hôtels sans site web à Paris"
    - "Analyse le site du lead 42"
    - "Génère un email pour le lead 15"
    - "Montre-moi les statistiques"
    """
    session_id = chat_request.session_id or "default"

    # Nettoyer les sessions expirées
    _cleanup_expired_sessions()

    # Récupérer ou créer la session d'agent
    if session_id not in agent_sessions:
        mode = (
            AgentMode(chat_request.mode) if chat_request.mode else AgentMode.SUPERVISED
        )
        agent_sessions[session_id] = ProspectionAgent(db=db, mode=mode)

    _touch_session(session_id)
    agent = agent_sessions[session_id]
    # Mettre à jour la session DB
    agent.db = db

    # Traiter le message
    messages = []
    async for msg in agent.process_message(chat_request.message):
        messages.append(
            {
                "role": msg.role,
                "content": msg.content,
                "tool_calls": [
                    {"name": tc["name"], "input": tc["input"]}
                    for tc in (msg.tool_calls or [])
                ]
                if msg.tool_calls
                else None,
                "timestamp": msg.timestamp.isoformat(),
            }
        )

    return ChatResponse(
        session_id=session_id,
        messages=messages,
        requires_human_input=agent.state.requires_human_input,
        human_question=agent.state.human_question,
    )


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_with_agent_stream(
    request: Request,
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Version streaming du chat - renvoie les messages au fur et à mesure.
    Utile pour une interface en temps réel.
    """
    session_id = chat_request.session_id or "default"

    _cleanup_expired_sessions()

    if session_id not in agent_sessions:
        mode = (
            AgentMode(chat_request.mode) if chat_request.mode else AgentMode.SUPERVISED
        )
        agent_sessions[session_id] = ProspectionAgent(db=db, mode=mode)

    _touch_session(session_id)
    agent = agent_sessions[session_id]
    agent.db = db

    async def generate():
        async for msg in agent.process_message(chat_request.message):
            data = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # Envoyer l'état final
        yield f"data: {json.dumps({'done': True, 'requires_human_input': agent.state.requires_human_input})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/respond")
@limiter.limit("20/minute")
async def respond_to_agent(
    request: Request,
    human_response: HumanResponse,
    db: AsyncSession = Depends(get_db),
):
    """
    Répond à une question posée par l'agent (human-in-the-loop).

    Utilisé quand l'agent demande une validation avant d'effectuer
    une action sensible (envoi d'email, etc.)
    """
    session_id = human_response.session_id

    _cleanup_expired_sessions()

    if session_id not in agent_sessions:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    _touch_session(session_id)
    agent = agent_sessions[session_id]
    agent.db = db

    # Réinitialiser l'état
    agent.state.requires_human_input = False
    agent.state.human_question = None

    # Traiter la réponse humaine comme un nouveau message
    messages = []
    async for msg in agent.process_message(
        f"Réponse de l'utilisateur: {human_response.response}"
    ):
        messages.append(
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
        )

    return ChatResponse(
        session_id=session_id,
        messages=messages,
        requires_human_input=agent.state.requires_human_input,
        human_question=agent.state.human_question,
    )


@router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    """
    Récupère l'état actuel d'une session d'agent.
    """
    _cleanup_expired_sessions()

    if session_id not in agent_sessions:
        raise HTTPException(status_code=404, detail="Session non trouvée")

    agent = agent_sessions[session_id]

    return {
        "session_id": session_id,
        "mode": agent.state.mode.value,
        "requires_human_input": agent.state.requires_human_input,
        "human_question": agent.state.human_question,
        "pending_actions": len(agent.state.pending_actions),
        "completed_actions": len(agent.state.completed_actions),
        "conversation_length": len(agent.state.conversation_history),
        "session_started": agent.state.session_started.isoformat(),
    }


@router.delete("/session/{session_id}")
async def reset_session(session_id: str):
    """
    Réinitialise une session d'agent.
    """
    if session_id in agent_sessions:
        agent_sessions[session_id].reset_conversation()
        del agent_sessions[session_id]
    _session_last_activity.pop(session_id, None)

    return {"message": f"Session {session_id} réinitialisée"}


@router.get("/tools")
async def list_available_tools():
    """
    Liste tous les outils disponibles pour l'agent.
    Utile pour comprendre ce que l'agent peut faire.
    """
    from app.agent.agent_tools import AGENT_TOOLS

    tools_info = []
    for tool in AGENT_TOOLS:
        tools_info.append(
            {
                "name": tool["name"],
                "description": tool["description"].strip(),
                "parameters": list(tool["input_schema"]["properties"].keys()),
            }
        )

    return {"total_tools": len(tools_info), "tools": tools_info}


@router.get("/examples")
async def get_example_prompts():
    """
    Retourne des exemples de prompts pour interagir avec l'agent.
    """
    return {
        "examples": [
            {
                "category": "Recherche",
                "prompts": [
                    "Trouve-moi des hôtels sans site web",
                    "Quels sont les leads chauds à Paris ?",
                    "Cherche des campings qui n'ont pas encore été contactés",
                    "Liste les prospects avec un site de mauvaise qualité",
                ],
            },
            {
                "category": "Analyse",
                "prompts": [
                    "Analyse le site web du lead 15",
                    "Donne-moi les détails du prospect Hôtel de la Plage",
                    "Quel est le score SEO de ce lead ?",
                ],
            },
            {
                "category": "Prospection",
                "prompts": [
                    "Génère un email pour le lead 42",
                    "Rédige un message LinkedIn pour les hôtels sans site",
                    "Prépare une campagne pour les leads chauds",
                ],
            },
            {
                "category": "Statistiques",
                "prompts": [
                    "Montre-moi les statistiques",
                    "Combien de leads par segment ?",
                    "Quels sont les prospects prioritaires ?",
                ],
            },
        ]
    }
