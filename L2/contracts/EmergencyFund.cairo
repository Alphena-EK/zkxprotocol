%lang starknet

%builtins pedersen range_check ecdsa

from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.starknet.common.syscalls import get_caller_address
from starkware.cairo.common.math import assert_not_zero, assert_le

# @notice Stores the address of AdminAuth contract
@storage_var
func auth_address() -> (contract_address : felt):
end

# @notice Stores the address of Holding contract
@storage_var
func holding_address() -> (contract_address : felt):
end

# @notice Stores the mapping from asset_id to its balance
@storage_var
func balance_mapping(asset_id : felt) -> (amount : felt):
end

# @notice Constructor of the smart-contract
# @param auth_address_ - Address of the adminAuth contract
# @param holding_address_ - Address of the holding contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    auth_address_ : felt, holding_address_ : felt
):
    auth_address.write(value=auth_address_)
    holding_address.write(value=holding_address_)
    return ()
end

# @notice Displays the amount of the balance for the asset_id (asset)
# @param asset_id - Target asset_id
@view
func balance{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt
) -> (
    amount : felt
):
    let (amount) = balance_mapping.read(asset_id = asset_id_)
    return (amount)
end

# @notice Manually add amount to asset_id's balance by admins only
# @param amount - value to add to asset_id's balance
# @param asset_id - target asset_id
@external
func fund{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (auth_addr) = auth_address.read()

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_addr, address=caller, action=0
    )
    assert_not_zero(access)

    let current_amount : felt = balance_mapping.read(asset_id = asset_id_)
    balance_mapping.write(asset_id = asset_id_, value = current_amount + amount)
    return ()
end

# @notice Manually deduct amount from asset_id's balance by admins only
# @param amount - value to add to asset_id's balance
# @param asset_id_ - target asset_id
@external
func defund{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (auth_addr) = auth_address.read()

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_addr, 
        address=caller, action=0
    )
    assert_not_zero(access)

    let current_amount : felt = balance_mapping.read(asset_id = asset_id_)
    with_attr error_message("Amount to be deducted is more than asset's balance"):
        assert_le(amount, current_amount)
    end
    balance_mapping.write(asset_id = asset_id_, value = current_amount - amount)

    return ()
end

# @notice Manually add amount to asset_id's balance in emergency fund and funding contract by admins only
# @param amount - value to add to asset_id's balance
# @param asset_id_ - target asset_id
@external
func fund_holding{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (auth_addr) = auth_address.read()

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address = auth_addr, address = caller, action=0)
    assert_not_zero(access)

    let current_amount : felt = balance_mapping.read(asset_id = asset_id_)
    balance_mapping.write(asset_id = asset_id_, value = current_amount + amount)

    let (holding_addr) = holding_address.read()
    IHolding.fund(contract_address = holding_addr, asset_id = asset_id_, amount = amount)

    return ()
end

# @notice Manually deduct amount from asset_id's balance in emergency fund and funding contract by admins only
# @param amount - value to add to asset_id's balance
# @param asset_id - target asset_id
@external
func defund_holding{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        asset_id : felt, amount : felt):
    alloc_locals

    let (caller) = get_caller_address()
    let (auth_addr) = auth_address.read()

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_addr, address=caller, action=0)
    assert_not_zero(access)

    let current_amount : felt = balance_mapping.read(asset_id=asset_id)
    with_attr error_message("Amount to be deducted is more than asset's balance"):
        assert_le(amount, current_amount)
    end
    balance_mapping.write(asset_id=asset_id, value=current_amount - amount)

    let (holding_addr) = holding_address.read()
    IHolding.defund(contract_address=holding_addr, asset_id=asset_id, amount=amount)

    return ()
end

# @notice AdminAuth interface
@contract_interface
namespace IAdminAuth:
    func get_admin_mapping(address : felt, action : felt) -> (allowed : felt):
    end
end

# @notice Holding interface
@contract_interface
namespace IHolding:
    func fund(asset_id : felt, amount : felt):
    end

    func defund(asset_id : felt, amount : felt):
    end
end