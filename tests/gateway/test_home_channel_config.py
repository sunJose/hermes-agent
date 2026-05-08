"""Tests for gateway HomeChannel config serialization."""

from gateway.config import HomeChannel, Platform


class TestHomeChannelRoundtrip:
    def test_thread_id_is_optional_and_serialized(self):
        home = HomeChannel(
            platform=Platform.FEISHU,
            chat_id="oc_home",
            name="Feishu DM",
            thread_id="thread-1",
        )

        data = home.to_dict()
        assert data == {
            "platform": "feishu",
            "chat_id": "oc_home",
            "name": "Feishu DM",
            "thread_id": "thread-1",
        }

        restored = HomeChannel.from_dict(data)
        assert restored == home

    def test_thread_id_can_be_omitted_for_backwards_compatibility(self):
        home = HomeChannel.from_dict({
            "platform": "telegram",
            "chat_id": "12345",
            "name": "Home",
        })

        assert home.thread_id is None
        assert home.to_dict() == {
            "platform": "telegram",
            "chat_id": "12345",
            "name": "Home",
        }
