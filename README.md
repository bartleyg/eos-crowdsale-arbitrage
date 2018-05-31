# eos-crowdsale-arbitrage
[EOS](https://eos.io/) had the largest cryptocurrency ICO crowdsale in history running over a period of approximately 341 days. During that time EOS was listed on many large cryptocurrency exchanges with decent liquidity. The [price of EOS from the daily EOS crowdsale](https://eosprice.io/) was determined by the total amount of ETH contributed by the end of each period. The price of EOS was also continuously trading on exchanges too. This presented an arbitrage opportunity at times when the EOS crowdsale did not raise enough ETH during the period to match the current market price on exchanges.

My script continuously checks the amount of ETH contributed during the current crowdfund period (determining the EOSETH crowdfund price) and compares it to the current [EOSETH trading bid price on Binance](https://www.binance.com/trade.html?symbol=EOS_ETH). If the effective crowdfund price was lower by at least a certain percent (~3%) a couple minutes before the crowdfund period ended, the script would send a ```buyWithLimit()``` transaction to the EOS crowdfund contract from my private wallet with a high gas price. If successful, once the period was over the script would send a ```claim()``` to the crowdfund contract. Once the EOS was received in the personal wallet, it would then transfer the EOS to the Binance deposit wallet. Then after the ~30 confirmations it would take for Binance to acknowledge the deposit, the script would immediately sell all the EOS for ETH at market price. Hopefully for a profit.

## In practice:
Unfortunately I was late to the game and only stumbled onto this opportunity about a month before the whole crowdsale ended. I was definitely not the only one doing this arbitrage. Often times the crowdfund price could be 10% lower than the exchange price 5 minutes before the period ended, only to see the crowdfund price rapidly converge all the way to the market price (or beyond) once the period ended.

The ethereum network would get extremely busy right before and after the EOS crowdsale period ended, so you had to send a very high gas price in hopes to get your buy in before the end (and there was no guarantee). I believe some bad actors may have even spammed the network at this time to keep others out of the crowdfund when the opportunity was big enough.

Using the ```buyWithLimit()``` contract function helped protect me some so that if my contribution was late and missed the period, the contribution would not automatically roll into the next period as it would with ```buy()```. Also the price was set (~3%) so that if the crowdfund price shot up in the time between us sending the ```buyWithLimit()``` and the time the transaction was mined, the buy transaction would fail.

Usually the EOSETH Binance price would start to fall in the minutes following each crowdsale period. The 30 confirmation deposit Binance required before selling the EOS was a huge bottleneck and risk. This translated into not being able to sell EOS until 7.5 - 10 minutes after the period ended, generally a couple percentage lower than the price at the period end. Clearly others had more favorable confirmation terms as I would see large limit asks stack the orderbook much sooner.

I also noticed the EOSETH price on Binance would get heavily manipulated after most periods ended. Usually the price would drop and converge towards the crowdfund price as sell orders would come in the first 10-15 minutes, but sometimes the price would get pumped up over ~30 minutes until I saw large sell orders clear the bid order book at higher prices. Crypto is the wild west as they say...

## Setup:
My script depends on [seth](https://github.com/dapphub/seth), a good command-line utility for easily interacting with the ethereum blockchain. First, setup ```seth``` with your personal ethereum wallet and ensure it is working fine. If you want to use the Infura remote node, you should probably get an [Infura API key](https://infura.io/signup) and add it to your ~/.sethrc file.

Then get API trading keys from your Binance account and install the python-binance dependency:
```
pip3 install python-binance
```

Add your Binance API keys, Binance deposit address, and personal ethereum wallet address to eos-crowdsale-arbitrage.py.

## Use:
Manually adjust the period, time, gas price as necessary before each period in eos-crowdsale-arbitrage.py. Make sure you have your ETH back into your personal wallet after having sold EOS for ETH at Binance and withdrawing.

```
python3 eos-crowdsale-arbitrage.py
```
