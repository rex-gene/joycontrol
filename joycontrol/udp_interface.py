import inspect
import logging
import socket

from aioconsole import ainput

from joycontrol.controller_state import button_push, ControllerState, button_down, button_up
from joycontrol.transport import NotConnectedError

logger = logging.getLogger(__name__)

def _print_doc(string):
    """
    Attempts to remove common white space at the start of the lines in a doc string
    to unify the output of doc strings with different indention levels.

    Keeps whitespace lines intact.

    :param fun: function to print the doc string of
    """
    lines = string.split('\n')
    if lines:
        prefix_i = 0
        for i, line_0 in enumerate(lines):
            # find non empty start lines
            if line_0.strip():
                # traverse line and stop if character mismatch with other non empty lines
                for prefix_i, c in enumerate(line_0):
                    if not c.isspace():
                        break
                    if any(lines[j].strip() and (prefix_i >= len(lines[j]) or c != lines[j][prefix_i])
                           for j in range(i+1, len(lines))):
                        break
                break

        for line in lines:
            print(line[prefix_i:] if line.strip() else line)


class ControllerCLI:
    def _udp_socket_init(self):
        s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.bind(("0.0.0.0",9081))
        self.udp_sk = s


    def _udp_recv(self):
        data = self.udp_sk.recv(1024) 
        return str(data, encoding="utf-8")

    def __init__(self, controller_state: ControllerState):
        self.controller_state = controller_state
        self.commands = {}
        self._udp_socket_init()

    async def cmd_help(self):
        print('Button commands:')
        print(', '.join(self.controller_state.button_state.get_available_buttons()))
        print()
        print('Commands:')
        for name, fun in inspect.getmembers(self):
            if name.startswith('cmd_') and fun.__doc__:
                _print_doc(fun.__doc__)

        for name, fun in self.commands.items():
            if fun.__doc__:
                _print_doc(fun.__doc__)

        print('Commands can be chained using "&&"')
        print('Type "exit" to close.')

    @staticmethod
    def _set_stick(stick, direction, value):
        if direction == 'center':
            stick.set_center()
        elif direction == 'up':
            stick.set_up()
        elif direction == 'down':
            stick.set_down()
        elif direction == 'left':
            stick.set_left()
        elif direction == 'right':
            stick.set_right()
        elif direction in ('h', 'horizontal'):
            if value is None:
                raise ValueError(f'Missing value')
            try:
                val = int(value)
            except ValueError:
                raise ValueError(f'Unexpected stick value "{value}"')
            stick.set_h(val)
        elif direction in ('v', 'vertical'):
            if value is None:
                raise ValueError(f'Missing value')
            try:
                val = int(value)
            except ValueError:
                raise ValueError(f'Unexpected stick value "{value}"')
            stick.set_v(val)
        else:
            raise ValueError(f'Unexpected argument "{direction}"')

        return f'{stick.__class__.__name__} was set to ({stick.get_h()}, {stick.get_v()}).'

    async def cmd_stick(self, side, direction, value=None):
        """
        stick - Command to set stick positions.
        :param side: 'l', 'left' for left control stick; 'r', 'right' for right control stick
        :param direction: 'center', 'up', 'down', 'left', 'right';
                          'h', 'horizontal' or 'v', 'vertical' to set the value directly to the "value" argument
        :param value: horizontal or vertical value
        """
        if side in ('l', 'left'):
            stick = self.controller_state.l_stick_state
            return ControllerCLI._set_stick(stick, direction, value)
        elif side in ('r', 'right'):
            stick = self.controller_state.r_stick_state
            return ControllerCLI._set_stick(stick, direction, value)
        else:
            raise ValueError('Value of side must be "l", "left" or "r", "right"')

    def add_command(self, name, command):
        if name in self.commands:
            raise ValueError(f'Command {name} already registered.')
        self.commands[name] = command

    async def run(self):
        while True:
            user_input = self._udp_recv()
            if not user_input:
                continue

            buttons_to_push = []
            is_button_down = False
            is_button_up = False

            for command in user_input.split('|'):
                cmd, *args = command.split()

                if cmd == 'exit':
                    return

                if cmd == '_u':
                    is_button_up = True
                elif cmd == '_d':
                    is_button_down = True

                available_buttons = self.controller_state.button_state.get_available_buttons()

                if cmd in available_buttons:
                    buttons_to_push.append(cmd)
                elif cmd[0] != '_':
                    print('command', cmd, 'not found, call help for help.')

            if buttons_to_push:
                if is_button_down:
                    await button_down(self.controller_state, *buttons_to_push)
                elif is_button_up:
                    await button_up(self.controller_state, *buttons_to_push)
                else:
                    await button_push(self.controller_state, *buttons_to_push)
            else:
                try:
                    await self.controller_state.send()
                except NotConnectedError:
                    logger.info('Connection was lost.')
                    return
