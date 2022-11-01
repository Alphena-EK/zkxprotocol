%lang starknet

from contracts.DataTypes import MultipleOrder, TraderStats

@contract_interface
namespace ITradingStats {
    // external functions
    func record_trade_batch_stats(
        pair_id_: felt,
        order_size_64x61_: felt,
        execution_price_64x61_: felt,
        request_list_len: felt,
        request_list: MultipleOrder*,
        trader_stats_list_len: felt,
        trader_stats_list: TraderStats*,
    ) -> () {
    }
}
