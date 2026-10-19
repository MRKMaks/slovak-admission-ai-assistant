"""
FormService — orchestrator of the LLM dialog and updating form_data in the DB.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.repositories.session_repo import SessionRepository
from app.schemas.form import ApplicationForm
from app.services.llm_service import LLMService



# Response DTO

@dataclass
class FormServiceResponse:
    """Result of processing a single user message."""
    reply: str
    is_complete: bool
    form_data: dict[str, Any]
    session_id: uuid.UUID



# FormService

class FormService:

    def __init__(self, repo: SessionRepository, llm: LLMService) -> None:
        self.repo = repo
        self._llm = llm

    async def process_message(
        self,
        session_id: uuid.UUID,
        user_text: str,
    ) -> FormServiceResponse:
        # 1. Load session
        session = await self.repo.get_by_id(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        # 2. Load message history
        messages = await self.repo.get_messages(session_id)
        history = [{"role": m.role, "content": m.content} for m in messages]

        # 3. Deserialize current form_data → ApplicationForm
        current_form = self._deserialize_form(session.form_data or {})

        # 4. Gap Analysis
        missing = current_form.missing_required_fields()

        # 5. Build system prompt
        system_prompt = self._llm.build_system_prompt(missing=missing)

        # 6. Save user message
        await self.repo.add_message(session_id=session_id, role="user", content=user_text)

        # 7. Request to LLM (add current user message to history)
        history_with_current = [*history, {"role": "user", "content": user_text}]
        llm_response = await self._llm.chat(
            system_prompt=system_prompt,
            history=history_with_current,
        )

        # 8. Merge extracted_data with current form_data
        merged_data = _deep_merge(session.form_data or {}, llm_response.extracted_data)

        # 9. Recalculate Gap Analysis after merge
        updated_form = self._deserialize_form(merged_data)
        new_missing = updated_form.missing_required_fields()
        new_status = "completed" if not new_missing else "active"

        _PDF_TRIGGERS = {
            "pdf prihlášku vytvorí",
            "pdf prihlasku vytvorí",
            "pdf prihlasku vytvorit",
            "daj pdf",
            "daj mi pdf",
            "vytvor pdf",
            "generuj pdf",
        }
        user_lower = user_text.lower().strip()
        if any(trigger in user_lower for trigger in _PDF_TRIGGERS):
            new_status = "completed"

        # 10. Save updated form_data and status
        await self.repo.update_form_data(
            session_id,
            merged_data,
            status=new_status,
        )

        # 11. Save assistant's reply
        await self.repo.add_message(
            session_id=session_id,
            role="assistant",
            content=llm_response.reply_to_user,
        )

        # 12. Return DTO
        return FormServiceResponse(
            reply=llm_response.reply_to_user,
            is_complete=(new_status == "completed"),
            form_data=merged_data,
            session_id=session_id,
        )

    
    # Helper methods
    
    async def get_session_form(self, session_id: uuid.UUID) -> ApplicationForm:

        session = await self.repo.get_by_id(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        return self._deserialize_form(session.form_data or {})

    @staticmethod
    def _deserialize_form(data: dict[str, Any]) -> ApplicationForm:
       
        try:
            return ApplicationForm.model_validate(data)
        except Exception:
            # If data is invalid, return empty form
            # to not break the dialog due to LLM errors
            return ApplicationForm()



# Deep merge of dictionaries

def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
  
    result = dict(base)
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
