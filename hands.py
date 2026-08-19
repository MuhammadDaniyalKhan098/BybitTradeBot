import os
import math
from pybit.unified_trading import HTTP

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
DEFAULT_COST = float(os.getenv("TRADE_COST", "100"))

try:
    session = HTTP(
        testnet=False, 
        demo=True,     
        api_key=API_KEY, 
        api_secret=API_SECRET,
        recv_window=20000 
    )
except Exception as e:
    print(f"[ERROR] Bybit connection failed: {e}")

def _format_float(num):
    if num is None: 
        return None
    return "{:.10f}".format(float(num)).rstrip('0').rstrip('.')

def _get_precision(symbol: str):
    try:
        info = session.get_instruments_info(category="linear", symbol=symbol)
        price_filter = info['result']['list'][0]['priceFilter']
        qty_filter = info['result']['list'][0]['lotSizeFilter']
        
        price_prec = int(abs(math.log10(float(price_filter['tickSize']))))
        qty_prec = int(abs(math.log10(float(qty_filter['qtyStep']))))
        
        ticker = session.get_tickers(category="linear", symbol=symbol)
        current_price = float(ticker['result']['list'][0]['lastPrice'])
        
        return price_prec, qty_prec, current_price
    except Exception:
        return 4, 3, 0.0

def execute_trade(trade_data: dict) -> str:
    if not trade_data or not trade_data.get('symbol'):
        return "Skipped: Invalid payload"
    
    symbol = trade_data['symbol'].upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"
        
    action = trade_data.get('action')
    entry_price = trade_data.get('entry_price')
    
    if symbol == "BTCUSDT" and entry_price and float(entry_price) < 1000:
        return f"Blocked: Erroneous BTC price detected ({entry_price})"

    try:
        if action == 'NEW_TRADE':
            return _place_hybrid_trade(symbol, trade_data)
        elif action == 'CLOSE_MARKET':
            return _close_position(symbol)
        elif action == 'CANCEL_ORDER':
            return _cancel_all_orders(symbol)
        elif action == 'MOVE_SL_TO_BE':
            return _move_sl_to_entry(symbol)
        elif action == 'UPDATE_SL':
            return _update_sl(symbol, trade_data.get('sl'))
        
        return f"Unknown action: {action}"
    except Exception as e:
        return f"Execution Error: {str(e)}"

def _cancel_all_orders(symbol: str) -> str:
    try:
        resp = session.cancel_all_orders(category="linear", symbol=symbol)
        if resp.get('retCode') == 0: 
            return f"Active orders cleared for {symbol}."
    except Exception:
        pass
    return ""

def _place_hybrid_trade(symbol: str, data: dict) -> str:
    cancel_log = _cancel_all_orders(symbol)
    price_prec, qty_prec, cur_price = _get_precision(symbol)
    
    side = data.get('side', 'Buy').capitalize()
    order_type = data.get('order_type', 'Market').capitalize()
    entry_price = data.get('entry_price')
    leverage = float(data.get('leverage', 10))
    sl_price = data.get('sl')
    tps = data.get('tps', [])
    
    try:
        session.set_leverage(
            category="linear", symbol=symbol, 
            buyLeverage=str(leverage), sellLeverage=str(leverage)
        )
    except Exception:
        pass

    ref_price = float(entry_price) if entry_price else cur_price
    total_qty = (DEFAULT_COST * leverage) / ref_price
    total_qty_str = str(round(total_qty, qty_prec))

    final_tp_price = None
    partial_tps = []

    if tps:
        sorted_tps = sorted(tps, key=lambda x: float(x['price']), reverse=(side != "Buy"))
        final_tp_price = sorted_tps[-1]['price']
        partial_tps = sorted_tps[:-1]

    order_params = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": total_qty_str,
        "positionIdx": 0,
    }
    
    if sl_price: 
        order_params["stopLoss"] = _format_float(sl_price)
    if final_tp_price: 
        order_params["takeProfit"] = _format_float(final_tp_price)
    if order_type == "Limit" and entry_price:
        order_params["price"] = _format_float(entry_price)
        
    try:
        session.place_order(**order_params)
        log_msg = f"{cancel_log}\nEntry placed: {total_qty_str} {symbol}."
    except Exception as e:
        return f"Entry Failed: {e}"

    tp_side = "Sell" if side == "Buy" else "Buy"
    for tp in partial_tps:
        try:
            chunk_pct = tp.get('percentage', 0.5)
            chunk_qty = round(total_qty * chunk_pct, qty_prec)
            tp_price = float(tp['price'])
            
            trigger_dir = 1 if tp_price > ref_price else 2
            
            session.place_order(
                category="linear",
                symbol=symbol,
                side=tp_side,
                orderType="Limit",
                qty=str(chunk_qty),
                price=_format_float(tp_price),
                triggerPrice=_format_float(tp_price),
                triggerDirection=trigger_dir,
                triggerBy="LastPrice",
                reduceOnly=True
            )
            log_msg += f"\nPartial TP set: {chunk_qty} @ {tp_price}"
        except Exception as e:
            log_msg += f"\nPartial TP Warning: {e}"

    return log_msg.strip()

def _close_position(symbol: str) -> str:
    try:
        session.cancel_all_orders(category="linear", symbol=symbol)
        positions = session.get_positions(category="linear", symbol=symbol)['result']['list']
        for p in positions:
            if float(p['size']) > 0:
                side = "Sell" if p['side'] == "Buy" else "Buy"
                session.place_order(
                    category="linear", symbol=symbol, side=side, 
                    orderType="Market", qty=p['size'], reduceOnly=True
                )
                return f"Position closed: {symbol}"
        return f"No open position found for {symbol}"
    except Exception as e: 
        return f"Close Error: {e}"

def _move_sl_to_entry(symbol: str) -> str:
    try:
        positions = session.get_positions(category="linear", symbol=symbol)['result']['list']
        for p in positions:
            if float(p['size']) > 0:
                session.set_trading_stop(
                    category="linear", symbol=symbol, 
                    stopLoss=p['avgPrice'], positionIdx=0
                )
                return f"Stop loss moved to breakeven for {symbol}"
        return "No open position to modify."
    except Exception as e: 
        return f"Error modifying SL: {e}"

def _update_sl(symbol: str, new_sl: float) -> str:
    try:
        session.set_trading_stop(
            category="linear", symbol=symbol, 
            stopLoss=_format_float(new_sl), positionIdx=0
        )
        return f"Stop loss updated to {new_sl} for {symbol}"
    except Exception as e: 
        return f"Error updating SL: {e}"