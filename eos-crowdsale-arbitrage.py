from binance.client import Client
from binance.helpers import *
from binance.exceptions import *
from decimal import *
from datetime import *
import time
import sys
import subprocess
import math
import requests


# return string from decimal without decimal point and trailing zeros
def dec_to_str(dec):
    s = str(dec)
    return s.rstrip('0').rstrip('.') if '.' in s else s

# determine avg price filled from market order on Binance
def get_weighted_avg_price_from_fills(order):
    weighted_sum = 0
    qty = 0
    for fill in order['fills']:
        weighted_sum += Decimal(fill['price']) * Decimal(fill['qty'])
        qty += Decimal(fill['qty'])

    weighted_avg_price = weighted_sum / qty
    return weighted_avg_price

# API keys for automatic trading on Binance
API_KEY = '<BINANCE API KEY>'
API_SECRET = '<BINANCE SECRET API KEY>'

# address on Binance to send and sell the EOS
Binance_EOS_address = '<BINANCE DEPOSIT ADDRESS FOR EOS>'
# address for sending ETH to buy EOS, claim EOS, and send EOS to your Binance address
ETH_private_wallet_address = '<ETH WALLET ADDRESS YOU HAVE KEYS FOR>'

client = Client(API_KEY, API_SECRET)

####  CHANGE & ADJUST MANUALLY EVERY DAY  ####
current_period = '347'  # next period
current_period_ends = datetime(2018, 5, 29, 21)
percent_below_price = Decimal('3')  # only attempt to buy EOS if there's at least a 3% difference in price
minutes_before_end = timedelta(minutes=3)   # time before end of period for price difference check above
####  CHANGE & ADJUST MANUALLY EVERY DAY  ####

#### ADJUST GAS PRICE AS NEEDED ####
gas_limit_contract = '400000' # wei
gas_limit_xfer = '200000' # wei
gas_price_contract = '125000000000' # 125 Gwei
gas_price_xfer = '125000000000' # 125 Gwei
# ETH amount we need to save in private wallet for gas:
#   - gas for buyWithLimit() = 400000 * 125000000000
#   - gas for claim() = 400000 * 125000000000
#   - gas for transfer = 200000 * 125000000000
total_gas_wei = Decimal(gas_limit_contract) * Decimal(gas_price_contract) * Decimal('2') \
                + Decimal(gas_limit_xfer) * Decimal(gas_price_xfer)

EOS_crowdfund_contract_address = '0xd0a6e6c54dbc68db5db3a091b171a77407ff7ccf'
EOS_token = '0x86fa049857e0209aa7d9e616f7eb3b3b78ecfdb0'
wei_in_ETH = Decimal('1000000000000000000')
EOS_in_period = Decimal('2000000')
fee = Decimal('0.05') # Binance transaction fee (0.05%)
Binance_withdraw_fee = Decimal('0.01') # 0.01 ETH
EOSETH_stepQty = Decimal('0.01')

time_before = current_period_ends - minutes_before_end


print('Waiting until %d' % (minutes_before_end.seconds / 60), 'minutes before end of period...')

# print current prices & wait until x minutes before end of crowdsale to use price to determine buylimit
while datetime.now() <= time_before:

    # check amount of ETH contributed
    try:
        r = requests.get('https://api.etherest.io:8080/v1/main/' + EOS_crowdfund_contract_address + '/dailyTotals/'
                        + current_period)
        wei_totals = Decimal(r.json()['response'])
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
    except:
        print('Exception on etherest request')
        continue

    ETH_totals = wei_totals / wei_in_ETH
    EOS_price = ETH_totals / EOS_in_period

    # check bid price of EOSETH
    try:
        ticker = client.get_ticker(symbol='EOSETH')
        # use bid price for comparing since we will market sell
        bid_price = Decimal(ticker['bidPrice'])
    except BinanceAPIException as e:
        print('Binance exception on get_ticker.', e.message)
        continue

    price_diff = (bid_price - EOS_price) / EOS_price * 100
    print('EOS crowdsale price: %.8f' % EOS_price, ' EOS Binance price: %.8f' % bid_price, ' Difference: %.2f%% ' % price_diff, datetime.now())
    # loop takes about 1 sec for API calls so don't sleep


# set buy with limit percent lower than bid price before period ends
if price_diff >= percent_below_price:
    buy_limit_price = (Decimal('1') - percent_below_price / Decimal('100')) * bid_price # ETH/EOS
    # need limit amount of ETH in wei
    ETH_buy_limit = buy_limit_price * EOS_in_period
    ETH_buy_limit_str = dec_to_str(ETH_buy_limit)
    ETH_wei_buy_limit = ETH_buy_limit * wei_in_ETH
    ETH_wei_buy_limit_str = dec_to_str(ETH_wei_buy_limit)

    print('Buy limit price: %.8f' % buy_limit_price, 'ETH limit: ', ETH_buy_limit_str, 'wei limit: ', ETH_wei_buy_limit_str)
else:
    # do not submit buy
    print('Price difference lower than %.1f%%. Do not buy with limit' % percent_below_price)
    sys.exit()


# get ETH wallet balance
process = subprocess.run(['seth', 'balance', ETH_private_wallet_address], stdout=subprocess.PIPE)
if process.returncode:
    print('return code not zero!', process.stderr)
    sys.exit()
# format string. seth balance output is scientific notation like '12.05730621E+18'
ETH_wei_wallet_qty_str = process.stdout.decode().rstrip()
ETH_wei_wallet_qty_dec = Decimal(ETH_wei_wallet_qty_str)
# both are scientific notation whole numbers we convert to int to remove E notation
ETH_wei_send_qty = int(ETH_wei_wallet_qty_dec - total_gas_wei)
ETH_wei_send_qty_str = str(ETH_wei_send_qty)
ETH_send_qty = ETH_wei_send_qty / wei_in_ETH


# converts wei to hex and pads with leading zeros to 64 length for parameter to buyWithLimit(uint,uint)
ETH_wei_buy_limit_hex_str = format(int(ETH_wei_buy_limit), 'x').zfill(64)
print('ETH wei buy limit hex', ETH_wei_buy_limit_hex_str)
print('Sending', ETH_send_qty, 'ETH =', ETH_wei_send_qty_str, 'wei', datetime.now())

# buy limit to EOS crowdfund contract
process = subprocess.run(['seth', 'send', '--gas='+gas_limit_contract, '--gas-price='+gas_price_contract,
                            '--value='+ETH_wei_send_qty_str, EOS_crowdfund_contract_address,
                            'buyWithLimit(uint,uint)', current_period, ETH_wei_buy_limit_hex_str])
if process.returncode:
    print('return code not zero!', process.stderr)
    sys.exit()



print('Sent. Waiting for period expiration...', datetime.now())
# loop until time period ended - difference (in seconds) is negative + 1 second safety factor
while (current_period_ends - datetime.now()).total_seconds() >= -1:
    
    # check amount everyone contributed so far
    try:
        r = requests.get('https://api.etherest.io:8080/v1/main/' + EOS_crowdfund_contract_address + '/dailyTotals/'
                        + current_period)
        wei_totals = Decimal(r.json()['response'])
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
    except:
        print('Exception on etherest request')
        continue

    ETH_totals = wei_totals / wei_in_ETH
    EOS_price = ETH_totals / EOS_in_period

    # check exchange bid price of EOSETH
    try:
        ticker = client.get_ticker(symbol='EOSETH')
        bid_price = Decimal(ticker['bidPrice'])
    except BinanceAPIException as e:
        print('Binance exception on get_ticker.', e.message)
        continue

    price_diff = (bid_price - EOS_price) / EOS_price * 100
    print('EOS crowdfund price %.8f' % EOS_price, ' EOS binance price %.8f' % bid_price, ' Difference %.2f%% ' % price_diff, datetime.now())



# period ended. check amount we contributed
print('Period has ended. Check if we contributed', datetime.now())
try:
    r = requests.get('https://api.etherest.io:8080/v1/main/'+EOS_crowdfund_contract_address+'/userBuys/'
                        +current_period+'/'+ETH_private_wallet_address)
    wei_contributed = Decimal(r.json()['response'])
except (KeyboardInterrupt, SystemExit):
    sys.exit()
except:
    print('Exception on etherest request')

# change 0 if we already contributed earlier
if wei_contributed != 0:
    print('Successfully contributed', wei_contributed, 'wei', datetime.now())
else:
    print('Must not have contributed this period.', datetime.now())
    sys.exit()



# claim & receive EOS we contributed from EOS crowdfund contract
print('Sending claim to EOS contract', datetime.now())
process = subprocess.run(['seth', 'send', '--gas='+gas_limit_contract, '--gas-price='+gas_price_contract,
                            EOS_crowdfund_contract_address, 'claim(uint256)', current_period])
if process.returncode:
    print('return code not zero!', process.stderr)
    sys.exit()
print('Claim finished', datetime.now())



# check local wallet EOS balance until nonzero
EOS_wallet_wei_qty_hex_str = ''
while EOS_wallet_wei_qty_hex_str == '':
    # get EOS balance. returns wei value in hex
    process = subprocess.run(['seth', 'call', EOS_token, 'balanceOf(address)(uint)',
                                ETH_private_wallet_address], stdout=subprocess.PIPE)
    if process.returncode:
        print('return code not zero!', process.stderr)
        sys.exit()
    # format string
    EOS_wallet_wei_qty_hex_str = process.stdout.decode().rstrip()

EOS_wallet_qty = Decimal(int(EOS_wallet_wei_qty_hex_str, 16) / wei_in_ETH)
EOS_crowd_price = ETH_send_qty / EOS_wallet_qty
print('EOS crowd price:', EOS_crowd_price) 



# transfer EOS from private wallet to Binance
print('Sending', EOS_wallet_qty, 'EOS', EOS_wallet_wei_qty_hex_str, 'wei hex to Binance', datetime.now())
process = subprocess.run(['seth', 'send', '--gas='+gas_limit_xfer, '--gas-price='+gas_price_xfer,
                            EOS_token, 'transfer(address,uint)(bool)', Binance_EOS_address, EOS_wallet_wei_qty_hex_str])
if process.returncode:
    print('return code not zero!', process.stderr)
    sys.exit()



# check EOS balance on Binance until nonzero
print('Waiting for EOS balance to show at Binance...', datetime.now())
EOS_balance = 0
while EOS_balance < 1:
    # check EOS Balance
    try:
        EOS_balance = Decimal(client.get_asset_balance(asset='EOS')['free'])
    except BinanceAPIException as e:
        print('Binance exception on get_asset_balance(asset=EOS).', e.message)
        continue
    
    # if EOS recieved on exchange, break loop so we don't waste time
    if EOS_balance >= 1:
        break
    
    # check amount of ETH contributed
    try:
        r = requests.get('https://api.etherest.io:8080/v1/main/' + EOS_crowdfund_contract_address + '/dailyTotals/'
                        + current_period)
        wei_totals = Decimal(r.json()['response'])
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
    except:
        print('Exception on etherest request')
        continue
    
    ETH_totals = wei_totals / wei_in_ETH
    EOS_price = ETH_totals / EOS_in_period

    # check bid price of EOSETH
    try:
        ticker = client.get_ticker(symbol='EOSETH')
        bid_price = Decimal(ticker['bidPrice'])
    except BinanceAPIException as e:
        print('Binance exception on get_ticker.', e.message)
        continue

    price_diff = (bid_price - EOS_price) / EOS_price * 100
    print('EOS crowdfund price %.8f' % EOS_price, ' EOS binance price %.8f' % bid_price, ' Difference %.2f%% ' % price_diff, datetime.now())
    # loop takes about 1 sec for API calls so don't sleep



# place Binance market sell order of EOS for ETH
EOS_qty_to_sell = math.floor(EOS_balance / EOSETH_stepQty) * EOSETH_stepQty 
print('Binance has EOS balance:', EOS_balance, 'Selling:', EOS_qty_to_sell, 'EOS', datetime.now())

try:
    market_order = client.order_market_sell(symbol='EOSETH', quantity=EOS_qty_to_sell, newOrderRespType='FULL')
except BinanceAPIException as e:
    print('Binance exception on order_market_sell.', e.message)

# get price sold
price_sold = get_weighted_avg_price_from_fills(market_order)
print('EOS sell executed at avg price %.8f' % price_sold, 'ETH', datetime.now())

gain_pct = (price_sold - EOS_crowd_price) / EOS_crowd_price * 100
print('Gain/Loss without any fees: %.2f%%' % gain_pct)
