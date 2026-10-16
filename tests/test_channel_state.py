from command8_bridge.channel_state import ChannelState


def test_initial_led_state_is_off():
    state = ChannelState(num_channels=8)
    assert state.get_button_led(0, "mute") is False


def test_set_and_get_button_led():
    state = ChannelState(num_channels=8)
    state.set_button_led(2, "solo", True)
    assert state.get_button_led(2, "solo") is True


def test_should_forward_button_true_on_change():
    state = ChannelState(num_channels=8)
    assert state.should_forward_button(0, "mute", True) is True


def test_should_forward_button_false_when_unchanged():
    state = ChannelState(num_channels=8)
    state.set_button_led(0, "mute", True)
    assert state.should_forward_button(0, "mute", True) is False


def test_should_forward_button_true_after_real_change():
    state = ChannelState(num_channels=8)
    state.set_button_led(0, "mute", True)
    assert state.should_forward_button(0, "mute", False) is True
