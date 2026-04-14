# test: 1000 iterations of Trader.run() each time with a TradingState object
#TradingState -> all trades that have happened since last iteration(mine and other bot traders)
#             -> overview of all pending buy and sell orders for each product


from datamodel import OrderDepth, UserId, TradingState, Order, Product
from typing import List, Optional
import string
import jsonpickle


POSITION_LIMITS = {
    'TOMATOES': 80,
    'EMERALDS': 80,
    'INTARIAN_PEPPER_ROOT': 80,
    'ASH_COATED_OSMIUM': 80
}

class ProductTrader:
    def __init__(self, product: Product, state: TradingState, new_trader_data: str):
        self.product = product
        self.state = state
        self.position_limit = POSITION_LIMITS.get(product, 0)
        self.initial_position = self.state.position.get(product, 0)
        self.new_trader_data = new_trader_data
        self.last_trader_data = self.get_last_trader_data()

        self.buy_orders, self.sell_orders = self.get_order_depths()
        self.total_market_buy_volume, self.total_market_sell_volume = self.get_total_market_buy_sell_volume()
        self.bid_wall, self.mid_wall, self.ask_wall = self.get_walls()
        self.best_bid, self.best_ask = self.get_best_bid_ask()
        self.max_allowed_buy_volume, self.max_allowed_sell_volume = self.get_max_allowed_volume()
        self.orders = []

    def get_max_allowed_volume(self):
        max_allowed_buy_volume = self.position_limit - self.initial_position
        max_allowed_sell_volume = self.position_limit + self.initial_position
        return max_allowed_buy_volume, max_allowed_sell_volume

    def get_last_trader_data(self):
                        
        last_traderData = {}
        try:
            if self.state.traderData != '':
                last_traderData = jsonpickle.loads(self.state.traderData)
        except: pass

        return last_traderData

    def get_best_bid_ask(self):

        best_bid = best_ask = None

        try:
            if len(self.buy_orders) > 0:
                best_bid = max(self.buy_orders.keys())
            if len(self.sell_orders) > 0:
                best_ask = min(self.sell_orders.keys())
        except: pass

        return best_bid, best_ask


    def get_walls(self):
        bid_wall = wall_mid = ask_wall = None

        try: bid_wall = min([x for x,_ in self.buy_orders.items()])
        except: pass
        
        try: ask_wall = max([x for x,_ in self.sell_orders.items()])
        except: pass

        try: wall_mid = (bid_wall + ask_wall) / 2
        except: pass

        return bid_wall, wall_mid, ask_wall

    def get_order_depths(self):
        order_depth, buy_orders, sell_orders = {}, {}, {}

        try: order_depth = self.state.order_depths[self.product]
        except: pass

        try: buy_orders = {buy_value: abs(buy_amount) for buy_value, buy_amount in sorted(order_depth.buy_orders.items(), key = lambda x: x[0], reverse = True)}
        except: pass

        try: sell_orders = {sell_value: abs(sell_amount) for sell_value, sell_amount in sorted(order_depth.sell_orders.items(), key = lambda x: x[0])}
        except: pass

        return buy_orders, sell_orders

    def get_total_market_buy_sell_volume(self):

        market_bid_volume = market_ask_volume = 0

        try:
            market_bid_volume = sum([v for p, v in self.buy_orders.items()])
            market_ask_volume = sum([v for p, v in self.sell_orders.items()])
        except: pass

        return market_bid_volume, market_ask_volume

    
    def bid(self, price, volume):
        abs_volume = min(abs(int(volume)), self.max_allowed_buy_volume)
        order = Order(self.product, int(price), abs_volume)
        self.max_allowed_buy_volume -= abs_volume
        self.orders.append(order)

    def ask(self, price, volume):
        abs_volume = min(abs(int(volume)), self.max_allowed_sell_volume)
        order = Order(self.product, int(price), -abs_volume)
        self.max_allowed_sell_volume -= abs_volume
        self.orders.append(order)

    def get_orders(self):
        return {}


class EmeraldsTrader(ProductTrader):
    def __init__(self, state, new_trader_data):
        super().__init__("EMERALDS", state, new_trader_data)

    def get_orders(self):
        if self.mid_wall is not None:
            #taking
            for sell_price, sell_volume in self.sell_orders.items():
                if sell_price < self.mid_wall:
                    self.bid(sell_price, sell_volume)
                elif sell_price <= self.mid_wall and self.initial_position < 0:
                    volume = min(sell_volume, abs(self.initial_position))
                    self.bid(sell_price, volume)

            for buy_price, buy_volume in self.buy_orders.items():
                if buy_price > self.mid_wall:
                    self.ask(buy_price, buy_volume)
                elif buy_price >= self.mid_wall and self.initial_position > 0:
                    volume = min(buy_volume, self.initial_position)
                    self.ask(buy_price, volume)

            #making
            bid_price = int(self.bid_wall + 1) # base case
            ask_price = int(self.ask_wall - 1) # base case

            #OVERBIDDING: overbid best bid that is still under the mid wall
            for buy_price, buy_volume in self.buy_orders.items():
                overbid_price = buy_price + 1
                if buy_volume > 1 and overbid_price < self.mid_wall:
                    bid_price = max(bid_price, overbid_price)
                    break
                elif buy_price < self.mid_wall:
                    bid_price = max(bid_price, buy_price)
                    break

            # UNDERBIDDING: underbid best ask that is still over the mid wall
            for sell_price, sell_volume in self.sell_orders.items():
                underbid_price = sell_price - 1
                if sell_volume > 1 and underbid_price > self.mid_wall:
                    ask_price = min(ask_price, underbid_price)
                    break
                elif sell_price > self.mid_wall:
                    ask_price = min(ask_price, sell_price)
                    break

            # POST ORDERS
            self.bid(bid_price, self.max_allowed_buy_volume)
            self.ask(ask_price, self.max_allowed_sell_volume)
        return self.orders

class TomatoesTrader(ProductTrader):
    """Touch-based market making: quote near best bid/ask, not full-book walls.
    Slow EMA of microprice as fair value; inventory skew; fair-vs-market nudge."""

    EMA_ALPHA = 0.08
    MAX_INV_SKEW = 5
    MAX_FAIR_ADJ = 4

    def __init__(self, state, new_trader_data):
        super().__init__("TOMATOES", state, new_trader_data)
        self.ema_mid: Optional[float] = None

    def get_orders(self):
        if self.best_bid is None or self.best_ask is None:
            return self.orders
        if self.best_ask <= self.best_bid:
            return self.orders

        mid = (self.best_bid + self.best_ask) / 2.0
        td = self.last_trader_data if isinstance(self.last_trader_data, dict) else {}
        raw = td.get("TOMATOES_EMA")
        if raw is None:
            self.ema_mid = mid
        else:
            self.ema_mid = self.EMA_ALPHA * mid + (1.0 - self.EMA_ALPHA) * float(raw)

        pos = self.initial_position
        sig = 0 if pos == 0 else (1 if pos > 0 else -1)
        mag = min(self.MAX_INV_SKEW, abs(pos) // 8)
        inv_adj = -sig * mag

        delta = mid - self.ema_mid
        fair_adj = max(-self.MAX_FAIR_ADJ, min(self.MAX_FAIR_ADJ, int(round(delta / 2))))
        bid_price = int(self.best_bid) + inv_adj - fair_adj
        ask_price = int(self.best_ask) + inv_adj - fair_adj

        if bid_price >= ask_price:
            bid_price = ask_price - 1

        self.bid(bid_price, self.max_allowed_buy_volume)
        self.ask(ask_price, self.max_allowed_sell_volume)
        return self.orders

class PepperTrader(ProductTrader):


    def __init__(self, state, new_trader_data):
        super().__init__("INTARIAN_PEPPER_ROOT", state, new_trader_data)

    def get_orders(self):
        for ask_price, ask_volume in self.sell_orders.items():
            if self.max_allowed_buy_volume <= 0:
                break
            self.bid(ask_price, ask_volume)
        return self.orders

class AshTrader(ProductTrader):
    def __init__(self, state, new_trader_data):
        super().__init__("ASH_COATED_OSMIUM", state, new_trader_data)

    def get_orders(self):
        if self.mid_wall is not None:
            #taking
            for sell_price, sell_volume in self.sell_orders.items():
                if sell_price < self.mid_wall:
                    self.bid(sell_price, sell_volume)
                elif sell_price <= self.mid_wall and self.initial_position < 0:
                    volume = min(sell_volume, abs(self.initial_position))
                    self.bid(sell_price, volume)

            for buy_price, buy_volume in self.buy_orders.items():
                if buy_price > self.mid_wall:
                    self.ask(buy_price, buy_volume)
                elif buy_price >= self.mid_wall and self.initial_position > 0:
                    volume = min(buy_volume, self.initial_position)
                    self.ask(buy_price, volume)

            #making
            bid_price = int(self.bid_wall + 1) # base case
            ask_price = int(self.ask_wall - 1) # base case

            #OVERBIDDING: overbid best bid that is still under the mid wall
            for buy_price, buy_volume in self.buy_orders.items():
                overbid_price = buy_price + 1
                if buy_volume > 1 and overbid_price < self.mid_wall:
                    bid_price = max(bid_price, overbid_price)
                    break
                elif buy_price < self.mid_wall:
                    bid_price = max(bid_price, buy_price)
                    break

            # UNDERBIDDING: underbid best ask that is still over the mid wall
            for sell_price, sell_volume in self.sell_orders.items():
                underbid_price = sell_price - 1
                if sell_volume > 1 and underbid_price > self.mid_wall:
                    ask_price = min(ask_price, underbid_price)
                    break
                elif sell_price > self.mid_wall:
                    ask_price = min(ask_price, sell_price)
                    break

            # POST ORDERS
            self.bid(bid_price, self.max_allowed_buy_volume)
            self.ask(ask_price, self.max_allowed_sell_volume)
        return self.orders


traders: dict[Product, ProductTrader] = {
    'EMERALDS': EmeraldsTrader,
    'TOMATOES': TomatoesTrader,
    'INTARIAN_PEPPER_ROOT': PepperTrader,
    'ASH_COATED_OSMIUM': AshTrader
}

class Trader:

    def bid(self):
        return 15
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        #BE ATTENTIVE AT POSITION LIMITS
        print("traderData: " + state.traderData)  # this object stores state between iterations of Trader.run()
        print("Observations: " + str(state.observations))

        # Orders to be placed on exchange matching engine
        result = {}
        trader_data_obj: dict = {}
        try:
            if state.traderData:
                trader_data_obj = jsonpickle.loads(state.traderData)
        except Exception:
            trader_data_obj = {}

        for product in state.order_depths:
            trader_class = traders[product]
            if trader_class is not None:
                trader: ProductTrader = trader_class(state, state.traderData)
                result[product] = trader.get_orders()
                if product == "TOMATOES" and isinstance(trader, TomatoesTrader) and trader.ema_mid is not None:
                    trader_data_obj["TOMATOES_EMA"] = trader.ema_mid
        # String value holding Trader state data required.
        # It will be delivered as TradingState.traderData on next execution.
        traderData = jsonpickle.dumps(trader_data_obj)
        
        # Sample conversion request. Check more details below. 
        conversions = None
        return result, conversions, traderData