import sys
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

import asyncio
from app.services.llm_service import GeminiLLMService
from app.services.reply_service import draft_reply

async def test():
    llm = GeminiLLMService.get_instance()
    try:
        html, plain, ref = await draft_reply(
            action="escalate",
            order=None,
            customer_name="AMKAR MRUNAL",
            customer_email="mca25.amkar.mrunal@gnims.com",
            original_email_body="I want to know where is my order",
            action_summary="Escalated to human agent: The order could not be located in the system, requiring manual investigation by the support team.",
            llm=llm,
            reference_id="CASE-260910-0951"
        )
        print("DRAFT REPLY SUCCESS!")
        print("HTML length:", len(html))
        print("HTML snippet:\n", html[:500])
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
