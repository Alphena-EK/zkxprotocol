%lang starknet

from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.bool import FALSE, TRUE
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_not_zero
from starkware.starknet.common.messages import send_message_to_l1
from starkware.starknet.common.syscalls import get_caller_address, get_contract_address

from contracts.Constants import AdminAuth_INDEX, L1_ZKX_Address_INDEX, ManageAssets_ACTION
from contracts.DataTypes import Asset, AssetWID
from contracts.interfaces.IAdminAuth import IAdminAuth
from contracts.interfaces.IAuthorizedRegistry import IAuthorizedRegistry
from contracts.libraries.Utils import verify_caller_authority

#############
# Constants #
#############

const ADD_ASSET = 1
const REMOVE_ASSET = 2

##########
# Events #
##########

# Event emitted on Asset contract deployment
@event
func Asset_Contract_Created(
    contract_address : felt, registry_address : felt, version : felt, caller_address : felt
):
end

# Event emitted whenever new asset is added
@event
func Asset_Added(asset_id : felt, ticker : felt, caller_address : felt):
end

# Event emitted whenever asset is removed
@event
func Asset_Removed(asset_id : felt, ticker : felt, caller_address : felt):
end

# Event emitted whenever asset core settings are updated
@event
func Asset_Core_Settings_Update(asset_id : felt, ticker : felt, caller_address : felt):
end

# Event emitted whenever asset trade settings are updated
@event
func Asset_Trade_Settings_Update(
    asset_id : felt,
    ticker : felt,
    new_contract_version : felt,
    new_asset_version : felt,
    caller_address : felt,
):
end

###########
# Storage #
###########

# Contract version
@storage_var
func contract_version() -> (version : felt):
end

# Address of AuthorizedRegistry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

# Version of Asset contract to refresh in node
@storage_var
func version() -> (res : felt):
end

# Length of assets array
@storage_var
func assets_array_len() -> (len : felt):
end

# Array of asset IDs
@storage_var
func asset_id_by_index(index : felt) -> (asset_id : felt):
end

# Mapping between asset ID and asset's index
@storage_var
func asset_index_by_id(asset_id : felt) -> (index : felt):
end

# Mapping between asset ID and asset's data
@storage_var
func asset_by_id(asset_id : felt) -> (res : Asset):
end

# Bool indicating if ID already exists
@storage_var
func asset_id_exists(asset_id : felt) -> (res : felt):
end

# Bool indicating if ticker already exists
@storage_var
func asset_ticker_exists(ticker : felt) -> (res : felt):
end

###############
# Constructor #
###############

# @notice Constructor of the smart-contract
# @param registry_address_ Address of the AuthorizedRegistry contract
# @param version_ Version of this contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _registry_address : felt, _version : felt
):
    # Validate arguments
    with_attr error_message("Registry address or version used for Asset deployment is 0"):
        assert_not_zero(_registry_address)
        assert_not_zero(_version)
    end

    # Initialize storage
    registry_address.write(_registry_address)
    contract_version.write(_version)

    # Emit event
    let (contract_address) = get_contract_address()
    let (caller_address) = get_caller_address()
    Asset_Contract_Created.emit(contract_address, _registry_address, _version, caller_address)

    return ()
end

##################
# View functions #
##################

# @notice View function for Assets
# @param _id - random string generated by zkxnode's mongodb
# @return currAsset - Returns the requested asset
@view
func getAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(_id : felt) -> (
    currAsset : Asset
):
    verify_asset_id_exists(_id, _should_exist=TRUE)
    let (asset : Asset) = asset_by_id.read(_id)
    return (asset)
end

# @notice View function to get the maintenance margin for the asset
# @param _id - Id of the asset
# @return maintenance_margin - Returns the maintenance margin of the asset
@view
func get_maintenance_margin{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _id : felt
) -> (maintenance_margin : felt):
    verify_asset_id_exists(_id, _should_exist=TRUE)
    let (asset : Asset) = asset_by_id.read(_id)
    return (asset.maintenance_margin_fraction)
end

# @notice View function for getting version
# @return - Returns the version
@view
func get_version{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    version : felt
):
    let (res) = version.read()
    return (res)
end

# @notice View function to return all the assets with ids in an array
# @return array_list_len - Number of assets
# @return array_list - Fully populated list of assets
@view
func returnAllAssets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    array_list_len : felt, array_list : AssetWID*
):
    let (final_len) = assets_array_len.read()
    let (asset_list : AssetWID*) = alloc()
    return populate_asset_list(0, final_len, asset_list)
end

######################
# External functions #
######################

# @notice Add asset function
# @param _id - random string generated by zkxnode's mongodb
# @param _new_asset - Asset struct variable with the required details
@external
func addAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _id : felt, _new_asset : Asset
):
    alloc_locals

    # Verify authority, state and input
    assert_not_zero(_id)
    verify_caller_authority_asset()
    verify_asset_id_exists(_id, _should_exist=FALSE)
    verify_ticker_exists(_new_asset.ticker, _should_exist=FALSE)
    validate_asset_properties(_new_asset)

    # Save asset_id
    let (curr_len) = assets_array_len.read()
    asset_id_by_index.write(curr_len, _id)
    asset_index_by_id.write(_id, curr_len)
    assets_array_len.write(curr_len + 1)

    # Update id & ticker existence
    asset_id_exists.write(_id, TRUE)
    asset_ticker_exists.write(_new_asset.ticker, TRUE)

    # Save new_asset struct
    asset_by_id.write(_id, _new_asset)

    # Trigger asset update on L1
    update_asset_on_L1(_asset_id=_id, _ticker=_new_asset.ticker, _action=ADD_ASSET)

    # Emit event
    let (caller_address) = get_caller_address()
    Asset_Added.emit(asset_id=_id, ticker=_new_asset.ticker, caller_address=caller_address)

    return ()
end

# @notice Remove asset function
# @param _id_to_remove - random string generated by zkxnode's mongodb
@external
func removeAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _id_to_remove : felt
):
    alloc_locals

    # Verify authority and state
    verify_caller_authority_asset()
    verify_asset_id_exists(_id_to_remove, _should_exist=TRUE)

    # Prepare necessary data
    let (asset_to_remove : Asset) = asset_by_id.read(_id_to_remove)
    local ticker_to_remove = asset_to_remove.ticker
    let (local index_to_remove) = asset_index_by_id.read(_id_to_remove)
    let (local curr_len) = assets_array_len.read()
    local last_asset_index = curr_len - 1
    let (local last_asset_id) = asset_id_by_index.read(last_asset_index)

    # Replace id_to_remove with last_asset_id
    asset_id_by_index.write(index_to_remove, last_asset_id)
    asset_index_by_id.write(last_asset_id, index_to_remove)

    # Delete id_to_remove
    asset_id_by_index.write(last_asset_index, 0)
    assets_array_len.write(curr_len - 1)

    # Mark id & ticker as non-existing
    asset_id_exists.write(_id_to_remove, FALSE)
    asset_ticker_exists.write(ticker_to_remove, FALSE)

    # Delete asset struct
    asset_by_id.write(
        _id_to_remove,
        Asset(
        asset_version=0,
        ticker=0,
        short_name=0,
        tradable=0,
        collateral=0,
        token_decimal=0,
        metadata_id=0,
        tick_size=0,
        step_size=0,
        minimum_order_size=0,
        minimum_leverage=0,
        maximum_leverage=0,
        currently_allowed_leverage=0,
        maintenance_margin_fraction=0,
        initial_margin_fraction=0,
        incremental_initial_margin_fraction=0,
        incremental_position_size=0,
        baseline_position_size=0,
        maximum_position_size=0
        ),
    )

    # Trigger asset update on L1
    update_asset_on_L1(_asset_id=_id_to_remove, _ticker=ticker_to_remove, _action=REMOVE_ASSET)

    # Emit event
    let (caller_address) = get_caller_address()
    Asset_Removed.emit(
        asset_id=_id_to_remove, ticker=ticker_to_remove, caller_address=caller_address
    )

    return ()
end

# @notice Modify core settings of asset function
# @param _id - random string generated by zkxnode's mongodb
# @param _short_name - new short_name for the asset
# @param _tradable - new tradable flag value for the asset
# @param _collateral - new collateral falg value for the asset
# @param _token_decimal - It represents decimal point value of the token
# @param _metadata_id - ID generated by asset metadata collection in zkx node
@external
func modify_core_settings{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _id : felt,
    _short_name : felt,
    _tradable : felt,
    _collateral : felt,
    _token_decimal : felt,
    _metadata_id : felt,
):
    alloc_locals

    # Verify authority and state
    verify_caller_authority_asset()
    verify_asset_id_exists(_id, _should_exist=TRUE)

    # Create updated_asset
    let (asset : Asset) = asset_by_id.read(_id)
    local updated_asset : Asset = Asset(
        asset_version=asset.asset_version,
        ticker=asset.ticker,
        short_name=_short_name,
        tradable=_tradable,
        collateral=_collateral,
        token_decimal=_token_decimal,
        metadata_id=_metadata_id,
        tick_size=asset.tick_size,
        step_size=asset.step_size,
        minimum_order_size=asset.minimum_order_size,
        minimum_leverage=asset.minimum_leverage,
        maximum_leverage=asset.maximum_leverage,
        currently_allowed_leverage=asset.currently_allowed_leverage,
        maintenance_margin_fraction=asset.maintenance_margin_fraction,
        initial_margin_fraction=asset.initial_margin_fraction,
        incremental_initial_margin_fraction=asset.incremental_initial_margin_fraction,
        incremental_position_size=asset.incremental_position_size,
        baseline_position_size=asset.baseline_position_size,
        maximum_position_size=asset.maximum_position_size
        )

    # Validate and save updated asset
    validate_asset_properties(updated_asset)
    asset_by_id.write(_id, updated_asset)

    # Emit event
    let (caller_address) = get_caller_address()
    Asset_Core_Settings_Update.emit(
        asset_id=_id, ticker=updated_asset.ticker, caller_address=caller_address
    )

    return ()
end

# @notice Modify core settings of asset function
# @param _id - random string generated by zkxnode's mongodb
# @param _tick_size - new tradable flag value for the asset
# @param _step_size - new collateral flag value for the asset
# @param _minimum_order_size - new minimum_order_size value for the asset
# @param _minimum_leverage - new minimum_leverage value for the asset
# @param _maximum_leverage - new maximum_leverage value for the asset
# @param _currently_allowed_leverage - new currently_allowed_leverage value for the asset
# @param _maintenance_margin_fraction - new maintenance_margin_fraction value for the asset
# @param _initial_margin_fraction - new initial_margin_fraction value for the asset
# @param _incremental_initial_margin_fraction - new incremental_initial_margin_fraction value for the asset
# @param _incremental_position_size - new incremental_position_size value for the asset
# @param _baseline_position_size - new baseline_position_size value for the asset
# @param _maximum_position_size - new maximum_position_size value for the asset
@external
func modify_trade_settings{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _id : felt,
    _tick_size : felt,
    _step_size : felt,
    _minimum_order_size : felt,
    _minimum_leverage : felt,
    _maximum_leverage : felt,
    _currently_allowed_leverage : felt,
    _maintenance_margin_fraction : felt,
    _initial_margin_fraction : felt,
    _incremental_initial_margin_fraction : felt,
    _incremental_position_size : felt,
    _baseline_position_size : felt,
    _maximum_position_size : felt,
):
    alloc_locals

    # Verify authority and state
    verify_caller_authority_asset()
    verify_asset_id_exists(_id, _should_exist=TRUE)

    # Create updated_asset
    let (asset : Asset) = asset_by_id.read(_id)
    local updated_asset : Asset = Asset(
        asset_version=asset.asset_version + 1,
        ticker=asset.ticker,
        short_name=asset.short_name,
        tradable=asset.tradable,
        collateral=asset.collateral,
        token_decimal=asset.token_decimal,
        metadata_id=asset.metadata_id,
        tick_size=_tick_size,
        step_size=_step_size,
        minimum_order_size=_minimum_order_size,
        minimum_leverage=_minimum_leverage,
        maximum_leverage=_maximum_leverage,
        currently_allowed_leverage=_currently_allowed_leverage,
        maintenance_margin_fraction=_maintenance_margin_fraction,
        initial_margin_fraction=_initial_margin_fraction,
        incremental_initial_margin_fraction=_incremental_initial_margin_fraction,
        incremental_position_size=_incremental_position_size,
        baseline_position_size=_baseline_position_size,
        maximum_position_size=_maximum_position_size
        )

    # Validate and save updated asset
    validate_asset_properties(updated_asset)
    asset_by_id.write(_id, updated_asset)

    # Bump version
    let (local curr_ver) = version.read()
    version.write(curr_ver + 1)

    # Emit event
    let (caller_address) = get_caller_address()
    Asset_Trade_Settings_Update.emit(
        asset_id=_id,
        ticker=updated_asset.ticker,
        new_contract_version=curr_ver + 1,
        new_asset_version=updated_asset.asset_version,
        caller_address=caller_address,
    )

    return ()
end

######################
# Internal functions #
######################

# @notice Internal function to update asset list in L1
# @param _asset_id - random string generated by zkxnode's mongodb
# @param _ticker - Ticker of the asset
# @param _action - It could be ADD_ASSET or REMOVE_ASSET action
func update_asset_on_L1{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _asset_id : felt, _ticker : felt, _action : felt
):
    # Build message payload
    let (message_payload : felt*) = alloc()
    assert message_payload[0] = _action
    assert message_payload[1] = _ticker
    assert message_payload[2] = _asset_id

    # Send asset update message to L1
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (L1_ZKX_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=L1_ZKX_Address_INDEX, version=version
    )
    send_message_to_l1(to_address=L1_ZKX_address, payload_size=3, payload=message_payload)

    return ()
end

# @notice Internal Function called by returnAllAssets to recursively add assets to the array and return it
# @param _current_len - current length of array being populated
# @param _final_len - final length of array being populated
# @param _asset_array - array being populated with assets
# @return array_list_len - Iterator used to populate array
# @return array_list - Fully populated array of AssetWID
func populate_asset_list{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _current_len : felt, _final_len : felt, _asset_array : AssetWID*
) -> (array_list_len : felt, array_list : AssetWID*):
    alloc_locals
    if _current_len == _final_len:
        return (_final_len, _asset_array)
    end
    let (id) = asset_id_by_index.read(_current_len)
    let (asset : Asset) = asset_by_id.read(id)
    assert _asset_array[_current_len] = AssetWID(
        id=id,
        asset_version=asset.asset_version,
        ticker=asset.ticker,
        short_name=asset.short_name,
        tradable=asset.tradable,
        collateral=asset.collateral,
        token_decimal=asset.token_decimal,
        metadata_id=asset.metadata_id,
        tick_size=asset.tick_size,
        step_size=asset.step_size,
        minimum_order_size=asset.minimum_order_size,
        minimum_leverage=asset.minimum_leverage,
        maximum_leverage=asset.maximum_leverage,
        currently_allowed_leverage=asset.currently_allowed_leverage,
        maintenance_margin_fraction=asset.maintenance_margin_fraction,
        initial_margin_fraction=asset.initial_margin_fraction,
        incremental_initial_margin_fraction=asset.incremental_initial_margin_fraction,
        incremental_position_size=asset.incremental_position_size,
        baseline_position_size=asset.baseline_position_size,
        maximum_position_size=asset.maximum_position_size,
        )
    return populate_asset_list(_current_len + 1, _final_len, _asset_array)
end

func verify_caller_authority_asset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}():
    with_attr error_message("Caller not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageAssets_ACTION)
    end
    return ()
end

func verify_asset_id_exists{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _asset_id : felt, _should_exist : felt
):
    with_attr error_message("asset_id existence mismatch"):
        let (id_exists) = asset_id_exists.read(_asset_id)
        assert id_exists = _should_exist
    end
    return ()
end

func verify_ticker_exists{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _ticker : felt, _should_exist : felt
):
    with_attr error_message("Ticker existence mismatch"):
        let (ticker_exists) = asset_ticker_exists.read(_ticker)
        assert ticker_exists = _should_exist
    end
    return ()
end

func validate_asset_properties{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _asset : Asset
):
    # TODO: add asset properties validation https://thalidao.atlassian.net/browse/ZKX-623
    return ()
end
