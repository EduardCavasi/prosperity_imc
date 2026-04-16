# price : volume
bid_book = [(20, 43, "default"), (19, 17, "default"), (18, 6, "default"), (17, 5, "default"),
(16, 10, "default"), (15, 5, "default"), (14, 10, "default"), (13, 7, "default")]

ask_book = [(12, 20, "default"), (13, 25, "default"), (14, 35, "default"), (15, 6, "default"),
(16, 5, "default"), (17, 0, "default"), (18, 10, "default"), (19, 12, "default")]

final_price = 19.9

#bid_book = [(30, 30, "default"), (29, 5, "default"), (28, 12, "default"), (27, 28, "default")]

#ask_book = [(28, 40, "default"), (31, 20, "default"), (32, 20, "default"), (33, 30, "default")]

#final_price = 30

# say be place buy order
max_profit = 0
best_buy_price = 0
best_buy_volume = 0
best_final_clearing_price = 0   
for buy_price in range(1, 35):
    for buy_volume in range(1, 200):
        max_matched_volume = 0
        final_clearing_price = 0

        # insert my bid in bid book
        insert_pos = len(bid_book)
        for pos in range(len(bid_book)):
            bp, bv, _ = bid_book[pos]
            if bp < buy_price:
                insert_pos = pos
                break
        new_bid_book = bid_book[:insert_pos] + [(buy_price, buy_volume, "mine")] + bid_book[insert_pos:]
        for clearing_price in range(35, 0, -1):
            demand = 0
            supply = 0
            for bid_book_price, bid_book_volume, _ in new_bid_book:
                if bid_book_price >= clearing_price:
                    demand += bid_book_volume
            
            for ask_book_price, ask_book_volume, _ in ask_book:
                if ask_book_price <= clearing_price:
                    supply += ask_book_volume
            matched_volume = min(demand, supply)

            if matched_volume > max_matched_volume:
                max_matched_volume = matched_volume
                final_clearing_price = clearing_price
        
        
        # we have found the clearing price

        #not profitable to buy at above final_price
        if final_clearing_price >= final_price:
            continue
        #keep only the orders that are included in the auction 
        buyers_included = [(bp, bv, _type) for bp, bv, _type in new_bid_book if bp >= final_clearing_price]
        sellers_included = [(ap, av, _type) for ap, av, _type in ask_book if ap <= final_clearing_price]
        #if my order not included skip
        if "mine" not in [t for _, _, t in buyers_included]:
            continue
        higher_priority_demand = 0
        for _, bv, _type in buyers_included:
            if _type == "mine":
                break
            higher_priority_demand += bv
        total_supply = sum([av for ap, av, _ in sellers_included])
        my_buy_volume = min(buy_volume, max(0, total_supply - higher_priority_demand))

        my_profit = (final_price - final_clearing_price) * my_buy_volume
        if my_profit > max_profit:
            max_profit = my_profit
            best_buy_price = buy_price
            best_buy_volume = buy_volume
            best_final_clearing_price = final_clearing_price

print(best_buy_price, str(best_buy_volume) + "k", best_final_clearing_price, str(max_profit) + "k")


max_profit = 0
best_ask_price = 0
best_ask_volume = 0
best_final_clearing_price = 0
for ask_price in range(1, 35):
    for ask_volume in range(1, 200):
        max_matched_volume = 0
        final_clearing_price = 0

        # insert my ask in ask book
        insert_pos = len(ask_book)
        for pos in range(len(ask_book)):
            ap, av, _ = ask_book[pos]
            if ap > ask_price:
                insert_pos = pos
                break
        new_ask_book = ask_book[:insert_pos] + [(ask_price, ask_volume, "mine")] + ask_book[insert_pos:]
        for clearing_price in range(35, 0, -1):
            demand = 0
            supply = 0
            for bid_book_price, bid_book_volume, _ in bid_book:
                if bid_book_price >= clearing_price:
                    demand += bid_book_volume
            
            for ask_book_price, ask_book_volume, _ in new_ask_book:
                if ask_book_price <= clearing_price:
                    supply += ask_book_volume
            matched_volume = min(demand, supply)

            if matched_volume > max_matched_volume:
                max_matched_volume = matched_volume
                final_clearing_price = clearing_price
        
        
        # we have found the clearing price

        if final_clearing_price <= final_price:
            continue
        #keep only the orders that are included in the auction 
        buyers_included = [(bp, bv, _type) for bp, bv, _type in bid_book if bp >= final_clearing_price]
        sellers_included = [(ap, av, _type) for ap, av, _type in new_ask_book if ap <= final_clearing_price]
        #if my order not included skip
        if "mine" not in [t for _, _, t in sellers_included]:
            continue

        higher_priority_supply = 0
        for _, av, _type in sellers_included:
            if _type == "mine":
                break
            higher_priority_supply += av
        total_demand = sum([bv for bp, bv, _ in buyers_included])
        my_ask_volume = min(max(0, total_demand - higher_priority_supply), ask_volume)

        my_profit = (final_clearing_price - final_price) * my_ask_volume
        if my_profit > max_profit:
            max_profit = my_profit
            best_ask_price = ask_price
            best_ask_volume = ask_volume
            best_final_clearing_price = final_clearing_price

print(best_ask_price, str(best_ask_volume) + "k", best_final_clearing_price, str(max_profit) + "k")