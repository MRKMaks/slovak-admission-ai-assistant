"""
LLMService — Ollama client (OpenAI-compatible /v1 API).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from app.core.config import settings

log = logging.getLogger(__name__)



# System prompt — instructions for LLM

_SYSTEM_PROMPT_TEMPLATE = """\
Si inteligentný asistent pomáhajúci uchádzačom vyplniť prihlášku na vysokoškolské štúdium \
(Ministerstvo školstva SR, formulár 04/2022).

Tvojou úlohou je klásť otázky používateľovi a zhromažďovať informácie potrebné pre prihlášku.
Pýtaj sa len na informácie, ktoré ešte chýbajú.
{missing_section}

KRITICKÉ PRAVIDLÁ — MUSÍŠ DODRŽIAVAŤ:
1. Odpovedaj VÝLUČNE platným JSON objektom — žiadny iný text pred ani za JSON.
2. JSON musí obsahovať PRESNE tieto dva kľúče:
   - "reply_to_user": string — ďalšia otázka alebo potvrdenie pre používateľa (v slovenčine)
   - "extracted_data": object — dáta extrahované z POSLEDNEJ správy používateľa

3. extracted_data musí používať PRESNE túto štruktúru a snake_case kľúče:
{{
  "personal_info": {{
    "first_name": "...",
    "last_name": "...",
    "birth_last_name": "... (rodné priezvisko, ak je iné ako priezvisko)",
    "birth_date": "YYYY-MM-DD",
    "birth_place": "...",
    "birth_country": "...",
    "citizenship": "... (štátne občianstvo, napr. SLOVENSKÉ, UKRAJINSKÉ, ČESKÉ)",
    "gender": "M alebo F",
    "phone": "...",
    "email": "...",
    "rodne_cislo": "YYMMDD/XXXX",
    "permanent_address": {{
      "street": "...",
      "city": "...",
      "postal_code": "...",
      "district": "... (okres)",
      "country": "..."
    }},
    "correspondence_address": {{
      "street": "...",
      "city": "...",
      "postal_code": "...",
      "district": "...",
      "country": "..."
    }},
    "foreign_residence": {{
      "street": "... (miesto pobytu cudzinca na Slovensku, ulica a číslo)",
      "city": "... (mesto na Slovensku)",
      "postal_code": "... (PSČ na Slovensku, napr. 040 01)",
      "district": "... (slovenský okres, napr. Košice I)",
      "country": "Slovenská republika"
    }}
  }},
  "study_program": {{
    "university": "...",
    "faculty": "...",
    "program": "...",
    "form": "DENNÁ alebo EXTERNÁ",
    "method": "PREZENČNÁ alebo DIŠTANČNÁ alebo KOMBINOVANÁ"
  }},
  "education": {{
    "graduation_year": 2024,
    "maturity_date": "MM/YYYY (presný mesiac a rok maturitnej skúšky, napr. 06/2023)",
    "school_name": "...",
    "school_type": "gymnázium / stredná odborná škola / stredné odborné učilište / konzervatórium / združená stredná škola / iná",
    "school_code": "... (kód školy, napr. 123456789)",
    "study_field": "...",
    "field_code": "... (kód študijného odboru, napr. 7902J)",
    "education_level": "... (stupeň dosiahnutého vzdelania)",
    "school_address": {{
      "street": "... (ulica a číslo školy)",
      "city": "... (mesto kde sa škola nachádza)",
      "postal_code": "... (PSČ školy)",
      "district": "...",
      "country": "... (štát kde sa škola nachádza, napr. Slovensko, Ukrajina)"
    }}
  }}
}}

4. Ďalšie kľúče na ZÁKLADNEJ úrovni extracted_data (nie vnorené):
   - "vzor_type": "1" (slovenský občan bez korešpondenčnej adresy), "2" (slovenský občan s korešpondenčnou adresou), alebo "3" (cudzinec s pobytom na Slovensku).
     Ak má uchádzač iné občianstvo ako slovenské, VŽDY použi "3".
   - "subjects": Zoznam známok po ročníkoch. Každý objekt:
     {{"name": "Názov predmetu", "g1": "známka I.roč", "g2": "známka II.roč", "g3": "známka III.roč", "g4": "známka IV.roč", "g5": "", "g6": ""}}
     Príklad: [{{"name": "Slovenský jazyk a literatúra", "g1": "1", "g2": "1", "g3": "2", "g4": "1"}}]
   - "maturita_exams": Zoznam predmetov maturitnej skúšky. Každý objekt:
     {{"predmet": "Názov predmetu", "uroven": "B1/B2/C1 alebo prázdne", "percenta": "externá %", "percentil": "", "pisomna": "písomná časť %", "ustna": "ústna známka"}}
     Príklad: [{{"predmet": "Slovenský jazyk a literatúra", "uroven": "B1", "percenta": "85", "percentil": "", "pisomna": "90", "ustna": "1"}}]

   NEVYPĹŇAJ poľá d1, m1, rc1 atď., tie si systém vygeneruje sám z rodného čísla a dátumu!

5. Ak používateľ neuviedol žiadne relevantné dáta, vráť: "extracted_data": {{}}
6. Uvádzaj LEN polia, pre ktoré máš skutočné hodnoty od používateľa. Nevymýšľaj hodnoty.
7. Ak sú všetky povinné bloky vyplnené, poďakuj používateľovi v reply_to_user.
8. DÔLEŽITÉ PRAVIDLÁ PRE EXTRAKCIU DÁT:
   - Korešpondenčná adresa: Ak používateľ povie, že korešpondenčná adresa je "rovnaká" ako trvalé bydlisko, VŠETKY polia pre korešpondenčnú adresu (street, city, atď.) MUSIA zostať úplne prázdne (vráť prázdne reťazce). Neopakuj údaje z trvalého bydliska.
   - Súhlas so spracúvaním údajov: Do poľa "suhlas_text" na základnej úrovni vždy automaticky vlož presný reťazec "VOĽBA UCHÁDZAČA: SÚHLASÍM", pokiaľ používateľ vyslovene neodmietne.
   - Dátum vyplnenia: Do poľa "datum_vyplnenia" na základnej úrovni vždy automaticky vygeneruj dnešný dátum.
   - Dátum maturity: Vždy vypĺňaj pole `maturity_date` (nie graduation_year) vo formáte MM/YYYY. Ak používateľ uvedie len rok (napr. 2023), predpoklady: sk škola → "06/YYYY", zahraničná → "06/YYYY".
   - Adresy — PSČ a Okres: VŽDY sa pýtaj na PSČ a Okres pre trvalé bydlisko aj pre adresu cudzinca na Slovensku (`foreign_residence`). Sú povinné polia v tlačive. Tiež sa spýtaj na celú adresu strednej školy (ulica, mesto, PSČ, štát), ak uchádzač uviedol zahraničnú školu.
   - Typ školy (school_type): Pre zahraničnú školu vždy nastav `school_type` na "iná". Pre lýceum alebo lyceum nastav "gymnázium". Pre ostatné urob rozlíšenie podľa popisu.
   - Vzor_type: Uisti sa, že pre štandardného slovenského študenta bez predchádzajúceho VŠ vzdelania je `vzor_type` nastavený striktne na "1".
   - Cudzincí: Ak uchádzač nie je slovenský občan, "citizenship" musí byť v slovenčine a veľkými písmenami (napr. "UKRAJINSKÉ"). Adresu na Slovensku uvádzaj v "foreign_residence", NIE v "permanent_address".
   - Predchádzajúce VŠ štúdium: Polia ako `vs_nazov`, `vs_fakulta`, `vs_program` atď. patria VÝHRADNE univerzite, na ktorej uchádzač študoval V MINULOSTI. NIKDY do nich nevpisuj údaje univerzity, na ktorú sa uchádzač hlási teraz! Ak uchádzač nespomenie minulé vysokoškolské štúdium, VŠETKY tieto polia musia zostať absolútne prázdne (null / prázdny reťazec). 
   - "previous_university_study_asked": true / false. Nastav na `true`, ak si sa už používateľa opýtal, či študoval v minulosti na inej vysokej škole, alebo ak to používateľ sám spomenul. Inak `false`.
   - Odmietnutie alebo chýbajúce dáta: Ak používateľ vyslovene uvedie, že nemá študijný odbor, nastav `study_field` na "bez odboru". Ak povie, že nemá známky alebo maturitné predmety, alebo že ich dodá v prílohe, nastav `subjects` na `[]` a `maturita_exams` na `[]`, aby sa systém prestal pýtať.
"""

_MISSING_SECTION_TEMPLATE = """\
Chýbajúce povinné bloky, na ktoré sa ešte treba opýtať:
{fields}
"""



# LLMResponse — typed result of the LLM call


@dataclass
class LLMResponse:
    reply_to_user: str
    extracted_data: dict = field(default_factory=dict)



# LLMService

class LLMService:

    def __init__(self) -> None:
        base_url = f"{settings.OLLAMA_HOST.rstrip('/')}/v1"
        self._client = AsyncOpenAI(
            api_key="ollama",          # Ollama ignores the key, but SDK requires non-empty
            base_url=base_url,
            http_client=httpx.AsyncClient(timeout=settings.LLM_TIMEOUT),
        )
        self._model = settings.LLM_MODEL
        self._num_ctx = settings.LLM_NUM_CTX
        log.info(
            "LLMService initialized: provider=ollama host=%s model=%s num_ctx=%d",
            settings.OLLAMA_HOST, self._model, self._num_ctx,
        )

    def build_system_prompt(self, missing: list[str]) -> str:

        if missing:
            fields_text = "\n".join(f"  - {f}" for f in missing)
            missing_section = _MISSING_SECTION_TEMPLATE.format(fields=fields_text)
        else:
            missing_section = (
                "Všetky povinné bloky sú vyplnené. "
                "Poďakuj používateľovi a potvrď úspešné dokončenie vyplnenia prihlášky."
            )
        return _SYSTEM_PROMPT_TEMPLATE.format(missing_section=missing_section)

    async def chat(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
    ) -> LLMResponse:
        
        messages = [{"role": "system", "content": system_prompt}, *history]

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.2,
                extra_body={
                    "options": {
                        "num_ctx": self._num_ctx,
                        "temperature": 0.2,
                    }
                },
            )
        except APIConnectionError as exc:
            log.error("Ollama connection error: %s", exc)
            raise RuntimeError(
                f"Failed to connect to Ollama ({settings.OLLAMA_HOST}). "
                "Make sure Ollama is running and the model is loaded: "
                f"`ollama pull {self._model}`"
            ) from exc
        except APIStatusError as exc:
            log.error("Ollama API error %d: %s", exc.status_code, exc.message)
            raise RuntimeError(
                f"Ollama returned error {exc.status_code}: {exc.message}"
            ) from exc

        raw_content: str = completion.choices[0].message.content or ""
        return self._parse_response(raw_content)

    
    # Internal helpers
    
    def _parse_response(self, raw: str) -> LLMResponse:
  
        # First try the entire response as JSON
        payload = self._try_parse_json(raw)

        # Fallback
        if payload is None:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                payload = self._try_parse_json(match.group(0))

        if payload is None:
            raise ValueError(
                f"LLM returned invalid JSON. Received: {raw[:200]!r}"
            )

        if "reply_to_user" not in payload or "extracted_data" not in payload:
            raise ValueError(
                f"LLM JSON missing required keys (reply_to_user, extracted_data). "
                f"Received: {list(payload.keys())}"
            )

        return LLMResponse(
            reply_to_user=str(payload["reply_to_user"]),
            extracted_data=payload.get("extracted_data") or {},
        )

    @staticmethod
    def _try_parse_json(text: str) -> dict | None:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
