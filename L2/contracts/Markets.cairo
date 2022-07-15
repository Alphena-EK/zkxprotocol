%lang starknet

from contracts.DataTypes import Asset, Market, MarketWID
from contracts.Constants import (
    AdminAuth_INDEX,
    Asset_INDEX,
    ManageMarkets_ACTION,
)
from contracts.interfaces.IAuthorizedRegistry import IAuthorizedRegistry
from contracts.interfaces.IAdminAuth import IAdminAuth
from contracts.interfaces.IAsset import IAsset
from contracts.libraries.Utils import verify_caller_authority
from starkware.cairo.common.alloc import alloc
from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.math import assert_not_zero
from starkware.cairo.common.math_cmp import is_le
from starkware.starknet.common.syscalls import get_caller_address

# @notice Stores the contract version
@storage_var
func contract_version() -> (version : felt):
end

# @notice Stores the address of Authorized Registry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

# Store markets in an array to enable retrieval from node
@storage_var
func markets_array(index : felt) -> (market_id : felt):
end

# Length of the markets array
@storage_var
func markets_array_len() -> (len : felt):
end

# @notice Mapping between market ID and Market data
@storage_var
func market(id : felt) -> (res : Market):
end

# @notice Mapping between assetID, collateralID and MarketID
@storage_var
func market_mapping(asset_id : felt, collateral_id : felt) -> (res : felt):
end

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

# @notice Add market function
# @param id - random string generated by zkxnode's mongodb
# @param newMarket - Market struct variable with the required details
# if tradable value of newMarket = 2, it means take value from Asset contract
@external
func addMarket{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt, newMarket : Market
):
    alloc_locals
    # Auth Check
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    with_attr error_message("Caller is not authorized to manage markets"):    
        verify_caller_authority(registry, version, ManageMarkets_ACTION)
    end

    # Value of tradable field should be less than or equal to 2
    let (is_less) = is_le(newMarket.tradable, 2)
    assert_not_zero(is_less)

    # Getting asset details
    let (asset_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=Asset_INDEX, version=version
    )
    let (asset1 : Asset) = IAsset.getAsset(contract_address=asset_address, id=newMarket.asset)
    let (asset2 : Asset) = IAsset.getAsset(
        contract_address=asset_address, id=newMarket.assetCollateral
    )

    assert_not_zero(asset2.collateral)
    assert_not_zero(asset1.ticker)

    if newMarket.tradable == 2:
        market.write(
            id=id,
            value=Market(asset=newMarket.asset, assetCollateral=newMarket.assetCollateral, leverage=newMarket.leverage, tradable=asset1.tradable, ttl=newMarket.ttl),
        )
        market_mapping.write(
            asset_id=newMarket.asset, collateral_id=newMarket.assetCollateral, value=id
        )
    else:
        if newMarket.tradable == 1:
            assert_not_zero(asset1.tradable)
        end

        market.write(id=id, value=newMarket)
        market_mapping.write(
            asset_id=newMarket.asset, collateral_id=newMarket.assetCollateral, value=id
        )
    end

    let (curr_len) = markets_array_len.read()
    markets_array.write(index=curr_len, value=id)
    markets_array_len.write(value=curr_len + 1)

    return ()
end

# @notice Remove market function
# @param id - random string generated by zkxnode's mongodb
@external
func removeMarket{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(id : felt):
    # Auth Check
    with_attr error_message("Caller is not authorized to manage markets"):    
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageMarkets_ACTION)
    end

    market.write(id=id, value=Market(asset=0, assetCollateral=0, leverage=0, tradable=0, ttl=0))
    return ()
end

# @notice Modify leverage for market
# @param id - random string generated by zkxnode's mongodb
# @param leverage - new value for leverage
@external
func modifyLeverage{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt, leverage : felt
):
    # Auth Check
    with_attr error_message("Caller is not authorized to manage markets"):    
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageMarkets_ACTION)
    end

    let (_market : Market) = market.read(id=id)

    market.write(
        id=id,
        value=Market(asset=_market.asset, assetCollateral=_market.assetCollateral, leverage=leverage, tradable=_market.tradable, ttl=_market.ttl),
    )
    return ()
end

# @notice Internal Function called by returnAllMarkets to recursively add assets to the array and return it
# @param array_list_len - Stores the current length of the populated array
# @param array_list - Array of MarketWID filled up to the index
# @returns array_list_len - Length of the array_list
# @returns array_list - Fully populated list of MarketWID
func populate_markets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    array_list_len : felt, array_list : MarketWID*
) -> (array_list_len : felt, array_list : MarketWID*):
    alloc_locals
    let (market_id) = markets_array.read(index=array_list_len)

    if market_id == 0:
        return (array_list_len, array_list)
    end

    let (market_details : Market) = market.read(id=market_id)
    let market_details_w_id = MarketWID(
        id=market_id,
        asset=market_details.asset,
        assetCollateral=market_details.assetCollateral,
        leverage=market_details.leverage,
        tradable=market_details.tradable,
        ttl=market_details.ttl
    )
    assert array_list[array_list_len] = market_details_w_id

    return populate_markets(array_list_len + 1, array_list)
end

# @notice View function to return all the markets with ids in an array
# @returns array_list_len - Length of the array_list
# @returns array_list - Fully populated list of MarketWID
@view
func returnAllMarkets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    array_list_len : felt, array_list : MarketWID*
):
    alloc_locals

    let (array_list : MarketWID*) = alloc()
    return populate_markets(array_list_len=0, array_list=array_list)
end

# @notice Modify tradable flag for market
# @param id - random string generated by zkxnode's mongodb
# @param leverage - new value for tradable flag
@external
func modifyTradable{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    id : felt, tradable : felt
):
    # Auth Check
    with_attr error_message("Caller is not authorized to manage markets"):    
        let (registry) = registry_address.read()
        let (version) = contract_version.read()
        verify_caller_authority(registry, version, ManageMarkets_ACTION)
    end

    # Value of tradable field should be less than or equal to 2
    let (is_less) = is_le(tradable, 2)
    assert_not_zero(is_less)

    let (_market : Market) = market.read(id=id)

    let (asset_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=Asset_INDEX, version=version
    )
    let (asset1 : Asset) = IAsset.getAsset(contract_address=asset_address, id=_market.asset)

    if _market.tradable == 2:
        market.write(
            id=id,
            value=Market(asset=_market.asset, assetCollateral=_market.assetCollateral, leverage=_market.leverage, tradable=asset1.tradable, ttl=_market.ttl),
        )
    else:
        if tradable == 1:
            assert_not_zero(asset1.tradable)
        end
        market.write(
            id=id,
            value=Market(asset=_market.asset, assetCollateral=_market.assetCollateral, leverage=_market.leverage, tradable=tradable, ttl=_market.ttl),
        )
    end

    return ()
end

# @notice Getter function for Markets
# @param id - random string generated by zkxnode's mongodb
# @return currMarket - Returns the requested market
@view
func getMarket{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(id : felt) -> (
    currMarket : Market
):
    let (currMarket) = market.read(id=id)
    return (currMarket)
end

# @notice Getter function for Markets from assetID and collateralID
# @param assetID - Id of the asset
# @param collateralID - Id of the collateral
# @return currMarket - Returns the requested market
@view
func getMarket_from_assets{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    asset_id : felt, collateral_id : felt
) -> (market_id : felt):
    let (currMarket) = market_mapping.read(asset_id=asset_id, collateral_id=collateral_id)
    return (currMarket)
end