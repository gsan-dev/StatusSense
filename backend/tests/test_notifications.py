from app.notifications.webhook import _is_discord_webhook


def test_is_discord_webhook_detects_discord_com():
    assert _is_discord_webhook("https://discord.com/api/webhooks/123/abc")


def test_is_discord_webhook_detects_discordapp_com():
    assert _is_discord_webhook("https://discordapp.com/api/webhooks/123/abc")


def test_is_discord_webhook_rejects_other_urls():
    assert not _is_discord_webhook("https://example.com/hook")
    assert not _is_discord_webhook("https://hooks.slack.com/services/x")
