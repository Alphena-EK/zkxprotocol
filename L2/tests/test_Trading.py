from copyreg import constructor
import pytest
import asyncio
import time
from starkware.starknet.testing.starknet import Starknet
from starkware.starkware_utils.error_handling import StarkException
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.cairo.lang.version import __version__ as STARKNET_VERSION
from starkware.starknet.business_logic.state.state import BlockInfo
from utils import ContractIndex, ManagerAction, Signer, uint, str_to_felt, MAX_UINT256, assert_revert, hash_order, from64x61, to64x61, print_parsed_positions, print_parsed_collaterals
from utils_trading import User, order_time_in_force, order_direction, order_types, order_side, close_order, OrderExecutor, fund_mapping
from utils_links import DEFAULT_LINK_1, prepare_starknet_string
from utils_asset import AssetID, build_asset_properties
from utils_markets import MarketProperties
from helpers import StarknetService, ContractType, AccountFactory
from dummy_addresses import L1_dummy_address


admin1_signer = Signer(123456789987654321)
admin2_signer = Signer(123456789987654322)
alice_signer = Signer(123456789987654323)
bob_signer = Signer(123456789987654324)
charlie_signer = Signer(123456789987654325)
dave_signer = Signer(123456789987654326)
eduard_signer = Signer(123456789987654327)


maker_trading_fees = to64x61(0.0002 * 0.97)
taker_trading_fees = to64x61(0.0005 * 0.97)

BTC_USD_ID = str_to_felt("gecn2j0cm45sz")
BTC_UST_ID = str_to_felt("gecn2j0c12rtzxcmsz")
ETH_USD_ID = str_to_felt("k84azmn47vsj8az")
TSLA_USD_ID = str_to_felt("2jfk20ckwlmzaksc")
UST_USDC_ID = str_to_felt("2jfk20wert12lmzaksc")


@pytest.fixture(scope='module')
def event_loop():
    return asyncio.new_event_loop()


@pytest.fixture(scope='module')
async def adminAuth_factory(starknet_service: StarknetService):
    # Deploy infrastructure (Part 1)
    admin1 = await starknet_service.deploy(ContractType.Account, [
        admin1_signer.public_key
    ])
    admin2 = await starknet_service.deploy(ContractType.Account, [
        admin2_signer.public_key
    ])
    adminAuth = await starknet_service.deploy(ContractType.AdminAuth, [admin1.contract_address, admin2.contract_address])
    registry = await starknet_service.deploy(ContractType.AuthorizedRegistry, [adminAuth.contract_address])
    account_registry = await starknet_service.deploy(ContractType.AccountRegistry, [registry.contract_address, 1])
    fees = await starknet_service.deploy(ContractType.TradingFees, [registry.contract_address, 1])
    asset = await starknet_service.deploy(ContractType.Asset, [registry.contract_address, 1])

    python_executor = OrderExecutor()
    # Deploy user accounts
    account_factory = AccountFactory(
        starknet_service,
        L1_dummy_address,
        registry.contract_address,
        1
    )
    alice = await account_factory.deploy_ZKX_account(alice_signer.public_key)
    print(alice.contract_address)
    alice_test = User(123456789987654323, alice.contract_address)

    bob = await account_factory.deploy_ZKX_account(bob_signer.public_key)
    print(bob.contract_address)
    bob_test = User(123456789987654324, bob.contract_address)

    charlie = await account_factory.deploy_ZKX_account(charlie_signer.public_key)
    print(charlie.contract_address)
    charlie_test = User(123456789987654325, charlie.contract_address)

    dave = await account_factory.deploy_account(dave_signer.public_key)

    eduard = await account_factory.deploy_ZKX_account(eduard_signer.public_key)
    print(eduard.contract_address)
    eduard_test = User(123456789987654327, eduard.contract_address)

    timestamp = int(time.time())
    starknet_service.starknet.state.state.block_info = BlockInfo(
        block_number=1,
        block_timestamp=timestamp,
        gas_price=starknet_service.starknet.state.state.block_info.gas_price,
        sequencer_address=starknet_service.starknet.state.state.block_info.sequencer_address,
        starknet_version=STARKNET_VERSION
    )

    # Deploy infrastructure (Part 2)
    fixed_math = await starknet_service.deploy(ContractType.Math_64x61, [])
    holding = await starknet_service.deploy(ContractType.Holding, [registry.contract_address, 1])
    feeBalance = await starknet_service.deploy(ContractType.FeeBalance, [registry.contract_address, 1])
    market = await starknet_service.deploy(ContractType.Markets, [registry.contract_address, 1])
    liquidity = await starknet_service.deploy(ContractType.LiquidityFund, [registry.contract_address, 1])
    insurance = await starknet_service.deploy(ContractType.InsuranceFund, [registry.contract_address, 1])
    emergency = await starknet_service.deploy(ContractType.EmergencyFund, [registry.contract_address, 1])
    trading = await starknet_service.deploy(ContractType.Trading, [registry.contract_address, 1])
    feeDiscount = await starknet_service.deploy(ContractType.FeeDiscount, [registry.contract_address, 1])
    marketPrices = await starknet_service.deploy(ContractType.MarketPrices, [registry.contract_address, 1])
    # liquidate = await starknet_service.deploy(ContractType.Liquidate, [registry.contract_address, 1])
    collateral_prices = await starknet_service.deploy(
        ContractType.CollateralPrices,
        [registry.contract_address, 1]
    )
    hightide = await starknet_service.deploy(ContractType.HighTide, [registry.contract_address, 1])
    trading_stats = await starknet_service.deploy(ContractType.TradingStats, [registry.contract_address, 1])
    user_stats = await starknet_service.deploy(ContractType.UserStats, [registry.contract_address, 1])

    # Give necessary rights to admin1
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageAssets, True])
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageMarkets, True])
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageAuthRegistry, True])
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageFeeDetails, True])
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageFunds, True])
    await admin1_signer.send_transaction(admin1, adminAuth.contract_address, 'update_admin_mapping', [admin1.contract_address, ManagerAction.ManageCollateralPrices, True])

    # spoof admin1 as account_deployer so that it can update account registry
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.AccountDeployer, 1, admin1.contract_address])

    # add user accounts to account registry
    await admin1_signer.send_transaction(admin1, account_registry.contract_address, 'add_to_account_registry', [admin1.contract_address])
    await admin1_signer.send_transaction(admin1, account_registry.contract_address, 'add_to_account_registry', [admin2.contract_address])
    await admin1_signer.send_transaction(admin1, account_registry.contract_address, 'add_to_account_registry', [alice.contract_address])
    await admin1_signer.send_transaction(admin1, account_registry.contract_address, 'add_to_account_registry', [bob.contract_address])
    await admin1_signer.send_transaction(admin1, account_registry.contract_address, 'add_to_account_registry', [charlie.contract_address])

    # Update contract addresses in registry
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Asset, 1, asset.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Market, 1, market.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.FeeDiscount, 1, feeDiscount.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.TradingFees, 1, fees.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Trading, 1, trading.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.FeeBalance, 1, feeBalance.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Holding, 1, holding.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.EmergencyFund, 1, emergency.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.LiquidityFund, 1, liquidity.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.InsuranceFund, 1, insurance.contract_address])
    # await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Liquidate, 1, liquidate.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.CollateralPrices, 1, collateral_prices.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.AccountRegistry, 1, account_registry.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.MarketPrices, 1, marketPrices.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.Hightide, 1, hightide.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.TradingStats, 1, trading_stats.contract_address])
    await admin1_signer.send_transaction(admin1, registry.contract_address, 'update_contract_registry', [ContractIndex.UserStats, 1, user_stats.contract_address])

    # Add base fee and discount in Trading Fee contract
    base_fee_maker1 = to64x61(0.0002)
    base_fee_taker1 = to64x61(0.0005)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_base_fees', [1, 0, base_fee_maker1, base_fee_taker1])
    base_fee_maker2 = to64x61(0.00015)
    base_fee_taker2 = to64x61(0.0004)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_base_fees', [2, 1000, base_fee_maker2, base_fee_taker2])
    base_fee_maker3 = to64x61(0.0001)
    base_fee_taker3 = to64x61(0.00035)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_base_fees', [3, 5000, base_fee_maker3, base_fee_taker3])
    discount1 = to64x61(0.03)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_discount', [1, 0, discount1])
    discount2 = to64x61(0.05)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_discount', [2, 1000, discount2])
    discount3 = to64x61(0.1)
    await admin1_signer.send_transaction(admin1, fees.contract_address, 'update_discount', [3, 5000, discount3])

    # Add assets
    BTC_properties = build_asset_properties(
        id=AssetID.BTC,
        asset_version=1,
        short_name=str_to_felt("BTC"),
        is_tradable=True,
        is_collateral=False,
        token_decimal=8
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', BTC_properties)

    ETH_properties = build_asset_properties(
        id=AssetID.ETH,
        asset_version=1,
        short_name=str_to_felt("ETH"),
        is_tradable=True,
        is_collateral=False,
        token_decimal=18
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', ETH_properties)

    USDC_properties = build_asset_properties(
        id=AssetID.USDC,
        asset_version=1,
        short_name=str_to_felt("USDC"),
        is_tradable=False,
        is_collateral=True,
        token_decimal=6
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', USDC_properties)

    UST_properties = build_asset_properties(
        id=AssetID.UST,
        asset_version=1,
        short_name=str_to_felt("UST"),
        is_tradable=True,
        is_collateral=True,
        token_decimal=6
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', UST_properties)

    DOGE_properties = build_asset_properties(
        id=AssetID.DOGE,
        asset_version=1,
        short_name=str_to_felt("DOGE"),
        is_tradable=False,
        is_collateral=False,
        token_decimal=8
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', DOGE_properties)

    TESLA_properties = build_asset_properties(
        id=AssetID.TSLA,
        asset_version=1,
        short_name=str_to_felt("TESLA"),
        is_tradable=True,
        is_collateral=False,
        token_decimal=8
    )
    await admin1_signer.send_transaction(admin1, asset.contract_address, 'add_asset', TESLA_properties)

    # Add markets
    BTC_USD_properties = MarketProperties(
        id=BTC_USD_ID,
        asset=AssetID.BTC,
        asset_collateral=AssetID.USDC,
        leverage=to64x61(10),
        is_tradable=True,
        is_archived=False,
        ttl=60,
        tick_size=1,
        step_size=1,
        minimum_order_size=10,
        minimum_leverage=to64x61(1),
        maximum_leverage=to64x61(10),
        currently_allowed_leverage=to64x61(10),
        maintenance_margin_fraction=1,
        initial_margin_fraction=1,
        incremental_initial_margin_fraction=1,
        incremental_position_size=100,
        baseline_position_size=1000,
        maximum_position_size=10000
    )
    await admin1_signer.send_transaction(admin1, market.contract_address, 'add_market', BTC_USD_properties.to_params_list())

    BTC_UST_properties = MarketProperties(
        id=BTC_UST_ID,
        asset=AssetID.BTC,
        asset_collateral=AssetID.UST,
        leverage=to64x61(10),
        is_tradable=True,
        is_archived=False,
        ttl=60,
        tick_size=1,
        step_size=1,
        minimum_order_size=10,
        minimum_leverage=to64x61(1),
        maximum_leverage=to64x61(5),
        currently_allowed_leverage=to64x61(3),
        maintenance_margin_fraction=1,
        initial_margin_fraction=1,
        incremental_initial_margin_fraction=1,
        incremental_position_size=100,
        baseline_position_size=1000,
        maximum_position_size=10000
    )
    await admin1_signer.send_transaction(admin1, market.contract_address, 'add_market', BTC_UST_properties.to_params_list())

    ETH_USD_properties = MarketProperties(
        id=ETH_USD_ID,
        asset=AssetID.ETH,
        asset_collateral=AssetID.USDC,
        leverage=to64x61(10),
        is_tradable=True,
        is_archived=False,
        ttl=60,
        tick_size=1,
        step_size=1,
        minimum_order_size=10,
        minimum_leverage=to64x61(1),
        maximum_leverage=to64x61(5),
        currently_allowed_leverage=to64x61(3),
        maintenance_margin_fraction=1,
        initial_margin_fraction=1,
        incremental_initial_margin_fraction=1,
        incremental_position_size=100,
        baseline_position_size=1000,
        maximum_position_size=10000
    )
    await admin1_signer.send_transaction(admin1, market.contract_address, 'add_market', ETH_USD_properties.to_params_list())

    TSLA_USD_properties = MarketProperties(
        id=TSLA_USD_ID,
        asset=AssetID.TSLA,
        asset_collateral=AssetID.USDC,
        leverage=to64x61(10),
        is_tradable=False,
        is_archived=False,
        ttl=60,
        tick_size=1,
        step_size=1,
        minimum_order_size=10,
        minimum_leverage=to64x61(1),
        maximum_leverage=to64x61(5),
        currently_allowed_leverage=to64x61(3),
        maintenance_margin_fraction=1,
        initial_margin_fraction=1,
        incremental_initial_margin_fraction=1,
        incremental_position_size=100,
        baseline_position_size=1000,
        maximum_position_size=10000
    )
    await admin1_signer.send_transaction(admin1, market.contract_address, 'add_market', TSLA_USD_properties.to_params_list())

    UST_USDC_properties = MarketProperties(
        id=UST_USDC_ID,
        asset=AssetID.UST,
        asset_collateral=AssetID.USDC,
        leverage=to64x61(10),
        is_tradable=True,
        is_archived=False,
        ttl=60,
        tick_size=1,
        step_size=1,
        minimum_order_size=10,
        minimum_leverage=to64x61(1),
        maximum_leverage=to64x61(5),
        currently_allowed_leverage=to64x61(3),
        maintenance_margin_fraction=1,
        initial_margin_fraction=1,
        incremental_initial_margin_fraction=1,
        incremental_position_size=100,
        baseline_position_size=1000,
        maximum_position_size=10000
    )
    await admin1_signer.send_transaction(admin1, market.contract_address, 'add_market', UST_USDC_properties.to_params_list())

    # Update collateral prices
    await admin1_signer.send_transaction(admin1, collateral_prices.contract_address, 'update_collateral_price', [AssetID.USDC, to64x61(1)])
    await admin1_signer.send_transaction(admin1, collateral_prices.contract_address, 'update_collateral_price', [AssetID.UST, to64x61(1)])

    # Fund the Holding contract
    python_executor.set_fund_balance(
        fund=fund_mapping["holding_fund"], asset_id=str_to_felt("USDC"), new_balance=1000000)
    await admin1_signer.send_transaction(admin1, holding.contract_address, 'fund', [AssetID.USDC, to64x61(1000000)])
    await admin1_signer.send_transaction(admin1, holding.contract_address, 'fund', [AssetID.USDC, to64x61(1000000)])

    # Fund the Liquidity fund contract
    python_executor.set_fund_balance(
        fund=fund_mapping["liquidity_fund"], asset_id=str_to_felt("USDC"), new_balance=1000000)
    await admin1_signer.send_transaction(admin1, liquidity.contract_address, 'fund', [AssetID.USDC, to64x61(1000000)])
    await admin1_signer.send_transaction(admin1, liquidity.contract_address, 'fund', [AssetID.UST, to64x61(1000000)])

    return starknet_service.starknet, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, marketPrices, alice_test, bob_test, charlie_test, eduard_test, python_executor, liquidity, insurance


async def set_balance(admin_signer, admin, user, asset_id, new_balance):
    await admin_signer.send_transaction(admin, user.contract_address, "set_balance", [asset_id, new_balance])


async def execute_batch(zkx_node_signer, zkx_node, trading, quantity_locked, market_id, oracle_price, order_list_len, order_list):
    # Send execute_batch transaction
    await zkx_node_signer.send_transaction(zkx_node, trading.contract_address, "execute_batch", [
        quantity_locked,
        market_id,
        oracle_price,
        order_list_len,
        *order_list
    ])


async def execute_batch_reverted(zkx_node_signer, zkx_node, trading, quantity_locked, market_id, oracle_price, order_list_len, order_list, error_message):
    # Send execute_batch transaction
    await assert_revert(
        zkx_node_signer.send_transaction(zkx_node, trading.contract_address, "execute_batch", [
            quantity_locked,
            market_id,
            oracle_price,
            order_list_len,
            *order_list
        ]), reverted_with=error_message)


async def get_user_position(user, market_id, direction):
    user_starknet_query = await user.get_position_data(market_id_=market_id, direction_=direction).call()
    user_starknet_query_parsed = list(user_starknet_query.result.res)
    user_starknet_position = [from64x61(x)
                              for x in user_starknet_query_parsed]
    return user_starknet_position


async def get_user_position_python(user, market_id, direction):
    user_python_query = user.get_position(
        market_id=market_id, direction=direction)
    return list(user_python_query.values())


async def get_fund_balance(fund, asset_id):
    fund_query = await fund.balance(asset_id_=asset_id).call()
    return from64x61(fund_query.result.amount)


async def get_fund_balance_python(executor, fund, asset_id):
    return executor.get_fund_balance(fund, asset_id)


async def get_user_balance(user, asset_id):
    user_query = await user.get_balance(assetID_=asset_id).call()
    return user_query.result.res


async def ger_user_balance_python(user, asset_id):
    return user.get_balance(asset_id)


async def compare_user_balances(users, user_tests, asset_id):
    for i in range(len(users)):
        user_balance = await get_user_balance(user=users[i], asset_id=asset_id)
        user_balance_python = await user_tests[i].get_user_balance_python(user=user_tests[i], asset_id=str_to_felt("USDC"))

        assert user_balance_python == pytest.approx(
            user_balance, abs=1e-6)


async def compare_fund_balances(executor, holding, liquidity, fee_balance, insurance):
    holding_fund_balance = await get_fund_balance(fund=holding, asset_id=AssetID.USDC_ID)
    holding_fund_balance_python = await get_fund_balance_python(executor=executor, fund=fund_mapping["holding_fund"], asset_id=str_to_felt("USDC"))
    assert holding_fund_balance_python == pytest.approx(
        holding_fund_balance, abs=1e-6)

    liquidity_fund_balance = await get_fund_balance(fund=liquidity, asset_id=AssetID.USDC_ID)
    liquidity_fund_balance_python = await get_fund_balance_python(executor=executor, fund=fund_mapping["liquidity_fund"], asset_id=str_to_felt("USDC"))
    assert liquidity_fund_balance_python == pytest.approx(
        liquidity_fund_balance, abs=1e-6)

    fee_balance_balance = await get_fund_balance(fund=fee_balance, asset_id=AssetID.USDC_ID)
    fee_balance_python = await get_fund_balance_python(executor=executor, fund=fund_mapping["fee_balance"], asset_id=str_to_felt("USDC"))
    assert fee_balance_python == pytest.approx(
        fee_balance_balance, abs=1e-6)

    insurance_balance = await get_fund_balance(fund=insurance, asset_id=AssetID.USDC_ID)
    insurance_balance_python = await get_fund_balance_python(executor=executor, fund=fund_mapping["insurance_fund"], asset_id=str_to_felt("USDC"))
    assert insurance_balance_python == pytest.approx(
        insurance_balance, abs=1e-6)

    # @pytest.mark.asyncio
    # async def test_revert_balance_low_user_1(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Insuffiecient balance for the alice
    #     alice_balance = to64x61(100)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Low Balance {alice.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_balance_low_user_2(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Insuffiecient balance for the alice
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(100)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Low Balance {bob.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_leverage_more_than_allowed_user_1(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1), leverage=to64x61(10.1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Leverage must be <= to the maximum allowed leverage- {alice.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_leverage_more_than_allowed_user_2(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, Edaurd, python_executor = adminAuth_factory

    #     # Sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"], leverage=to64x61(10.1))

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Leverage must be <= to the maximum allowed leverage- {bob.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_wrong_market_passed(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=ETH_USD_ID, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: All orders in a batch must be from the same market- {bob.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_taker_direction_wrong(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=ETH_USD_ID, quantity=to64x61(
    #         1), side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Taker order must be in opposite direction of Maker order(s)- {bob.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_maker_direction_wrong(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1.5))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1.5), direction=order_direction["short"])
    #     charlie_short = charlie_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(3), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *
    #               list(charlie_short.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=3, order_list=orders, error_message=f"Trading: All Maker orders must be in the same direction- {charlie.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_quantity_low_user_1(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, edaurd, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Set sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(0.0005)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(0.0005))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Quantity must be >= to the minimum order size- {alice.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_quantity_low_user_2(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Set sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(0.0005)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         0.0005), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Quantity must be >= to the minimum order size- {bob.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_market_untradable(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Set sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = TSLA_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Market is not tradable")

    # @pytest.mark.asyncio
    # async def test_revert_if_leverage_below_1(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Set sufficient balance for alice and bob
    #     alice_balance = to64x61(10000)
    #     bob_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=USDC_ID, new_balance=bob_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = TSLA_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1), leverage=to64x61(0.05))
    #     bob_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(bob_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Leverage must be >= 1- {alice.contract_address}")

    # @pytest.mark.asyncio
    # async def test_revert_if_unregistered_user(adminAuth_factory):
    #     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, feeBalance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor = adminAuth_factory

    #     # Set sufficient balance for alice and eduard
    #     alice_balance = to64x61(10000)
    #     eduard_balance = to64x61(10000)

    #     # Set balance
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=USDC_ID, new_balance=alice_balance)
    #     await set_balance(admin_signer=admin1_signer, admin=admin1, user=eduard, asset_id=USDC_ID, new_balance=eduard_balance)

    #     # Batch params
    #     quantity_locked_1 = to64x61(1)
    #     market_id_1 = BTC_USD_ID
    #     oracle_price_1 = to64x61(1000)

    #     # Generate orders
    #     alice_long = alice_test.create_order(
    #         market_id=market_id_1, quantity=to64x61(1), leverage=to64x61(1))
    #     eduard_short = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #         1), direction=order_direction["short"], side=order_side["taker"])

    #     # Collate orders
    #     orders = [*list(alice_long.values()), *list(eduard_short.values())]

    #     # Check for the error
    #     await execute_batch_reverted(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders, error_message=f"Trading: Leverage must be >= 1- {alice.contract_address}")


@pytest.mark.asyncio
async def test_opening_and_closing_full_orders(adminAuth_factory):
    _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, eduard, fixed_math, holding, fee_balance, _, alice_test, bob_test, charlie_test, eduard_test, python_executor, liquidity, insurance = adminAuth_factory

    ############################################
    # Sufficient balance for users
    alice_balance = to64x61(10000)
    bob_balance = to64x61(10000)

    # Set balance in Starknet
    await set_balance(admin_signer=admin1_signer, admin=admin1, user=alice, asset_id=AssetID.USDC, new_balance=alice_balance)
    await set_balance(admin_signer=admin1_signer, admin=admin1, user=bob, asset_id=AssetID.USDC, new_balance=bob_balance)

    # Set balance in python script
    alice_test.set_balance(new_balance=alice_balance,
                           asset_id=AssetID.USDC)
    bob_test.set_balance(new_balance=bob_balance, asset_id=str_to_felt("USDC"))

    # Batch params for OPEN orders in Starknet
    quantity_locked_1 = to64x61(3)
    market_id_1 = BTC_USD_ID
    oracle_price_1 = to64x61(1000)

    # Batch params for OPEn orders in python script
    quantity_locked_2 = 3
    market_id_2 = BTC_USD_ID
    oracle_price_2 = 1000

    # Generate orders in Starknet
    alice_long_open_1 = alice_test.create_order(
        market_id=market_id_1, quantity=to64x61(3), leverage=to64x61(1))
    bob_short_open_1 = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
        3), direction=order_direction["short"], side=order_side["taker"])

    # Generate orders in python script
    alice_long_open_2 = alice_test.create_order_decimals(
        market_id=market_id_2, quantity=3, leverage=1)
    bob_short_open_2 = bob_test.create_order_decimals(
        market_id=market_id_2, quantity=3, direction=order_direction["short"], side=order_side["taker"])

    # Collate orders in Starknet
    orders_1 = [*list(alice_long_open_1.values()), *
                list(bob_short_open_1.values())]

    # Collate orders in python script
    orders_2 = [alice_long_open_2, bob_short_open_2]
    users_1 = [alice_test, bob_test]

    # Execute the order in starknet
    await execute_batch(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders_1)

    # Execute the order in python sc
    python_executor.execute_batch(
        orders_2, users_1, quantity_locked_2, market_id_2, oracle_price_2)

    # Check the user state with python and starknet
    # alice_long_position = await get_user_position(user=alice, market_id=market_id_1, direction=alice_long_open_1["direction"])
    # alice_long_position_python = await get_user_position_python(user=alice_test, market_id=market_id_2, direction=alice_long_open_2["direction"])
    # print("alice position starknet", alice_long_position)
    # print("alice position python", alice_long_position_python)
    # await compare_user_positions(user = alice, market_id, direction)
    # await compare_user_positions(user = bob,)
    await compare_user_balances(users=[alice, bob], user_tests=[alice_test, bob_test], asset_id=USDC_ID)
    await compare_fund_balances(executor=python_executor, holding=holding, liquidity=liquidity, fee_balance=fee_balance, insurance=insurance)
    # bob_short_position = await get_user_position(user=bob, market_id=market_id_1, direction=bob_short_open_1["direction"])
    # bob_short_position_python = await get_user_position_python(user=bob_test, market_id=market_id_2, direction=bob_short_open_2["direction"])
    # print("bob position starknet", bob_short_position)
    # print("bob position python", bob_short_position_python)

    # holding_fund_balance = await get_fund_balance(fund=holding, asset_id=USDC_ID)
    # holding_fund_balance_python = await get_fund_balance_python(executor=python_executor, fund=fund_mapping["holding_fund"], asset_id=str_to_felt("USDC"))
    # print("holding fund balance:", holding_fund_balance,
    #       holding_fund_balance_python)

    # liquidity_fund_balance = await get_fund_balance(fund=liquidity, asset_id=USDC_ID)
    # liquidity_fund_balance_python = await get_fund_balance_python(executor=python_executor, fund=fund_mapping["liquidity_fund"], asset_id=str_to_felt("USDC"))
    # print("liquidity_fund_balance:", liquidity_fund_balance,
    #       liquidity_fund_balance_python)


#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

    ############################################
    # # Batch params for CLOSE orders
    # quantity_locked_1 = to64x61(3)
    # market_id_1 = BTC_USD_ID
    # oracle_price_1 = to64x61(1000)

    # # Generate orders
    # alice_short_close = alice_test.create_order(
    #     market_id=market_id_1, direction=order_direction["short"], quantity=to64x61(3), close_order=close_order["close"])
    # bob_long_close = bob_test.create_order(market_id=market_id_1, quantity=to64x61(
    #     3), direction=order_direction["long"], side=order_side["taker"], close_order=close_order["close"])

    # print("alice_test..", alice_long_open)
    # print("bob_test...", bob_short_open)

    # # Collate orders
    # orders = [*list(alice_short_close.values()),
    #           *list(bob_long_close.values())]

    # # Execute the order
    # await execute_batch(zkx_node_signer=dave_signer, zkx_node=dave, trading=trading, quantity_locked=quantity_locked_1, market_id=market_id_1, oracle_price=oracle_price_1, order_list_len=2, order_list=orders)

    # orderState1 = await alice.get_position_data(market_id_=market_id_1, direction_=order_direction["long"]).call()
    # res1 = list(orderState1.result.res)
    # print(res1)
    # print("in decimal")
    # print([from64x61(x) for x in res1])

    # orderState2 = await bob.get_position_data(market_id_=market_id_1, direction_=order_direction["short"]).call()
    # res2 = list(orderState2.result.res)
    # print(res2)
    # print("in decimal")
    # print([from64x61(x) for x in res2])

    ############################################


# @pytest.mark.asyncio
# async def test_set_balance_for_testing(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_balance = to64x61(10000)
#     bob_balance = to64x61(10000)
#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [UST_ID, bob_balance])

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()

#     assert alice_curr_balance.result.res == alice_balance
#     assert bob_curr_balance.result.res == bob_balance

#     alice_collaterals = await alice.return_array_collaterals().call()
#     print_parsed_collaterals(alice_collaterals.result.array_list)

#     bob_collaterals = await bob.return_array_collaterals().call()
#     print_parsed_collaterals(bob_collaterals.result.array_list)


# @pytest.mark.asyncio
# async def test_revert_if_market_order_2percent_deviation(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("df54gdfa")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1000)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("adsfgiu34hjjhks")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1000)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1021)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="Trading: Market Order 2% above")


# @pytest.mark.asyncio
# async def test_revert_if_bad_limit_order_long(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("kvhn3m87yhfs")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1000)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("3hf83hdfska")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1000)
#     stopPrice2 = 0
#     orderType2 = 1
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1001)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1,  orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="Trading: Bad long limit order")


# @pytest.mark.asyncio
# async def test_revert_if_bad_limit_order_short(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("fgkiu3iujsd78")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1000)
#     stopPrice1 = 0
#     orderType1 = 1
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("65duhhj438187i")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1000)
#     stopPrice2 = 0
#     orderType2 = 1
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(999)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="Trading: Bad short limit order")


# @pytest.mark.asyncio
# async def test_revert_if_order_mismatch(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("8721jhfkf93hk1")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1078)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("9fd1k31k5h7")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1078)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1078)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="Trading: Net size is non-zero")


# @pytest.mark.asyncio
# async def test_revert_if_asset_not_tradable(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = TSLA_USD_ID

#     order_id_1 = str_to_felt("k3j43l1l34")
#     assetID_1 = TSLA_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1078)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("45kj341kj4")
#     assetID_2 = TSLA_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1078)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1078)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with=f"Trading: Market not tradable")


# @pytest.mark.asyncio
# async def test_revert_if_collateral_mismatch(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("iu4n31kh123")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1078)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("932jh1mjdfsl")
#     assetID_2 = BTC_ID
#     collateralID_2 = UST_ID
#     price2 = to64x61(1078)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1078)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="Trading: Collateral Mismatch")


# @pytest.mark.asyncio
# async def test_revert_if_asset_mismatch(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("3jh1udkasd")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1078)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(3)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("5jkhfdjkew")
#     assetID_2 = ETH_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1078)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(3)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1078)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with=f"Trading: Asset Mismatch")


# @pytest.mark.asyncio
# async def test_revert_wrong_signature(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("zxcds35yts")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(10789)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(1)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("mjuwoxzbcwq4")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(10789)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(10789)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message1[0], signed_message1[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress1, 0,
#     ]))


# @pytest.mark.asyncio
# async def test_revert_stop_orders_execution_price_not_in_range(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     ####### Opening of Orders #######
#     size = to64x61(1)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("bidjsf732hjsfd")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(5000)
#     stopPrice1 = to64x61(6000)
#     orderType1 = 2
#     position1 = to64x61(1)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(1)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("iu32n3246dfsj")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(5000)
#     stopPrice2 = to64x61(4000)
#     orderType2 = 2
#     position2 = to64x61(1)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(7000)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees1 = await fixed_math.Math64x61_mul(amount1.result.res, maker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees2 = await fixed_math.Math64x61_mul(amount2.result.res, taker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 0,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 1,
#     ]), reverted_with="Trading: Invalid stop-limit-price short order")


# @pytest.mark.asyncio
# async def test_retrieval_of_net_positions_1(adminAuth_factory):
#     starknet, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_net_positions = await alice.get_net_positions().call()
#     alice_net_positions_parsed = list(
#         alice_net_positions.result.net_positions_array)

#     assert len(alice_net_positions_parsed) == 0

#     bob_net_positions = await bob.get_net_positions().call()
#     bob_net_positions_parsed = list(
#         bob_net_positions.result.net_positions_array)

#     assert len(bob_net_positions_parsed) == 0


# @pytest.mark.asyncio
# async def test_three_orders_in_a_batch(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_balance = to64x61(50000)
#     bob_balance = to64x61(50000)
#     charlie_balance = to64x61(50000)

#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])
#     await admin2_signer.send_transaction(admin2, charlie.contract_address, 'set_balance', [USDC_ID, charlie_balance])

#     alice_curr_balance_before = await alice.get_balance(assetID_=USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(assetID_=USDC_ID).call()
#     charlie_curr_balance_before = await charlie.get_balance(assetID_=USDC_ID).call()

#     ####### Opening of Orders #######
#     size1 = to64x61(4)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("32iga62jsgfds")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(9325.2432042)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(5)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(1)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("873h2kkjsffg")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(9325.03424)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(3)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     order_id_3 = str_to_felt("dsfwr432")
#     assetID_3 = BTC_ID
#     collateralID_3 = USDC_ID
#     price3 = to64x61(9324.43)
#     stopPrice3 = 0
#     orderType3 = 0
#     position3 = to64x61(1)
#     direction3 = 1
#     closeOrder3 = 0
#     parentOrder3 = 0
#     leverage3 = to64x61(1)
#     liquidatorAddress3 = 0

#     execution_price1 = to64x61(9325)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)
#     hash_computed3 = hash_order(order_id_3, assetID_3, collateralID_3,
#                                 price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)
#     signed_message3 = charlie_signer.sign(hash_computed3)

#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size1).call()
#     fees1 = await fixed_math.Math64x61_mul(amount1.result.res, taker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     amount2 = await fixed_math.Math64x61_mul(execution_price1, position2).call()
#     fees2 = await fixed_math.Math64x61_mul(amount2.result.res, maker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     amount3 = await fixed_math.Math64x61_mul(execution_price1, position3).call()
#     fees3 = await fixed_math.Math64x61_mul(amount3.result.res, maker_trading_fees).call()
#     total_amount3 = amount3.result.res + fees3.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()
#     charlie_total_fees_before = await feeBalance.get_user_fee(address=charlie.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         3,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_2, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#         charlie.contract_address, signed_message3[0], signed_message3[
#             1], order_id_3, assetID_3, collateralID_3, price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3, liquidatorAddress3, 0,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)

#     assert res1 == [
#         execution_price1,
#         to64x61(4),
#         to64x61(37300),
#         to64x61(0),
#         leverage1
#     ]

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     assert res2 == [
#         execution_price1,
#         position2,
#         to64x61(27975),
#         to64x61(0),
#         leverage2
#     ]

#     orderState3 = await charlie.get_position_data(market_id_=marketID_1, direction_=direction3).call()
#     res3 = list(orderState3.result.res)

#     assert res3 == [
#         execution_price1,
#         position3,
#         to64x61(9325),
#         to64x61(0),
#         leverage3
#     ]

#     alice_curr_balance = await alice.get_balance(assetID_=USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(assetID_=USDC_ID).call()
#     charlie_curr_balance = await charlie.get_balance(assetID_=USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()
#     charlie_total_fees = await feeBalance.get_user_fee(address=charlie.contract_address, assetID_=USDC_ID).call()

#     assert alice_curr_balance.result.res == alice_curr_balance_before.result.res - total_amount1
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert from64x61(charlie_curr_balance.result.res) == from64x61(
#         charlie_curr_balance_before.result.res - total_amount3)
#     assert from64x61(holdingBalance.result.amount) == from64x61(
#         holdingBalance_before.result.amount + amount1.result.res + amount2.result.res + amount3.result.res)
#     assert from64x61(alice_total_fees.result.fee) == from64x61(
#         alice_total_fees_before.result.fee + fees1.result.res)
#     # Commenting the following check because of 64x61 bug
#     #assert from64x61(bob_total_fees.result.fee) == from64x61(bob_total_fees_before.result.fee + fees2.result.res)
#     #assert from64x61(charlie_total_fees.result.fee) == from64x61(charlie_total_fees_before.result.fee + fees3.result.res)
#     #assert from64x61(feeBalance_curr.result.fee) == from64x61(feeBalance_before.result.fee + fees1.result.res + fees2.result.res + fees3.result.res)

#     ##### Closing Of Orders ########
#     size2 = to64x61(4)
#     marketID_2 = BTC_USD_ID

#     order_id_4 = str_to_felt("er8u324hj4hd")
#     assetID_4 = BTC_ID
#     collateralID_4 = USDC_ID
#     price4 = to64x61(12000.2432042)
#     stopPrice4 = 0
#     orderType4 = 0
#     position4 = to64x61(4)
#     direction4 = 1
#     closeOrder4 = 1
#     parentOrder4 = order_id_1
#     leverage4 = to64x61(1)
#     liquidatorAddress4 = 0

#     order_id_5 = str_to_felt("5324k34")
#     assetID_5 = BTC_ID
#     collateralID_5 = USDC_ID
#     price5 = to64x61(12032.9803)
#     stopPrice5 = 0
#     orderType5 = 0
#     position5 = to64x61(3)
#     direction5 = 0
#     closeOrder5 = 1
#     parentOrder5 = order_id_2
#     leverage5 = to64x61(1)
#     liquidatorAddress5 = 0

#     order_id_6 = str_to_felt("3df324gds34")
#     assetID_6 = BTC_ID
#     collateralID_6 = USDC_ID
#     price6 = to64x61(12010.2610396)
#     stopPrice6 = 0
#     orderType6 = 0
#     position6 = to64x61(1)
#     direction6 = 0
#     closeOrder6 = 1
#     parentOrder6 = order_id_3
#     leverage6 = to64x61(1)
#     liquidatorAddress6 = 0

#     execution_price2 = to64x61(12025.432)

#     hash_computed4 = hash_order(order_id_4, assetID_4, collateralID_4,
#                                 price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4)
#     hash_computed5 = hash_order(order_id_5, assetID_5, collateralID_5,
#                                 price5, stopPrice5, orderType5, position5, direction5, closeOrder5, leverage5)
#     hash_computed6 = hash_order(order_id_6, assetID_6, collateralID_6,
#                                 price6, stopPrice6, orderType6, position6, direction6, closeOrder6, leverage6)

#     signed_message4 = alice_signer.sign(hash_computed4)
#     signed_message5 = bob_signer.sign(hash_computed5)
#     signed_message6 = charlie_signer.sign(hash_computed6)

#     pnl = execution_price2 - execution_price1
#     adjusted_price = execution_price1 - pnl
#     amount1 = await fixed_math.Math64x61_mul(adjusted_price, size2).call()

#     amount2 = await fixed_math.Math64x61_mul(execution_price2, position2).call()

#     amount3 = await fixed_math.Math64x61_mul(execution_price2, position3).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size2,
#         execution_price2,
#         marketID_2,
#         3,
#         alice.contract_address, signed_message4[0], signed_message4[
#             1], order_id_4, assetID_4, collateralID_4, price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4, liquidatorAddress4, 1,
#         bob.contract_address, signed_message5[0], signed_message5[
#             1], order_id_5, assetID_5, collateralID_5, price5, stopPrice5, orderType5, position5, direction5, closeOrder5, leverage5, liquidatorAddress5, 0,
#         charlie.contract_address, signed_message6[0], signed_message6[
#             1], order_id_6, assetID_6, collateralID_6, price6, stopPrice6, orderType6, position6, direction6, closeOrder6, leverage6, liquidatorAddress6, 0,
#     ])

#     orderState4 = await alice.get_position_data(market_id_=marketID_2, direction_=direction1).call()
#     res4 = list(orderState4.result.res)
#     assert res4 == [
#         execution_price1,
#         0,
#         to64x61(0),
#         to64x61(0),
#         leverage4
#     ]

#     orderState5 = await bob.get_position_data(market_id_=marketID_2, direction_=direction2).call()
#     res5 = list(orderState5.result.res)
#     assert res5 == [
#         execution_price1,
#         0,
#         to64x61(0),
#         to64x61(0),
#         leverage5
#     ]

#     orderState6 = await charlie.get_position_data(market_id_=marketID_2, direction_=direction3).call()
#     res6 = list(orderState6.result.res)
#     assert res6 == [
#         execution_price1,
#         0,
#         to64x61(0),
#         to64x61(0),
#         leverage6
#     ]

#     alice_curr_balance_after = await alice.get_balance(assetID_=USDC_ID).call()
#     bob_curr_balance_after = await bob.get_balance(assetID_=USDC_ID).call()
#     charlie_curr_balance_after = await charlie.get_balance(assetID_=USDC_ID).call()
#     holdingBalance_after = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_after = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_after = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_after = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()
#     charlie_total_fees_after = await feeBalance.get_user_fee(address=charlie.contract_address, assetID_=USDC_ID).call()

#     assert holdingBalance_after.result.amount == holdingBalance.result.amount - \
#         amount1.result.res - amount2.result.res - amount3.result.res
#     assert alice_curr_balance_after.result.res == alice_curr_balance.result.res + \
#         amount1.result.res
#     assert bob_curr_balance_after.result.res == bob_curr_balance.result.res + amount2.result.res
#     assert charlie_curr_balance_after.result.res == charlie_curr_balance.result.res + \
#         amount3.result.res
#     assert alice_total_fees_after.result.fee == alice_total_fees.result.fee
#     assert bob_total_fees_after.result.fee == bob_total_fees.result.fee
#     assert charlie_total_fees_after.result.fee == charlie_total_fees.result.fee
#     assert feeBalance_after.result.fee == feeBalance_curr.result.fee


# @pytest.mark.asyncio
# async def test_opening_and_closing_full_orders_with_leverage(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_balance = to64x61(100000)
#     bob_balance = to64x61(100000)

#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])

#     alice_curr_balance_before = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(USDC_ID).call()

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("iu21iosdf8453")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(5000)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(2)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(2)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("wer4iljemn")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(5000)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(2)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(2)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(5000)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     size_without_leverage1 = await fixed_math.Math64x61_div(size1, leverage1).call()
#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage1.result.res).call()
#     amount_for_fee1 = await fixed_math.Math64x61_mul(execution_price1, size1).call()
#     fees1 = await fixed_math.Math64x61_mul(amount_for_fee1.result.res, taker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     size_without_leverage2 = await fixed_math.Math64x61_div(size1, leverage2).call()
#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage2.result.res).call()
#     amount_for_fee2 = await fixed_math.Math64x61_mul(execution_price1, size1).call()
#     fees2 = await fixed_math.Math64x61_mul(amount_for_fee2.result.res, maker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)

#     assert res1 == [
#         execution_price1,
#         to64x61(2),
#         to64x61(5000),
#         to64x61(5000),
#         leverage1
#     ]

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     assert res2 == [
#         execution_price1,
#         to64x61(2),
#         to64x61(5000),
#         to64x61(5000),
#         leverage2
#     ]

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     assert from64x61(alice_curr_balance.result.res) == from64x61(
#         alice_curr_balance_before.result.res - total_amount1)
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert from64x61(holdingBalance.result.amount) == from64x61(
#         holdingBalance_before.result.amount + amount_for_fee1.result.res + amount_for_fee2.result.res)
#     assert from64x61(alice_total_fees.result.fee) == from64x61(
#         alice_total_fees_before.result.fee + fees1.result.res)
#     # Commenting due to 64x61 bug
#     #assert from64x61(bob_total_fees.result.fee) == from64x61(bob_total_fees_before.result.fee + fees2.result.res)
#     #assert from64x61(feeBalance_curr.result.fee) == from64x61(feeBalance_before.result.fee + fees1.result.res + fees2.result.res)
#     #### Closing Of Orders ########
#     size2 = to64x61(2)
#     marketID_2 = BTC_USD_ID

#     order_id_3 = str_to_felt("dfs32423gdsga")
#     assetID_3 = BTC_ID
#     collateralID_3 = USDC_ID
#     price3 = to64x61(6000)
#     stopPrice3 = 0
#     orderType3 = 0
#     position3 = to64x61(2)
#     direction3 = 1
#     closeOrder3 = 1
#     parentOrder3 = order_id_1
#     leverage3 = to64x61(2)
#     liquidatorAddress3 = 0

#     order_id_4 = str_to_felt("tew2hda334")
#     assetID_4 = BTC_ID
#     collateralID_4 = USDC_ID
#     price4 = to64x61(6000)
#     stopPrice4 = 0
#     orderType4 = 0
#     position4 = to64x61(2)
#     direction4 = 0
#     closeOrder4 = 1
#     parentOrder4 = order_id_2
#     leverage4 = to64x61(2)
#     liquidatorAddress4 = 0

#     execution_price2 = to64x61(6000)

#     hash_computed3 = hash_order(order_id_3, assetID_3, collateralID_3,
#                                 price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3)
#     hash_computed4 = hash_order(order_id_4, assetID_4, collateralID_4,
#                                 price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4)

#     signed_message3 = alice_signer.sign(hash_computed3)
#     signed_message4 = bob_signer.sign(hash_computed4)

#     diff1 = execution_price1 - execution_price2

#     adjusted_price3 = to64x61(from64x61(execution_price1) + from64x61(diff1))
#     pnl3 = await fixed_math.Math64x61_mul(diff1, size1).call()
#     fraction_closed3 = await fixed_math.Math64x61_div(size1, size2).call()
#     pnl_closed3 = await fixed_math.Math64x61_mul(pnl3.result.res, fraction_closed3.result.res).call()
#     margin_returned3 = await fixed_math.Math64x61_mul(amount2.result.res, fraction_closed3.result.res).call()
#     amount_returned3 = to64x61(
#         from64x61(pnl_closed3.result.res) + from64x61(margin_returned3.result.res))
#     position_value_closed3 = await fixed_math.Math64x61_mul(adjusted_price3, size2).call()

#     print("alice difference is: ", from64x61(diff1))
#     print("amount to be returned to alice is: ", from64x61(amount_returned3))
#     print("amount to be returned to alice is: ", amount_returned3)
#     print("margin returned of alice is: ",
#           from64x61(margin_returned3.result.res))
#     print("fraction closed of alice is: ",
#           from64x61(fraction_closed3.result.res))
#     print("pnl of alice is:", from64x61(pnl3.result.res))
#     print("posiiton value of alice is: ", from64x61(
#         position_value_closed3.result.res))

#     diff2 = execution_price2 - execution_price1

#     pnl4 = await fixed_math.Math64x61_mul(diff2, size1).call()
#     fraction_closed4 = await fixed_math.Math64x61_div(size1, size2).call()
#     pnl_closed4 = await fixed_math.Math64x61_mul(pnl4.result.res, fraction_closed4.result.res).call()
#     margin_returned4 = await fixed_math.Math64x61_mul(amount1.result.res, fraction_closed4.result.res).call()
#     amount_returned4 = to64x61(
#         from64x61(pnl_closed4.result.res) + from64x61(margin_returned4.result.res))
#     position_value_closed4 = await fixed_math.Math64x61_mul(execution_price2, size2).call()

#     print("bob difference is: ", from64x61(diff2))
#     print("amount to be returned to bob is: ", from64x61(amount_returned4))
#     print("amount to be returned to bob is: ", amount_returned4)
#     print("margin returned of bob is: ", from64x61(margin_returned4.result.res))
#     print("fraction closed of bob is: ", from64x61(fraction_closed4.result.res))
#     print("pnl of bob is:", from64x61(pnl4.result.res))
#     print("posiiton value of bob is: ", from64x61(
#         position_value_closed4.result.res))

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size2,
#         execution_price2,
#         marketID_2,
#         2,
#         alice.contract_address, signed_message3[0], signed_message3[
#             1], order_id_3, assetID_3, collateralID_3, price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3, liquidatorAddress3, 1,
#         bob.contract_address, signed_message4[0], signed_message4[
#             1], order_id_4, assetID_4, collateralID_4, price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4, liquidatorAddress4, 0,
#     ])

#     orderState3 = await alice.get_position_data(market_id_=marketID_2, direction_=direction1).call()
#     res3 = list(orderState3.result.res)

#     assert res3 == [
#         execution_price1,
#         0,
#         to64x61(0),
#         to64x61(0),
#         leverage3
#     ]

#     orderState4 = await bob.get_position_data(market_id_=marketID_2, direction_=direction2).call()
#     res4 = list(orderState4.result.res)

#     assert res4 == [
#         execution_price1,
#         0,
#         to64x61(0),
#         to64x61(0),
#         leverage4
#     ]

#     alice_curr_balance_after = await alice.get_balance(collateralID_3).call()
#     print("alice_test current balance is", from64x61(
#         alice_curr_balance_after.result.res))
#     print("alice_test difference is", from64x61(
#         alice_curr_balance.result.res) + from64x61(amount_returned3))
#     bob_curr_balance_after = await bob.get_balance(collateralID_4).call()
#     print("bob_test current balance is", from64x61(
#         bob_curr_balance_after.result.res))
#     print("bob_test difference is", from64x61(
#         bob_curr_balance.result.res) + from64x61(amount_returned3))
#     holdingBalance_after = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_after = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_after = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_after = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     assert holdingBalance_after.result.amount == holdingBalance.result.amount - \
#         position_value_closed3.result.res - position_value_closed4.result.res
#     assert alice_curr_balance_after.result.res == (
#         alice_curr_balance.result.res + amount_returned3)
#     assert bob_curr_balance_after.result.res == (
#         bob_curr_balance.result.res + amount_returned4)
#     assert alice_total_fees_after.result.fee == alice_total_fees.result.fee
#     assert bob_total_fees_after.result.fee == bob_total_fees.result.fee
#     assert feeBalance_after.result.fee == feeBalance_curr.result.fee


# @pytest.mark.asyncio
# async def test_opening_full_stop_orders(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_balance = to64x61(100000)
#     bob_balance = to64x61(100000)

#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])

#     alice_curr_balance_before = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(USDC_ID).call()

#     ####### Opening of Orders #######
#     size = to64x61(1)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("ds32kjksdldsf")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(5000)
#     stopPrice1 = to64x61(6000)
#     orderType1 = 2
#     position1 = to64x61(1)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(1)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("34kj1hkhadsf")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(5000)
#     stopPrice2 = to64x61(4000)
#     orderType2 = 2
#     position2 = to64x61(1)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(5000)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees1 = await fixed_math.Math64x61_mul(amount1.result.res, maker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees2 = await fixed_math.Math64x61_mul(amount2.result.res, taker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 0,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 1,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)
#     print("Stop order 1", from64x61(res1[0]), from64x61(res1[1]), from64x61(
#         res1[2]), from64x61(res1[3]), from64x61(res1[4]))

#     assert res1 == [
#         execution_price1,
#         to64x61(1),
#         to64x61(5000),
#         to64x61(0),
#         leverage1
#     ]

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     print("Stop order 2", from64x61(res2[0]), from64x61(res2[1]), from64x61(
#         res2[2]), from64x61(res2[3]), from64x61(res2[4]))
#     assert res2 == [
#         execution_price1,
#         to64x61(1),
#         to64x61(5000),
#         to64x61(0),
#         leverage2
#     ]

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     print("Fee balance got: ", feeBalance_curr.result.fee)
#     print("alice_test fee: ", alice_total_fees.result.fee)
#     print("bob_test fee: ", bob_total_fees.result.fee)

#     assert from64x61(alice_curr_balance.result.res) == from64x61(
#         alice_curr_balance_before.result.res - total_amount1)
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert holdingBalance.result.amount == holdingBalance_before.result.amount + \
#         amount1.result.res + amount2.result.res
#     # Commenting the below line because of 64x61 bug
#     #assert from64x61(alice_total_fees.result.fee) == from64x61(alice_total_fees_before.result.fee) + from64x61(fees1.result.res)
#     assert from64x61(bob_total_fees.result.fee) == from64x61(
#         bob_total_fees_before.result.fee + fees2.result.res)
#     #assert from64x61(feeBalance_curr.result.fee) == from64x61(feeBalance_before.result.fee + fees1.result.res + fees2.result.res)


# @pytest.mark.asyncio
# async def test_opening_and_closing_orders_with_leverage_partial_open_and_close(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_balance = to64x61(100000)
#     bob_balance = to64x61(100000)

#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])

#     alice_curr_balance_before = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(USDC_ID).call()

#     ####### Open order partially #######
#     size1 = to64x61(5)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("gf8oiahkjhxcv")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(5000)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(10)
#     direction1 = 1
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(10)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("324kjhkldfs832")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(5000)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(5)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(5000)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     order_executed_user1 = to64x61(min(from64x61(size1), from64x61(position1)))
#     order_executed_user2 = to64x61(min(from64x61(size1), from64x61(position1)))

#     size_without_leverage1 = await fixed_math.Math64x61_div(order_executed_user1, leverage1).call()
#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage1.result.res).call()
#     amount_for_fee1 = await fixed_math.Math64x61_mul(execution_price1, order_executed_user1).call()
#     fees1 = await fixed_math.Math64x61_mul(amount_for_fee1.result.res, taker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     size_without_leverage2 = await fixed_math.Math64x61_div(order_executed_user2, leverage2).call()
#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage2.result.res).call()
#     amount_for_fee2 = await fixed_math.Math64x61_mul(execution_price1, order_executed_user2).call()
#     fees2 = await fixed_math.Math64x61_mul(amount_for_fee2.result.res, maker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)

#     assert res1 == [
#         execution_price1,
#         to64x61(5),
#         to64x61(2500),
#         to64x61(22500),
#         leverage1
#     ]

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     assert res2 == [
#         execution_price1,
#         to64x61(5),
#         to64x61(25000),
#         to64x61(0),
#         leverage2
#     ]

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     print("alice_test balance before trade:", from64x61(
#         alice_curr_balance_before.result.res))
#     print("alice_test balance after trade:", from64x61(
#         alice_curr_balance.result.res))
#     print("bob_test balance before trade:", from64x61(
#         bob_curr_balance_before.result.res))
#     print("bob_test balance after trade:", from64x61(bob_curr_balance.result.res))

#     assert from64x61(alice_curr_balance.result.res) == from64x61(
#         alice_curr_balance_before.result.res - total_amount1)
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert from64x61(holdingBalance.result.amount) == from64x61(
#         holdingBalance_before.result.amount + amount_for_fee1.result.res + amount_for_fee2.result.res)
#     assert from64x61(alice_total_fees.result.fee) == from64x61(
#         alice_total_fees_before.result.fee + fees1.result.res)
#     # Commenting the below line because of 64x61 bug
#     #assert from64x61(bob_total_fees.result.fee) == from64x61(bob_total_fees_before.result.fee + fees2.result.res)
#     #assert from64x61(feeBalance_curr.result.fee) == from64x61(feeBalance_before.result.fee + fees1.result.res + fees2.result.res)

#     #### Close order partially ########
#     size2 = to64x61(2.5)
#     marketID_2 = BTC_USD_ID

#     order_id_3 = str_to_felt("35hsarfg")
#     assetID_3 = BTC_ID
#     collateralID_3 = USDC_ID
#     price3 = to64x61(6000)
#     stopPrice3 = 0
#     orderType3 = 0
#     position3 = to64x61(10)
#     direction3 = 0
#     closeOrder3 = 1
#     parentOrder3 = order_id_1
#     leverage3 = to64x61(10)
#     liquidatorAddress3 = 0

#     order_id_4 = str_to_felt("t3242sfhzad334")
#     assetID_4 = BTC_ID
#     collateralID_4 = USDC_ID
#     price4 = to64x61(6000)
#     stopPrice4 = 0
#     orderType4 = 0
#     position4 = to64x61(5)
#     direction4 = 1
#     closeOrder4 = 1
#     parentOrder4 = order_id_2
#     leverage4 = to64x61(1)
#     liquidatorAddress4 = 0

#     execution_price2 = to64x61(6000)

#     hash_computed3 = hash_order(order_id_3, assetID_3, collateralID_3, price3, stopPrice3,
#                                 orderType3, position3, direction3, closeOrder3, leverage3)
#     hash_computed4 = hash_order(order_id_4, assetID_4, collateralID_4, price4, stopPrice4,
#                                 orderType4, position4, direction4, closeOrder4, leverage4)

#     print("bob hash: ", hash_computed4)
#     signed_message3 = alice_signer.sign(hash_computed3)
#     signed_message4 = bob_signer.sign(hash_computed4)

#     order_executed_user3 = to64x61(from64x61(min(size2, position1)))
#     order_executed_user4 = to64x61(from64x61(min(size2, position2)))

#     diff1 = execution_price2 - execution_price1

#     pnl3 = await fixed_math.Math64x61_mul(diff1, order_executed_user1).call()
#     fraction_closed3 = await fixed_math.Math64x61_div(order_executed_user3, order_executed_user1).call()
#     pnl_closed3 = await fixed_math.Math64x61_mul(pnl3.result.res, fraction_closed3.result.res).call()
#     margin_returned3 = await fixed_math.Math64x61_mul(amount1.result.res, fraction_closed3.result.res).call()
#     amount_returned3 = to64x61(
#         from64x61(pnl_closed3.result.res) + from64x61(margin_returned3.result.res))
#     position_value_closed3 = await fixed_math.Math64x61_mul(execution_price2, order_executed_user3).call()

#     print("alice difference is: ", from64x61(diff1))
#     print("amount to be returned to alice is: ", from64x61(amount_returned3))
#     print("margin returned of alice is: ",
#           from64x61(margin_returned3.result.res))
#     print("fraction closed of alice is: ",
#           from64x61(fraction_closed3.result.res))
#     print("pnl of alice is:", from64x61(pnl3.result.res))
#     print("posiiton value of alice is: ", from64x61(
#         position_value_closed3.result.res))

#     diff2 = execution_price1 - execution_price2

#     adjusted_price4 = execution_price1 + diff2
#     pnl4 = await fixed_math.Math64x61_mul(diff2, order_executed_user1).call()
#     fraction_closed4 = await fixed_math.Math64x61_div(order_executed_user4, order_executed_user1).call()
#     pnl_closed4 = await fixed_math.Math64x61_mul(pnl4.result.res, fraction_closed4.result.res).call()
#     margin_returned4 = await fixed_math.Math64x61_mul(amount2.result.res, fraction_closed4.result.res).call()
#     amount_returned4 = to64x61(
#         from64x61(pnl_closed4.result.res) + from64x61(margin_returned4.result.res))
#     position_value_closed4 = await fixed_math.Math64x61_mul(adjusted_price4, order_executed_user4).call()

#     print("bob difference is: ", from64x61(diff2))
#     print("amount to be returned to bob is: ", from64x61(amount_returned4))
#     print("amount to be returned to bob is: ", amount_returned4)
#     print("margin returned of bob is: ", from64x61(margin_returned4.result.res))
#     print("fraction closed of bob is: ", from64x61(fraction_closed4.result.res))
#     print("pnl of bob is:", from64x61(pnl4.result.res))
#     print("posiiton value of bob is: ", from64x61(
#         position_value_closed4.result.res))

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size2,
#         execution_price2,
#         marketID_2,
#         2,
#         alice.contract_address, signed_message3[0], signed_message3[
#             1], order_id_3, assetID_3, collateralID_3, price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3, liquidatorAddress3, 1,
#         bob.contract_address, signed_message4[0], signed_message4[
#             1], order_id_4, assetID_4, collateralID_4, price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4, liquidatorAddress4, 0,
#     ])

#     orderState3 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res3 = list(orderState3.result.res)

#     assert res3 == [
#         execution_price1,
#         to64x61(2.5),
#         to64x61(1250),
#         to64x61(11250),
#         leverage3
#     ]

#     orderState4 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res4 = list(orderState4.result.res)

#     assert res4 == [
#         execution_price1,
#         to64x61(2.5),
#         to64x61(12500),
#         to64x61(0),
#         leverage4
#     ]

#     alice_curr_balance_after = await alice.get_balance(collateralID_3).call()
#     bob_curr_balance_after = await bob.get_balance(collateralID_4).call()
#     holdingBalance_after = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_after = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_after = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_after = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     print("alice_test balance before:", from64x61(alice_curr_balance.result.res))
#     print("alice_test balance after:", from64x61(
#         alice_curr_balance_after.result.res))
#     print("bob_test balance before:", from64x61(bob_curr_balance.result.res))
#     print("bob_test balance after:", from64x61(bob_curr_balance_after.result.res))
#     print("Position value close 3", from64x61(
#         position_value_closed3.result.res))
#     print("Position value close 4", from64x61(
#         position_value_closed4.result.res))
#     print("Holding balance before", from64x61(holdingBalance.result.amount))
#     print("Holding balance after", from64x61(
#         holdingBalance_after.result.amount))
#     print("Holding balance comaparison", from64x61(holdingBalance_after.result.amount -
#           position_value_closed3.result.res - position_value_closed4.result.res),  from64x61(holdingBalance.result.amount))

#     assert from64x61(holdingBalance_after.result.amount) == from64x61(
#         holdingBalance.result.amount - position_value_closed3.result.res - position_value_closed4.result.res)
#     assert from64x61(alice_curr_balance_after.result.res) == from64x61(
#         alice_curr_balance.result.res + amount_returned3)
#     assert from64x61(bob_curr_balance_after.result.res) == from64x61(
#         bob_curr_balance.result.res + amount_returned4)
#     assert from64x61(alice_total_fees_after.result.fee) == from64x61(
#         alice_total_fees.result.fee)
#     assert from64x61(bob_total_fees_after.result.fee) == from64x61(
#         bob_total_fees.result.fee)
#     assert from64x61(feeBalance_after.result.fee) == from64x61(
#         feeBalance_curr.result.fee)

#     # ####### Open order partially for the second time #######
#     alice_curr_balance_before = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(USDC_ID).call()

#     size = to64x61(2.5)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("yt56kjhxcv")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(5000)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(7.5)
#     direction1 = 1
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(10)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("324kjh65fghdfs832")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(5000)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(5.7)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(5000)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     size_by_leverage1 = await fixed_math.Math64x61_div(size, leverage1).call()
#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size_by_leverage1.result.res).call()
#     amount_for_fee1 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees1 = await fixed_math.Math64x61_mul(amount_for_fee1.result.res, taker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     size_by_leverage2 = await fixed_math.Math64x61_div(size, leverage2).call()
#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size_by_leverage2.result.res).call()
#     amount_for_fee2 = await fixed_math.Math64x61_mul(execution_price1, size).call()
#     fees2 = await fixed_math.Math64x61_mul(amount_for_fee2.result.res, maker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     assert res1 == [
#         execution_price1,
#         to64x61(5),
#         to64x61(2500),
#         to64x61(22500),
#         leverage1
#     ]

#     assert res2 == [
#         execution_price1,
#         to64x61(5),
#         to64x61(25000),
#         to64x61(0),
#         leverage2
#     ]

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     assert from64x61(alice_curr_balance.result.res) == from64x61(
#         alice_curr_balance_before.result.res - total_amount1)
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert from64x61(holdingBalance.result.amount) == from64x61(
#         holdingBalance_before.result.amount + amount_for_fee1.result.res + amount_for_fee2.result.res)
#     assert from64x61(alice_total_fees.result.fee) == from64x61(
#         alice_total_fees_before.result.fee + fees1.result.res)
#     # Commenting the below line because of 64x61 bug
#     #assert from64x61(bob_total_fees.result.fee) == from64x61(bob_total_fees_before.result.fee + fees2.result.res)
#     #assert from64x61(feeBalance_curr.result.fee) == from64x61(feeBalance_before.result.fee + fees1.result.res + fees2.result.res)


# @pytest.mark.asyncio
# async def test_opening_multiple_markets(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     alice_curr_balance_before = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance_before = await bob.get_balance(USDC_ID).call()

#     ####### Opening of Orders #######
#     size1 = to64x61(2)
#     marketID_1 = ETH_USD_ID

#     order_id_1 = str_to_felt("i21dsgsfsdf8453")
#     assetID_1 = ETH_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(1500)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(2)
#     direction1 = 0
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(2)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("jdsio3kllcx")
#     assetID_2 = ETH_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(1500)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(2)
#     direction2 = 1
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(2)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(1500)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     size_without_leverage1 = await fixed_math.Math64x61_div(size1, leverage1).call()
#     amount1 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage1.result.res).call()
#     amount_for_fee1 = await fixed_math.Math64x61_mul(execution_price1, size1).call()
#     fees1 = await fixed_math.Math64x61_mul(amount_for_fee1.result.res, taker_trading_fees).call()
#     total_amount1 = amount1.result.res + fees1.result.res

#     size_without_leverage2 = await fixed_math.Math64x61_div(size1, leverage2).call()
#     amount2 = await fixed_math.Math64x61_mul(execution_price1, size_without_leverage2.result.res).call()
#     amount_for_fee2 = await fixed_math.Math64x61_mul(execution_price1, size1).call()
#     fees2 = await fixed_math.Math64x61_mul(amount_for_fee2.result.res, maker_trading_fees).call()
#     total_amount2 = amount2.result.res + fees2.result.res

#     holdingBalance_before = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_before = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees_before = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees_before = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ])

#     orderState1 = await alice.get_position_data(market_id_=marketID_1, direction_=direction1).call()
#     res1 = list(orderState1.result.res)

#     assert res1 == [
#         execution_price1,
#         to64x61(2),
#         to64x61(1500),
#         to64x61(1500),
#         leverage1
#     ]

#     orderState2 = await bob.get_position_data(market_id_=marketID_1, direction_=direction2).call()
#     res2 = list(orderState2.result.res)

#     assert res2 == [
#         execution_price1,
#         to64x61(2),
#         to64x61(1500),
#         to64x61(1500),
#         leverage2
#     ]

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()
#     holdingBalance = await holding.balance(asset_id_=USDC_ID).call()
#     feeBalance_curr = await feeBalance.get_total_fee(assetID_=USDC_ID).call()
#     alice_total_fees = await feeBalance.get_user_fee(address=alice.contract_address, assetID_=USDC_ID).call()
#     bob_total_fees = await feeBalance.get_user_fee(address=bob.contract_address, assetID_=USDC_ID).call()

#     assert from64x61(alice_curr_balance.result.res) == from64x61(
#         alice_curr_balance_before.result.res - total_amount1)
#     assert from64x61(bob_curr_balance.result.res) == from64x61(
#         bob_curr_balance_before.result.res - total_amount2)
#     assert from64x61(holdingBalance.result.amount) == from64x61(
#         holdingBalance_before.result.amount + amount_for_fee1.result.res + amount_for_fee2.result.res)
#     assert from64x61(alice_total_fees.result.fee) == from64x61(
#         alice_total_fees_before.result.fee + fees1.result.res)


# @pytest.mark.asyncio
# async def test_retrieval_of_net_positions_2(adminAuth_factory):
#     starknet, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, marketPrices, _ = adminAuth_factory

#     alice_net_positions = await alice.get_net_positions().call()
#     alice_net_positions_parsed = list(
#         alice_net_positions.result.net_positions_array)

#     bob_net_positions = await bob.get_net_positions().call()
#     bob_net_positions_parsed = list(
#         bob_net_positions.result.net_positions_array)

#     print(from64x61(alice_net_positions_parsed[0].position_size))
#     print(from64x61(bob_net_positions_parsed[0].position_size))

#     assert len(alice_net_positions_parsed) == 2
#     assert len(bob_net_positions_parsed) == 2

#     assert from64x61(alice_net_positions_parsed[0].position_size) == 4.0
#     assert from64x61(bob_net_positions_parsed[0].position_size) == -4.0

#     assert from64x61(alice_net_positions_parsed[1].position_size) == -2.0
#     assert from64x61(bob_net_positions_parsed[1].position_size) == 2.0

#     alice_positions = await alice.get_positions().call()
#     print_parsed_positions(alice_positions.result.positions_array)
#     # print(list(alice_positions.result.positions_array))

#     bob_positions = await bob.get_positions().call()
#     # print(list(bob_positions.result.positions_array))
#     print_parsed_positions(bob_positions.result.positions_array)

#     alice_collaterals = await alice.return_array_collaterals().call()
#     print_parsed_collaterals(alice_collaterals.result.array_list)

#     bob_collaterals = await bob.return_array_collaterals().call()
#     print_parsed_collaterals(bob_collaterals.result.array_list)

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()

#     print("alice_test new balance", from64x61(alice_curr_balance.result.res))
#     print("bob_test new balance", from64x61(bob_curr_balance.result.res))

#     BTC_market_price = await marketPrices.get_market_price(BTC_USD_ID).call()
#     print(from64x61(BTC_market_price.result.market_price.price))

#     ETH_market_price = await marketPrices.get_market_price(ETH_USD_ID).call()
#     print(from64x61(ETH_market_price.result.market_price.price))


# @pytest.mark.asyncio
# async def test_for_risk_while_opening_order(adminAuth_factory):
#     starknet, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, marketPrices, liquidate = adminAuth_factory

#     alice_balance = to64x61(100)
#     bob_balance = to64x61(800)

#     await admin1_signer.send_transaction(admin1, alice.contract_address, 'set_balance', [USDC_ID, alice_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])

#     alice_curr_balance = await alice.get_balance(USDC_ID).call()
#     bob_curr_balance = await bob.get_balance(USDC_ID).call()

#     print("alice_test new balance", from64x61(alice_curr_balance.result.res))
#     print("bob_test new balance", from64x61(bob_curr_balance.result.res))

#     alice_collaterals = await alice.return_array_collaterals().call()
#     print_parsed_collaterals(alice_collaterals.result.array_list)

#     bob_collaterals = await bob.return_array_collaterals().call()
#     print_parsed_collaterals(bob_collaterals.result.array_list)

#     timestamp = int(time.time()) + 61

#     starknet.state.state.block_info = BlockInfo(
#         block_number=1, block_timestamp=timestamp, gas_price=starknet.state.state.block_info.gas_price,
#         sequencer_address=starknet.state.state.block_info.sequencer_address,
#         starknet_version=STARKNET_VERSION
#     )

#     ####### Opening of Orders #######
#     size = to64x61(1)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("343uosawhdft")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(200)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(1)
#     direction1 = 1
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(10)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("dfsdsw34fds")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(200)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(1)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(200)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = alice_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size,
#         execution_price1,
#         marketID_1,
#         2,
#         alice.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 0,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 1,
#     ])

#     BTC_market_price = await marketPrices.get_market_price(BTC_USD_ID).call()
#     print("BTC price is ", from64x61(BTC_market_price.result.market_price.price))

#     ETH_market_price = await marketPrices.get_market_price(ETH_USD_ID).call()
#     print("ETH price before is ", from64x61(
#         ETH_market_price.result.market_price.price))

#     print("timestamp for BTC is: ", BTC_market_price.result.market_price.timestamp)
#     print("timestamp for ETH before is: ",
#           ETH_market_price.result.market_price.timestamp)
#     print("current timestamp is:", timestamp)

#     await admin1_signer.send_transaction(admin1, marketPrices.contract_address, "update_market_price", [ETH_USD_ID, to64x61(1500)])

#     ETH_market_price = await marketPrices.get_market_price(ETH_USD_ID).call()
#     print("ETH price after is ", from64x61(
#         ETH_market_price.result.market_price.price))
#     print("timestamp for ETH after is: ",
#           ETH_market_price.result.market_price.timestamp)

#     #### Opening Of new Order ########
#     size2 = to64x61(1)
#     marketID_2 = BTC_USD_ID

#     order_id_3 = str_to_felt("rlbruidd")
#     assetID_3 = BTC_ID
#     collateralID_3 = USDC_ID
#     price3 = to64x61(100)
#     stopPrice3 = 0
#     orderType3 = 0
#     position3 = to64x61(1)
#     direction3 = 1
#     closeOrder3 = 0
#     parentOrder3 = 0
#     leverage3 = to64x61(10)
#     liquidatorAddress3 = 0

#     order_id_4 = str_to_felt("tew43d34")
#     assetID_4 = BTC_ID
#     collateralID_4 = USDC_ID
#     price4 = to64x61(100)
#     stopPrice4 = 0
#     orderType4 = 0
#     position4 = to64x61(1)
#     direction4 = 0
#     closeOrder4 = 0
#     parentOrder4 = 0
#     leverage4 = to64x61(1)
#     liquidatorAddress4 = 0

#     execution_price2 = to64x61(100)

#     hash_computed3 = hash_order(order_id_3, assetID_3, collateralID_3,
#                                 price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3)
#     hash_computed4 = hash_order(order_id_4, assetID_4, collateralID_4,
#                                 price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4)

#     signed_message3 = alice_signer.sign(hash_computed3)
#     signed_message4 = bob_signer.sign(hash_computed4)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size2,
#         execution_price2,
#         marketID_2,
#         2,
#         alice.contract_address, signed_message3[0], signed_message3[
#             1], order_id_3, assetID_3, collateralID_3, price3, stopPrice3, orderType3, position3, direction3, closeOrder3, leverage3, liquidatorAddress3, 0,
#         bob.contract_address, signed_message4[0], signed_message4[
#             1], order_id_4, assetID_4, collateralID_4, price4, stopPrice4, orderType4, position4, direction4, closeOrder4, leverage4, liquidatorAddress4, 1,
#     ]), reverted_with="Liquidate: Position doesn't satisfy maintanence margin")


# @pytest.mark.asyncio
# async def test_check_for_collision(adminAuth_factory):
#     _, adminAuth, fees, admin1, admin2, asset, trading, alice, bob, charlie, dave, fixed_math, holding, feeBalance, _, _ = adminAuth_factory

#     charlie_balance = to64x61(10000)
#     bob_balance = to64x61(5000)
#     await admin1_signer.send_transaction(admin1, charlie.contract_address, 'set_balance', [USDC_ID, charlie_balance])
#     await admin2_signer.send_transaction(admin2, bob.contract_address, 'set_balance', [USDC_ID, bob_balance])

#     ####### Open order partially #######
#     size1 = to64x61(3)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("fdswq23ji3i4u2")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(250)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(10)
#     direction1 = 1
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(2)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("93jfkdslasfvdsz")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(250)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(5)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(250)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = charlie_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     res = await dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         charlie.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ])

#     ####### Open order partially #######
#     size1 = to64x61(1)
#     marketID_1 = BTC_USD_ID

#     order_id_1 = str_to_felt("fdswq23ji3i4u2")
#     assetID_1 = BTC_ID
#     collateralID_1 = USDC_ID
#     price1 = to64x61(250)
#     stopPrice1 = 0
#     orderType1 = 0
#     position1 = to64x61(4)
#     direction1 = 1
#     closeOrder1 = 0
#     parentOrder1 = 0
#     leverage1 = to64x61(5)
#     liquidatorAddress1 = 0

#     order_id_2 = str_to_felt("93jfkdslasfvdsz")
#     assetID_2 = BTC_ID
#     collateralID_2 = USDC_ID
#     price2 = to64x61(250)
#     stopPrice2 = 0
#     orderType2 = 0
#     position2 = to64x61(5)
#     direction2 = 0
#     closeOrder2 = 0
#     parentOrder2 = 0
#     leverage2 = to64x61(1)
#     liquidatorAddress2 = 0

#     execution_price1 = to64x61(250)

#     hash_computed1 = hash_order(order_id_1, assetID_1, collateralID_1,
#                                 price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1)
#     hash_computed2 = hash_order(order_id_2, assetID_2, collateralID_2,
#                                 price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2)

#     signed_message1 = charlie_signer.sign(hash_computed1)
#     signed_message2 = bob_signer.sign(hash_computed2)

#     await assert_revert(dave_signer.send_transaction(dave, trading.contract_address, "execute_batch", [
#         size1,
#         execution_price1,
#         marketID_1,
#         2,
#         charlie.contract_address, signed_message1[0], signed_message1[
#             1], order_id_1, assetID_1, collateralID_1, price1, stopPrice1, orderType1, position1, direction1, closeOrder1, leverage1, liquidatorAddress1, 1,
#         bob.contract_address, signed_message2[0], signed_message2[
#             1], order_id_2, assetID_1, collateralID_2, price2, stopPrice2, orderType2, position2, direction2, closeOrder2, leverage2, liquidatorAddress2, 0,
#     ]), reverted_with="AccountManager: Hash mismatch")
