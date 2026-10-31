#!/bin/bash
# Tên cũ, chuyển tiếp tạm (luật 20, 31/10): nút mới là commands/Deploy_Bot.command
exec "$(cd "$(dirname "$0")" && pwd)/Deploy_Bot.command" "$@"
