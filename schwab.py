import schwabdev
import os
import logging
from dotenv import load_dotenv
from time import sleep
import math # For calculating quantity
import asyncio # Added for asynchronous operations

# Function to initialize client (remains synchronous for initial setup)
def initialize_client():
    load_dotenv()
    app_key = os.getenv('app_key')
    app_secret = os.getenv('app_secret')
    callback_url = os.getenv('callback_url')
    if not app_key or len(app_key) != 32 or not app_secret or len(app_secret) != 16:
        raise ValueError("App key and app secret must be set in .env file and be the correct length.")
    # Configure logging only once if not already configured
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = schwabdev.Client(app_key, app_secret, callback_url)
    logging.info("Schwab client initialized.")
    return client

# Async function to get the primary account hash
async def get_primary_account_hash(client):
    try:
        logging.info("Fetching linked accounts...")
        # Wrap synchronous call in asyncio.to_thread
        linked_accounts_resp = await asyncio.to_thread(client.account_linked)
        linked_accounts_resp.raise_for_status() # Check for HTTP errors
        linked_accounts = linked_accounts_resp.json()
        logging.info(f"Linked accounts response: {linked_accounts}")

        if linked_accounts and isinstance(linked_accounts, list) and len(linked_accounts) > 0:
            first_account = linked_accounts[0]
            if isinstance(first_account, dict) and 'hashValue' in first_account:
                 account_hash = first_account.get('hashValue')
                 if account_hash:
                     logging.info(f"Using account hash: {account_hash}")
                     return account_hash
                 else:
                     raise ValueError("hashValue is empty or null in the first linked account.")
            else:
                 raise ValueError(f"Unexpected format for the first account item: {first_account}")
        else:
            raise ValueError("No linked accounts found or unexpected format.")
    except Exception as e:
        logging.error(f"Error fetching account hash: {e}")
        raise

# Async function to get quote
async def get_quote(client, symbol):
    try:
        logging.info(f"Fetching quote for {symbol}...")
        symbol_upper = symbol.upper()
        # Wrap synchronous call in asyncio.to_thread
        quote_resp = await asyncio.to_thread(client.quote, symbol_upper)
        quote_resp.raise_for_status() # Check for HTTP errors
        quote_data = quote_resp.json()
        logging.info(f"Quote response for {symbol}: {quote_data}")

        if symbol_upper in quote_data and isinstance(quote_data[symbol_upper], dict):
            quote_details = quote_data[symbol_upper].get('quote', {})

            price = quote_details.get('askPrice')
            if not price or price == 0:
                logging.warning(f"Ask price not found or zero for {symbol}, falling back to last price.")
                price = quote_details.get('lastPrice')

            if price and price > 0:
                logging.info(f"Using price {price} for {symbol}")
                return price
            else:
                raise ValueError(f"Could not retrieve a valid price (ask or last) for {symbol} from quote details: {quote_details}")
        else:
            raise ValueError(f"Unexpected quote response format or symbol '{symbol_upper}' not found in response keys: {quote_data.keys()}")

    except Exception as e:
        logging.error(f"Error fetching quote for {symbol}: {e}")
        raise

# Async function to place an order for a specific dollar amount
async def place_dollar_amount_order(client, account_hash, symbol, dollar_amount, order_instruction="BUY"):
    if dollar_amount <= 0:
        raise ValueError("Dollar amount must be positive.")

    calculated_quantity = 0 # Initialize
    try:
        # Await the async get_quote function
        current_price = await get_quote(client, symbol)

        calculated_quantity = math.floor(dollar_amount / current_price)

        if calculated_quantity <= 0:
            raise ValueError(f"Calculated quantity is zero or less ({calculated_quantity}) for ${dollar_amount} of {symbol} at ${current_price}. Order not placed.")

        logging.info(f"Calculated quantity {calculated_quantity} for ${dollar_amount} of {symbol} at ${current_price}")

        # Use the internal function to place the order
        resp, order_id = await place_order_internal(client, account_hash, symbol, calculated_quantity, order_instruction)

        # Return the response, order_id, AND the calculated quantity
        return resp, order_id, calculated_quantity

    except Exception as e:
        # Specific logging for dollar amount order failure
        logging.error(f"Error placing {order_instruction} order for ${dollar_amount} of {symbol}: {e}")
        # Return None for resp/order_id but also the quantity that failed
        raise # Re-raise the exception after logging

# Internal async function to place any order (buy/sell) by quantity
async def place_order_internal(client, account_hash, symbol, quantity, order_instruction):
    """Internal helper to place buy/sell market orders by quantity."""
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive to place {order_instruction} order.")

    symbol_upper = symbol.upper()
    order_instruction_upper = order_instruction.upper()

    order = {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": order_instruction_upper,
                "quantity": int(quantity),
                "instrument": {
                    "symbol": symbol_upper,
                    "assetType": "EQUITY"
                }
            }
        ]
    }

    try:
        logging.info(f"Placing {order_instruction_upper} order: {order}")
        # Wrap synchronous call in asyncio.to_thread
        resp = await asyncio.to_thread(client.order_place, account_hash, order)
        resp.raise_for_status()

        logging.info(f"Order placement response status: {resp.status_code}")
        order_id = None
        location_header = resp.headers.get('location')
        if location_header:
             try:
                 order_id = location_header.split('/')[-1]
                 if order_id.isdigit():
                     logging.info(f"{order_instruction_upper} Order placed. Order ID: {order_id}")
                 else:
                     logging.warning(f"Extracted location '{order_id}' does not look like an order ID. Full location: {location_header}")
                     order_id = None
             except IndexError:
                 logging.warning(f"Could not extract order ID from location header: {location_header}")
        else:
            logging.warning("Order response did not contain a 'location' header.")

        return resp, order_id

    except Exception as e:
        logging.error(f"Error in place_order_internal for {quantity} {symbol} ({order_instruction_upper}): {e}")
        raise

# Async function to get order details
async def get_order_details(client, account_hash, order_id):
     if not order_id:
         logging.warning("Cannot get order details without an order ID.")
         return None
     try:
         logging.info(f"Fetching details for order {order_id}...")
         # Wrap synchronous call in asyncio.to_thread
         details_resp = await asyncio.to_thread(client.order_details, account_hash, order_id)
         details_resp.raise_for_status()
         details = details_resp.json()
         logging.info(f"Order details for {order_id}: {details}")
         return details
     except Exception as e:
         logging.error(f"Error fetching details for order {order_id}: {e}")
         raise

# Modified async function to encapsulate the buy trade execution flow
async def execute_schwab_trade(client, account_hash, symbol: str, dollar_amount: float, order_instruction: str = "BUY"):
    """
    Places a market order for a specified dollar amount of a given symbol.
    Now accepts initialized client and account_hash.
    Returns the order ID and the calculated quantity if successful.
    """
    order_id = None
    calculated_quantity = 0 # Initialize
    try:
        logging.info(f"Attempting to place a ${dollar_amount:.2f} {order_instruction} market order for {symbol}...")

        if order_instruction.upper() == "BUY":
            # Capture all three return values
            order_resp, order_id, calculated_quantity = await place_dollar_amount_order(
                client,
                account_hash,
                symbol,
                dollar_amount,
                order_instruction
            )
        else:
             raise NotImplementedError("execute_schwab_trade only supports BUY. Use execute_sell_trade for selling.")

        logging.info(f"Trade execution attempt finished for {symbol}. Order ID: {order_id}, Calculated Quantity: {calculated_quantity}")
        # Return both order_id and calculated_quantity
        return order_id, calculated_quantity

    except ValueError as ve:
        logging.error(f"Trade Execution Error (ValueError) for {symbol}: {ve}", exc_info=True)
        print(f"Configuration or Value Error during trade execution: {ve}")
        return None, 0 # Return None order ID and 0 quantity on error
    except NotImplementedError as nie:
        logging.error(f"Trade Execution Error: {nie}")
        print(f"Error: {nie}")
        return None, 0
    except Exception as e:
        logging.error(f"Trade Execution Error (Exception) for {symbol}: {e}", exc_info=True)
        print(f"An unexpected error occurred during trade execution: {e}")
        return None, 0

# New async function to execute a SELL trade for a specific quantity
async def execute_sell_trade(client, account_hash, symbol: str, dollar_amount: int):
    """
    Places a market SELL order for a specific quantity of a given symbol.
    Returns the order ID if successful.
    """
    order_id = None

    
    # Await the async get_quote function
    current_price = await get_quote(client, symbol)

    calculated_quantity = math.floor(dollar_amount / current_price)
    
    try:
        logging.info(f"Attempting to place a SELL market order for {calculated_quantity} shares of {symbol}...")
        
        # Use the internal place order function directly for SELL
        sell_resp, order_id = await place_order_internal(
            client,
            account_hash,
            symbol,
            calculated_quantity,
            "SELL_SHORT"
        )
        
        logging.info(f"SELL execution attempt finished for {symbol}. Order ID: {order_id}")
        return order_id # Return the order ID

    except ValueError as ve:
        # place_order_internal might raise ValueError (e.g., negative quantity, although checked above)
        logging.error(f"SELL Execution Error (ValueError) for {calculated_quantity} {symbol}: {ve}", exc_info=True)
        print(f"Configuration or Value Error during SELL execution: {ve}")
        return None # Return None order ID on error
    except Exception as e:
        logging.error(f"SELL Execution Error (Exception) for {calculated_quantity} {symbol}: {e}", exc_info=True)
        print(f"An unexpected error occurred during SELL execution: {e}")
        return None

# Main async execution function
async def main():
    # --- Configuration ---
    TARGET_SYMBOL = "MSFT"
    TARGET_DOLLAR_AMOUNT = 500 # Adjusted from user edit
    WAIT_TIME_SECONDS = 60 # Wait 1 minute before selling
    # --- End Configuration ---

    print(f"Welcome to the Async Schwab Trading Script")
    print(f"Config: Buy ~${TARGET_DOLLAR_AMOUNT:.2f} of {TARGET_SYMBOL}, wait {WAIT_TIME_SECONDS}s, then sell calculated quantity.")

    buy_order_id = None
    calculated_buy_quantity = 0
    sell_order_id = None
    client = None
    account_hash = None

    try:
        # Initialize client and get hash once
        client = initialize_client()
        account_hash = await get_primary_account_hash(client)
        await asyncio.sleep(1) # Small delay

        # --- Execute Buy Order ---
        print(f"\n--- Placing Buy Order ---")
        # Capture both return values
        buy_order_id, calculated_buy_quantity = await execute_schwab_trade(
            client,
            account_hash,
            TARGET_SYMBOL,
            TARGET_DOLLAR_AMOUNT,
            "BUY"
        )

        # Check if buy order was placed AND we have a positive calculated quantity
        if buy_order_id and calculated_buy_quantity > 0:
            print(f"Buy order placed successfully. Order ID: {buy_order_id}, Calculated Quantity: {calculated_buy_quantity}")
            print(f"NOTE: Sell order will attempt to sell this calculated quantity ({calculated_buy_quantity}). Actual buy fill quantity may differ.")
            await asyncio.sleep(2) # Short delay

            # --- Wait Period ---
            print(f"\n--- Waiting {WAIT_TIME_SECONDS} seconds before selling ---")
            await asyncio.sleep(WAIT_TIME_SECONDS)

            # --- Execute Sell Order --- 
            print(f"\n--- Placing Sell Order for {calculated_buy_quantity} shares of {TARGET_SYMBOL} ---")
            try:
                # Call the new execute_sell_trade function with the calculated quantity
                sell_order_id = await execute_sell_trade(
                    client,
                    account_hash,
                    TARGET_SYMBOL,
                    calculated_buy_quantity # Use the quantity calculated during buy
                )

                if sell_order_id:
                    print(f"Sell order placed successfully. Order ID: {sell_order_id}")
                    # Optional: Fetch sell order details here if needed
                else:
                    # This covers cases where execute_sell_trade failed or returned None
                    print(f"Sell order for {calculated_buy_quantity} shares of {TARGET_SYMBOL} failed or Order ID not returned. Check logs.")

            except Exception as sell_err:
                # Catch errors specifically from the sell attempt
                print(f"An error occurred during the sell attempt for {TARGET_SYMBOL}: {sell_err}")
                logging.error(f"Error during execute_sell_trade call: {sell_err}", exc_info=True)

        elif buy_order_id: # Buy order placed but calculated quantity was <= 0 (shouldn't happen due to checks, but safe)
             print(f"\nBuy order {buy_order_id} placed, but calculated quantity was {calculated_buy_quantity}. Skipping sell step.")
        else: # buy_order_id was None
            print(f"\nBuy order for {TARGET_SYMBOL} failed or Order ID not returned. Skipping sell step.")

    except Exception as e:
        # Catch initialization errors or errors in execute_schwab_trade itself
        print(f"\nAn error occurred in the main execution block: {e}")
        logging.error(f"Error in main execution block: {e}", exc_info=True)

    finally:
        # Client cleanup could be added here if needed
        print("\nScript finished.")


# Run the main async function
if __name__ == "__main__":
    asyncio.run(main())

# Original code removed/integrated into functions above
# The async functions can now be potentially imported and used from other async modules.

