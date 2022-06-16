%lang starknet
%builtins pedersen range_check ecdsa

from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.starknet.common.syscalls import get_caller_address
from starkware.cairo.common.math import assert_not_zero

# @notice Stores the contract version
@storage_var
func contract_version() -> (version : felt):
end

# @notice Stores the address of AuthorizedRegistry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

# stores all account contract addresses of users
@storage_var
func account_registry(index : felt) -> (address : felt):
end

# stores length of the account registry
@storage_var
func account_registry_len() -> (len : felt):
end

# @notice Constructor for the smart-contract
# @param registry_address_ Address of the AuthorizedRegistry contract
# @param version_ Version of this contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    registry_address_ : felt, version_ : felt
):
    registry_address.write(value=registry_address_)
    contract_version.write(value=version_)
    return ()
end

# @notice function to add account contract address to registry, when user deposits funds to L2 for the first time
# @param address_ - Account address to be added
# @returns 1 - If successfully added
@external
func add_to_account_registry{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    address_ : felt
) -> (res : felt):
    let (reg_len) = account_registry_len.read()
    account_registry.write(index=reg_len, value=address_)
    account_registry_len.write(reg_len + 1)
    return (1)
end

# @notice External function called to remove account address from registry
# @param id_ - Index of the element in the list
# @returns 1 - If successfully removed
@external
func remove_from_account_registry{
    syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr
}(id_ : felt) -> (res : felt):
    alloc_locals

    let (caller) = get_caller_address()
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (auth_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=0, version=version
    )

    let (access) = IAdminAuth.get_admin_mapping(
        contract_address=auth_address, address=caller, action=0
    )
    assert_not_zero(access)

    let (account_address) = account_registry.read(index=id_)
    if account_address == 0:
        with_attr error_message("account address does not exists in that index"):
            assert 1 = 0
        end
    end

    let (reg_len) = account_registry_len.read()
    let (last_account_address) = account_registry.read(index=reg_len - 1)

    account_registry.write(index=id_, value=last_account_address)
    account_registry.write(index=reg_len - 1, value=0)

    account_registry_len.write(reg_len - 1)
    return (1)
end

# @notice Internal Function called by get_account_registry to recursively add accounts to the registry and return it
# @param account_registry_len_ - Stores the current length of the populated account registry
# @param account_registry_list_ - Registry of accounts filled up to the index
# @returns account_registry_len_ - Length of the account registry
# @returns account_registry_list_ - registry of account addresses
func populate_account_registry{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    account_registry_len_ : felt, account_registry_list_ : felt*
) -> (account_registry_len_ : felt, account_registry_list_ : felt*):
    alloc_locals
    let (address) = account_registry.read(index=account_registry_len_)

    if address == 0:
        return (account_registry_len_, account_registry_list_)
    end

    assert account_registry_list_[account_registry_len_] = address
    return populate_account_registry(account_registry_len_ + 1, account_registry_list_)
end

# @notice Function to get all user account addresses
# @returns account_registry_len - Length of the account registry
# @returns account_registry - registry of account addresses
@view
func get_account_registry{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    account_registry_len : felt, account_registry : felt*
):
    alloc_locals
    let (account_registry_list : felt*) = alloc()
    let (account_registry_len_, account_registry_list_) = populate_account_registry(
        0, account_registry_list
    )
    return (account_registry_len=account_registry_len_, account_registry=account_registry_list_)
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