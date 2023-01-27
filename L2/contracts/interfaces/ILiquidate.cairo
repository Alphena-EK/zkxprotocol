%lang starknet

from contracts.DataTypes import PriceData, MultipleOrder, PositionDetailsForRiskManagement

@contract_interface
namespace ILiquidate {
    func find_under_collateralized_position(
        account_address: felt, prices_len: felt, prices: PriceData*
    ) -> (liq_result: felt, least_collateral_ratio_position: PositionDetailsForRiskManagement) {
    }

    func check_for_risk(order: MultipleOrder, size: felt, execution_price: felt) {
    }
}
