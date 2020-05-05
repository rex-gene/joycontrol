#!/bin/bash

sudo python3 run_controller_cli.py --spi_flash ./flash_data --port $1 -d $2 PRO_CONTROLLER
