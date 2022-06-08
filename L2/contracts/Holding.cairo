%lang starknet

%builtins pedersen range_check ecdsa

from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.starknet.common.syscalls import get_caller_address
from starkware.cairo.common.math import assert_not_zero, assert_le

# @notice Stores the contract version
@storage_var
func contract_version() -> (version : felt):
end

# @notice Stores the address of Authorized Registry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

# @notice Stores the mapping from asset_id to its balance
@storage_var
func balance_mapping(asset_id : felt) -> (amount : felt):
end

# @notice Constructor of the smart-contract
# @param resgitry_address_ Address of the AuthorizedRegistry contract
# @param version_ Version of this contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    registry_address_ : felt, version_ : felt
):
    registry_address.write(value=registry_address_)
    contract_version.write(value=version_)
    return ()
end

# @notice Manually add amount to asset_id's balance
# @param asset_id - target asset_id
# @param amount - value to add to asset_id's balance
@external
func fund{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals
    # Auth Check
    let (caller) = get_caller_address()
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (auth_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=0, version=version
    )

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_address, address=caller, action=5
    )

    if access == 0:
        # Get EmergencyFund address from registry
        let (emergency_fund_address) = IAuthorizedRegistry.get_contract_address(
            contract_address=registry, index=8, version=version
        )

        with_attr error_message("Caller is not authorized to do the transfer"):
            assert caller = emergency_fund_address
        end

        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    else:
        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    end

    let current_amount : felt = balance_mapping.read(asset_id=asset_id_)
    balance_mapping.write(asset_id=asset_id_, value=current_amount + amount)

    return ()
end

# @notice Manually deduct amount from asset_id's balance
# @param asset_id - target asset_id
# @param amount - value to deduct from asset_id's balance
@external
func defund{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (auth_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=0, version=version
    )

    # Auth Check
    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_address, address=caller, action=5
    )

    if access == 0:
        # Get EmergencyFund address from registry
        let (emergency_fund_address) = IAuthorizedRegistry.get_contract_address(
            contract_address=registry, index=8, version=version
        )

        with_attr error_message("Caller is not authorized to do the transfer"):
            assert caller = emergency_fund_address
        end

        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    else:
        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    end

    let current_amount : felt = balance_mapping.read(asset_id=asset_id_)
    with_attr error_message("Amount to be deducted is more than asset's balance"):
        assert_le(amount, current_amount)
    end
    balance_mapping.write(asset_id=asset_id_, value=current_amount - amount)

    return ()
end

# @notice Deposit amount for a asset_id by an order
# @parama setID - target asset_id
# @param amount - value to deduct from asset_id's balance
@external
func deposit{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (registry) = registry_address.read()
    let (version) = contract_version.read()

    # Get trading contract address
    let (trading_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=5, version=version
    )

    with_attr error_message("Caller is not authorized to do the transfer"):
        assert caller = trading_address
    end

    let current_amount : felt = balance_mapping.read(asset_id=asset_id_)
    balance_mapping.write(asset_id=asset_id_, value=current_amount + amount)

    return ()
end

# @notice Withdraw amount for a asset_id by an order
# @param asset_id - target asset_id
# @param amount - value to deduct from asset_id's balance
@external
func withdraw{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt, amount : felt
):
    alloc_locals

    let (caller) = get_caller_address()
    let (registry) = registry_address.read()
    let (version) = contract_version.read()

    # Get trading contract address
    let (trading_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=5, version=version
    )

    with_attr error_message("Caller is not authorized to do the transfer"):
        assert caller = trading_address
    end

    let current_amount : felt = balance_mapping.read(asset_id=asset_id_)
    with_attr error_message("Amount to be deducted is more than asset's balance"):
        assert_le(amount, current_amount)
    end
    balance_mapping.write(asset_id=asset_id_, value=current_amount - amount)

    return ()
end

# @notice Displays the amount of the balance for the asset_id(asset)
# @param asset_id - Target asset_id
# @return amount - Balance amount corresponding to the asset_id
@view
func balance{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id_ : felt
) -> (amount : felt):
    let (amount) = balance_mapping.read(asset_id=asset_id_)
    return (amount)
end

# @notice AuthorizedRegistry interface
@contract_interface
namespace IAuthorizedRegistry:
    func get_contract_address(index : felt, version : felt) -> (address : felt):
    end
end

# @notice AdminAuth interface
@contract_interface
namespace IAdminAuth:
    func get_admin_mapping(address : felt, action : felt) -> (allowed : felt):
    end
end
