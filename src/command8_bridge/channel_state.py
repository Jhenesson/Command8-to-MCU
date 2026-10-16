# Esse estado só é atualizado no sentido hardware->host (bridge.py chama
# set_button_led só em handle_hardware_message). Isso é intencional, não um bug:
# botões MCU são momentâneos (o Logic decide o toggle e manda o LED de volta), e
# se handle_host_message também chamasse set_button_led, um LED aceso pelo Logic
# suprimiria o próximo aperto físico do usuário (should_forward_button acharia que
# "já está nesse estado"). Não "consertar" isso sem redesenhar como o mute/solo
# real funciona.
class ChannelState:
    def __init__(self, num_channels: int = 8):
        self.num_channels = num_channels
        self._button_leds: dict[tuple[int, str], bool] = {}

    def get_button_led(self, channel: int, button: str) -> bool:
        return self._button_leds.get((channel, button), False)

    def set_button_led(self, channel: int, button: str, on: bool) -> None:
        self._button_leds[(channel, button)] = on

    def should_forward_button(self, channel: int, button: str, on: bool) -> bool:
        current = self.get_button_led(channel, button)
        return current != on
