%lang starknet

@contract_interface
namespace IABR_Calculations {
    func get_abr_value(market_id: felt) -> (abr: felt, price: felt) {
    }

    func calculate_abr(
        market_id_: felt,
        perp_index_len: felt,
        perp_index: felt*,
        perp_mark_len: felt,
        perp_mark: felt*,
        timestamp_: felt,
    ) -> (res: felt) {
    }
}
