%lang starknet
%builtins pedersen range_check ecdsa

from starkware.cairo.common.registers import get_fp_and_pc
from starkware.cairo.common.math import assert_not_zero, assert_nn
from starkware.cairo.common.cairo_builtins import HashBuiltin, SignatureBuiltin
from starkware.cairo.common.math_cmp import is_le
from starkware.cairo.common.hash import hash2
from starkware.starknet.common.syscalls import get_caller_address
from contracts.Math_64x61 import Math64x61_mul, Math64x61_div

# status 0: initialized
# status 1: partial
# status 2: executed
# status 3: close partial
# status 4: close
# status 5: toBeDeleveraged
# status 6: toBeLiquidated
# status 7: fullyLiquidated
struct OrderDetails:
    member assetID : felt
    member collateralID : felt
    member price : felt
    member executionPrice : felt
    member positionSize : felt
    member orderType : felt
    member direction : felt
    member portionExecuted : felt
    member status : felt
    member marginAmount : felt
    member borrowedAmount : felt
    member leverage : felt
end

# @notice struct for passing the order request to Account Contract
# status 0: initialized
# status 1: partial
# status 2: executed
# status 3: close partial
# status 4: close
# status 5: toBeDeleveraged
# status 6: toBeLiquidated
# status 7: fullyLiquidated
struct OrderDetailsWithIDs:
    member orderID : felt
    member assetID : felt
    member collateralID : felt
    member price : felt
    member executionPrice : felt
    member positionSize : felt
    member orderType : felt
    member direction : felt
    member portionExecuted : felt
    member status : felt
    member marginAmount : felt
    member borrowedAmount : felt
end

# @notice struct to pass price data to the contract
struct PriceData:
    member assetID : felt
    member collateralID : felt
    member assetPrice : felt
    member collateralPrice : felt
end

# @notice struct to pass balances of collaterals from account
struct CollateralBalance:
    member assetID : felt
    member balance : felt
end

# @notice Stores the contract version
@storage_var
func contract_version() -> (version : felt):
end

# @notice Stores the address of Authorized Registry contract
@storage_var
func registry_address() -> (contract_address : felt):
end

#################
# To be removed #
@storage_var
func maintenance() -> (maintenance : felt):
end

@storage_var
func acc_value() -> (acc_value : felt):
end

@storage_var
func collateral_total() -> (collateral_total : felt):
end
#################

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

####################
# To be removed    #
@view
func return_maintenance{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    res : felt
):
    let (_maintenance) = maintenance.read()
    return (res=_maintenance)
end

@view
func return_acc_value{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}() -> (
    res : felt
):
    let (_acc_value) = acc_value.read()
    return (res=_acc_value)
end

@view
func return_collateral_total{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    ) -> (res : felt):
    let (_ct) = collateral_total.read()
    return (res=_ct)
end
#####################

# @notice Finds the usd value of all the collaterals in account contract
# @param prices_len - Length of the prices array
# @param prices - Array containing prices of corresponding collaterals in collaterals array
# @param collaterals_len - Length of the collateral array
# @param collaterals - Array containing balance of each collateral of the user
# @param total_value - Stores the total value in usd of all the collaterals recursed over
# @return usd_value - Value of the collaterals held by user in usd
func find_collateral_balance{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    prices_len : felt,
    prices : PriceData*,
    collaterals_len : felt,
    collaterals : CollateralBalance*,
    total_value : felt,
) -> (usd_value : felt):
    # If the length of the collateral array is 0, return
    if collaterals_len == 0:
        # # To remove ####
        collateral_total.write(total_value)
        #################
        return (total_value)
    end

    # Create a temporary struct to read data from the array element of prices
    tempvar price_details : PriceData = PriceData(
        assetID=[prices].assetID,
        collateralID=[prices].collateralID,
        assetPrice=[prices].assetPrice,
        collateralPrice=[prices].collateralPrice
        )

    # Create a temporary struct to read data from the array element of collaterals
    tempvar collateral_details : CollateralBalance = CollateralBalance(
        assetID=[collaterals].assetID,
        balance=[collaterals].balance
        )
    # Check if the passed prices list is in proper order and the price is not negative
    with_attr error_message("assetID and collateralID do not match"):
        assert price_details.collateralID = collateral_details.assetID
        assert_nn(price_details.collateralPrice)
        assert price_details.assetPrice = 0
    end

    # Calculate the value of the current collateral
    let (collateral_value_usd) = Math64x61_mul(
        collateral_details.balance, price_details.collateralPrice
    )

    # Recurse over the next element
    return find_collateral_balance(
        prices_len=prices_len - 1,
        prices=prices + PriceData.SIZE,
        collaterals_len=collaterals_len - 1,
        collaterals=collaterals + CollateralBalance.SIZE,
        total_value=total_value + collateral_value_usd,
    )
end

# @notice Function that is called recursively by check_recurse
# @param account_address - Account address of the user
# @param positions_len - Length of the positions array
# @param postions - Array with all the position details
# @param prices_len - Length of the prices array
# @param prices - Array with all the price details
# @param total_account_value - Collateral value - borrowed value + positionSize * price
# @param total_maintenance_requirement - maintenance ratio of the asset * value of the position when executed
# @param least_collateral_ratio - The least collateral ratio among the positions
# @param least_collateral_ratio_position - The positionID of the postion which is having the least collateral ratio
# @param least_collateral_ratio_position_collateral_price - Collateral price of the collateral in the postion which is having the least collateral ratio
# @param least_collateral_ratio_position_asset_price - Asset price of an asset in the postion which is having the least collateral ratio
# @return is_liquidation - 1 if positions are marked to be liquidated
# @return least_collateral_ratio_position - The positionID of the least collateralized position
# @return least_collateral_ratio_position_collateral_price - Collateral price of the collateral in least_collateral_ratio_position
# @return least_collateral_ratio_position_asset_price - Asset price of an asset in least_collateral_ratio_position
func check_liquidation_recurse{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    account_address : felt,
    positions_len : felt,
    positions : OrderDetailsWithIDs*,
    prices_len : felt,
    prices : PriceData*,
    total_account_value : felt,
    total_maintenance_requirement : felt,
    least_collateral_ratio : felt,
    least_collateral_ratio_position : felt,
    least_collateral_ratio_position_collateral_price: felt,
    least_collateral_ratio_position_asset_price: felt,
) -> (is_liquidation, least_collateral_ratio_position : felt, least_collateral_ratio_position_collateral_price : felt, least_collateral_ratio_position_asset_price : felt):
    alloc_locals

    # Check if the list is empty, if yes return the result
    if positions_len == 0:
        # Fetch all the collaterals that the user holds
        let (
            collaterals_len : felt, collaterals : CollateralBalance*
        ) = IAccount.return_array_collaterals(contract_address=account_address)

        # Calculate the value of all the collaterals in usd
        let (user_balance) = find_collateral_balance(
            prices_len=prices_len,
            prices=prices,
            collaterals_len=collaterals_len,
            collaterals=collaterals,
            total_value=0,
        )

        # Add the collateral value to the total_account_value
        local total_account_value_collateral = total_account_value + user_balance

        # # To Remove
        # ######################
        maintenance.write(total_maintenance_requirement)
        acc_value.write(total_account_value_collateral)
        # ######################

        # Check if the maintenance margin is not satisfied
        let (is_liquidation) = is_le(total_account_value_collateral, total_maintenance_requirement)

        # Return if the account should be liquidated or not and the orderId of the least colalteralized position
        return (is_liquidation, least_collateral_ratio_position, least_collateral_ratio_position_collateral_price, least_collateral_ratio_position_asset_price)
    end

    # Create a temporary struct to read data from the array element of positions
    tempvar order_details : OrderDetailsWithIDs = OrderDetailsWithIDs(
        orderID=[positions].orderID,
        assetID=[positions].assetID,
        collateralID=[positions].collateralID,
        price=[positions].price,
        executionPrice=[positions].executionPrice,
        positionSize=[positions].positionSize,
        orderType=[positions].orderType,
        direction=[positions].direction,
        portionExecuted=[positions].portionExecuted,
        status=[positions].status,
        marginAmount=[positions].marginAmount,
        borrowedAmount=[positions].borrowedAmount
        )

    # Create a temporary struct to read data from the array element of prices
    tempvar price_details : PriceData = PriceData(
        assetID=[prices].assetID,
        collateralID=[prices].collateralID,
        assetPrice=[prices].assetPrice,
        collateralPrice=[prices].collateralPrice
        )

    # Check if there is a mismatch in prices array and positions array
    with_attr error_message("assetID and collateralID do not match"):
        assert order_details.assetID = price_details.assetID
        assert order_details.collateralID = price_details.collateralID
    end

    # Check if the prices are not negative
    with_attr error("price is invalid or the array is out of bounds"):
        assert_nn(price_details.collateralPrice)
        assert_nn(price_details.assetPrice)
    end

    # Fetch the maintatanence margin requirement from asset contract
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (asset_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=1, version=version
    )
    let (req_margin) = IAsset.get_maintenance_margin(
        contract_address=asset_address, id=order_details.assetID
    )

    # Calculate the required margin in usd
    local total_value = order_details.marginAmount + order_details.borrowedAmount
    let (average_execution_price : felt) = Math64x61_div(total_value, order_details.portionExecuted)
    let (maintenance_position) = Math64x61_mul(
        average_execution_price, order_details.portionExecuted
    )
    let (maintenance_requirement) = Math64x61_mul(req_margin, maintenance_position)
    let (maintenance_requirement_usd) = Math64x61_mul(
        maintenance_requirement, price_details.collateralPrice
    )

    # Calculate pnl to check if it is the least collateralized position
    local price_diff_
    if order_details.direction == 1:
        tempvar price_diff = price_details.assetPrice - average_execution_price
        price_diff_ = price_diff
    else:
        tempvar price_diff = average_execution_price - price_details.assetPrice
        price_diff_ = price_diff
    end

    let (pnl) = Math64x61_mul(price_diff_, order_details.portionExecuted)

    # Calculate the value of the current account margin in usd
    local position_value = maintenance_position - order_details.borrowedAmount + pnl
    let (net_position_value_usd : felt) = Math64x61_mul(
        position_value, price_details.collateralPrice
    )

    # Margin ratio calculation
    local numerator = order_details.marginAmount + pnl
    let (denominator) = Math64x61_mul(order_details.portionExecuted, price_details.assetPrice)
    let (collateral_ratio_position) = Math64x61_div(numerator, denominator)

    let (if_lesser) = is_le(collateral_ratio_position, least_collateral_ratio)

    # If it is the lowest, update least_collateral_ratio and least_collateral_ratio_position
    local least_collateral_ratio_
    local least_collateral_ratio_position_
    local least_collateral_ratio_position_collateral_price_
    local least_collateral_ratio_position_asset_price_
    if if_lesser == 1:
        assert least_collateral_ratio_ = collateral_ratio_position
        assert least_collateral_ratio_position_ = order_details.orderID
        assert least_collateral_ratio_position_collateral_price_ = price_details.collateralPrice
        assert least_collateral_ratio_position_asset_price_ = price_details.assetPrice
    else:
        assert least_collateral_ratio_ = least_collateral_ratio
        assert least_collateral_ratio_position_ = least_collateral_ratio_position
        assert least_collateral_ratio_position_collateral_price_ = least_collateral_ratio_position_collateral_price
        assert least_collateral_ratio_position_asset_price_ = least_collateral_ratio_position_asset_price
    end

    # Recurse over to the next position
    return check_liquidation_recurse(
        account_address=account_address,
        positions_len=positions_len - 1,
        positions=positions + OrderDetailsWithIDs.SIZE,
        prices_len=prices_len - 1,
        prices=prices + PriceData.SIZE,
        total_account_value=total_account_value + net_position_value_usd,
        total_maintenance_requirement=total_maintenance_requirement + maintenance_requirement_usd,
        least_collateral_ratio=least_collateral_ratio_,
        least_collateral_ratio_position=least_collateral_ratio_position_,
        least_collateral_ratio_position_collateral_price = least_collateral_ratio_position_collateral_price_,
        least_collateral_ratio_position_asset_price = least_collateral_ratio_position_asset_price_
    )
end

# @notice Function to calculate amount to be put on sale for deleveraging
# @param account_address_ - account address of the user
# @param position_ - position to be deleveraged
# @param collateral_price_ - collateral price of the collateral in the position
# @param asset_price_ - asset price of the asset in the position
# @returns amount_to_sold - amount to be put on sale for deleveraging
func check_deleveraging{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    account_address_ : felt, position_ : felt, collateral_price_ : felt, asset_price_ : felt
) -> (amount_to_be_sold : felt):
    alloc_locals

    # Get order details
    let (order_details : OrderDetails) = IAccount.get_order_data(
        contract_address=account_address_, order_ID=position_
    )

    # Fetch the maintatanence margin requirement from asset contract
    let (registry) = registry_address.read()
    let (version) = contract_version.read()
    let (asset_address) = IAuthorizedRegistry.get_contract_address(
        contract_address=registry, index=1, version=version
    )
    let (req_margin) = IAsset.get_maintenance_margin(
        contract_address=asset_address, id=order_details.assetID
    )

    let margin_amount = order_details.marginAmount
    let borrowed_amount = order_details.borrowedAmount
    let position_size = order_details.positionSize

    # Calculate the average execution price
    local total_value = margin_amount + borrowed_amount
    let (average_execution_price : felt) = Math64x61_div(total_value, order_details.portionExecuted)

    local price_diff
    if order_details.direction == 1:
        price_diff = asset_price_ - average_execution_price
    else:
        price_diff = average_execution_price - asset_price_
    end    

    # Calcculate amount to be sold for deleveraging
    let (margin_amount_in_usd) = Math64x61_mul(margin_amount , collateral_price_)
    let (maintenance_requirement_in_usd) = Math64x61_mul(req_margin , asset_price_)
    let price_diff_in_usd  = maintenance_requirement_in_usd - price_diff
    let (amount_to_be_present) = Math64x61_div(margin_amount_in_usd, price_diff_in_usd)
    let amount_to_be_sold = position_size - amount_to_be_present

    # Calculate the leverage after deleveraging
    let position_value = margin_amount + borrowed_amount
    let (position_value_in_usd) = Math64x61_mul(position_value, collateral_price_)
    let (amount_to_be_sold_value_in_usd) = Math64x61_mul(amount_to_be_sold, asset_price_)
    let remaining_position_value_in_usd = position_value_in_usd - amount_to_be_sold_value_in_usd
    let (leverage_after_deleveraging) = Math64x61_div(remaining_position_value_in_usd, margin_amount_in_usd)

    # to64x61(2) == 4611686018427387904
    let (can_be_deleveraged) = is_le(leverage_after_deleveraging, 4611686018427387904)
    if can_be_deleveraged == 1:
        return (0)
    else:
        return (amount_to_be_sold)
    end
end

# @notice Function to check and mark the positions to be liquidated
# @param account_address - Account address of the user
# @param prices_len - Length of the prices array
# @param prices - Array with all the price details
# @return res - 1 if positions are marked to be liquidated
@external
func check_liquidation{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    account_address : felt, prices_len : felt, prices : PriceData*
) -> (liq_result : felt, least_collateral_ratio_position : felt):
    alloc_locals

    # Check if the caller is the liquidator contract
    let (caller) = get_caller_address()

    # ###### Add the check here ########

    # Check if the list is empty
    with_attr error_message("Invalid Input"):
        assert_not_zero(prices_len)
    end

    # Fetch all the positions from the Account contract
    let (positions_len : felt, positions : OrderDetailsWithIDs*) = IAccount.return_array_positions(
        contract_address=account_address
    )

    # Check if the list is empty
    with_attr error_message("Position array length is 0"):
        assert_not_zero(positions_len)
    end

    # Recurse through all positions to see if it needs to liquidated
    let (liq_result, least_collateral_ratio_position, least_collateral_ratio_position_collateral_price, least_collateral_ratio_position_asset_price) = check_liquidation_recurse(
        account_address=account_address,
        positions_len=positions_len,
        positions=positions,
        prices_len=prices_len,
        prices=prices,
        total_account_value=0,
        total_maintenance_requirement=0,
        least_collateral_ratio=2305843009213693952,
        least_collateral_ratio_position=0,
        least_collateral_ratio_position_collateral_price = 0,
        least_collateral_ratio_position_asset_price = 0,
    )

    if liq_result == 1:
        let (amount_to_be_sold) = check_deleveraging(account_address, least_collateral_ratio_position, 
            least_collateral_ratio_position_collateral_price, 
            least_collateral_ratio_position_asset_price
        )
        IAccount.liquidate_position(
            contract_address=account_address, id=least_collateral_ratio_position, amount = amount_to_be_sold
        )
        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    else:
        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    end

    return (liq_result, least_collateral_ratio_position)
end

# @notice Account interface
@contract_interface
namespace IAccount:
    func return_array_positions() -> (array_list_len : felt, array_list : OrderDetailsWithIDs*):
    end

    func return_array_collaterals() -> (array_list_len : felt, array_list : CollateralBalance*):
    end

    func liquidate_position(id : felt, amount : felt) -> ():
    end

    func get_balance(assetID_ : felt) -> (res : felt):
    end
    func get_order_data(order_ID : felt) -> (res : OrderDetails):
    end
end

# @notice AuthorizedRegistry interface
@contract_interface
namespace IAuthorizedRegistry:
    func get_contract_address(index : felt, version : felt) -> (address : felt):
    end
end

# @notice Asset interface
@contract_interface
namespace IAsset:
    func get_maintenance_margin(id : felt) -> (maintenance_margin : felt):
    end
end