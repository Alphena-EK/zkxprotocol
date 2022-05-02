%lang starknet

%builtins pedersen range_check ecdsa

from starkware.cairo.common.registers import get_fp_and_pc
from starkware.starknet.common.syscalls import get_contract_address
from starkware.cairo.common.math import assert_not_zero, assert_nn, assert_le, assert_in_range
from starkware.cairo.common.cairo_builtins import HashBuiltin, SignatureBuiltin
from starkware.cairo.common.signature import verify_ecdsa_signature
from starkware.cairo.common.math_cmp import is_le
from starkware.cairo.common.hash import hash2
from starkware.cairo.common.hash_state import hash_init, hash_finalize, hash_update
from contracts.Math_64x61 import mul_fp, div_fp

@storage_var
func asset_contract_address() -> (res : felt):
end

@storage_var
func fees_contract_address() -> (res : felt):
end

@storage_var
func holding_contract_address() -> (res : felt):
end

@storage_var
func fees_balance_contract_address() -> (res : felt):
end

@storage_var
func market_contract_address() -> (res : felt):
end

@storage_var
func liquidity_fund_contract_address() -> (res : felt):
end

# @notice struct to store details of markets
struct Market:
    member asset : felt
    member asset_collateral : felt
    member leverage : felt
    member tradable : felt
end

# Struct to pass orders+signatures in a batch in the execute_batch fn
struct MultipleOrder:
    member pub_key : felt
    member sig_r : felt
    member sig_s : felt
    member orderID : felt
    member assetID : felt
    member collateralID : felt
    member price : felt
    member orderType : felt
    member positionSize : felt
    member direction : felt
    member closeOrder : felt
    member parentOrder : felt
    member leverage : felt
end

# Struct for passing the order request to Account Contract
struct OrderRequest:
    member orderID : felt
    member assetID : felt
    member collateralID : felt
    member price : felt
    member orderType : felt
    member positionSize : felt
    member direction : felt
    member closeOrder : felt
    member leverage : felt
    member parentOrder : felt
end

# Struct for passing signature to Account Contract
struct Signature:
    member r_value : felt
    member s_value : felt
end

# @notice struct to store details of assets
struct Asset:
    member asset_version : felt
    member ticker : felt
    member short_name : felt
    member tradable : felt
    member collateral : felt
    member token_decimal : felt
    member metadata_id : felt
    member tick_size : felt
    member step_size : felt
    member minimum_order_size : felt
    member minimum_leverage : felt
    member maximum_leverage : felt
    member currently_allowed_leverage : felt
    member maintenance_margin_fraction : felt
    member initial_margin_fraction : felt
    member incremental_initial_margin_fraction : felt
    member incremental_position_size : felt
    member baseline_position_size : felt
    member maximum_position_size : felt
end

# status 0: initialized
# status 1: partial
# status 2: executed
# status 3: close partial
# status 4: close
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
end

# @notice Constructor for the contract
# @param _asset_contract - Address of the deployed address contract
# @param _trading_fees - Address of the deployed tradingfees contract
@constructor
func constructor{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    _asset_contract,
    _fees_contract,
    _holding_contract,
    _fees_balance_contract,
    _market_contract,
    _liquidity_fund_contract,
):
    asset_contract_address.write(_asset_contract)
    fees_contract_address.write(_fees_contract)
    holding_contract_address.write(_holding_contract)
    fees_balance_contract_address.write(_fees_balance_contract)
    market_contract_address.write(_market_contract)
    liquidity_fund_contract_address.write(_liquidity_fund_contract)
    return ()
end

# @notice Internal function called by execute_batch
# @param size - Size of the order to be executed
# @param ticker - The ticker of each order in the batch
# @param execution_price - Price at which the orders must be executed
# @param request_list_len - No of orders in the batch
# @param request_list - The batch of the orders
# @returns 1, if executed correctly
func check_and_execute{syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}(
    size : felt,
    assetID : felt,
    collateralID : felt,
    marketID : felt,
    execution_price : felt,
    request_list_len : felt,
    request_list : MultipleOrder*,
    long_fees : felt,
    short_fees : felt,
    sum : felt,
) -> (res : felt):
    alloc_locals

    # Check if the list is empty, if yes return 1
    if request_list_len == 0:
        return (sum)
    end

    local margin_amount_
    local borrowed_amount_

    # Create a struct object for the order
    tempvar temp_order : MultipleOrder = MultipleOrder(
        pub_key=[request_list].pub_key,
        sig_r=[request_list].sig_r,
        sig_s=[request_list].sig_s,
        orderID=[request_list].orderID,
        assetID=[request_list].assetID,
        collateralID=[request_list].collateralID,
        price=[request_list].price,
        orderType=[request_list].orderType,
        positionSize=[request_list].positionSize,
        direction=[request_list].direction,
        closeOrder=[request_list].closeOrder,
        parentOrder=[request_list].parentOrder,
        leverage=[request_list].leverage
        )

    # Check whether the leverage is less than currently allowed leverage of the asset
    let (asset_address) = asset_contract_address.read()
    let (asset : Asset) = IAsset.getAsset(contract_address=asset_address, id=temp_order.assetID)
    with_attr error_message("leverage is not less than currently allowed leverage of the asset"):
        assert_le(temp_order.leverage, asset.currently_allowed_leverage)
    end

    # Check if the execution_price is correct
    if temp_order.orderType == 0:
        # if it's a market order, it must be within 2% of the index price
        let (two_percent) = mul_fp(temp_order.price, 46116860184273879)
        tempvar lowerLimit = temp_order.price - two_percent
        tempvar upperLimit = temp_order.price + two_percent

        with_attr error_message("Execution price is not in range."):
            assert_in_range(execution_price, lowerLimit, upperLimit)
        end
        tempvar range_check_ptr = range_check_ptr
    else:
        # if it's a limit order
        if temp_order.direction == 1:
            # if it's a long order
            with_attr error_message(
                    "limit-long order execution price should be less than limit price."):
                assert_le(execution_price, temp_order.price)
            end
            tempvar range_check_ptr = range_check_ptr
        else:
            # if it's a short order
            with_attr error_message(
                    "limit-short order limit price should be less than execution price."):
                assert_le(temp_order.price, execution_price)
            end
            tempvar range_check_ptr = range_check_ptr
        end
        tempvar range_check_ptr = range_check_ptr
    end

    # Check if size is less than or equal to postionSize
    let (cmp_res) = is_le(size, temp_order.positionSize)

    local order_size

    if cmp_res == 1:
        # If yes, make the order_size to be size
        assert order_size = size
    else:
        # If no, make order_size to be the positionSize
        assert order_size = temp_order.positionSize
    end

    local fees_rate
    local sum_temp
    # Calculate the fees depending on whether the order is long or short
    if temp_order.direction == 1:
        assert fees_rate = long_fees
        assert sum_temp = sum + order_size

        # tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
    else:
        assert fees_rate = short_fees
        assert sum_temp = sum - order_size

        # tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
    end

    if temp_order.closeOrder == 0:
        # If the order is to be opened
        let (contract_address) = get_contract_address()

        # Get order details
        let (order_details : OrderDetails) = IAccount.get_order_data(
            contract_address=temp_order.pub_key, order_ID=temp_order.orderID
        )
        let margin_amount = order_details.marginAmount
        let borrowed_amount = order_details.borrowedAmount

        let (leveraged_position_value) = mul_fp(order_size, execution_price)
        let (total_position_value) = div_fp(leveraged_position_value, temp_order.leverage)
        tempvar amount_to_be_borrowed = leveraged_position_value - total_position_value

        # Calculate borrowed and margin amounts to be stored in account contract
        margin_amount_ = margin_amount + total_position_value
        borrowed_amount_ = borrowed_amount + amount_to_be_borrowed

        # Deduct the amount from liquidity funds if order is leveraged
        let (is_non_leveraged) = is_le(temp_order.leverage, 2305843009213693952)

        if is_non_leveraged == 0:
            let (liquidity_fund_address) = liquidity_fund_contract_address.read()
            ILiquidityFund.withdraw(
                contract_address=liquidity_fund_address,
                asset_id_=temp_order.collateralID,
                amount=borrowed_amount_,
                position_id_=temp_order.orderID,
            )
            tempvar syscall_ptr = syscall_ptr
            tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
            tempvar range_check_ptr = range_check_ptr
        else:
            tempvar syscall_ptr = syscall_ptr
            tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
            tempvar range_check_ptr = range_check_ptr
        end
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr

        let (user_balance) = IAccount.get_balance(
            contract_address=temp_order.pub_key, assetID_=temp_order.collateralID
        )

        # Calculate the fees for the order
        let (fees) = mul_fp(fees_rate, leveraged_position_value)

        # Update the fees to be paid by user in fee balance contract
        let (fees_balance_address) = fees_balance_contract_address.read()
        IFeeBalance.update_fee_mapping(
            contract_address=fees_balance_address,
            address=temp_order.pub_key,
            assetID=temp_order.collateralID,
            fee_to_add=fees,
        )

        # Calculate the total amount by adding fees
        tempvar total_amount = total_position_value + fees

        # User must be able to pay the amount
        with_attr error_message(
                "User balance is less than value of the position in trading contract."):
            assert_le(total_amount, user_balance)
        end

        # Transfer the amount to Holding Contract
        IAccount.transfer_from(
            contract_address=temp_order.pub_key,
            assetID_=temp_order.collateralID,
            amount=total_amount,
        )

        # Deposit the funds taken from the user
        let (holding_address) = holding_contract_address.read()
        IHolding.deposit(
            contract_address=holding_address,
            assetID_=temp_order.collateralID,
            amount=leveraged_position_value,
        )

        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    else:
        # If it's a close order
        with_attr error_message(
                "parentOrder field of closing order request is zero in trading contract."):
            assert_not_zero(temp_order.parentOrder)
        end

        local actual_execution_price

        # Get order details
        let (order_details : OrderDetails) = IAccount.get_order_data(
            contract_address=temp_order.pub_key, order_ID=temp_order.parentOrder
        )
        let margin_amount = order_details.marginAmount
        let borrowed_amount = order_details.borrowedAmount

        # current order is short order
        if temp_order.direction == 0:
            actual_execution_price = execution_price
            tempvar range_check_ptr = range_check_ptr
            # current order is long order
        else:
            let (total_value) = mul_fp(order_details.marginAmount, temp_order.leverage)
            let (average_execution_price) = div_fp(total_value, order_details.portionExecuted)
            tempvar pnl = execution_price - average_execution_price
            actual_execution_price = order_details.executionPrice - pnl

            # Check if the user owes the exchange money
            let (is_negative) = is_le(actual_execution_price, 0)

            if is_negative == 1:
                actual_execution_price = 0
            end
            tempvar range_check_ptr = range_check_ptr
        end

        let (leveraged_amount_out) = mul_fp(order_size, actual_execution_price)

        # Calculate the amount that needs to be returned to liquidity fund
        let (percent_of_order) = div_fp(order_size, order_details.portionExecuted)
        let (value_to_be_returned) = mul_fp(borrowed_amount, percent_of_order)
        let (margin_to_be_reduced) = mul_fp(margin_amount, percent_of_order)

        # Deposit the borrowed amount to liquidity funds if order is leveraged
        let (is_non_leveraged) = is_le(temp_order.leverage, 2305843009213693952)

        if is_non_leveraged == 0:
            let (liquidity_fund_address) = liquidity_fund_contract_address.read()
            ILiquidityFund.deposit(
                contract_address=liquidity_fund_address,
                asset_id_=temp_order.collateralID,
                amount=value_to_be_returned,
                position_id_=temp_order.orderID,
            )
            tempvar syscall_ptr = syscall_ptr
            tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
            tempvar range_check_ptr = range_check_ptr
        else:
            tempvar syscall_ptr = syscall_ptr
            tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
            tempvar range_check_ptr = range_check_ptr
        end
        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr

        # Calculate new values for margin and borrowed amounts
        borrowed_amount_ = borrowed_amount - value_to_be_returned
        let margin_amount_temp = margin_amount - margin_to_be_reduced

        # Make margin amount as 0 if the value is negative
        let (is_margin_negative) = is_le(margin_amount_temp, 0)

        if is_margin_negative == 1:
            margin_amount_ = 0
        else:
            margin_amount_ = margin_amount_temp
        end

        let (holding_address) = holding_contract_address.read()
        IHolding.withdraw(
            contract_address=holding_address,
            assetID_=temp_order.collateralID,
            amount=leveraged_amount_out,
        )

        IAccount.transfer(
            contract_address=temp_order.pub_key,
            assetID_=temp_order.collateralID,
            amount=leveraged_amount_out,
        )

        tempvar syscall_ptr = syscall_ptr
        tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        tempvar range_check_ptr = range_check_ptr
    end

    # Create a temporary order object
    let temp_order_request : OrderRequest = OrderRequest(
        orderID=temp_order.orderID,
        assetID=temp_order.assetID,
        collateralID=temp_order.collateralID,
        price=temp_order.price,
        orderType=temp_order.orderType,
        positionSize=temp_order.positionSize,
        direction=temp_order.direction,
        closeOrder=temp_order.closeOrder,
        leverage=temp_order.leverage,
        parentOrder=temp_order.parentOrder,
    )

    # Create a temporary signature object
    let temp_signature : Signature = Signature(r_value=temp_order.sig_r, s_value=temp_order.sig_s)

    tempvar syscall_ptr = syscall_ptr
    tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
    tempvar range_check_ptr = range_check_ptr

    # Call the account contract to initialize the order
    IAccount.execute_order(
        contract_address=temp_order.pub_key,
        request=temp_order_request,
        signature=temp_signature,
        size=order_size,
        execution_price=execution_price,
        margin_amount=margin_amount_,
        borrowed_amount=borrowed_amount_,
    )

    # If it's the first order in the array
    if assetID == 0:
        # Check if the asset is tradable
        let (asset_address) = asset_contract_address.read()
        let (market_address) = market_contract_address.read()
        let (asset : Asset) = IAsset.getAsset(contract_address=asset_address, id=temp_order.assetID)
        let (collateral : Asset) = IAsset.getAsset(
            contract_address=asset_address, id=temp_order.collateralID
        )
        let (market : Market) = IMarket.getMarket(contract_address=market_address, id=marketID)

        # tempvar pedersen_ptr : HashBuiltin* = pedersen_ptr
        with_attr error_message("asset is non tradable in trading contract."):
            assert_not_zero(asset.tradable)
        end

        with_attr error_message("asset is non collaterable in trading contract."):
            assert_not_zero(collateral.collateral)
        end

        with_attr error_message("market is non tradable in trading contract."):
            assert_not_zero(market.tradable)
        end

        # Recursive call with the ticker and price to compare against
        return check_and_execute(
            size,
            temp_order.assetID,
            temp_order.collateralID,
            marketID,
            execution_price,
            request_list_len - 1,
            request_list + MultipleOrder.SIZE,
            long_fees,
            short_fees,
            sum_temp,
        )
    end
    # Assert that the order has the same ticker and price as the first order
    with_attr error_message("assetID is not same as opposite order's assetID in trading contract."):
        assert assetID = temp_order.assetID
    end

    with_attr error_message(
            "collateralID is not same as opposite order's collateralID in trading contract."):
        assert collateralID = temp_order.collateralID
    end

    # Recursive Call
    return check_and_execute(
        size,
        assetID,
        collateralID,
        marketID,
        execution_price,
        request_list_len - 1,
        request_list + MultipleOrder.SIZE,
        long_fees,
        short_fees,
        sum_temp,
    )
end

# @notice Function to execute multiple orders in a batch
# @param size - Size of the order to be executed
# @param execution_price - Price at which the orders must be executed
# @param request_list_len - No of orders in the batch
# @param request_list - The batch of the orders
# @returns res - 1 if executed correctly
@external
func execute_batch{
    syscall_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr, ecdsa_ptr : SignatureBuiltin*
}(
    size : felt,
    execution_price : felt,
    marketID : felt,
    request_list_len : felt,
    request_list : MultipleOrder*,
) -> (res : felt):
    alloc_locals

    # Fetch the base fees for long and short orders
    let (fees_address) = fees_contract_address.read()
    let (long, short) = ITradingFees.get_fees(contract_address=fees_address)

    # Assert that these fees are not 0
    with_attr error_message("long must not be zero. Got long={long}."):
        assert_not_zero(long)
    end

    with_attr error_message("short must not be zero. Got short={short}."):
        assert_not_zero(short)
    end

    # Store it in a local var to send it to check_and_execute
    local long_fee = long
    local short_fee = short

    # Recursively loop through the orders in the batch
    let (result) = check_and_execute(
        size,
        0,
        0,
        marketID,
        execution_price,
        request_list_len,
        request_list,
        long_fee,
        short_fee,
        0,
    )

    # Check if every order has a counter order
    with_attr error_message("check and execute returned non zero integer."):
        assert result = 0
    end
    return (1)
end

# @notice Account interface
@contract_interface
namespace IAccount:
    func execute_order(
        request : OrderRequest,
        signature : Signature,
        size : felt,
        execution_price : felt,
        margin_amount : felt,
        borrowed_amount : felt,
    ) -> (res : felt):
    end

    func transfer_from(assetID_ : felt, amount : felt) -> ():
    end

    func get_order_data(order_ID : felt) -> (res : OrderDetails):
    end

    func transfer(assetID_ : felt, amount : felt) -> ():
    end

    func get_balance(assetID_ : felt) -> (res : felt):
    end
end

# @notice TradingFees interface
@contract_interface
namespace ITradingFees:
    func get_fees() -> (long_fees : felt, short_fees : felt):
    end
end

# @notice Asset interface
@contract_interface
namespace IAsset:
    func getAsset(id : felt) -> (currAsset : Asset):
    end
end

# @notice Holding interface
@contract_interface
namespace IHolding:
    func deposit(assetID_ : felt, amount : felt):
    end

    func withdraw(assetID_ : felt, amount : felt):
    end
end

# @notice Fee Balance interface
@contract_interface
namespace IFeeBalance:
    func update_fee_mapping(address : felt, assetID : felt, fee_to_add : felt):
    end
end

# @notice Markets interface
@contract_interface
namespace IMarket:
    func getMarket(id : felt) -> (currMarket : Market):
    end
end

# @notice Liquidity fund interface
@contract_interface
namespace ILiquidityFund:
    func deposit(asset_id_ : felt, amount : felt, position_id_):
    end

    func withdraw(asset_id_ : felt, amount : felt, position_id_):
    end
end
