def is_admin(event, config) -> bool:
    # Explicit QQ IDs are only trusted on the OneBot adapter.
    return bool(event.is_admin()) or (
        event.get_platform_name() == "aiocqhttp"
        and str(event.get_sender_id()) in config["admins"]
    )
