import unittest
import asyncio
from unittest.mock import patch, AsyncMock
import os
from dotenv import load_dotenv

# Assuming schwab.py is in the same directory or accessible via PYTHONPATH
# We need more imports for the integration test
import schwab

# Load environment variables for potential integration test
load_dotenv()

class TestSchwabExecuteSellTrade(unittest.TestCase):

    def test_sell_trade_success(self):
        """Tests successful sell trade execution."""
        mock_client = AsyncMock() # Mock client object (not strictly needed if patching internal)
        account_hash = "test_hash_123"
        symbol = "MSFT"
        quantity = 10
        expected_order_id = "54321"

        # Patch the internal function that execute_sell_trade calls
        with patch('schwab.place_order_internal', new_callable=AsyncMock) as mock_place_order:
            # Configure the mock to return a successful response tuple (response_obj, order_id)
            # The response object itself isn't checked by execute_sell_trade, only the order_id
            mock_place_order.return_value = (AsyncMock(), expected_order_id)

            # Run the async function under test
            result_order_id = asyncio.run(schwab.execute_sell_trade(
                mock_client,
                account_hash,
                symbol,
                quantity
            ))

            # Assertions
            mock_place_order.assert_called_once_with(
                mock_client,
                account_hash,
                symbol.upper(), # Ensure symbol was uppercased
                quantity,      # Ensure quantity is passed correctly
                "SELL"         # Ensure instruction is SELL
            )
            self.assertEqual(result_order_id, expected_order_id)

    def test_sell_trade_invalid_quantity_zero(self):
        """Tests sell trade with zero quantity."""
        mock_client = AsyncMock()
        account_hash = "test_hash_123"
        symbol = "AAPL"
        quantity = 0

        with patch('schwab.place_order_internal', new_callable=AsyncMock) as mock_place_order:
            # Use self.assertWarns to check for the logged warning
            with self.assertLogs(level='WARNING') as cm:
                result_order_id = asyncio.run(schwab.execute_sell_trade(
                    mock_client,
                    account_hash,
                    symbol,
                    quantity
                ))
            self.assertIn(f"Sell quantity must be positive. Received {quantity}", cm.output[0])

            # Assertions
            mock_place_order.assert_not_called() # Internal function should not be called
            self.assertIsNone(result_order_id)    # Should return None

    def test_sell_trade_invalid_quantity_negative(self):
        """Tests sell trade with negative quantity."""
        mock_client = AsyncMock()
        account_hash = "test_hash_123"
        symbol = "GOOG"
        quantity = -5

        with patch('schwab.place_order_internal', new_callable=AsyncMock) as mock_place_order:
            # Use self.assertWarns to check for the logged warning
            with self.assertLogs(level='WARNING') as cm:
                result_order_id = asyncio.run(schwab.execute_sell_trade(
                    mock_client,
                    account_hash,
                    symbol,
                    quantity
                ))
            self.assertIn(f"Sell quantity must be positive. Received {quantity}", cm.output[0])

            # Assertions
            mock_place_order.assert_not_called() # Internal function should not be called
            self.assertIsNone(result_order_id)    # Should return None

    def test_sell_trade_api_error(self):
        """Tests sell trade when the internal call fails."""
        mock_client = AsyncMock()
        account_hash = "test_hash_123"
        symbol = "TSLA"
        quantity = 2

        # Patch the internal function to raise an exception
        with patch('schwab.place_order_internal', new_callable=AsyncMock) as mock_place_order:
            mock_place_order.side_effect = Exception("Simulated API Error")

            # Check that the error is logged
            with self.assertLogs(level='ERROR') as cm:
                result_order_id = asyncio.run(schwab.execute_sell_trade(
                    mock_client,
                    account_hash,
                    symbol,
                    quantity
                ))
            self.assertTrue(any("SELL Execution Error" in msg and "Simulated API Error" in msg for msg in cm.output))

            # Assertions
            mock_place_order.assert_called_once() # Ensure the internal function was attempted
            self.assertIsNone(result_order_id)    # Should return None on error

    # --- Integration Test --- 
    @unittest.skipUnless(
        os.getenv('RUN_SCHWAB_INTEGRATION_TESTS') == 'true',
        "Skipping integration tests unless RUN_SCHWAB_INTEGRATION_TESTS=true env var is set"
    )
    def test_sell_trade_integration_real_call(self):
        """ 
        !!! INTEGRATION TEST - MAKES REAL API CALLS AND PLACES REAL ORDERS !!!
        Requires environment variables:
          - RUN_SCHWAB_INTEGRATION_TESTS=true (to enable)
          - INTEGRATION_TEST_SELL_SYMBOL (e.g., F)
          - INTEGRATION_TEST_SELL_QTY (e.g., 1)
          - Valid Schwab API keys in .env
        Account MUST own the specified quantity of the symbol before running.
        """
        print("\n--- RUNNING REAL SELL TRADE INTEGRATION TEST ---")
        symbol_to_sell = os.getenv('INTEGRATION_TEST_SELL_SYMBOL')
        qty_to_sell_str = os.getenv('INTEGRATION_TEST_SELL_QTY')

        self.assertTrue(symbol_to_sell, "INTEGRATION_TEST_SELL_SYMBOL env var not set.")
        self.assertTrue(qty_to_sell_str, "INTEGRATION_TEST_SELL_QTY env var not set.")

        try:
            qty_to_sell = int(qty_to_sell_str)
            self.assertGreater(qty_to_sell, 0, "INTEGRATION_TEST_SELL_QTY must be positive.")
        except ValueError:
            self.fail("INTEGRATION_TEST_SELL_QTY must be a valid integer.")

        print(f"Attempting to sell {qty_to_sell} shares of {symbol_to_sell} using real API call...")
        print("Ensure account owns sufficient shares and credentials are correct.")

        client = None
        account_hash = None
        order_id = None

        try:
            # Initialize real client (synchronous part)
            print("Initializing real Schwab client...")
            client = schwab.initialize_client()
            self.assertIsNotNone(client)
            print("Client initialized.")
            
            # Get real account hash (asynchronous part)
            print("Fetching real account hash...")
            account_hash = asyncio.run(schwab.get_primary_account_hash(client))
            self.assertIsNotNone(account_hash)
            self.assertIsInstance(account_hash, str)
            self.assertTrue(len(account_hash) > 0)
            print(f"Account hash obtained: ...{account_hash[-4:]}") # Print last 4 chars for confirmation

            # --- Make the real API call --- 
            print(f"Executing real sell trade for {qty_to_sell} of {symbol_to_sell}...")
            order_id = asyncio.run(schwab.execute_sell_trade(
                client,
                account_hash,
                symbol_to_sell,
                qty_to_sell
            ))
            print(f"execute_sell_trade returned: {order_id}")
            # --- End Real API call --- 

            # Basic assertion: Check if an order ID was returned
            self.assertIsNotNone(order_id, "execute_sell_trade returned None, expected an order ID string.")
            self.assertIsInstance(order_id, str, "Expected order_id to be a string.")
            # self.assertTrue(order_id.isdigit(), "Expected order_id to contain digits.") # Might be too strict depending on format
            self.assertTrue(len(order_id) > 0, "Expected order_id string to be non-empty.")
            print(f"--->>> Successfully submitted REAL sell order. Order ID: {order_id} <<<--- ")
            print("Please verify order status in your Schwab account.")

        except Exception as e:
            print(f"Error during integration test: {e}")
            self.fail(f"Integration test failed with exception: {e}")
        finally:
             print("--- FINISHED REAL SELL TRADE INTEGRATION TEST ---")


if __name__ == '__main__':
    unittest.main() 