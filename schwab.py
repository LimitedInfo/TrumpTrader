import schwabdev
import os
import logging
from dotenv import load_dotenv
from time import sleep
import math # For calculating quantity

# Function to initialize client
def initialize_client():
    load_dotenv()
    app_key = os.getenv('app_key')
    app_secret = os.getenv('app_secret')
    callback_url = os.getenv('callback_url')
    if not app_key or len(app_key) != 32 or not app_secret or len(app_secret) != 16:
        raise ValueError("App key and app secret must be set in .env file and be the correct length.")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = schwabdev.Client(app_key, app_secret, callback_url)
    logging.info("Schwab client initialized.")
    return client

# Function to get the primary account hash
def get_primary_account_hash(client):
    try:
        logging.info("Fetching linked accounts...")
        linked_accounts_resp = client.account_linked()
        linked_accounts_resp.raise_for_status() # Check for HTTP errors
        linked_accounts = linked_accounts_resp.json()
        logging.info(f"Linked accounts response: {linked_accounts}")

        if linked_accounts and isinstance(linked_accounts, list) and len(linked_accounts) > 0:
            # Assuming the structure is a list of accounts, each with 'hashValue'
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

# Function to get quote
def get_quote(client, symbol):
    try:
        logging.info(f"Fetching quote for {symbol}...")
        # Use client.quote instead of client.quote_single
        quote_resp = client.quote(symbol.upper()) # Ensure symbol is uppercase for API
        quote_resp.raise_for_status() # Check for HTTP errors
        quote_data = quote_resp.json()
        logging.info(f"Quote response for {symbol}: {quote_data}")

        # Adjust parsing based on the example structure: client.quote("INTC").json()
        # This usually returns a dictionary where keys are symbols.
        symbol_upper = symbol.upper()
        if symbol_upper in quote_data and isinstance(quote_data[symbol_upper], dict):
            quote_details = quote_data[symbol_upper].get('quote', {}) # Access nested 'quote' dict safely

            # Prioritize ask price for calculating buy quantity
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
        # Consider if specific exceptions from schwabdev should be caught
        raise


# Function to place an order for a specific dollar amount
def place_dollar_amount_order(client, account_hash, symbol, dollar_amount, order_instruction="BUY"):
    if dollar_amount <= 0:
        raise ValueError("Dollar amount must be positive.")

    try:
        current_price = get_quote(client, symbol)
        # No need to check current_price > 0 here, get_quote already ensures it

        # Calculate quantity, rounding down to the nearest whole share
        quantity = math.floor(dollar_amount / current_price)

        if quantity <= 0:
            raise ValueError(f"Calculated quantity is zero or less ({quantity}) for ${dollar_amount} of {symbol} at ${current_price}. Order not placed.")

        logging.info(f"Calculated quantity {quantity} for ${dollar_amount} of {symbol} at ${current_price}")

        order = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": order_instruction.upper(), # Ensure instruction is uppercase
                    "quantity": int(quantity), # Ensure quantity is integer
                    "instrument": {
                        "symbol": symbol.upper(), # Ensure symbol is uppercase
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        logging.info(f"Placing {order_instruction} order: {order}")
        resp = client.order_place(account_hash, order)
        resp.raise_for_status() # Check for HTTP errors during order placement

        logging.info(f"Order placement response status: {resp.status_code}")
        # Attempt to get order ID from 'location' header
        order_id = None
        location_header = resp.headers.get('location')
        if location_header:
             try:
                 order_id = location_header.split('/')[-1]
                 # Validate if it looks like an ID (e.g., is numeric)
                 if order_id.isdigit():
                     logging.info(f"Order placed. Order ID: {order_id}")
                 else:
                     logging.warning(f"Extracted location '{order_id}' does not look like an order ID. Full location: {location_header}")
                     order_id = None # Reset if invalid format
             except IndexError:
                 logging.warning(f"Could not extract order ID from location header: {location_header}")
        else:
            logging.warning("Order response did not contain a 'location' header. Order might be filled immediately or failed silently.")

        return resp, order_id

    except Exception as e:
        logging.error(f"Error placing {order_instruction} order for {symbol}: {e}")
        raise

# Function to get order details
def get_order_details(client, account_hash, order_id):
     if not order_id:
         logging.warning("Cannot get order details without an order ID.")
         return None
     try:
         logging.info(f"Fetching details for order {order_id}...")
         details_resp = client.order_details(account_hash, order_id)
         details_resp.raise_for_status()
         details = details_resp.json()
         logging.info(f"Order details for {order_id}: {details}")
         return details
     except Exception as e:
         # Catch specific exceptions if known, e.g., order not found
         logging.error(f"Error fetching details for order {order_id}: {e}")
         raise


# New function to encapsulate the trade execution flow
def execute_schwab_trade(symbol: str, dollar_amount: float, order_instruction: str = "BUY"):
    """
    Initializes the Schwab client, finds the primary account hash, and places
    a market order for a specified dollar amount of a given symbol.

    Args:
        symbol (str): The stock symbol to trade.
        dollar_amount (float): The target dollar amount for the trade.
        order_instruction (str, optional): "BUY" or "SELL". Defaults to "BUY".

    Returns:
        str or None: The order ID if successfully placed and retrieved, otherwise None.
                     Returns None if an error occurs during the process.
    """
    client = None
    order_id = None
    try:
        client = initialize_client()
        account_hash = get_primary_account_hash(client)
        sleep(1) # Small delay

        logging.info(f"Attempting to place a ${dollar_amount:.2f} {order_instruction} market order for {symbol}...")
        order_resp, order_id = place_dollar_amount_order(
            client,
            account_hash,
            symbol,
            dollar_amount,
            order_instruction
        )
        logging.info(f"Trade execution attempt finished for {symbol}. Order ID: {order_id}")
        return order_id # Return the order_id (could be None if header wasn't found)

    except ValueError as ve:
        logging.error(f"Trade Execution Error (ValueError) for {symbol}: {ve}", exc_info=True)
        print(f"Configuration or Value Error during trade execution: {ve}")
        return None
    except Exception as e:
        logging.error(f"Trade Execution Error (Exception) for {symbol}: {e}", exc_info=True)
        print(f"An unexpected error occurred during trade execution: {e}")
        return None
    # No finally block for client cleanup here, as client is local to this function


# Main execution
if __name__ == "__main__":
    # --- Configuration ---
    TARGET_SYMBOL = "MSFT"  # Example: Microsoft
    TARGET_DOLLAR_AMOUNT = 1000 # Example: Buy $1000 worth
    ORDER_INSTRUCTION = "BUY" # "BUY" or "SELL"
    # --- End Configuration ---

    print(f"Welcome to the Schwab Trading Script")
    print(f"Attempting main execution: {ORDER_INSTRUCTION} ${TARGET_DOLLAR_AMOUNT:.2f} of {TARGET_SYMBOL}")

    final_order_id = None
    try:
        # Execute the trade using the main function
        final_order_id = execute_schwab_trade(
            TARGET_SYMBOL,
            TARGET_DOLLAR_AMOUNT,
            ORDER_INSTRUCTION
        )
        sleep(3) # Wait a bit after placing the order

        # --- Optional: Get Order Details ---
        # We need the client and hash again if we want details now.
        # Alternatively, get_order_details could also handle client init.
        # For simplicity here, we re-initialize if we need details.
        if final_order_id:
             print(f"\nFetching details for order {final_order_id}...")
             # Re-initialize client and get hash to fetch details
             temp_client = initialize_client()
             temp_account_hash = get_primary_account_hash(temp_client)
             order_details = get_order_details(temp_client, temp_account_hash, final_order_id)
             if order_details:
                 # Logging inside get_order_details shows the details
                 print(f"Order details retrieved successfully.")
             else:
                 print("Could not retrieve order details (may already be filled or error occurred).")
             sleep(1)
        elif final_order_id is None and ORDER_INSTRUCTION: # Check if trade was attempted
             # Only print this if execute_schwab_trade was expected to run and returned None
             print("\nOrder ID not returned from trade execution. Check logs or Schwab account.")
        # --- End Optional ---

    except Exception as e:
        # Catch any exceptions that might occur outside execute_schwab_trade
        # (e.g., during the re-initialization for getting details)
        print(f"\nAn error occurred in the main execution block: {e}")
        logging.error(f"Error in main execution block: {e}", exc_info=True)

    finally:
        print("\nScript finished.")

# Original code removed/integrated into functions above
# Comments explaining the original logic can be added if needed for clarity
# The functions initialize_client, get_primary_account_hash, get_quote,
# place_dollar_amount_order, get_order_details, and execute_schwab_trade
# can now be imported and used from other modules.

