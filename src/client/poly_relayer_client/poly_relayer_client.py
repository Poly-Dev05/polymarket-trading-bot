"""
PolyRelayerClient - Wrapper for Polymarket Builder Relayer Client
"""
import os
from typing import Optional, Dict, Any, List
from eth_abi import encode
from eth_utils import keccak, to_checksum_address
from py_builder_relayer_client.models import SafeTransaction, OperationType
from web3.constants import HASH_ZERO


try:
    from py_builder_relayer_client.client import RelayClient  # pyright: ignore[reportMissingImports]
    from py_builder_signing_sdk.config import BuilderConfig, BuilderApiKeyCreds
    RELAYER_AVAILABLE = True
except ImportError:
    RelayClient = None  # type: ignore
    BuilderConfig = None  # type: ignore
    BuilderApiKeyCreds = None  # type: ignore
    RELAYER_AVAILABLE = False

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None  # type: ignore
    WEB3_AVAILABLE = False


class PolyRelayerClient:
    """
    Client wrapper for Polymarket Builder Relayer
    
    This class provides a simplified interface to interact with the Polymarket
    Builder Relayer for executing on-chain split, merge, and redeem on the CTF.
    """
    
    # --- Polygon mainnet — Polymarket upgraded deployments ---
    CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    CTF_EXCHANGE = "0xE111180000d2663C0091e4f400237545B87B996B"
    NEG_RISK_CTF_EXCHANGE = "0xe2222d279d744050d28e00520010520000310F59"
    NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

    CTF_COLLATERAL_ADAPTER = "0xAdA100Db00Ca00073811820692005400218FcE1f"
    NEG_RISK_CTF_COLLATERAL_ADAPTER = "0xadA2005600Dec949baf300f4C6120000bDB6eAab"

    PUSD_ADDRESS = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
    # Bridged USDC — used as collateral on Conditional Tokens in inner txs after adapter unwrap
    USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

    # Back-compat: historic name pointed at CTF; redeem still targets Conditional Tokens.
    CTF_EXCHANGE_ADDRESS = CONDITIONAL_TOKENS

    # Split/merge default collateral when routing through CtfCollateralAdapter (matches Polymarket UI).
    USDC_ADDRESS = PUSD_ADDRESS
    
    def __init__(
        self,
        relayer_url: str,
        chain_id: int,
        private_key: str,
        builder_api_key: Optional[str] = None,
        builder_secret: Optional[str] = None,
        builder_passphrase: Optional[str] = None
    ):
        """
        Initialize PolyRelayerClient
        
        Args:
            relayer_url: URL of the relayer service (e.g., "https://relayer-v2-staging.polymarket.dev/")
            chain_id: Blockchain chain ID (e.g., 80002 for Polygon zkEVM testnet, 137 for Polygon mainnet)
            private_key: Private key for signing transactions
            builder_api_key: Optional Builder API key (defaults to BUILDER_API_KEY env var)
            builder_secret: Optional Builder API secret (defaults to BUILDER_SECRET env var)
            builder_passphrase: Optional Builder API passphrase (defaults to BUILDER_PASS_PHRASE env var)
        """
        self.relayer_url = relayer_url
        self.chain_id = chain_id
        self.private_key = private_key
        self.builder_api_key = builder_api_key
        self.builder_secret = builder_secret
        self.builder_passphrase = builder_passphrase
        # Get builder credentials from args or environment

        
        # Initialize relayer client if available
        if RELAYER_AVAILABLE and BuilderConfig is not None and BuilderApiKeyCreds is not None:
            if self.builder_api_key and self.builder_secret and self.builder_passphrase:
                try:

                    builder_config = BuilderConfig(
                        local_builder_creds=BuilderApiKeyCreds(
                            key=self.builder_api_key,
                            secret=self.builder_secret,
                            passphrase=self.builder_passphrase,
                        )
                    )
                    self.builder_config = builder_config
                    self.client = RelayClient(
                        self.relayer_url,
                        self.chain_id,
                        self.private_key,
                        self.builder_config
                    )
                except Exception as e:
                    print(f"Warning: Failed to initialize relayer client: {e}")
                    self.builder_config = None
                    self.client = None
            else:
                print("Warning: Builder API credentials not provided. Relayer client not initialized.")
                self.builder_config = None
                self.client = None
        else:
            self.builder_config = None
            self.client = None
            if not RELAYER_AVAILABLE:
                print("Warning: py-builder-relayer-client not installed. Install with: pip install py-builder-relayer-client")
    
    def is_available(self) -> bool:
        """Check if relayer client is available and initialized"""
        return self.client is not None
    
    def merge_tokens(
        self,
        condition_id: str,
        amount: int,
        collateral_token: Optional[str] = None,
        parent_collection_id: Optional[bytes] = None,
        partition: Optional[List[int]] = None,
        neg_risk: bool = False,
    ) -> Optional[Any]:
        """
        Merge outcome tokens back into collateral
        
        Args:
            condition_id: The condition ID of the market (bytes32)
            amount: Amount to merge (in token units, e.g., 1 * 10^6 for 1 token with 6 decimals)
            collateral_token: Collateral token address (default: pUSD — adapter path, matches Polymarket UI)
            parent_collection_id: Parent collection ID (default: bytes32(0))
            partition: Partition/index set (default: [1, 2] for binary markets)
            neg_risk: If True, use NegRiskCtfCollateralAdapter for neg-risk markets.
            
        Returns:
            Transaction response object or None if failed
        """
        if not self.client:
            print("Error: Relayer client not initialized. Cannot merge tokens.")
            return None
        
        if not WEB3_AVAILABLE or Web3 is None:
            print("Error: Web3 not available. Cannot merge tokens.")
            return None
        
        try:
            # Default values
            collateral_token = collateral_token or self.USDC_ADDRESS
            parent_collection_id = b"\x00" * 32
            partition = partition or [1, 2]
            adapter = (
                self.NEG_RISK_CTF_COLLATERAL_ADAPTER
                if neg_risk
                else self.CTF_COLLATERAL_ADAPTER
            )
            
            # Ensure condition_id has 0x prefix
            condition_id_bytes32 = self._condition_id_to_bytes32(condition_id)
            data_hex = self.encode_merge_collateral_data(condition_id_bytes32, partition, collateral_token, amount, parent_collection_id)
            tx = SafeTransaction(
                to=adapter,
                operation = OperationType.Call,
                data=data_hex,
                value="0"
            )
            
            # Execute transaction
            response = self.client.execute([tx], "Merge positions")
            response.wait()
            print(f"Merge transaction hash: {response.transaction_hash}")
            print("Merge complete!")
            return response
            
        except Exception as e:
            print(f"Error merging tokens: {e}")
            import traceback
            traceback.print_exc()
            return None

    def split_tokens(
        self,
        condition_id: str,
        amount: int,
        collateral_token: Optional[str] = None,
        parent_collection_id: Optional[bytes] = None,
        partition: Optional[List[int]] = None,
        neg_risk: bool = False,
    ) -> Optional[Any]:
        """
        Split collateral into outcome tokens for a condition (inverse of merge).

        Same `partition` convention as merge: binary Polymarket markets typically
        use ``[1, 2]``. ``amount`` is collateral units (e.g. pUSD / 6 decimals when
        using the default adapter path).

        Args:
            condition_id: Market condition ID (hex bytes32).
            amount: Amount of collateral to split.
            collateral_token: Collateral address (default: pUSD — CtfCollateralAdapter path, matches Polymarket UI).
            parent_collection_id: Parent collection (default: zeros32).
            partition: Index set partition (default: ``[1, 2]``).
            neg_risk: If True, use NegRiskCtfCollateralAdapter for neg-risk markets.

        Returns:
            Relayer response or None if failed.
        """
        if not self.client:
            print("Error: Relayer client not initialized. Cannot split tokens.")
            return None

        if not WEB3_AVAILABLE or Web3 is None:
            print("Error: Web3 not available. Cannot split tokens.")
            return None

        try:
            collateral_token = collateral_token or self.USDC_ADDRESS
            parent_collection_id = (
                parent_collection_id if parent_collection_id is not None else b"\x00" * 32
            )
            partition = partition or [1, 2]
            adapter = (
                self.NEG_RISK_CTF_COLLATERAL_ADAPTER
                if neg_risk
                else self.CTF_COLLATERAL_ADAPTER
            )
            condition_id_bytes32 = self._condition_id_to_bytes32(condition_id)
            data_hex = self.encode_split_collateral_data(
                condition_id_bytes32,
                partition,
                collateral_token,
                amount,
                parent_collection_id,
            )
            tx = SafeTransaction(
                to=adapter,
                operation=OperationType.Call,
                data=data_hex,
                value="0",
            )
            response = self.client.execute([tx], "Split positions")
            response.wait()
            print(f"Split transaction hash: {response.transaction_hash}")
            print("Split complete!")
            return response

        except Exception as e:
            print(f"Error splitting tokens: {e}")
            import traceback
            traceback.print_exc()
            return None

    def redeem_positions(
        self,
        condition_id: str,
        index_sets: Optional[List[int]] = None,
        collateral_token: Optional[str] = None,
        parent_collection_id: Optional[bytes] = None
    ) -> Optional[Any]:
        """
        Redeem winning outcome tokens for collateral
        
        Args:
            condition_id: The condition ID of the market (bytes32)
            index_sets: Index sets to redeem (default: [1, 2] for binary markets)
            collateral_token: Collateral token address (default: USDC)
            parent_collection_id: Parent collection ID (default: bytes32(0))
            
        Returns:
            Transaction response object or None if failed
        """
        if not self.client:
            print("Error: Relayer client not initialized. Cannot redeem positions.")
            return None
        
        if not WEB3_AVAILABLE or Web3 is None:
            print("Error: Web3 not available. Cannot redeem positions.")
            return None
        
        try:
            index_sets = index_sets if index_sets is not None else [1, 2]
            # Redeem is executed on Conditional Tokens; collateral is the CTF-registered token (USDC.e on Polygon).
            collateral_token = (
                collateral_token if collateral_token is not None else self.USDC_E_ADDRESS
            )
            parent_collection_id = b"\x00" * 32
            condition_id_bytes32 = self._condition_id_to_bytes32(condition_id)
            data_hex = self.encode_redeem_collateral_data(condition_id_bytes32, index_sets, collateral_token, parent_collection_id) # Default values
            
            tx = SafeTransaction(
                to=self.CONDITIONAL_TOKENS,
                operation = OperationType.Call,
                data=data_hex,
                value="0"
            )

            # print(f"Redeem transaction: {tx}")
            response = self.client.execute([tx], "Redeem winnings")
            response.wait()
            # print(f"Redeem transaction hash: {response.transaction_hash}")
            print("Redeem complete!")
            return response

        except Exception as e:
            # print(f"Error redeeming positions: {e}")
            # import traceback
            # traceback.print_exc()
            return None
    
    def execute_transaction(
        self,
        transactions: List[Dict[str, str]],
        description: str = "Execute transaction"
    ) -> Optional[Any]:
        """
        Execute a generic transaction through the relayer
        
        Args:
            transactions: List of transaction dictionaries with 'to', 'data', and 'value' keys
            description: Description of the transaction
            
        Returns:
            Transaction response object or None if failed
        """
        if not self.client:
            print("Error: Relayer client not initialized. Cannot execute transaction.")
            return None
        
        try:
            response = self.client.execute(transactions, description)
            response.wait()
            print(f"Transaction hash: {response.transaction_hash}")
            return response
        except Exception as e:
            print(f"Error executing transaction: {e}")
            import traceback
            traceback.print_exc()
            return None



    def function_selector(self, signature: str) -> str:
        """
        Get the function selector for a given signature
        
        Args:
            signature: The signature of the function
        """
        return keccak(text=signature)[:4]

    def encode_redeem_collateral_data(self, condition_id: bytes, index_sets: List[int], collateral_token: str, parent_collection_id: bytes) -> str:
        """
        Encode the redeem collateral data
        
        Args:
            condition_id: The condition ID of the market (bytes32)
            index_sets: Index sets to redeem (default: [1, 2] for binary markets)
            collateral_token: Collateral token address (default: USDC)
            parent_collection_id: Parent collection ID (default: bytes32(0))
        """        
        
        seleector = self.function_selector("redeemPositions(address,bytes32,bytes32,uint256[])")
        encoded_data = encode(["address", "bytes32", "bytes32", "uint256[]"],
         [to_checksum_address(collateral_token), parent_collection_id, condition_id, index_sets])
        return "0x" +  (seleector + encoded_data).hex()


    def encode_merge_collateral_data(self, condition_id: bytes, partition: List[int], collateral_token: str, amount: int, parent_collection_id: bytes) -> str:
        """
        Encode the merge collateral data
        
        Args:
            condition_id: The condition ID of the market (bytes32)
            partition: Partition/index set (default: [1, 2] for binary markets)
            collateral_token: Collateral token address (default: USDC)
            parent_collection_id: Parent collection ID (default: bytes32(0))
        """
        seleector = self.function_selector("mergePositions(address,bytes32,bytes32,uint256[],uint256)")
        encoded_data = encode(["address", "bytes32", "bytes32", "uint256[]", "uint256"],
         [to_checksum_address(collateral_token), parent_collection_id, condition_id, partition, amount])
        return "0x" +  (seleector + encoded_data).hex()

    def encode_split_collateral_data(
        self,
        condition_id: bytes,
        partition: List[int],
        collateral_token: str,
        amount: int,
        parent_collection_id: bytes,
    ) -> str:
        """ABI-encode splitPosition(collateralToken, parentCollectionId, conditionId, partition, amount)."""
        seleector = self.function_selector(
            "splitPosition(address,bytes32,bytes32,uint256[],uint256)"
        )
        encoded_data = encode(
            ["address", "bytes32", "bytes32", "uint256[]", "uint256"],
            [
                to_checksum_address(collateral_token),
                parent_collection_id,
                condition_id,
                partition,
                amount,
            ],
        )
        return "0x" + (seleector + encoded_data).hex()

    def _condition_id_to_bytes32(self, condition_id: str) -> bytes:
        """Convert hex condition_id (0x... or raw hex) to 32-byte bytes."""
        raw = condition_id.strip()
        if raw.startswith("0x"):
            raw = raw[2:]
        b = bytes.fromhex(raw)
        if len(b) > 32:
            return b[-32:]
        if len(b) < 32:
            return b"\x00" * (32 - len(b)) + b
        return b
