%lang starknet

from contracts.DataTypes import PriceData, MultipleOrder

@contract_interface
namespace ILiquidate:

    func check_liquidation(account_address : felt, prices_len : felt, prices : PriceData*
                        ) -> (liq_result : felt, least_collateral_ratio_position : felt):
    end

    func check_order_can_be_opened(order : MultipleOrder, size : felt, execution_price: felt):
    end

end
