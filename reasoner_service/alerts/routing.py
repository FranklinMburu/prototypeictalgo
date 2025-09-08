def route_channels_for_symbol(symbol):
    # Simple routing: send to all channels
    return ["slack", "discord", "telegram"]
