from copyreg import constructor
import pytest
import asyncio
from starkware.starknet.testing.starknet import Starknet
from starkware.starkware_utils.error_handling import StarkException
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from utils import Signer, uint, str_to_felt, MAX_UINT256, assert_revert, hash_order, from64x61, to64x61, convertList

alice_signer = Signer(123456789987654323)

BTC_ID = str_to_felt("32f0406jz7qj8")
ETH_ID = str_to_felt("65ksgn23nv")
USDC_ID = str_to_felt("fghj3am52qpzsib")
UST_ID = str_to_felt("yjk45lvmasopq")
BTC_USD_ID = str_to_felt("gecn2j0cm45sz")
ETH_USD_ID = str_to_felt("k84azmn47vsj8az")
TSLA_USD_ID = str_to_felt("2jfk20ckwlmzaksc")
DOGE_ID = str_to_felt("jdi2i8621hzmnc7324o")
TSLA_ID = str_to_felt("i39sk1nxlqlzcee")


@pytest.fixture(scope='module')
def event_loop():
    return asyncio.new_event_loop()


@pytest.fixture(scope='module')
async def adminAuth_factory():
    starknet = await Starknet.empty()

    alice = await starknet.deploy(
        "contracts/Account.cairo",
        constructor_calldata=[
            alice_signer.public_key,
            0,
        ]
    )

    return alice


@pytest.mark.asyncio
async def test_should_calculate_correct_liq_ratio_1(adminAuth_factory):
    alice = adminAuth_factory

    alice_balance_usdc = to64x61(5500)
    alice_balance_ust = to64x61(100)

    await alice_signer.send_transaction(alice, alice.contract_address, 'set_balance', [USDC_ID, alice_balance_usdc])
    await alice_signer.send_transaction(alice, alice.contract_address, 'set_balance', [UST_ID, alice_balance_ust])

    alice_curr_balance_usdc_before = await alice.get_balance(USDC_ID).call()
    alice_curr_balance_ust_before = await alice.get_balance(UST_ID).call()
    assert from64x61(alice_curr_balance_usdc_before.result.res) == 5500
    assert from64x61(alice_curr_balance_ust_before.result.res) == 100

    alice_list = await alice.return_array_collaterals().call()
    assert from64x61(
        alice_list.result.array_list[0].balance) == from64x61(alice_balance_usdc)
    assert from64x61(
        alice_list.result.array_list[1].balance) == from64x61(alice_balance_ust)

    alice_increment = to64x61(100000)
    await alice_signer.send_transaction(alice, alice.contract_address, 'set_balance', [USDC_ID, alice_increment])

    alice_list_1 = await alice.return_array_collaterals().call()
    assert from64x61(
        alice_list_1.result.array_list[0].balance) == from64x61(alice_balance_usdc + alice_increment)
    assert from64x61(
        alice_list_1.result.array_list[1].balance) == from64x61(alice_balance_ust)
    assert len(alice_list_1.result.array_list) == 2

