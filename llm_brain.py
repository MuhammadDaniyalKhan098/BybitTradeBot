import os
import time
from typing import List, Literal, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

class TakeProfit(BaseModel):
    price: float
    percentage: Optional[float] = 0.5

class TradeSignal(BaseModel):
    action: Literal["NEW_TRADE", "CLOSE_MARKET", "CANCEL_ORDER", "MOVE_SL_TO_BE", "UPDATE_SL", "IGNORE"]
    symbol: Optional[str] = None
    side: Optional[Literal["Buy", "Sell"]] = None
    order_type: Optional[Literal["Market", "Limit"]] = "Market"
    entry_price: Optional[float] = None
    leverage: Optional[int] = 10
    sl: Optional[float] = None
    tps: Optional[List[TakeProfit]] = None

def parse_with_llm(text: str) -> List[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARN] GEMINI_API_KEY not configured.")
        return []

    client = genai.Client(api_key=api_key)
    
    system_prompt = """
    Extract trade execution details into a structured JSON list.
    If the message lacks a specific STOP LOSS (SL) or TAKE PROFIT (TP) number for a NEW_TRADE, return IGNORE.
    Do not parse analysis or potential setups.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.7-flash",
                contents=f"{system_prompt}\n\nMessage:\n{text}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[TradeSignal],
                    temperature=0.0,
                ),
            )
            
            signals = response.parsed
            if not signals:
                return []

            valid_signals = []
            for sig in signals:
                if sig.action == "IGNORE":
                    continue
                
                sig_dict = sig.model_dump(exclude_none=True)
                
                if sig.action == "NEW_TRADE":
                    if "sl" in sig_dict and "tps" in sig_dict and len(sig_dict["tps"]) > 0:
                        valid_signals.append(sig_dict)
                    else:
                        print(f"[INFO] Dropped incomplete signal for {sig.symbol}")
                else:
                    valid_signals.append(sig_dict)
                    
            return valid_signals

        except Exception as e:
            print(f"[WARN] LLM Attempt {attempt + 1} failed: {e}")
            if "503" in str(e) and attempt < max_retries - 1:
                print("[INFO] Waiting 2 seconds before retrying...")
                time.sleep(2)
            else:
                print(f"[ERROR] Final LLM Parsing Error: {e}")
                return []