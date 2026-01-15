def calculate_discount(price, category):
    """
    Calculates discount based on price and category.
    High complexity example.
    """
    if price > 1000:
        if category == "electronics":
            return price * 0.1
        elif category == "clothing":
            return price * 0.2
    elif price > 500:
        if category == "bulk":
            return price * 0.05
    
    return 0

def process_order(order):
    price = order.get("price")
    cat = order.get("category")
    discount = calculate_discount(price, cat)
    final_price = price - discount
    save_to_db(final_price)
    return final_price

def save_to_db(amount):
    print(f"Saving {amount} to database...")
