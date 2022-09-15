%lang starknet

from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_not_zero
from contracts.Constants import MasterAdmin_ACTION
from contracts.libraries.Utils import verify_caller_authority

###########
# Events  #
###########

# event emitted whenever a public key is whitelisted
@event
func pubkey_added_to_whitelist(pubkey : felt):
end

# event emitted whenever a public key is removed from whitelist
@event
func pubkey_removed_from_whitelist(pubkey : felt):
end

###########
# Storage #
###########

# this stores a mapping from pubkey to whether it is whitelisted
@storage_var
func pubkey_to_whitelist(pubkey : felt) -> (res : felt):
end

# this var stores the registry address
@storage_var
func registry_address() -> (address : felt):
end

# stores contract version
@storage_var
func version() -> (res : felt):
end

###############
# Constructor #
###############

@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        registry_address_ : felt, version_ : felt):

    with_attr error_message("Registry Address or Version cannot be 0"):
        assert_not_zero(registry_address_)
        assert_not_zero(version_)
    end

    registry_address.write(registry_address_)
    version.write(version_)
    return ()
end


##################
# View Functions #
##################

# @notice - returns whether a public key is whitelisted or not
@view
func is_whitelisted{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        pubkey : felt) -> (res : felt):
    let (res) = pubkey_to_whitelist.read(pubkey)
    return (res)
end

@view
func get_registry_address{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
        address : felt):
    let (current_registry_address) = registry_address.read()
    return (current_registry_address)
end

@view
func get_current_version{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
        current_version : felt):
    let (current_version) = version.read()
    return (current_version)
end

######################
# External Functions #
######################

@external
func set_version{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        new_version : felt):
    let (current_registry_address) = registry_address.read()
    let (current_version) = version.read()

    verify_caller_authority(current_registry_address, current_version, MasterAdmin_ACTION)
    version.write(new_version)
    return ()
end

# @notice - function to whitelist a  public key - callable only by admin
@external
func whitelist_pubkey{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        pubkey : felt):
    let (current_registry_address) = registry_address.read()
    let (current_version) = version.read()

    verify_caller_authority(current_registry_address, current_version, MasterAdmin_ACTION)

    pubkey_to_whitelist.write(pubkey, 1)
    pubkey_added_to_whitelist.emit(pubkey=pubkey)
    return ()
end

# @notice - function to de-whitelist a  public key - callable only by admin
@external
func delist_pubkey{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
        pubkey : felt):
    let (current_registry_address) = registry_address.read()
    let (current_version) = version.read()

    verify_caller_authority(current_registry_address, current_version, MasterAdmin_ACTION)

    pubkey_to_whitelist.write(pubkey, 0)
    pubkey_removed_from_whitelist.emit(pubkey=pubkey)
    return ()
end