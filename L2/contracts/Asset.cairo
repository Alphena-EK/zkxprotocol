%lang starknet

from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_not_zero
from starkware.starknet.common.messages import send_message_to_l1
from starkware.starknet.common.syscalls import get_caller_address

from contracts.Constants import AdminAuth_INDEX, L1_ZKX_Address_INDEX, ManageAssets_ACTION
from contracts.DataTypes import Asset, AssetWID
from contracts.interfaces.IAdminAuth import IAdminAuth
from contracts.interfaces.IAuthorizedRegistry import IAuthorizedRegistry
from contracts.libraries.Utils import verify_caller_authority

const ADD_ASSET = 1
const REMOVE_ASSET = 2

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

# Stores the version of the asset contract to refresh in node
@storage_var
func version() -> (res : felt):
end

# Mapping between asset ID and Asset data
@storage_var
func asset(id : felt) -> (res : Asset):
end

# Stores all assets available in the platform
@storage_var
func assets_array(index : felt) -> (asset_id : felt):
end

# Stores the length of the assets array
@storage_var
func assets_array_len() -> (len : felt):
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
    registry_address.write(value=registry_address_)
    contract_version.write(value=version_)
    return ()
end

##################
# View Functions #
##################

# @notice View function to get asset info
# @param id - ID of the asset
# @return currAsset - Returns the requested asset
@view
func getAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(id : felt) -> (
    currAsset : Asset
):
    let (currAsset) = asset.read(id=id)
    return (currAsset)
end

# @notice View function to get the maintenance margin for the asset
# @param id - Id of the asset
# @return maintenance_margin - Returns the maintenance margin of the asset
@view
func get_maintenance_margin{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt
) -> (maintenance_margin : felt):
    let (curr_asset) = asset.read(id=id)
    return (curr_asset.maintenance_margin_fraction)
end

# @notice View function for getting version
# @return  - Returns the version
@view
func get_version{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    version : felt
):
    let (res) = version.read()
    return (version=res)
end

# @notice View function to return all the assets with ids in an array
# @return array_list_len - Length of the array_list
# @return array_list - Fully populated list of AssetWID
@view
func returnAllAssets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    array_list_len : felt, array_list : AssetWID*
):
    alloc_locals

    let (array_list : AssetWID*) = alloc()
    return populate_assets(array_list_len=0, array_list=array_list)
end

######################
# External Functions #
######################

# @notice Add asset function
# @param id - random string generated by zkxnode's mongodb
# @param Asset - Asset struct variable with the required details
@external
func addAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt, newAsset : Asset
):
    with_attr error_message("Caller is not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageAssets_ACTION)
    end

    asset.write(id=id, value=newAsset)
    updateAssetListInL1(assetId=id, ticker=newAsset.ticker, action=ADD_ASSET)

    let (curr_len) = assets_array_len.read()
    assets_array.write(index=curr_len, value=id)
    assets_array_len.write(value=curr_len + 1)
    return ()
end

# @notice Remove asset function
# @param id - random string generated by zkxnode's mongodb
@external
func removeAsset{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(id : felt):
    with_attr error_message("Caller is not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageAssets_ACTION)
    end

    let (_asset : Asset) = asset.read(id=id)

    asset.write(
        id=id,
        value=Asset(asset_version=0, ticker=0, short_name=0, tradable=0, collateral=0, token_decimal=0,
        metadata_id=0, tick_size=0, step_size=0, minimum_order_size=0, minimum_leverage=0, maximum_leverage=0,
        currently_allowed_leverage=0, maintenance_margin_fraction=0, initial_margin_fraction=0, incremental_initial_margin_fraction=0,
        incremental_position_size=0, baseline_position_size=0, maximum_position_size=0),
    )

    updateAssetListInL1(assetId=id, ticker=_asset.ticker, action=REMOVE_ASSET)

    return ()
end

# @notice Modify core settings of asset function
# @param id - random string generated by zkxnode's mongodb
# @param short_name - new short_name for the asset
# @param tradable - new tradable flag value for the asset
# @param collateral - new collateral falg value for the asset
# @param token_decimal - It represents decimal point value of the token
# @param metadata_id -ID generated by asset metadata collection in zkx node
@external
func modify_core_settings{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt,
    short_name : felt,
    tradable : felt,
    collateral : felt,
    token_decimal : felt,
    metadata_id : felt,
):
    with_attr error_message("Caller is not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageAssets_ACTION)
    end

    let (_asset : Asset) = asset.read(id=id)

    asset.write(
        id=id,
        value=Asset(asset_version=_asset.asset_version, ticker=_asset.ticker, short_name=short_name, tradable=tradable,
        collateral=collateral, token_decimal=token_decimal, metadata_id=metadata_id, tick_size=_asset.tick_size, step_size=_asset.step_size,
        minimum_order_size=_asset.minimum_order_size, minimum_leverage=_asset.minimum_leverage, maximum_leverage=_asset.maximum_leverage,
        currently_allowed_leverage=_asset.currently_allowed_leverage, maintenance_margin_fraction=_asset.maintenance_margin_fraction,
        initial_margin_fraction=_asset.initial_margin_fraction, incremental_initial_margin_fraction=_asset.incremental_initial_margin_fraction,
        incremental_position_size=_asset.incremental_position_size, baseline_position_size=_asset.baseline_position_size,
        maximum_position_size=_asset.maximum_position_size),
    )
    return ()
end

# @notice Modify core settings of asset function
# @param id - random string generated by zkxnode's mongodb
# @param tick_size - new tradable flag value for the asset
# @param step_size - new collateral flag value for the asset
# @param minimum_order_size - new minimum_order_size value for the asset
# @param minimum_leverage - new minimum_leverage value for the asset
# @param maximum_leverage - new maximum_leverage value for the asset
# @param currently_allowed_leverage - new currently_allowed_leverage value for the asset
# @param maintenance_margin_fraction - new maintenance_margin_fraction value for the asset
# @param initial_margin_fraction - new initial_margin_fraction value for the asset
# @param incremental_initial_margin_fraction - new incremental_initial_margin_fraction value for the asset
# @param incremental_position_size - new incremental_position_size value for the asset
# @param baseline_position_size - new baseline_position_size value for the asset
# @param maximum_position_size - new maximum_position_size value for the asset
@external
func modify_trade_settings{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt,
    tick_size : felt,
    step_size : felt,
    minimum_order_size : felt,
    minimum_leverage : felt,
    maximum_leverage : felt,
    currently_allowed_leverage : felt,
    maintenance_margin_fraction : felt,
    initial_margin_fraction : felt,
    incremental_initial_margin_fraction : felt,
    incremental_position_size : felt,
    baseline_position_size : felt,
    maximum_position_size : felt,
):
    with_attr error_message("Caller is not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (ver) = contract_version.read()
        verify_caller_authority(registry, ver, ManageAssets_ACTION)
    end

    let (ver) = version.read()
    version.write(value=ver + 1)

    let (_asset : Asset) = asset.read(id=id)

    asset.write(
        id=id,
        value=Asset(asset_version=_asset.asset_version + 1, ticker=_asset.ticker, short_name=_asset.short_name, tradable=_asset.tradable,
        collateral=_asset.collateral, token_decimal=_asset.token_decimal, metadata_id=_asset.metadata_id, tick_size=tick_size, step_size=step_size,
        minimum_order_size=minimum_order_size, minimum_leverage=minimum_leverage, maximum_leverage=maximum_leverage,
        currently_allowed_leverage=currently_allowed_leverage, maintenance_margin_fraction=maintenance_margin_fraction,
        initial_margin_fraction=initial_margin_fraction, incremental_initial_margin_fraction=incremental_initial_margin_fraction,
        incremental_position_size=incremental_position_size, baseline_position_size=baseline_position_size, maximum_position_size=maximum_position_size),
    )
    return ()
end

######################
# Internal Functions #
######################

# @notice Internal function to update asset list in L1
# @param assetId - random string generated by zkxnode's mongodb
# @param ticker - Name of the asset
# @param action - It could be ADD_ASSET or REMOVE_ASSET action
func updateAssetListInL1{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    assetId : felt, ticker : felt, action : felt
):
    with_attr error_message("Caller is not authorized to manage assets"):
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageAssets_ACTION)
    end

    # Send the add asset message.
    let (message_payload : felt*) = alloc()
    assert message_payload[0] = action
    assert message_payload[1] = ticker
    assert message_payload[2] = assetId

    # Get L1 ZKX contract address
    let (L1_CONTRACT_ADDRESS) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=L1_ZKX_Address_INDEX, version=version
    )

    send_message_to_l1(to_address=L1_CONTRACT_ADDRESS, payload_size=3, payload=message_payload)

    return ()
end

# @notice Internal Function called by returnAllAssets to recursively add assets to the array and return it
# @param array_list_len - Stores the current length of the populated array
# @param array_list - Array of AssetWID filled up to the index
# @return array_list_len - Length of the array_list
# @return array_list - Fully populated list of AssetWID
func populate_assets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    array_list_len : felt, array_list : AssetWID*
) -> (array_list_len : felt, array_list : AssetWID*):
    alloc_locals
    let (asset_id) = assets_array.read(index=array_list_len)

    if asset_id == 0:
        return (array_list_len, array_list)
    end

    let (asset_details : Asset) = asset.read(id=asset_id)
    let assets_details_w_id = AssetWID(
        id=asset_id,
        asset_version=asset_details.asset_version,
        ticker=asset_details.ticker,
        short_name=asset_details.short_name,
        tradable=asset_details.tradable,
        collateral=asset_details.collateral,
        token_decimal=asset_details.token_decimal,
        metadata_id=asset_details.metadata_id,
        tick_size=asset_details.tick_size,
        step_size=asset_details.step_size,
        minimum_order_size=asset_details.minimum_order_size,
        minimum_leverage=asset_details.minimum_leverage,
        maximum_leverage=asset_details.maximum_leverage,
        currently_allowed_leverage=asset_details.currently_allowed_leverage,
        maintenance_margin_fraction=asset_details.maintenance_margin_fraction,
        initial_margin_fraction=asset_details.initial_margin_fraction,
        incremental_initial_margin_fraction=asset_details.incremental_initial_margin_fraction,
        incremental_position_size=asset_details.incremental_position_size,
        baseline_position_size=asset_details.baseline_position_size,
        maximum_position_size=asset_details.maximum_position_size,
    )
    assert array_list[array_list_len] = assets_details_w_id

    return populate_assets(array_list_len + 1, array_list)
end
