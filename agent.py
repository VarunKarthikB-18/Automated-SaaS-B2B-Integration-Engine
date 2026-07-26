"""
agent.py – LLM Column Mapping Agent
Uses Google Gemini (gemini-2.0-flash) to translate arbitrary incoming column
names → canonical database schema field names, with a rule-based + fuzzy
fallback when no API key is configured.
"""

import os
import json
import logging
import re
from typing import Any

logger = logging.getLogger("integration_engine.agent")

# ── Canonical target schema ────────────────────────────────────────────────────
CANONICAL_SCHEMA = {
    "first_name":   "Customer's given / first name",
    "last_name":    "Customer's family / last name",
    "email":        "Primary email address",
    "phone_number": "Primary phone number (any format)",
    "company_name": "Legal company / organisation name",
    "plan_type":    "Subscription plan tier (e.g. free, starter, pro, enterprise)",
    "signup_date":  "ISO-8601 date when the customer signed up (YYYY-MM-DD)",
    "country":      "ISO 3166-1 alpha-2 country code or full country name",
    "mrr":          "Monthly recurring revenue in USD (numeric)",
    "is_active":    "Boolean – whether the account is currently active",
}

# ── Hard-coded alias fallback ──────────────────────────────────────────────────
_FALLBACK_RULES: dict[str, str] = {
    # name variants
    "fname": "first_name", "given_name": "first_name", "firstname": "first_name",
    "lname": "last_name", "surname": "last_name", "lastname": "last_name",
    "full_name": "first_name",
    # contact
    "cell_phone": "phone_number", "cell_phone_v2": "phone_number",
    "mobile": "phone_number", "mobile_number": "phone_number",
    "telephone": "phone_number", "phone": "phone_number",
    "primary_phone": "phone_number", "contact_phone": "phone_number",
    "email_address": "email", "primary_email": "email",
    # company
    "company": "company_name", "organization": "company_name",
    "organisation": "company_name", "account_name": "company_name",
    "corp": "company_name", "business_name": "company_name",
    # plan
    "plan": "plan_type", "tier": "plan_type", "subscription_tier": "plan_type",
    "subscription_plan": "plan_type", "package": "plan_type",
    # dates
    "created_at": "signup_date", "joined_at": "signup_date",
    "registration_date": "signup_date", "start_date": "signup_date",
    "onboarding_date": "signup_date",
    # revenue
    "mrr_usd": "mrr", "monthly_revenue": "mrr",
    "monthly_recurring_revenue": "mrr", "revenue": "mrr",
    # status
    "active": "is_active", "status": "is_active", "enabled": "is_active",
    "account_status": "is_active",
    # geo
    "country_code": "country", "region": "country", "location": "country",
    "billing_country": "country",
}


class ColumnMappingAgent:
    """
    Maps an arbitrary dict of cleaned data fields to the canonical schema.

    Strategy:
      1. Exact canonical match → keep as-is
      2. Hard-coded alias rules → remap
      3. Gemini LLM → ask the model to predict the best match
      4. Fuzzy token overlap → last-resort fallback when LLM is unavailable
    """

    def __init__(self) -> None:
        self._model = None
        self._model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._init_gemini()

    def _init_gemini(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                "GEMINI_API_KEY not set – LLM column mapping disabled; "
                "falling back to rule-based mapper only."
            )
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(self._model_name)
            logger.info("Gemini client initialised (model=%s)", self._model_name)
        except ImportError:
            logger.warning(
                "google-generativeai package not installed – LLM disabled. "
                "Run: pip install google-generativeai"
            )

    # ── Public API ─────────────────────────────────────────────────────────────
    async def map_columns(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Accepts a cleaned data dict and returns a new dict whose keys are
        canonical schema column names.  Fields that cannot be mapped are
        silently dropped (logged at DEBUG level).
        """
        canonical: dict[str, Any] = {}
        unmapped:  dict[str, Any] = {}

        for key, value in data.items():
            if key in CANONICAL_SCHEMA:
                canonical[key] = value
            elif key in _FALLBACK_RULES:
                target = _FALLBACK_RULES[key]
                logger.debug("Rule map: %r → %r", key, target)
                canonical[target] = value
            else:
                unmapped[key] = value

        # Ask Gemini for anything still unmapped
        if unmapped and self._model:
            llm_mappings = self._llm_map(list(unmapped.keys()))
            for src_key, tgt_key in llm_mappings.items():
                if tgt_key in CANONICAL_SCHEMA and src_key in unmapped:
                    logger.info("Gemini map: %r → %r", src_key, tgt_key)
                    canonical[tgt_key] = unmapped[src_key]
                else:
                    logger.debug(
                        "Gemini returned unknown target %r for %r – skipping",
                        tgt_key, src_key,
                    )
        elif unmapped:
            # No LLM – attempt fuzzy token match
            for key in unmapped:
                guessed = self._fuzzy_match(key)
                if guessed:
                    logger.info("Fuzzy map: %r → %r", key, guessed)
                    canonical[guessed] = unmapped[key]
                else:
                    logger.debug("Could not map column %r – dropping", key)

        return canonical

    # ── Gemini call ───────────────────────────────────────────────────────────
    def _llm_map(self, unmapped_keys: list[str]) -> dict[str, str]:
        """
        Send unmapped column names to Gemini and parse the JSON response.
        Returns { source_key: canonical_key } for confident mappings only.
        """
        schema_str = "\n".join(
            f"  {col}: {desc}" for col, desc in CANONICAL_SCHEMA.items()
        )
        keys_str = "\n".join(f"  - {k}" for k in unmapped_keys)

        prompt = (
            "You are a data integration assistant.\n\n"
            "CANONICAL DATABASE SCHEMA (the only valid target column names):\n"
            f"{schema_str}\n\n"
            "UNMAPPED SOURCE COLUMNS (incoming from a customer's system):\n"
            f"{keys_str}\n\n"
            "Task: For each source column, predict the BEST matching canonical "
            "column name from the schema above. If no confident match exists, "
            "output null for that entry.\n\n"
            "Respond ONLY with a valid JSON object, for example:\n"
            '{"cell_phone_v2": "phone_number", "unknownXYZ": null}'
        )

        try:
            response = self._model.generate_content(prompt)
            raw = response.text.strip()
            # Extract JSON even if the model wraps it in markdown fences
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON object found in Gemini response")
            mapping: dict[str, str | None] = json.loads(json_match.group())
            return {k: v for k, v in mapping.items() if v is not None}
        except Exception as exc:
            logger.error("Gemini mapping call failed: %s", exc)
            return {}

    # ── Fuzzy fallback ────────────────────────────────────────────────────────
    @staticmethod
    def _fuzzy_match(key: str) -> str | None:
        """Simple token-overlap scoring when the LLM is unavailable."""
        key_tokens = set(re.split(r"[_\s]+", key.lower()))
        best_target: str | None = None
        best_score = 0

        for canonical in CANONICAL_SCHEMA:
            canonical_tokens = set(re.split(r"[_\s]+", canonical.lower()))
            overlap = len(key_tokens & canonical_tokens)
            if overlap > best_score:
                best_score = overlap
                best_target = canonical

        return best_target if best_score > 0 else None
