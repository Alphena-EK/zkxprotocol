%lang starknet

from contracts.interfaces.IFeeDiscount import IFeeDiscount
from contracts.libraries.RelayLibrary import (
record_call_details, 
get_inner_contract, 
initialize,
get_current_version,
get_caller_hash_status,
get_call_counter,
get_registry_address_at_relay,
get_self_index,
get_caller_hash_list,
set_current_version,
mark_caller_hash_paid,
reset_call_counter,
set_self_index,
verify_caller_authority
)


from starkware.cairo.common.cairo_builtins import HashBuiltin

// @notice - This will call initialize to set the registrey address, version and index of underlying contract
@constructor
func constructor{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    registry_address_: felt, version_: felt, index_: felt
) {
    initialize(registry_address_, version_, index_);
    return ();
}

// @notice - All the following are mirror functions for FeeDiscount.cairo - just record call details and forward call

@external
func increment_governance_tokens{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    address: felt, value: felt
) {
    record_call_details('add_user_tokens');
    let (inner_address) = get_inner_contract();
    IFeeDiscount.increment_governance_tokens(inner_address, address, value);
    return ();
}

@external
func decrement_governance_tokens{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    address: felt, value: felt
) {
    record_call_details('remove_user_tokens');
    let (inner_address) = get_inner_contract();
    IFeeDiscount.decrement_governance_tokens(inner_address, address, value);
    return ();
}

@view
func get_user_tokens{syscall_ptr: felt*, pedersen_ptr: HashBuiltin*, range_check_ptr}(
    address: felt
) -> (value: felt) {
    let (inner_address) = get_inner_contract();
    let (res) = IFeeDiscount.get_user_tokens(inner_address, address);
    return (res,);
}
