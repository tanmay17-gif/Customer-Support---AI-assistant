"""
Gemini LLM Service — handles all three AI jobs:
  1. Extract structured data from OCR text
  2. Decide resolution action
  3. Draft customer reply content
"""
import asyncio
import json
import re
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class GeminiLLMService:
    """Singleton Gemini client. Call get_instance() to obtain it."""

    _instance: Optional["GeminiLLMService"] = None

    def __init__(self):
        # Use the new google-genai SDK which supports AQ. style API keys
        from google import genai
        from google.genai import types

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")

        self._primary_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Use second key if provided, else fallback to primary key for safety/compatibility
        auditor_key = settings.GEMINI_API_KEY_2 if settings.GEMINI_API_KEY_2 else settings.GEMINI_API_KEY
        self._auditor_client = genai.Client(api_key=auditor_key)
        
        self._model = settings.LLM_MODEL
        self._types = types
        logger.info(f"Gemini LLM service ready (Dual agents, model={self._model})")

    @classmethod
    def get_instance(cls) -> "GeminiLLMService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Helper ──────────────────────────────────────────────────────────────
    def _parse_json_safe(self, text: str) -> dict:
        """Robustly parse JSON even if wrapped in markdown fences."""
        text = text.strip()
        # Strip ```json ... ``` fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    async def _generate(self, prompt: str, response_mime_type: str = "text/plain", client_type: str = "primary") -> str:
        """Run a Gemini generate call using the specified client in a thread."""
        config = self._types.GenerateContentConfig(
            response_mime_type=response_mime_type,
        )

        client = self._auditor_client if client_type == "auditor" else self._primary_client

        def _sync_call():
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return response.text

        return await asyncio.to_thread(_sync_call)

    # ── Job 1 — Extract invoice data ─────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def extract_invoice_data(self, ocr_text: str) -> dict:
        """
        Sends OCR text to Gemini; returns {order_id, item, amount}.
        Fields are None when not found.
        """
        prompt = f"""You are an OCR data extractor. Extract the following fields from the receipt/invoice text below.

Return ONLY valid JSON with exactly these keys:
{{
  "order_id": "ORD-XXXX or null",
  "item": "product name or null",
  "amount": 0.00 or null
}}

Rules:
- order_id: look for patterns like ORD-XXXX, Order #XXXX, Invoice #XXXX
- amount: the TOTAL amount paid as a number (no currency symbols)
- item: the main product name
- If a field is not present, use null (not the string "null")

Receipt/Invoice text:
---
{ocr_text}
---"""
        try:
            text = await self._generate(prompt, response_mime_type="application/json")
            result = self._parse_json_safe(text)
            logger.info(f"Extracted: {result}")
            return result
        except Exception as e:
            logger.warning(f"Extraction failed: {e}")
            return {"order_id": None, "item": None, "amount": None}

    # ── Job 2 — Decide action ────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def decide_action(
        self,
        email_body: str,
        order: Optional[dict],
        policy_context: str,
    ) -> dict:
        """
        Decides one of: refund | replace | reissue_invoice | escalate.
        Returns {action, reasoning}.
        """
        order_str = json.dumps(order, default=str) if order else "ORDER NOT FOUND IN SYSTEM"

        prompt = f"""You are a customer support decision engine. Based on the customer email, the matched order record, and the relevant policy, decide the SINGLE best action.

CUSTOMER EMAIL:
{email_body}

ORDER RECORD:
{order_str}

RELEVANT POLICY:
{policy_context}

ACTIONS available:
- "refund": customer received damaged/wrong item OR was overcharged, within policy window
- "replace": customer wants replacement for wrong/damaged item, within policy window
- "reissue_invoice": invoice amount is incorrect or tax breakdown is missing
- "request_info": order is not found, missing, or ambiguous. Ask the customer for their exact Order ID.
- "answer_query": the customer's question can be answered using the provided ORDER RECORD or CUSTOMER HISTORY. (e.g. tracking status, payment confirmation, policy inquiry)
- "escalate": unclear situation, sensitive issue, outside policy window, or technical/warranty issue

IMPORTANT:
- First, check if the issue can be resolved using existing database info (order status, refund info). If yes, choose "answer_query".
- If order is NOT FOUND or the customer didn't provide one, always choose "request_info" (unless you can answer their general question from the policy).
- If the issue is technical (app crash, login, etc.), always escalate.
- If the claim seems legitimate and within policy, be helpful — refund or replace.
- If unsure between refund and escalate, choose escalate.

Return ONLY valid JSON:
{{
  "action": "refund|replace|reissue_invoice|request_info|answer_query|escalate",
  "reasoning": "one sentence plain English explanation"
}}"""
        try:
            text = await self._generate(prompt, response_mime_type="application/json")
            logger.info(f"LLM RAW DECISION OUTPUT:\n{text}")
            result = self._parse_json_safe(text)
            logger.info(f"Decision: {result}")
            return result
        except Exception as e:
            err_msg = str(e).replace('\n', ' ')
            logger.error(f"Decision failed: {err_msg}")
            return {"action": "escalate", "reasoning": f"System Error during decision: {err_msg}"}

    # ── Job 3 — Draft reply content ──────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def draft_reply_content(
        self,
        action: str,
        order: Optional[dict],
        customer_name: str,
        original_email_body: str,
        action_summary: str,
        attachment_names: list[str] = None,
        company_name: str = "Customer Support",
    ) -> dict:
        """
        Returns {action_summary, body_paragraphs: list[str], timeline_steps: list[dict]}.
        Timeline step dict: {icon, color, title, description}
        """
        order_str = json.dumps(order, default=str) if order else "NOT FOUND IN SYSTEM"
        
        attachment_context = ""
        if attachment_names:
            names_str = ", ".join(attachment_names)
            attachment_context = f"\nFiles attached to this email: {names_str}\n"
            
        prompt = f"""You are a customer support agent writing a direct status update email AFTER completing the following action.

Action taken: {action}
Action summary: {action_summary}
Customer name: {customer_name}
Company name: {company_name}
Order details: {order_str}
Original customer email: {original_email_body[:500]}{attachment_context}

Write exactly ONE paragraph of body text in plain active voice. 
CRITICAL REQUIREMENTS FOR THIS PARAGRAPH:
1. Reassurance through specificity: You MUST name the specific item/issue the customer described, and state the specific action taken (e.g. "we're sending a replacement Wireless Mouse").
2. Explicitly restate the order ID the customer mentioned (or mention if they didn't provide one).
3. State a concrete timeframe/next step. For resolved cases use e.g. "you'll receive a shipping confirmation within 24 hours". For escalations use e.g. "a human agent will respond within 1 business day".
4. If the action is "request_info", politely explain that we cannot find their order and ask them to reply with the correct Order ID or a copy of their receipt.
5. If the action is "answer_query", directly answer their question clearly using the provided order details or context.
6. If the case is escalated, state plainly WHY it couldn't be resolved automatically. Do NOT use vague placeholders. Use the real reason from the Action summary.
7. Always conclude the paragraph with a sign-off explicitly mentioning the Company name (e.g., "— The {company_name} Support Team").

CRITICAL RULES:
- Explicitly ban all empty empathy phrasing (e.g. "I completely understand your eagerness," "as quickly as possible," "top priority," "thank you for reaching out to us" as an opener).
- Empathy phrasing is only allowed when paired with a concrete fact — no empathy-only filler.
- If files are attached, you MUST explicitly reference them by name in the body text (e.g., "we have attached invoice_ORD1005.png for your reference").

Return ONLY valid JSON:
{{
  "body_paragraph": "your single paragraph text here"
}}"""
        try:
            text = await self._generate(prompt, response_mime_type="application/json")
            logger.info(f"LLM RAW DRAFT OUTPUT:\n{text}")
            result = self._parse_json_safe(text)
            return result
        except Exception as e:
            err_msg = str(e).replace('\n', ' ')
            logger.error(f"Draft reply failed: {err_msg}")
            return {
                "body_paragraph": f"System Error drafting reply: {err_msg}"
            }

    # ── Job 4 — Auditor Critic Agent ─────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def audit_decision(
        self,
        primary_action: str,
        primary_reasoning: str,
        email_body: str,
        ocr_text: str,
        attachment_filename: Optional[str],
        order: Optional[dict],
        policy_context: str,
        customer_history_claims_count: int = 0,
    ) -> dict:
        """
        Independent Auditor Critic Agent — audits primary decision for:
        1. Policy document compliance
        2. Receipt / OCR tampering or metadata mismatch
        3. Excessive claim frequency / fraud pattern
        Returns {verdict: "AGREE"|"VETO", risk_score: int, reasons: list[str], flags: list[str]}
        """
        prompt = f"""You are an independent Senior Forensic Auditor & Fraud Critic Agent. Audit the proposed automated resolution decision.

PRIMARY PROPOSED DECISION:
Action: {primary_action}
Reasoning: {primary_reasoning}

CUSTOMER EMAIL:
{email_body}

ATTACHMENT OCR TEXT:
{ocr_text or 'NO OCR ATTACHMENT'}
Filename: {attachment_filename or 'None'}

MATCHED ORDER RECORD:
{json.dumps(order, default=str) if order else 'ORDER NOT FOUND'}

POLICY CONTEXT:
{policy_context}

CUSTOMER RETURN CLAIM HISTORY:
{customer_history_claims_count} previous claims in last 90 days.

AUDIT RULES:
1. VETO if the primary decision violates policy (e.g. refunding an order not found, or over-the-limit replacement).
2. VETO if attachment or OCR text shows signs of tampering, font inconsistencies, fake receipt markers, or amount mismatch > $0.50 between OCR and database.
3. VETO if customer has > 3 refund claims in 90 days.
4. If OCR text or filename contains words like "fake", "manipulated", "edited", "photoshop", or date anomalies -> flag POSSIBLY_TAMPERED_RECEIPT and VETO immediately.
5. If sound and compliant -> AGREE with risk_score < 20.

Return ONLY valid JSON:
{{
  "verdict": "AGREE" or "VETO",
  "risk_score": 0 to 100,
  "reasons": ["explanation of audit finding"],
  "flags": ["POSSIBLY_TAMPERED_RECEIPT", "CLAIM_FREQUENCY_HIGH", "AMOUNT_MISMATCH", "POLICY_VIOLATION"]
}}"""
        try:
            text = await self._generate(prompt, response_mime_type="application/json", client_type="auditor")
            result = self._parse_json_safe(text)
            logger.info(f"Auditor Critic Verdict: {result}")
            return result
        except Exception as e:
            logger.warning(f"Auditor audit failed ({e}), defaulting to conservative VETO for safety")
            return {
                "verdict": "VETO",
                "risk_score": 75,
                "reasons": [f"Auditor engine error: {e}"],
                "flags": ["AUDITOR_SYSTEM_ERROR"]
            }

    # ── Job 5 — Self-Improving Policy Loop Amendment Generator ─────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def draft_policy_amendment(
        self,
        business_id: str,
        overrides: list[dict],
    ) -> dict:
        """
        Drafts a plain-language policy amendment based on accumulated human agent overrides.
        Returns {title: str, proposed_diff: str, reasoning: str}
        """
        overrides_str = json.dumps(overrides, indent=2)
        prompt = f"""You are a Customer Support Policy Architect. Analyze the following human agent override records for business '{business_id}' and synthesize a single, clear policy amendment.

HUMAN OVERRIDE RECORDS:
{overrides_str}

TASK:
Write a clean, plain-language policy clause addition (proposed_diff) that, if added to the policy document, would make future AI decisions match what the human agents decided in these cases.

Return ONLY valid JSON:
{{
  "title": "Clear 5-10 word title of proposed policy rule",
  "proposed_diff": "Plain language policy clause addition in markdown bullet points",
  "reasoning": "Explanation citing how this proposal solves the override pattern across the cases"
}}"""
        try:
            text = await self._generate(prompt, response_mime_type="application/json")
            return self._parse_json_safe(text)
        except Exception as e:
            return {
                "title": f"Policy Rule Update for {business_id}",
                "proposed_diff": "- Human agent consensus rule: Handle escalated claims with standard discretion.",
                "reasoning": f"Synthesized from human override pattern analysis ({e})."
            }

