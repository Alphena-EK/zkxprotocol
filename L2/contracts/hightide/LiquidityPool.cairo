%lang starknet

from starkware.cairo.common.bool import FALSE
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_not_zero
from starkware.starknet.common.syscalls import get_caller_address
from starkware.cairo.common.uint256 import Uint256, uint256_le

from contracts.Constants import Hightide_INDEX, Starkway_INDEX
from contracts.DataTypes import HighTideMetaData, RewardToken
from contracts.interfaces.IAuthorizedRegistry import IAuthorizedRegistry
from contracts.interfaces.IERC20 import IERC20
from contracts.interfaces.IHighTide import IHighTide
from contracts.interfaces.IStarkway import IStarkway
from contracts.libraries.CommonLibrary import CommonLib

// ///////////
// Storage //
// ///////////

// Stores hightide id of the corresponding liquidity pool contract
@storage_var
func hightide_id() -> (id: felt) {
}

// ///////////////
// Constructor //
// ///////////////

// @notice Constructor of the smart-contract
// @param high_tide_id - id of hightide
// @param registry_address Address of the AuthorizedRegistry contract
// @param version Version of this contract
@constructor
func constructor{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    high_tide_id: felt, registry_address: felt, version: felt
) {
    with_attr error_message("LiquidityPool: Hightide id cannot be 0") {
        assert_not_zero(high_tide_id);
    }

    hightide_id.write(high_tide_id);
    CommonLib.initialize(registry_address, version);
    return ();
}

// ///////////
// External //
// ///////////

// @notice - This function is used for either returning or burning the tokens
// @param hightide_id - id of hightide
@external
func perform_return_or_burn{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    hightide_id: felt
) {
    alloc_locals;
    let (registry) = CommonLib.get_registry_address();
    let (version) = CommonLib.get_contract_version();

    // Get Starkway contract address
    let (local starkway_contract_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=Starkway_INDEX, version=version
    );

    // Get Hightide contract address
    let (local hightide_contract_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=Hightide_INDEX, version=version
    );

    // Make sure this function is called from hightide contract
    let (caller) = get_caller_address();
    with_attr error_message("LiquidityPool: caller is not hightide contract") {
        assert caller = hightide_contract_address;
    }

    let (
        reward_tokens_list_len: felt, reward_tokens_list: RewardToken*
    ) = IHighTide.get_hightide_reward_tokens(
        contract_address=hightide_contract_address, hightide_id=hightide_id
    );

    let (hightide_metadata: HighTideMetaData) = IHighTide.get_hightide(
        contract_address=hightide_contract_address, hightide_id=hightide_id
    );

    reward_tokens_recurse(
        hightide_metadata.token_lister_address,
        hightide_metadata.is_burnable,
        hightide_metadata.liquidity_pool_address,
        starkway_contract_address,
        0,
        reward_tokens_list_len,
        reward_tokens_list,
    );
    return ();
}

// ///////////
// Internal //
// ///////////

func reward_tokens_recurse{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    token_lister_address: felt,
    is_burnable: felt,
    liquidity_pool_address: felt,
    starkway_contract_address: felt,
    iterator: felt,
    reward_tokens_list_len: felt,
    reward_tokens_list: RewardToken*,
) {
    if (iterator == reward_tokens_list_len) {
        return ();
    }

    let (
        contract_address_list_len: felt, contract_address_list: felt*
    ) = IStarkway.get_whitelisted_token_addresses(
        contract_address=starkway_contract_address, token_id=[reward_tokens_list].token_id
    );

    transfer_or_burn_tokens(
        token_lister_address,
        is_burnable,
        liquidity_pool_address,
        0,
        contract_address_list_len,
        contract_address_list,
    );

    reward_tokens_recurse(
        token_lister_address,
        is_burnable,
        liquidity_pool_address,
        starkway_contract_address,
        iterator + 1,
        reward_tokens_list_len,
        reward_tokens_list + RewardToken.SIZE,
    );

    return ();
}

func transfer_or_burn_tokens{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    token_lister_address: felt,
    is_burnable: felt,
    liquidity_pool_address: felt,
    iterator: felt,
    contract_address_list_len: felt,
    contract_address_list: felt*,
) {
    if (iterator == contract_address_list_len) {
        return ();
    }

    let current_balance_Uint256: Uint256 = IERC20.balanceOf(
        [contract_address_list], liquidity_pool_address
    );

    let zero_Uint256: Uint256 = Uint256(0, 0);
    let (result) = uint256_le(current_balance_Uint256, zero_Uint256);
    if (result == FALSE) {
        if (is_burnable == FALSE) {
            IERC20.transfer([contract_address_list], token_lister_address, current_balance_Uint256);
        } else {
            IERC20.transfer([contract_address_list], 0x0000DEAD, current_balance_Uint256);
        }
        tempvar syscall_ptr = syscall_ptr;
    } else {
        tempvar syscall_ptr = syscall_ptr;
    }

    transfer_or_burn_tokens(
        token_lister_address,
        is_burnable,
        liquidity_pool_address,
        iterator + 1,
        contract_address_list_len,
        contract_address_list + 1,
    );

    return ();
}