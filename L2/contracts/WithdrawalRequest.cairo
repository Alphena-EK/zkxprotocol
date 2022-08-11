%lang starknet

from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_le, assert_not_zero
from starkware.starknet.common.syscalls import get_caller_address

from contracts.Constants import AccountRegistry_INDEX, Asset_INDEX, L1_ZKX_Address_INDEX
from contracts.DataTypes import WithdrawalRequest
from contracts.interfaces.IAccounts import IAccount
from contracts.interfaces.IAccountRegistry import IAccountRegistry
from contracts.interfaces.IAsset import IAsset
from contracts.interfaces.IAuthorizedRegistry import IAuthorizedRegistry
from contracts.libraries.Utils import verify_caller_authority

##########
# Events #
##########

# Event emitted whenever add_withdrawal_request() is called
@event
func add_withdrawal_request_called(
    request_id : felt, user_l1_address : felt, ticker : felt, amount : felt
):
end

# Event emitted whenever update_withdrawal_request() l1 handler is called
@event
func update_withdrawal_request_called(
    from_address : felt, user_l2_address : felt, request_id : felt
):
end

###########
# Storage #
###########

# Stores the contract version
@storage_var
func contract_version() -> (version : felt):
end

# Stores the address of Authorized Registry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

# Maps request id to withdrawal request
@storage_var
func withdrawal_request_mapping(request_id : felt) -> (res : WithdrawalRequest):
end

###############
# Constructor #
###############

# @notice Constructor of the smart-contract
# @param registry_address_ Address of the AuthorizedRegistry contract
# @param version_ Version of this contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    registry_address_ : felt, version_ : felt
):
    with_attr error_message("Registry address and version cannot be 0"):
        assert_not_zero(registry_address_)
        assert_not_zero(version_)
    end

    registry_address.write(value=registry_address_)
    contract_version.write(value=version_)
    return ()
end

##################
# View Functions #
##################

# @notice Function to get withdrawal request corresponding to the request ID
# @param request_id_ ID of the withdrawal Request
# @return withdrawal_request - returns withdrawal request structure
@view
func get_withdrawal_request_data{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    request_id_ : felt
) -> (withdrawal_request : WithdrawalRequest):
    let (res : WithdrawalRequest) = withdrawal_request_mapping.read(request_id=request_id_)
    return (withdrawal_request=res)
end

##############
# L1 Handler #
##############

# @notice Function to handle status updates on withdrawal requests
# @param from_address - The address from where update withdrawal request function is called from
# @param user_l2_address_ - Uers's L2 account contract address
# @param request_id_ - ID of the withdrawal Request
@l1_handler
func update_withdrawal_request{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    from_address : felt, user_l2_address_ : felt, request_id_ : felt
):
    let (registry) = registry_address.read()
    let (version) = contract_version.read()

    # Get L1 ZKX contract address
    let (l1_zkx_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=L1_ZKX_Address_INDEX, version=version
    )

    # Make sure the message was sent by the intended L1 contract.
    with_attr error_message("from address is not matching"):
        assert from_address = l1_zkx_address
    end

    # Create a struct with the withdrawal Request
    let updated_request = WithdrawalRequest(
        user_l1_address=0, user_l2_address=0, ticker=0, amount=0
    )
    withdrawal_request_mapping.write(request_id=request_id_, value=updated_request)

    # update withdrawal history status field to 1
    IAccount.update_withdrawal_history(contract_address=user_l2_address_, request_id_=request_id_)

    # update_withdrawal_request_called event is emitted
    update_withdrawal_request_called.emit(
        from_address=from_address, user_l2_address=user_l2_address_, request_id=request_id_
    )

    return ()
end

######################
# External Functions #
######################

# @notice function to add withdrawal request to the withdrawal request array
# @param request_id_ ID of the withdrawal Request
# @param ticker_ collateral for the requested withdrawal
# @param amount_ Amount to be withdrawn
@external
func add_withdrawal_request{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    request_id_ : felt, ticker_ : felt, amount_ : felt
):
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (caller) = get_caller_address()

    # fetch account registry contract address
    let (account_registry_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=AccountRegistry_INDEX, version=version
    )
    # check whether caller is registered user
    let (present) = IAccountRegistry.is_registered_user(
        contract_address=account_registry_address, address_=caller
    )

    with_attr error_message("Called account contract is not registered"):
        assert_not_zero(present)
    end

    # fetch asset contract address
    let (asset_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=Asset_INDEX, version=version
    )
    
    let (asset_id) = IAsset.get_asset_id_from_ticker(
            contract_address=asset_address, ticker=ticker_
    )

    # check whether user has enough balance
    let (user_balance) = IAccount.get_balance(
            contract_address=caller, assetID_=asset_id
    )

    with_attr error_message(
            "Amount to be withdrawan should be less than or equal to the user balance"):
        assert_le(amount_, user_balance)
    end

    # Validate if the user_l1_address_ is really the counterpart address of the caller
    let (user_l1_address) = IAccount.get_L1_address(contract_address=caller)

    with_attr error_message(
            "User's L1 address should be non zero "):
        assert_not_zero(user_l1_address)
    end

    # Create a struct with the withdrawal Request
    let new_request = WithdrawalRequest(
        user_l1_address=user_l1_address, user_l2_address=caller, ticker=ticker_, amount=amount_
    )

    withdrawal_request_mapping.write(request_id=request_id_, value=new_request)

    # add_withdrawal_request_called event is emitted
    add_withdrawal_request_called.emit(
        request_id=request_id_, user_l1_address=user_l1_address, ticker=ticker_, amount=amount_
    )

    return ()
end
