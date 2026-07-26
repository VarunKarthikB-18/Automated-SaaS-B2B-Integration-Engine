"""
cleaner.py – Data Transformation Module
Standardises incoming raw customer payloads:
  • Strip / normalise whitespace
  • Format dates → ISO-8601
  • Handle null / missing values
"""

import re
import logging
from typing import Any
from datetime import datetime, date
from dateutil import parser as date_parser          # pip install python-dateutil

logger = logging.getLogger("integration_engine.cleaner")

# ── Constants ──────────────────────────────────────────────────────────────────
_NULL_SENTINELS = {
    None, "", "null", "NULL", "Null", "none", "None", "NONE",
    "n/a", "N/A", "na", "NA", "undefined", "UNDEFINED", "-",
}

_DATE_FIELDS = {
    "signup_date", "created_at", "updated_at", "trial_end_date",
    "contract_start", "contract_end", "dob", "date_of_birth",
    "subscription_date",
}

_BOOL_FIELDS = {
    "is_active", "active", "enabled", "verified", "is_verified",
}

_NUMERIC_FIELDS = {
    "mrr", "arr", "monthly_recurring_revenue", "annual_revenue",
    "seat_count", "seats",
}


class DataCleaner:
    """
    Stateless transformer.  Call `clean(raw_dict)` to receive a normalised dict.
    """

    # ── Public API ─────────────────────────────────────────────────────────────
    def clean(self, raw: dict[str, Any]) -> dict[str, Any]:
        """
        Iterate every key-value pair in the raw payload and apply the
        appropriate cleaning strategy.  Unknown keys are passed through as
        cleaned strings so the mapping agent can still handle them.
        """
        result: dict[str, Any] = {}

        for key, value in raw.items():
            normalised_key = self._normalise_key(key)
            cleaned_value = self._clean_value(normalised_key, value)
            result[normalised_key] = cleaned_value

        logger.debug("Cleaned payload: %s", result)
        return result

    # ── Key normalisation ──────────────────────────────────────────────────────
    @staticmethod
    def _normalise_key(key: str) -> str:
        """
        Lower-case, strip surrounding whitespace, replace spaces / dashes /
        dots with underscores, collapse repeated underscores.
        """
        if not isinstance(key, str):
            key = str(key)
        key = key.strip().lower()
        key = re.sub(r"[\s\-\.]+", "_", key)   # spaces, hyphens, dots → _
        key = re.sub(r"_+", "_", key)           # collapse duplicates
        key = re.sub(r"[^\w]", "", key)         # strip anything non-word
        return key

    # ── Value dispatch ─────────────────────────────────────────────────────────
    def _clean_value(self, key: str, value: Any) -> Any:
        if self._is_null(value):
            return None

        if key in _DATE_FIELDS:
            return self._parse_date(value)

        if key in _BOOL_FIELDS:
            return self._parse_bool(value)

        if key in _NUMERIC_FIELDS:
            return self._parse_numeric(value)

        if isinstance(value, str):
            return self._clean_string(value)

        # Nested dict – recurse
        if isinstance(value, dict):
            return self.clean(value)

        # Lists – clean each element
        if isinstance(value, list):
            return [self._clean_value(key, item) for item in value]

        return value  # int, float, bool – already clean

    # ── Type helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _is_null(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip() in _NULL_SENTINELS:
            return True
        return False

    @staticmethod
    def _clean_string(value: str) -> str:
        """Collapse internal whitespace runs, strip edges."""
        value = value.strip()
        value = re.sub(r"\s+", " ", value)   # collapse internal whitespace
        return value

    @staticmethod
    def _parse_date(value: Any) -> str | None:
        """
        Convert any recognisable date-like string to ISO-8601 (YYYY-MM-DD).
        Returns None if parsing fails rather than raising.
        """
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d")

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()
        if not value or value in _NULL_SENTINELS:
            return None

        try:
            parsed = date_parser.parse(value, dayfirst=False)
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            logger.warning("Could not parse date value: %r", value)
            return None

    @staticmethod
    def _parse_bool(value: Any) -> bool | None:
        """Interpret common truthy / falsy representations."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "yes", "1", "on", "active", "enabled"}:
                return True
            if v in {"false", "no", "0", "off", "inactive", "disabled"}:
                return False
        return None

    @staticmethod
    def _parse_numeric(value: Any) -> float | None:
        """Strip currency symbols / commas and return a float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d\.\-]", "", value.strip())
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
