%lang starknet

from contracts.DataTypes import TraderStats, VolumeMetaData

@contract_interface
namespace IUserStats {
    // external functions
    func record_trader_stats(
        season_id_: felt,
        pair_id_: felt,
        trader_stats_list_len: felt,
        trader_stats_list: TraderStats*,
    ) {
    }

    // View functions
    func get_trader_fee(season_id_: felt, pair_id_: felt, trader_address_: felt) -> (
        fee_64x61: felt
    ) {
    }
    func get_total_fee(season_id_: felt, pair_id_: felt) -> (total_fee_64x61: felt) {
    }
    func get_trader_order_volume(trader_address_: felt, volume_type_: VolumeMetaData) -> (
        number_of_orders: felt, total_volume_64x61: felt
    ) {
    }
    func get_trader_pnl(season_id_: felt, pair_id_: felt, trader_address_: felt) -> (
        pnl_64x61: felt
    ) {
    }
    func get_trader_margin_amount(season_id_: felt, pair_id_: felt, trader_address_: felt) -> (
        margin_amount_64x61: felt
    ) {
    }
}
